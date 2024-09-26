use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyType};
use std::collections::HashMap;
use subversion::delta::{Editor, DirectoryEditor, FileEditor, TxDeltaWindow};
use subversion::Revnum;
use subversion::auth::SimpleCredentials;
use common::{map_py_err_to_svn_err, map_svn_error_to_py_err};

#[pyclass]
struct PyReporter(Box<dyn subversion::ra::Reporter + Send>);

impl PyReporter {
}

#[pyfunction]
fn version() -> (i32, i32, i32, String) {
    let version = subversion::ra::version();
    (
        version.major(),
        version.minor(),
        version.patch(),
        version.tag().to_string(),
    )
}

#[pyclass(frozen)]
struct AuthProvider(subversion::auth::AuthProvider);

#[pymethods]
impl AuthProvider {
    #[getter]
    fn cred_kind(&self) -> &str {
        self.0.cred_kind()
    }
}


#[pyfunction]
fn get_ssl_client_cert_pw_file_provider(prompt_func: PyObject) -> AuthProvider {
    let prompt_fn = |realm: &str| -> Result<bool, subversion::Error> {
        Python::with_gil(|py| {
            let pw = prompt_func.call1(py, (realm,))
                .map_err(map_py_err_to_svn_err)?;
            Ok(pw.extract(py).map_err(map_py_err_to_svn_err)?)
        })
    };
    AuthProvider(subversion::auth::get_ssl_client_cert_pw_file_provider(&prompt_fn))
}

#[pyfunction]
fn get_ssl_client_cert_file_provider() -> AuthProvider {
    AuthProvider(subversion::auth::get_ssl_client_cert_file_provider())
}

#[pyfunction]
fn get_ssl_server_trust_file_provider() -> AuthProvider {
    AuthProvider(subversion::auth::get_ssl_server_trust_file_provider())
}

#[pyfunction]
fn get_simple_provider(plaintext_prompt_fn: PyObject) -> AuthProvider {
    let plain_prompt = |realm: &str| -> Result<bool, subversion::Error> {
        Python::with_gil(|py| {
            let may_save: bool  = plaintext_prompt_fn.call1(py, (realm, )).map_err(map_py_err_to_svn_err)?.extract(py).map_err(map_py_err_to_svn_err)?;
            Ok(may_save)
        })
    };
    AuthProvider(subversion::auth::get_simple_provider(&plain_prompt))
}

#[pyfunction]
fn get_username_prompt_provider(username_prompt_func: PyObject, retry_limit: usize) -> AuthProvider {
    let prompt = |realm: &str, may_save: bool| -> Result<String, subversion::Error> {
        Python::with_gil(|py| {
            let username: String = username_prompt_func.call1(py, (realm, may_save)).map_err(map_py_err_to_svn_err)?.extract(py).map_err(map_py_err_to_svn_err)?;
            Ok(username)
        })
    };
    AuthProvider(subversion::auth::get_username_prompt_provider(&prompt, retry_limit))
}

#[pyfunction]
fn get_simple_prompt_provider(simple_prompt_fn: PyObject, retry_limit: usize) -> AuthProvider {
    let plain_prompt = |realm: &str, username: Option<&str>, may_save: bool| -> Result<SimpleCredentials, subversion::Error> {
        Python::with_gil(|py| {
            let (username, password, may_save) = simple_prompt_fn.call1(py, (realm, username, may_save)).map_err(map_py_err_to_svn_err)?.extract(py).map_err(map_py_err_to_svn_err)?;
            Ok(subversion::auth::SimpleCredentials::new(username, password, may_save))
        })
    };
    AuthProvider(subversion::auth::get_simple_prompt_provider(&plain_prompt, retry_limit))
}

#[pyclass]
pub struct SslServerTrust(subversion::auth::SslServerTrust);

impl SslServerTrust {
    fn as_raw(&self) -> subversion::auth::SslServerTrust {
        self.0.dup()
    }
}

#[pyclass]
pub struct SslServerCertInfo(subversion::auth::SslServerCertInfo);

impl SslServerCertInfo {
    fn as_raw(&self) -> subversion::auth::SslServerCertInfo {
        self.0.dup()
    }
}

#[pyfunction]
fn get_ssl_server_trust_prompt_provider(prompt_fn: PyObject) -> AuthProvider {
    let prompt_fn = |realm: &str, failures: usize, cert_info: &subversion::auth::SslServerCertInfo, may_save: bool| -> Result<subversion::auth::SslServerTrust, subversion::Error> {
        Python::with_gil(|py| {
            let cert_info = SslServerCertInfo(cert_info.dup());
            let trust: PyRef<SslServerTrust> = prompt_fn.call1(py, (realm, failures, cert_info, may_save)).map_err(map_py_err_to_svn_err)?.extract(py).map_err(map_py_err_to_svn_err)?;

            Ok(trust.as_raw())
        })
    };
    AuthProvider(subversion::auth::get_ssl_server_trust_prompt_provider(&prompt_fn))
}

#[pyclass]
pub struct SslClientCertCredentials(subversion::auth::SslClientCertCredentials);

impl SslClientCertCredentials {
    fn as_raw(&self) -> subversion::auth::SslClientCertCredentials {
        self.0.dup()
    }
}

#[pyfunction]
fn get_ssl_client_cert_prompt_provider(prompt_fn: PyObject, retry_limit: usize) -> AuthProvider {
    let prompt_fn = |realm: &str, may_save: bool| -> Result<subversion::auth::SslClientCertCredentials, subversion::Error> {
        Python::with_gil(|py| {
            let creds: PyRef<SslClientCertCredentials> = prompt_fn.call1(py, (realm, may_save)).map_err(map_py_err_to_svn_err)?.extract(py).map_err(map_py_err_to_svn_err)?;
            Ok(creds.as_raw())
        })
    };
    AuthProvider(subversion::auth::get_ssl_client_cert_prompt_provider(&prompt_fn, retry_limit))
}

#[pyfunction]
fn get_platform_specific_client_providers() -> Result<Vec<AuthProvider>, PyErr> {
    Ok(subversion::auth::get_platform_specific_client_providers()
        .map_err(map_svn_error_to_py_err)?
        .into_iter().map(AuthProvider).collect())
}

#[pyfunction]
fn get_username_provider() -> AuthProvider {
    AuthProvider(subversion::auth::get_username_provider())
}

#[pyfunction]
fn get_platform_specific_provider(provider_name: &str, provider_type: &str) -> Result<AuthProvider, PyErr> {
    Ok(AuthProvider(subversion::auth::get_platform_specific_provider(provider_name, provider_type).map_err(map_svn_error_to_py_err)?))
}

#[pyfunction]
fn print_modules() -> Result<String, PyErr> {
    subversion::ra::modules().map_err(map_svn_error_to_py_err)
}

#[pyclass]
struct RemoteAccess {
    ra: std::sync::Mutex<subversion::ra::Session>,
    corrected_url: String,
}

#[pyclass]
struct PyDirent(subversion::ra::Dirent);

#[pyclass]
struct WrapEditor(Box<dyn Editor + Send>);

struct PyEditor(PyObject);

impl Editor for PyEditor {
    fn set_target_revision(&mut self, revision: Revnum) -> Result<(), subversion::Error> {
        Python::with_gil(|py| {
            let revision = Into::<u64>::into(revision);
            self.0.call_method1(py, "set_target_revision", (revision,)).map_err(map_py_err_to_svn_err)?;
            Ok(())
        })
    }

    fn open_root<'a>(
        &'a mut self,
        base_revision: Revnum,
    ) -> Result<Box<dyn DirectoryEditor + 'a>, subversion::Error> {
        let directory = Python::with_gil(|py| self.0.call_method1(py, "open_root", (Into::<i64>::into(base_revision),))).map_err(map_py_err_to_svn_err)?;
        Ok(Box::new(PyDirectoryEditor(directory)))
    }

    fn close(&mut self) -> Result<(), subversion::Error> {
        Python::with_gil(|py| {
            self.0.call_method0(py, "close").map_err(map_py_err_to_svn_err)?;
            Ok(())
        })
    }

    fn abort(&mut self) -> Result<(), subversion::Error> {
        Python::with_gil(|py| {
            self.0.call_method0(py, "abort").map_err(map_py_err_to_svn_err)?;
            Ok(())
        })
    }
}

struct PyDirectoryEditor(PyObject);

impl subversion::delta::DirectoryEditor for PyDirectoryEditor {
    fn delete_entry(&mut self, path: &str, revision: Option<Revnum>) -> Result<(), subversion::Error> {
        let revision: Option<u64> = revision.map(Into::into);
        Python::with_gil(|py| {
            self.0.call_method1(py, "delete_entry", (path, revision)).map_err(map_py_err_to_svn_err)?;
            Ok(())
        })
    }

    fn add_directory<'a>(
        &'a mut self,
        path: &str,
        copyfrom: Option<(&str, Revnum)>,
    ) -> Result<Box<dyn DirectoryEditor + 'a>, subversion::Error> {
        let copyfrom: Option<(&str, u64)> = copyfrom.map(|(path, rev)| (path, rev.into()));
        let directory = Python::with_gil(|py| self.0.call_method1(py, "add_directory", (path, copyfrom))).map_err(map_py_err_to_svn_err)?;
        Ok(Box::new(PyDirectoryEditor(directory)))
    }

    fn open_directory<'a>(
        &'a mut self,
        path: &str,
        base_revision: Option<Revnum>,
    ) -> Result<Box<dyn DirectoryEditor + 'a>, subversion::Error> {
        let base_revision: Option<u64> = base_revision.map(Into::into);
        let directory = Python::with_gil(|py| self.0.call_method1(py, "open_directory", (path, base_revision))).map_err(map_py_err_to_svn_err)?;
        Ok(Box::new(PyDirectoryEditor(directory)))
    }

    fn change_prop(&mut self, name: &str, value: &[u8]) -> Result<(), subversion::Error> {
        Python::with_gil(|py| {
            self.0.call_method1(py, "change_prop", (name, value)).map_err(map_py_err_to_svn_err)?;
            Ok(())
        })
    }

    fn close(&mut self) -> Result<(), subversion::Error> {
        Python::with_gil(|py| {
            self.0.call_method0(py, "close").map_err(map_py_err_to_svn_err)?;
            Ok(())
        })
    }

    fn absent_directory(&mut self, path: &str) -> Result<(), subversion::Error> {
        Python::with_gil(|py| {
            self.0.call_method1(py, "absent_directory", (path,))
                .map_err(map_py_err_to_svn_err)?;
            Ok(())
        })
    }

    fn add_file<'a>(
        &'a mut self,
        path: &str,
        copyfrom: Option<(&str, Revnum)>,
    ) -> Result<Box<dyn FileEditor + 'a>, subversion::Error> {
        let copyfrom: Option<(&str, u64)> = copyfrom.map(|(path, rev)| (path, rev.into()));
        let file = Python::with_gil(|py| self.0.call_method1(py, "add_file", (path, copyfrom))).map_err(map_py_err_to_svn_err)?;
        Ok(Box::new(PyFileEditor(file)))
    }

    fn open_file<'a>(
        &'a mut self,
        path: &str,
        base_revision: Option<Revnum>,
    ) -> Result<Box<dyn FileEditor + 'a>, subversion::Error> {
        let base_revision: Option<u64> = base_revision.map(Into::into);
        let file = Python::with_gil(|py| self.0.call_method1(py, "open_file", (path, base_revision))).map_err(map_py_err_to_svn_err)?;
        Ok(Box::new(PyFileEditor(file)))
    }

    fn absent_file(&mut self, path: &str) -> Result<(), subversion::Error> {
        Python::with_gil(|py| {
            self.0.call_method1(py, "absent_file", (path,))
                .map_err(map_py_err_to_svn_err)?;
            Ok(())
        })
    }
}

#[pyclass]
struct PyWindow(TxDeltaWindow);

struct PyFileEditor(PyObject);

impl FileEditor for PyFileEditor {
    fn apply_textdelta(&mut self, base_checksum: Option<&str>) -> Result<Box<dyn for<'b> Fn(&'b mut TxDeltaWindow) -> Result<(), subversion::Error>>, subversion::Error> {
        let text_delta = Python::with_gil(|py| self.0.call_method1(py, "apply_textdelta", (base_checksum,))).map_err(map_py_err_to_svn_err)?;
        Ok(Box::new(move |window| {
            let window = PyWindow(window.dup());
            Python::with_gil(|py| {
                text_delta.call_method1(py, "apply", (window,)).map_err(map_py_err_to_svn_err)?;
                Ok(())
            })
        }))
    }

    fn change_prop(&mut self, name: &str, value: &[u8]) -> Result<(), subversion::Error> {
        Python::with_gil(|py| {
            self.0.call_method1(py, "change_prop", (name, value)).map_err(map_py_err_to_svn_err)?;
            Ok(())
        })
    }

    fn close(&mut self, text_checksum: Option<&str>) -> Result<(), subversion::Error> {
        Python::with_gil(|py| {
            self.0.call_method1(py, "close", (text_checksum,)).map_err(map_py_err_to_svn_err)?;
            Ok(())
        })
    }
}

#[pyclass]
struct PyCommitInfo(subversion::CommitInfo);

#[pymethods]
impl RemoteAccess {
    #[getter]
    fn busy(&mut self) -> bool {
        self.ra.lock().is_err()
    }

    #[getter]
    fn corrected_url(&self) -> &str {
        &self.corrected_url
    }

    #[getter]
    fn get_progress_func(&self) {
        unimplemented!()
    }

    #[setter]
    fn set_progress_func(&self, _progress_func: &Bound<PyAny>) {
        unimplemented!()
    }

    fn get_session_url(&self) -> Result<String, PyErr> {
        Ok(self.ra.lock().unwrap().get_session_url().unwrap())
    }

    fn get_file_revs(&self, _path: &str, _start_rev: i64, _end_revs: i64, _handler: &Bound<PyAny>) {
        unimplemented!()
    }

    fn get_locations(&self, _path: &str, _peg_revision: i64, _location_revisions: i64) {
        unimplemented!()
    }

    fn get_locks(&self, _path: &str, _depth: i64) {
        unimplemented!()
    }

    fn lock(&self, _path_revs: &str, _comment: &str, _steal_lock: bool, _lock_func: &Bound<PyAny>) {
        unimplemented!()
    }

    fn unlock(&self, _path_tokens: &str, _break_lock: bool, _lock_func: &Bound<PyAny>) {
        unimplemented!()
    }

    fn mergeinfo(&self, _paths: &str, _revision: i64, _inherit: bool, _include_descendants: bool) {
        unimplemented!()
    }

    fn get_location_segments(
        &self,
        _path: &str,
        _peg_revision: i64,
        _start_revision: i64,
        _end_revision: i64,
        _rcvr: &Bound<PyAny>,
    ) {
        unimplemented!()
    }

    fn has_capability(&self, name: &str) -> bool {
        self.ra.lock().unwrap().has_capability(name).unwrap()
    }

    fn check_path(&self, path: &str, revnum: u64) -> i64 {
        match self.ra.lock().unwrap().check_path(path, revnum.into()).unwrap() {
            subversion::NodeKind::None => 0,
            subversion::NodeKind::File => 1,
            subversion::NodeKind::Dir => 2,
            subversion::NodeKind::Symlink => 3,
            subversion::NodeKind::Unknown => 4,
        }
    }

    fn stat(&self, path: &str, revnum: u64) -> Result<PyDirent, PyErr> {
        Ok(PyDirent(self.ra.lock().unwrap().stat(path, revnum.into()).unwrap()))
    }

    fn get_lock(&self, _path: &str) {
        unimplemented!()
    }

    fn get_dir(&self, py: Python<'_>, path: &'_ str, revision: u64, dirent_fields: i64) -> Result<(u64, HashMap<String, PyDirent>, HashMap<String, PyObject>), PyErr> {
        let (revnum, dirents, props) = self
            .ra
            .lock()
            .unwrap()
            .get_dir(path, revision.into())
            .map_err(map_svn_error_to_py_err)?;

        let dirents = dirents
            .into_iter()
            .map(|(k, v)| (k, PyDirent(v)))
            .collect();

        let props = props
            .into_iter()
            .map(|(k, v)| (k, PyBytes::new_bound(py, &v).to_object(py)))
            .collect();

        Ok((revnum.into(), dirents, props))
    }

    fn get_file(&self, _path: &str, _stream: &Bound<PyAny>, _revnum: u64) {
        unimplemented!()
    }

    #[pyo3(signature = (revnum, name, old_value, new_value))]
    fn change_rev_prop(&self, revnum: u64, name: &str, old_value: Option<&[u8]>, new_value: &[u8]) -> Result<(), PyErr> {
        Ok(self.ra.lock().unwrap().change_revprop(revnum.into(), name, old_value, new_value).map_err(map_svn_error_to_py_err)?)
    }

    #[pyo3(signature = (revprops, commit_callback, lock_tokens=None, keep_locks=false))]
    fn get_commit_editor(
        &self,
        py: Python,
        revprops: HashMap<String, Vec<u8>>,
        commit_callback: &Bound<PyAny>,
        lock_tokens: Option<HashMap<String, String>>,
        keep_locks: bool,
    ) -> Result<WrapEditor, PyErr> {
        let editor = self
            .ra
            .lock()
            .unwrap()
            .get_commit_editor(
                revprops.into_iter().collect(),
                &|ci| {
                    let ci = PyCommitInfo(ci.clone());
                    Python::with_gil(|py| {
                        commit_callback.call1((ci,)).map_err(map_py_err_to_svn_err)?;
                        Ok(())
                    })
                },
                lock_tokens.unwrap_or_default(),
                keep_locks,
            )
            .unwrap();

        Ok(WrapEditor(editor))
    }

    fn rev_proplist(&self, py: Python, revnum: u64) -> Result<HashMap<String, PyObject>, PyErr> {
        let revprops = self.ra.lock().unwrap().rev_proplist(revnum.into()).unwrap();

        Ok(revprops
            .into_iter()
            .map(|(k, v)| (k, PyBytes::new_bound(py, &v).to_object(py)))
            .collect())
    }

    fn replay(
        &self,
        _revision: i64,
        _low_water_mark: i64,
        _update_editor: &Bound<PyAny>,
        _send_deltas: bool,
    ) {
        unimplemented!()
    }

    fn replay_range(
        &self,
        _start_rev: i64,
        _end_rev: i64,
        _low_water_mark: i64,
        _cbs: &Bound<PyAny>,
        _send_deltas: bool,
    ) {
        unimplemented!()
    }

    #[pyo3(signature = (revision_to_update_to, switch_target, switch_url, update_editor, depth=None, send_copyfrom_args=false, ignore_ancestry=false))]
    fn do_switch(
        &self,
        py: Python,
        revision_to_update_to: u64,
        switch_target: &str,
        switch_url: &str,
        update_editor: &Bound<PyAny>,
        depth: Option<subversion::Depth>,
        send_copyfrom_args: bool,
        ignore_ancestry: bool,
    ) -> Result<PyReporter, PyErr> {
        self.ra
            .lock()
            .unwrap()
            .do_switch(
                revision_to_update_to.into(),
                switch_target,
                depth.unwrap_or(subversion::Depth::Infinity),
                switch_url,
                send_copyfrom_args,
                ignore_ancestry,
                &mut PyEditor(update_editor.to_object(py)),
            ).map_err(map_svn_error_to_py_err)
            .map(PyReporter)
    }

    #[pyo3(signature = (revision_to_update_to, update_target, update_editor, depth=None, send_copyfrom_args=false, ignore_ancestry=false))]
    fn do_update(
        &self,
        py: Python,
        revision_to_update_to: u64,
        update_target: &str,
        update_editor: &Bound<PyAny>,
        depth: Option<subversion::Depth>,
        send_copyfrom_args: bool,
        ignore_ancestry: bool,
    ) {
        self.ra
            .lock()
            .unwrap()
            .do_update(
                revision_to_update_to.into(),
                update_target,
                depth.unwrap_or(subversion::Depth::Infinity),
                send_copyfrom_args,
                ignore_ancestry,
                &mut PyEditor(update_editor.to_object(py)),
            )
            .unwrap();
    }

    #[pyo3(signature = (revision_to_update_to, diff_target, versus_url, diff_editor, depth=None, ignore_ancestry=false, text_deltas=false))]
    fn do_diff(
        &self,
        py: Python,
        revision_to_update_to: u64,
        diff_target: &str,
        versus_url: &str,
        diff_editor: &Bound<PyAny>,
        depth: Option<subversion::Depth>,
        ignore_ancestry: bool,
        text_deltas: bool,
    ) {
        self.ra
            .lock()
            .unwrap()
            .diff(
                revision_to_update_to.into(),
                diff_target,
                depth.unwrap_or(subversion::Depth::Infinity),
                ignore_ancestry,
                text_deltas,
                versus_url,
                &mut PyEditor(diff_editor.to_object(py)),
            )
            .unwrap();
    }

    fn get_repos_root(&self) -> Result<String, PyErr> {
        Ok(self.ra.lock().unwrap().get_repos_root().unwrap())
    }

    fn get_log(
        &self,
        _callback: &Bound<PyAny>,
        _paths: &str,
        _start: i64,
        _end: i64,
        _limit: i64,
        _discover_changed_paths: bool,
        _strict_node_history: bool,
        _include_merged_revisions: bool,
        _revprops: &str,
    ) {
        unimplemented!()
    }

    fn iter_log(
        &self,
        _paths: &str,
        _start: i64,
        _end: i64,
        _limit: i64,
        _discover_changed_paths: bool,
        _strict_node_history: bool,
        _include_merged_revisions: bool,
        _revprops: &str,
    ) {
        unimplemented!()
    }

    fn get_latest_revnum(&self) -> Result<i64, PyErr> {
        Ok(self.ra.lock().unwrap().get_latest_revnum().unwrap().into())
    }

    fn reparent(&self, url: &str) -> Result<(), PyErr> {
        Ok(self.ra.lock().unwrap().reparent(url).unwrap())
    }

    fn get_uuid(&self) -> Result<String, PyErr> {
        Ok(self.ra.lock().unwrap().get_uuid().unwrap())
    }
}

#[pyclass]
pub struct Auth(subversion::auth::AuthBaton);

#[pymethods]
impl Auth {
    #[classmethod]
    fn open(_type: &Bound<PyType>, providers: Vec<PyRef<AuthProvider>>) -> Result<Auth, PyErr> {
        let mut pool = apr::pool::Pool::new();
        use subversion::auth::AsAuthProvider;
        let auth_providers = providers.into_iter().map(|p| (*p).0.as_auth_provider(&mut pool)).collect::<Vec<_>>();
        Ok(Auth(subversion::auth::AuthBaton::open(auth_providers.as_slice()).map_err(map_svn_error_to_py_err)?))
    }

    fn set_parameter(&mut self, name: &str, value: &str) {
        unimplemented!()
    }

    fn get_parameter(&self, name: &str) -> String {
        unimplemented!()
    }

    fn credentials(&self) {
        unimplemented!()
    }
}

#[pymodule]
fn ra(_py: Python, m: &Bound<PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(get_ssl_client_cert_pw_file_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_ssl_client_cert_file_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_ssl_server_trust_file_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_simple_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_username_prompt_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_simple_prompt_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_ssl_server_trust_prompt_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_ssl_client_cert_prompt_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_username_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_platform_specific_client_providers, m)?)?;
    m.add_function(wrap_pyfunction!(print_modules, m)?)?;

    m.add_class::<RemoteAccess>()?;
    m.add_class::<Auth>()?;
    Ok(())
}
