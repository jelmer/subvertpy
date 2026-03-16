//! Authentication Python bindings
//!
//! Shared auth types used by both the `ra` and `client` crates.

use pyo3::prelude::*;
use std::cell::RefCell;

/// Subversion authentication context
#[pyclass(name = "Auth", unsendable)]
pub struct Auth {
    baton: Option<RefCell<subversion::auth::AuthBaton>>,
    params: std::collections::HashMap<String, Py<PyAny>>,
}

const AUTH_BATON_CAPSULE_NAME: &std::ffi::CStr = c"subvertpy._auth_baton";

impl Auth {
    /// Take the auth baton out of this Auth object (for use in same-cdylib code).
    ///
    /// This replaces the baton with a dummy — prefer `with_baton_mut` when
    /// ownership transfer is not required.
    pub fn take_baton(&self) -> Option<subversion::auth::AuthBaton> {
        self.baton.as_ref().map(|b| {
            b.replace(
                // Replace with a dummy baton - this Auth object's baton is now consumed.
                // We use open() with empty providers.
                subversion::auth::AuthBaton::open(vec![]).unwrap(),
            )
        })
    }

    /// Apply a function to the auth baton without consuming it.
    ///
    /// This allows setting the auth baton on a Client or RemoteAccess session
    /// without transferring ownership. The caller should keep a Python reference
    /// to the Auth object to ensure the baton remains alive.
    pub fn with_baton_mut<F, R>(&self, f: F) -> Option<R>
    where
        F: FnOnce(&mut subversion::auth::AuthBaton) -> R,
    {
        self.baton.as_ref().map(|b| f(&mut b.borrow_mut()))
    }
}

/// Apply a function to the AuthBaton inside a Python Auth object (works across cdylib boundaries).
///
/// Calls `_borrow_baton_capsule()` on the object and applies `f` to the borrowed AuthBaton.
/// The Auth Python object retains ownership; the caller must keep a reference to it.
pub fn with_baton_from_py<F, R>(auth: &pyo3::Bound<pyo3::PyAny>, f: F) -> PyResult<Option<R>>
where
    F: FnOnce(&mut subversion::auth::AuthBaton) -> R,
{
    use pyo3::types::PyCapsuleMethods;

    let capsule_obj = auth.call_method0("_borrow_baton_capsule")?;
    if capsule_obj.is_none() {
        return Ok(None);
    }
    let capsule = capsule_obj.cast::<pyo3::types::PyCapsule>()?;
    let ptr = capsule.pointer_checked(Some(AUTH_BATON_CAPSULE_NAME))?;
    // Safety: the capsule contains a pointer to a RefCell<AuthBaton> that is
    // kept alive by the Auth Python object. We borrow it mutably here.
    let baton_cell = unsafe { &*(ptr.as_ptr() as *const RefCell<subversion::auth::AuthBaton>) };
    let result = f(&mut baton_cell.borrow_mut());
    Ok(Some(result))
}

#[pymethods]
impl Auth {
    /// Create a new auth context
    #[new]
    fn init(mut providers: Vec<Bound<AuthProvider>>) -> PyResult<Self> {
        let svn_providers: Vec<subversion::auth::AuthProvider> = providers
            .iter_mut()
            .filter_map(|p| p.borrow_mut().provider.take())
            .collect();

        if svn_providers.is_empty() {
            return Ok(Self {
                baton: None,
                params: std::collections::HashMap::new(),
            });
        }

        let auth_baton = subversion::auth::AuthBaton::open(svn_providers)
            .map_err(|e| crate::error::svn_err_to_py(e))?;

        Ok(Self {
            baton: Some(RefCell::new(auth_baton)),
            params: std::collections::HashMap::new(),
        })
    }

    /// Set an auth parameter
    fn set_parameter(&mut self, name: &str, value: Bound<PyAny>) -> PyResult<()> {
        self.params.insert(name.to_string(), value.clone().unbind());

        if let Some(ref baton_cell) = self.baton {
            let mut baton = baton_cell.borrow_mut();
            match name {
                "svn:auth:username" => {
                    let s: String = value.extract()?;
                    baton
                        .set(subversion::auth::AuthSetting::DefaultUsername(&s))
                        .map_err(crate::error::svn_err_to_py)?;
                }
                "svn:auth:password" => {
                    let s: String = value.extract()?;
                    baton
                        .set(subversion::auth::AuthSetting::DefaultPassword(&s))
                        .map_err(crate::error::svn_err_to_py)?;
                }
                "svn:auth:ssl:failures" => {
                    let v: u32 = value.extract()?;
                    baton
                        .set(subversion::auth::AuthSetting::SslServerFailures(v))
                        .map_err(crate::error::svn_err_to_py)?;
                }
                _ => {
                    return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                        "Unknown auth parameter: {}",
                        name
                    )));
                }
            }
        }

        Ok(())
    }

    /// Get an auth parameter
    fn get_parameter(&self, py: Python, name: &str) -> PyResult<Option<Py<PyAny>>> {
        Ok(self.params.get(name).map(|v| v.clone_ref(py)))
    }

    /// Return the auth baton as a PyCapsule for cross-cdylib use.
    ///
    /// The capsule stores a pointer to the AuthBaton (not ownership).
    /// The caller must keep a Python reference to this Auth object to
    /// ensure the baton remains valid.
    fn _borrow_baton_capsule(&self, py: Python) -> PyResult<Option<Py<PyAny>>> {
        let Some(ref baton_cell) = self.baton else {
            return Ok(None);
        };
        let ptr = baton_cell as *const RefCell<subversion::auth::AuthBaton>;
        let capsule = unsafe {
            pyo3::Bound::from_owned_ptr(
                py,
                pyo3::ffi::PyCapsule_New(
                    ptr as *mut std::ffi::c_void,
                    AUTH_BATON_CAPSULE_NAME.as_ptr(),
                    None,
                ),
            )
        };
        Ok(Some(capsule.unbind()))
    }

    /// Get credentials iterator
    fn credentials(
        slf: Py<Self>,
        py: Python,
        kind: &str,
        realm: &str,
    ) -> PyResult<CredentialsIter> {
        // Check if baton exists
        {
            let auth = slf.borrow(py);
            if auth.baton.is_none() {
                return Err(crate::error::svn_err_to_py(
                    subversion::Error::from_message("No authentication providers registered"),
                ));
            }
        }

        Ok(CredentialsIter {
            state: None,
            auth: slf,
            kind: kind.to_string(),
            realm: realm.to_string(),
        })
    }
}

/// Authentication provider
#[pyclass(name = "AuthProvider", unsendable)]
pub struct AuthProvider {
    pub provider: Option<subversion::auth::AuthProvider>,
}

#[pymethods]
impl AuthProvider {
    /// Create a new auth provider (stub - use factory functions instead)
    #[new]
    fn init() -> PyResult<Self> {
        Ok(Self { provider: None })
    }
}

use subversion::auth::{
    IterState, SimpleCredentials, SslClientCertCredentials, SslClientCertPwCredentials,
    SslServerTrustCredentials, UsernameCredentials,
};

enum CredState {
    Simple(IterState<SimpleCredentials<'static>>),
    Username(IterState<UsernameCredentials<'static>>),
    SslClientCert(IterState<SslClientCertCredentials<'static>>),
    SslClientCertPw(IterState<SslClientCertPwCredentials<'static>>),
    SslServerTrust(IterState<SslServerTrustCredentials<'static>>),
}

/// Credentials iterator
#[pyclass(name = "CredentialsIter", unsendable)]
pub struct CredentialsIter {
    state: Option<CredState>,
    auth: Py<Auth>,
    kind: String,
    realm: String,
}

impl CredentialsIter {
    fn creds_to_py(
        py: Python,
        kind: &str,
        creds_ptr: &dyn subversion::auth::Credentials,
    ) -> PyResult<Py<PyAny>> {
        match kind {
            "svn.simple" => {
                let c = creds_ptr.as_simple().unwrap();
                Ok(
                    (c.username(), c.password(), if c.may_save() { 1 } else { 0 })
                        .into_pyobject(py)?
                        .into_any()
                        .unbind(),
                )
            }
            "svn.username" => {
                let c = creds_ptr.as_username().unwrap();
                Ok((c.username(), if c.may_save() { 1 } else { 0 })
                    .into_pyobject(py)?
                    .into_any()
                    .unbind())
            }
            "svn.ssl.client-cert" => {
                let c = creds_ptr.as_ssl_client_cert().unwrap();
                Ok((c.cert_file(), c.may_save())
                    .into_pyobject(py)?
                    .into_any()
                    .unbind())
            }
            "svn.ssl.client-passphrase" => {
                let c = creds_ptr.as_ssl_client_cert_pw().unwrap();
                Ok((c.password(), c.may_save())
                    .into_pyobject(py)?
                    .into_any()
                    .unbind())
            }
            "svn.ssl.server" => {
                let c = creds_ptr.as_ssl_server_trust().unwrap();
                Ok((c.accepted_failures(), if c.may_save() { 1 } else { 0 })
                    .into_pyobject(py)?
                    .into_any()
                    .unbind())
            }
            _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Unsupported credential kind: {}",
                kind
            ))),
        }
    }
}

#[pymethods]
impl CredentialsIter {
    fn __next__(&mut self, py: Python) -> PyResult<Option<Py<PyAny>>> {
        // Subsequent calls: get next credentials from stored state
        if let Some(ref mut state) = self.state {
            let next = match state {
                CredState::Simple(s) => s
                    .next_credentials()
                    .map(|o| o.map(|c| Box::new(c) as Box<dyn subversion::auth::Credentials>)),
                CredState::Username(s) => s
                    .next_credentials()
                    .map(|o| o.map(|c| Box::new(c) as Box<dyn subversion::auth::Credentials>)),
                CredState::SslClientCert(s) => s
                    .next_credentials()
                    .map(|o| o.map(|c| Box::new(c) as Box<dyn subversion::auth::Credentials>)),
                CredState::SslClientCertPw(s) => s
                    .next_credentials()
                    .map(|o| o.map(|c| Box::new(c) as Box<dyn subversion::auth::Credentials>)),
                CredState::SslServerTrust(s) => s
                    .next_credentials()
                    .map(|o| o.map(|c| Box::new(c) as Box<dyn subversion::auth::Credentials>)),
            }
            .map_err(crate::error::svn_err_to_py)?;

            return match next {
                Some(c) => Self::creds_to_py(py, &self.kind, c.as_ref()).map(Some),
                None => Ok(None),
            };
        }

        // First call: get first credentials from baton
        let auth = self.auth.borrow(py);
        let baton_ref = auth.baton.as_ref().ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Auth baton not initialized")
        })?;
        let mut baton = baton_ref.borrow_mut();

        macro_rules! first_creds {
            ($cred_type:ty, $variant:ident) => {{
                let iter_state = baton
                    .credentials::<$cred_type>(&self.realm)
                    .map_err(crate::error::svn_err_to_py)?;
                let result = iter_state
                    .credentials()
                    .map(|c| Self::creds_to_py(py, &self.kind, c))
                    .transpose()?;
                self.state = Some(CredState::$variant(iter_state));
                Ok(result)
            }};
        }

        match self.kind.as_str() {
            "svn.simple" => first_creds!(SimpleCredentials, Simple),
            "svn.username" => first_creds!(UsernameCredentials, Username),
            "svn.ssl.client-cert" => first_creds!(SslClientCertCredentials, SslClientCert),
            "svn.ssl.client-passphrase" => {
                first_creds!(SslClientCertPwCredentials, SslClientCertPw)
            }
            "svn.ssl.server" => first_creds!(SslServerTrustCredentials, SslServerTrust),
            _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Unsupported credential kind: {}",
                self.kind
            ))),
        }
    }
}

// Auth provider factory functions

/// Get a simple authentication provider (username/password from file)
#[pyfunction]
#[pyo3(signature = (_callback=None))]
pub fn get_simple_provider(_callback: Option<Bound<PyAny>>) -> PyResult<AuthProvider> {
    let provider = subversion::auth::get_simple_provider(
        None::<&fn(&str) -> Result<bool, subversion::Error<'static>>>,
    );
    Ok(AuthProvider {
        provider: Some(provider),
    })
}

/// Get a username authentication provider
#[pyfunction]
pub fn get_username_provider() -> PyResult<AuthProvider> {
    let provider = subversion::auth::get_username_provider();
    Ok(AuthProvider {
        provider: Some(provider),
    })
}

/// Get an SSL server trust file provider
#[pyfunction]
pub fn get_ssl_server_trust_file_provider() -> PyResult<AuthProvider> {
    let provider = subversion::auth::get_ssl_server_trust_file_provider();
    Ok(AuthProvider {
        provider: Some(provider),
    })
}

/// Get an SSL client certificate file provider
#[pyfunction]
pub fn get_ssl_client_cert_file_provider() -> PyResult<AuthProvider> {
    let provider = subversion::auth::get_ssl_client_cert_file_provider();
    Ok(AuthProvider {
        provider: Some(provider),
    })
}

/// Get an SSL client certificate password file provider
#[pyfunction]
#[pyo3(signature = (_callback=None))]
pub fn get_ssl_client_cert_pw_file_provider(
    _callback: Option<Bound<PyAny>>,
) -> PyResult<AuthProvider> {
    let provider = subversion::auth::get_ssl_client_cert_pw_file_provider(
        None::<&fn(&str) -> Result<bool, subversion::Error<'static>>>,
    );
    Ok(AuthProvider {
        provider: Some(provider),
    })
}

/// Get platform-specific client providers
#[pyfunction]
pub fn get_platform_specific_client_providers() -> PyResult<Vec<AuthProvider>> {
    let providers = subversion::auth::get_platform_specific_client_providers(None)
        .map_err(|e| crate::error::svn_err_to_py(e))?;

    Ok(providers
        .into_iter()
        .map(|p| AuthProvider { provider: Some(p) })
        .collect())
}

/// Get a username prompt provider
#[pyfunction]
pub fn get_username_prompt_provider(
    callback: Bound<PyAny>,
    retry_limit: i32,
) -> PyResult<AuthProvider> {
    let py_callback = callback.unbind();

    let prompt_fn = Box::new(move |realm: &str, may_save: bool| {
        Python::attach(|py| {
            let callback_bound = py_callback.bind(py);
            let result = callback_bound.call1((realm, may_save)).map_err(|e| {
                subversion::Error::from_message(&format!("Auth callback failed: {}", e))
            })?;

            let (username, save): (String, bool) = result.extract().map_err(|e| {
                subversion::Error::from_message(&format!(
                    "Auth callback must return (username, may_save) tuple: {}",
                    e
                ))
            })?;

            Ok((username, save))
        })
    });

    let provider =
        subversion::auth::get_username_prompt_provider_boxed(prompt_fn, retry_limit as usize);
    Ok(AuthProvider {
        provider: Some(provider),
    })
}

/// Get a simple (username/password) prompt provider
#[pyfunction]
pub fn get_simple_prompt_provider(
    callback: Bound<PyAny>,
    retry_limit: i32,
) -> PyResult<AuthProvider> {
    let py_callback = callback.unbind();

    let prompt_fn = Box::new(
        move |realm: &str,
              username: Option<&str>,
              may_save: bool|
              -> Result<(String, String, bool), subversion::Error<'static>> {
            Python::attach(|py| {
                let callback_bound = py_callback.bind(py);
                let result = callback_bound
                    .call1((realm, username, may_save))
                    .map_err(|e| {
                        subversion::Error::from_message(&format!("Auth callback failed: {}", e))
                    })?;

                let (username, password, save): (String, String, bool) =
                    result.extract().map_err(|e| {
                        subversion::Error::from_message(&format!(
                            "Auth callback must return (username, password, may_save) tuple: {}",
                            e
                        ))
                    })?;

                Ok((username, password, save))
            })
        },
    );

    let provider =
        subversion::auth::get_simple_prompt_provider_boxed(prompt_fn, retry_limit as usize);
    Ok(AuthProvider {
        provider: Some(provider),
    })
}

/// Get an SSL server trust prompt provider
#[pyfunction]
pub fn get_ssl_server_trust_prompt_provider(callback: Bound<PyAny>) -> PyResult<AuthProvider> {
    let py_callback = callback.unbind();

    let prompt_fn = Box::new(
        move |realm: &str,
              failures: u32,
              cert_info: Option<&subversion::auth::SslServerCertInfo>,
              may_save: bool| {
            Python::attach(|py| {
                let callback_bound = py_callback.bind(py);
                let cert_info_py: Py<PyAny> = match cert_info {
                    Some(info) => {
                        let dict = pyo3::types::PyDict::new(py);
                        dict.set_item("hostname", info.hostname())
                            .map_err(|e| subversion::Error::from_message(&format!("{}", e)))?;
                        dict.set_item("fingerprint", info.fingerprint())
                            .map_err(|e| subversion::Error::from_message(&format!("{}", e)))?;
                        dict.set_item("valid_from", info.valid_from())
                            .map_err(|e| subversion::Error::from_message(&format!("{}", e)))?;
                        dict.set_item("valid_until", info.valid_until())
                            .map_err(|e| subversion::Error::from_message(&format!("{}", e)))?;
                        dict.set_item("issuer_dname", info.issuer_dname())
                            .map_err(|e| subversion::Error::from_message(&format!("{}", e)))?;
                        dict.set_item("ascii_cert", info.ascii_cert())
                            .map_err(|e| subversion::Error::from_message(&format!("{}", e)))?;
                        dict.into_any().unbind()
                    }
                    None => py.None(),
                };
                let result = callback_bound
                    .call1((realm, failures, cert_info_py, may_save))
                    .map_err(|e| {
                        subversion::Error::from_message(&format!("Auth callback failed: {}", e))
                    })?;

                if result.is_none() {
                    return Ok(None);
                }

                let (accepted_failures, save): (u32, bool) = result.extract().map_err(|e| {
                    subversion::Error::from_message(&format!(
                        "Auth callback must return (accepted_failures, may_save) tuple or None: {}",
                        e
                    ))
                })?;

                Ok(Some((accepted_failures, save)))
            })
        },
    );

    let provider = subversion::auth::get_ssl_server_trust_prompt_provider_boxed(prompt_fn);
    Ok(AuthProvider {
        provider: Some(provider),
    })
}

/// Get an SSL client certificate prompt provider
#[pyfunction]
pub fn get_ssl_client_cert_prompt_provider(
    callback: Bound<PyAny>,
    retry_limit: i32,
) -> PyResult<AuthProvider> {
    let py_callback = callback.unbind();

    let prompt_fn = Box::new(move |realm: &str, may_save: bool| {
        Python::attach(|py| {
            let callback_bound = py_callback.bind(py);
            let result = callback_bound.call1((realm, may_save)).map_err(|e| {
                subversion::Error::from_message(&format!("Auth callback failed: {}", e))
            })?;

            let (cert_file, save): (String, bool) = result.extract().map_err(|e| {
                subversion::Error::from_message(&format!(
                    "Auth callback must return (cert_file, may_save) tuple: {}",
                    e
                ))
            })?;

            Ok((cert_file, save))
        })
    });

    let provider = subversion::auth::get_ssl_client_cert_prompt_provider_boxed(
        prompt_fn,
        retry_limit as usize,
    );
    Ok(AuthProvider {
        provider: Some(provider),
    })
}

/// Get an SSL client certificate password prompt provider
#[pyfunction]
pub fn get_ssl_client_cert_pw_prompt_provider(
    callback: Bound<PyAny>,
    retry_limit: i32,
) -> PyResult<AuthProvider> {
    let py_callback = callback.unbind();

    let prompt_fn = Box::new(move |realm: &str, may_save: bool| {
        Python::attach(|py| {
            let callback_bound = py_callback.bind(py);
            let result = callback_bound.call1((realm, may_save)).map_err(|e| {
                subversion::Error::from_message(&format!("Auth callback failed: {}", e))
            })?;

            let (password, save): (String, bool) = result.extract().map_err(|e| {
                subversion::Error::from_message(&format!(
                    "Auth callback must return (password, may_save) tuple: {}",
                    e
                ))
            })?;

            Ok((password, save))
        })
    });

    let provider = subversion::auth::get_ssl_client_cert_pw_prompt_provider_boxed(
        prompt_fn,
        retry_limit as usize,
    );
    Ok(AuthProvider {
        provider: Some(provider),
    })
}
