use common::{map_py_err_to_svn_err, map_svn_error_to_py_err};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyType};
use std::collections::HashMap;
use subversion::auth::SimpleCredentials;
use subversion::delta::{DirectoryEditor, Editor, FileEditor, TxDeltaWindow};
use subversion::Revnum;

#[pyclass]
struct PyReporter(Box<dyn subversion::ra::Reporter + Send>);

impl PyReporter {}

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
            let pw = prompt_func
                .call1(py, (realm,))
                .map_err(map_py_err_to_svn_err)?;
            Ok(pw.extract(py).map_err(map_py_err_to_svn_err)?)
        })
    };
    AuthProvider(subversion::auth::get_ssl_client_cert_pw_file_provider(
        &prompt_fn,
    ))
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
            let may_save: bool = plaintext_prompt_fn
                .call1(py, (realm,))
                .map_err(map_py_err_to_svn_err)?
                .extract(py)
                .map_err(map_py_err_to_svn_err)?;
            Ok(may_save)
        })
    };
    AuthProvider(subversion::auth::get_simple_provider(&plain_prompt))
}

#[pyfunction]
fn get_username_prompt_provider(
    username_prompt_func: PyObject,
    retry_limit: usize,
) -> AuthProvider {
    let prompt = |realm: &str, may_save: bool| -> Result<String, subversion::Error> {
        Python::with_gil(|py| {
            let username: String = username_prompt_func
                .call1(py, (realm, may_save))
                .map_err(map_py_err_to_svn_err)?
                .extract(py)
                .map_err(map_py_err_to_svn_err)?;
            Ok(username)
        })
    };
    AuthProvider(subversion::auth::get_username_prompt_provider(
        &prompt,
        retry_limit,
    ))
}

#[pyfunction]
fn get_simple_prompt_provider(simple_prompt_fn: PyObject, retry_limit: usize) -> AuthProvider {
    let plain_prompt = |realm: &str,
                        username: Option<&str>,
                        may_save: bool|
     -> Result<SimpleCredentials, subversion::Error> {
        Python::with_gil(|py| {
            let (username, password, may_save) = simple_prompt_fn
                .call1(py, (realm, username, may_save))
                .map_err(map_py_err_to_svn_err)?
                .extract(py)
                .map_err(map_py_err_to_svn_err)?;
            Ok(subversion::auth::SimpleCredentials::new(
                username, password, may_save,
            ))
        })
    };
    AuthProvider(subversion::auth::get_simple_prompt_provider(
        &plain_prompt,
        retry_limit,
    ))
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
    let prompt_fn = |realm: &str,
                     failures: usize,
                     cert_info: &subversion::auth::SslServerCertInfo,
                     may_save: bool|
     -> Result<subversion::auth::SslServerTrust, subversion::Error> {
        Python::with_gil(|py| {
            let cert_info = SslServerCertInfo(cert_info.dup());
            let trust: PyRef<SslServerTrust> = prompt_fn
                .call1(py, (realm, failures, cert_info, may_save))
                .map_err(map_py_err_to_svn_err)?
                .extract(py)
                .map_err(map_py_err_to_svn_err)?;

            Ok(trust.as_raw())
        })
    };
    AuthProvider(subversion::auth::get_ssl_server_trust_prompt_provider(
        &prompt_fn,
    ))
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
    let prompt_fn = |realm: &str,
                     may_save: bool|
     -> Result<subversion::auth::SslClientCertCredentials, subversion::Error> {
        Python::with_gil(|py| {
            let creds: PyRef<SslClientCertCredentials> = prompt_fn
                .call1(py, (realm, may_save))
                .map_err(map_py_err_to_svn_err)?
                .extract(py)
                .map_err(map_py_err_to_svn_err)?;
            Ok(creds.as_raw())
        })
    };
    AuthProvider(subversion::auth::get_ssl_client_cert_prompt_provider(
        &prompt_fn,
        retry_limit,
    ))
}

#[pyfunction]
fn get_platform_specific_client_providers() -> Result<Vec<AuthProvider>, PyErr> {
    Ok(subversion::auth::get_platform_specific_client_providers()
        .map_err(map_svn_error_to_py_err)?
        .into_iter()
        .map(AuthProvider)
        .collect())
}

#[pyfunction]
fn get_username_provider() -> AuthProvider {
    AuthProvider(subversion::auth::get_username_provider())
}

#[pyfunction]
fn get_platform_specific_provider(
    provider_name: &str,
    provider_type: &str,
) -> Result<AuthProvider, PyErr> {
    Ok(AuthProvider(
        subversion::auth::get_platform_specific_provider(provider_name, provider_type)
            .map_err(map_svn_error_to_py_err)?,
    ))
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
            self.0
                .call_method1(py, "set_target_revision", (revision,))
                .map_err(map_py_err_to_svn_err)?;
            Ok(())
        })
    }

    fn open_root<'a>(
        &'a mut self,
        base_revision: Revnum,
    ) -> Result<Box<dyn DirectoryEditor + 'a>, subversion::Error> {
        let directory = Python::with_gil(|py| {
            self.0
                .call_method1(py, "open_root", (Into::<i64>::into(base_revision),))
        })
        .map_err(map_py_err_to_svn_err)?;
        Ok(Box::new(PyDirectoryEditor(directory)))
    }

    fn close(&mut self) -> Result<(), subversion::Error> {
        Python::with_gil(|py| {
            self.0
                .call_method0(py, "close")
                .map_err(map_py_err_to_svn_err)?;
            Ok(())
        })
    }

    fn abort(&mut self) -> Result<(), subversion::Error> {
        Python::with_gil(|py| {
            self.0
                .call_method0(py, "abort")
                .map_err(map_py_err_to_svn_err)?;
            Ok(())
        })
    }
}

struct PyDirectoryEditor(PyObject);

impl subversion::delta::DirectoryEditor for PyDirectoryEditor {
    fn delete_entry(
        &mut self,
        path: &str,
        revision: Option<Revnum>,
    ) -> Result<(), subversion::Error> {
        let revision: Option<u64> = revision.map(Into::into);
        Python::with_gil(|py| {
            self.0
                .call_method1(py, "delete_entry", (path, revision))
                .map_err(map_py_err_to_svn_err)?;
            Ok(())
        })
    }

    fn add_directory<'a>(
        &'a mut self,
        path: &str,
        copyfrom: Option<(&str, Revnum)>,
    ) -> Result<Box<dyn DirectoryEditor + 'a>, subversion::Error> {
        let copyfrom: Option<(&str, u64)> = copyfrom.map(|(path, rev)| (path, rev.into()));
        let directory =
            Python::with_gil(|py| self.0.call_method1(py, "add_directory", (path, copyfrom)))
                .map_err(map_py_err_to_svn_err)?;
        Ok(Box::new(PyDirectoryEditor(directory)))
    }

    fn open_directory<'a>(
        &'a mut self,
        path: &str,
        base_revision: Option<Revnum>,
    ) -> Result<Box<dyn DirectoryEditor + 'a>, subversion::Error> {
        let base_revision: Option<u64> = base_revision.map(Into::into);
        let directory = Python::with_gil(|py| {
            self.0
                .call_method1(py, "open_directory", (path, base_revision))
        })
        .map_err(map_py_err_to_svn_err)?;
        Ok(Box::new(PyDirectoryEditor(directory)))
    }

    fn change_prop(&mut self, name: &str, value: &[u8]) -> Result<(), subversion::Error> {
        Python::with_gil(|py| {
            self.0
                .call_method1(py, "change_prop", (name, value))
                .map_err(map_py_err_to_svn_err)?;
            Ok(())
        })
    }

    fn close(&mut self) -> Result<(), subversion::Error> {
        Python::with_gil(|py| {
            self.0
                .call_method0(py, "close")
                .map_err(map_py_err_to_svn_err)?;
            Ok(())
        })
    }

    fn absent_directory(&mut self, path: &str) -> Result<(), subversion::Error> {
        Python::with_gil(|py| {
            self.0
                .call_method1(py, "absent_directory", (path,))
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
        let file = Python::with_gil(|py| self.0.call_method1(py, "add_file", (path, copyfrom)))
            .map_err(map_py_err_to_svn_err)?;
        Ok(Box::new(PyFileEditor(file)))
    }

    fn open_file<'a>(
        &'a mut self,
        path: &str,
        base_revision: Option<Revnum>,
    ) -> Result<Box<dyn FileEditor + 'a>, subversion::Error> {
        let base_revision: Option<u64> = base_revision.map(Into::into);
        let file =
            Python::with_gil(|py| self.0.call_method1(py, "open_file", (path, base_revision)))
                .map_err(map_py_err_to_svn_err)?;
        Ok(Box::new(PyFileEditor(file)))
    }

    fn absent_file(&mut self, path: &str) -> Result<(), subversion::Error> {
        Python::with_gil(|py| {
            self.0
                .call_method1(py, "absent_file", (path,))
                .map_err(map_py_err_to_svn_err)?;
            Ok(())
        })
    }
}

#[pyclass]
struct PyWindow(TxDeltaWindow);

struct PyFileEditor(PyObject);

impl FileEditor for PyFileEditor {
    fn apply_textdelta(
        &mut self,
        base_checksum: Option<&str>,
    ) -> Result<
        Box<dyn for<'b> Fn(&'b mut TxDeltaWindow) -> Result<(), subversion::Error>>,
        subversion::Error,
    > {
        let text_delta =
            Python::with_gil(|py| self.0.call_method1(py, "apply_textdelta", (base_checksum,)))
                .map_err(map_py_err_to_svn_err)?;
        Ok(Box::new(move |window| {
            let window = PyWindow(window.dup());
            Python::with_gil(|py| {
                text_delta
                    .call_method1(py, "apply", (window,))
                    .map_err(map_py_err_to_svn_err)?;
                Ok(())
            })
        }))
    }

    fn change_prop(&mut self, name: &str, value: &[u8]) -> Result<(), subversion::Error> {
        Python::with_gil(|py| {
            self.0
                .call_method1(py, "change_prop", (name, value))
                .map_err(map_py_err_to_svn_err)?;
            Ok(())
        })
    }

    fn close(&mut self, text_checksum: Option<&str>) -> Result<(), subversion::Error> {
        Python::with_gil(|py| {
            self.0
                .call_method1(py, "close", (text_checksum,))
                .map_err(map_py_err_to_svn_err)?;
            Ok(())
        })
    }
}

#[pyclass]
struct PyLock(subversion::Lock);

#[pyclass]
struct PyCommitInfo(subversion::CommitInfo);

#[pyclass]
struct PyLocationSegment(subversion::LocationSegment);

#[pyclass]
struct Mergeinfo(subversion::mergeinfo::Mergeinfo);
unsafe impl Send for Mergeinfo {}

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

    #[pyo3(signature = (path, peg_revision, location_revisions))]
    fn get_locations(
        &self,
        path: &str,
        peg_revision: u64,
        location_revisions: Vec<u64>,
    ) -> Result<HashMap<u64, String>, PyErr> {
        self.ra
            .lock()
            .unwrap()
            .get_locations(
                path,
                peg_revision.into(),
                location_revisions
                    .into_iter()
                    .map(|r| r.into())
                    .collect::<Vec<_>>()
                    .as_slice(),
            )
            .map_err(map_svn_error_to_py_err)
            .map(|locs| locs.into_iter().map(|(k, v)| (k.into(), v)).collect())
    }

    #[pyo3(signature = (path, depth=None))]
    fn get_locks(
        &self,
        path: &str,
        depth: Option<subversion::Depth>,
    ) -> Result<HashMap<String, PyLock>, PyErr> {
        self.ra
            .lock()
            .unwrap()
            .get_locks(path, depth.unwrap_or(subversion::Depth::Infinity))
            .map_err(map_svn_error_to_py_err)
            .map(|locks| locks.into_iter().map(|(k, v)| (k, PyLock(v))).collect())
    }

    #[pyo3(signature = (path_revs, comment, steal_lock, lock_func))]
    fn lock(
        &self,
        path_revs: HashMap<String, u64>,
        comment: &str,
        steal_lock: bool,
        lock_func: &Bound<PyAny>,
    ) -> Result<(), PyErr> {
        let path_revs = path_revs.into_iter().map(|(k, v)| (k, v.into())).collect();
        self.ra
            .lock()
            .unwrap()
            .lock(
                &path_revs,
                comment,
                steal_lock,
                |path, steal, lock, error| {
                    let path = path.to_string();
                    let error = error.map(|e| e.to_string());
                    let lock = PyLock(lock.dup());
                    lock_func
                        .call1((path, steal, lock, error))
                        .map_err(map_py_err_to_svn_err)?;
                    Ok(())
                },
            )
            .map_err(map_svn_error_to_py_err)
    }

    #[pyo3(signature = (path_tokens, break_lock, lock_func))]
    fn unlock(
        &self,
        path_tokens: HashMap<String, String>,
        break_lock: bool,
        lock_func: &Bound<PyAny>,
    ) -> Result<(), PyErr> {
        self.ra
            .lock()
            .unwrap()
            .unlock(&path_tokens, break_lock, &|path: &str,
                                                steal: bool,
                                                lock: &subversion::Lock,
                                                error: Option<
                &subversion::Error,
            >|
             -> Result<
                (),
                subversion::Error,
            > {
                let path = path.to_string();
                let error = error.map(|e| e.to_string());
                let lock = PyLock(lock.dup());
                lock_func
                    .call1((path, steal, lock, error))
                    .map_err(map_py_err_to_svn_err)?;
                Ok(())
            })
            .map_err(map_svn_error_to_py_err)
    }

    #[pyo3(signature = (paths, revision, inherit=false, include_descendants=false))]
    fn mergeinfo(
        &self,
        paths: Vec<String>,
        revision: u64,
        inherit: bool,
        include_descendants: bool,
    ) -> Result<HashMap<String, Mergeinfo>, PyErr> {
        let paths = paths.iter().map(|p| p.as_str()).collect::<Vec<_>>();
        self.ra
            .lock()
            .unwrap()
            .get_mergeinfo(
                paths.as_slice(),
                revision.into(),
                if inherit {
                    subversion::mergeinfo::MergeinfoInheritance::Inherited
                } else {
                    subversion::mergeinfo::MergeinfoInheritance::Explicit
                },
                include_descendants,
            )
            .map_err(map_svn_error_to_py_err)
            .map(|mi| mi.into_iter().map(|(k, v)| (k, Mergeinfo(v))).collect())
    }

    #[pyo3(signature = (path, peg_revision, start_revision, end_revision, rcvr))]
    fn get_location_segments(
        &self,
        path: &str,
        peg_revision: u64,
        start_revision: u64,
        end_revision: u64,
        rcvr: &Bound<PyAny>,
    ) -> Result<(), PyErr> {
        self.ra
            .lock()
            .unwrap()
            .get_location_segments(
                path,
                peg_revision.into(),
                start_revision.into(),
                end_revision.into(),
                &|ls| {
                    let ls = PyLocationSegment(ls.dup());
                    rcvr.call1((ls,)).map_err(map_py_err_to_svn_err)?;
                    Ok(())
                },
            )
            .map_err(map_svn_error_to_py_err)
    }

    #[pyo3(signature = (name, ))]
    fn has_capability(&self, name: &str) -> Result<bool, PyErr> {
        self.ra
            .lock()
            .unwrap()
            .has_capability(name)
            .map_err(map_svn_error_to_py_err)
    }

    #[pyo3(signature = (path, revnum))]
    fn check_path(&self, path: &str, revnum: u64) -> Result<i64, PyErr> {
        match self.ra.lock().unwrap().check_path(path, revnum.into()) {
            Ok(subversion::NodeKind::None) => Ok(0),
            Ok(subversion::NodeKind::File) => Ok(1),
            Ok(subversion::NodeKind::Dir) => Ok(2),
            Ok(subversion::NodeKind::Symlink) => Ok(3),
            Ok(subversion::NodeKind::Unknown) => Ok(4),
            Err(e) => return Err(map_svn_error_to_py_err(e)),
        }
    }

    #[pyo3(signature = (path, revnum))]
    fn stat(&self, path: &str, revnum: u64) -> Result<PyDirent, PyErr> {
        Ok(PyDirent(
            self.ra
                .lock()
                .unwrap()
                .stat(path, revnum.into())
                .map_err(map_svn_error_to_py_err)?,
        ))
    }

    #[pyo3(signature = (path, ))]
    fn get_lock(&self, path: &str) -> Result<PyLock, PyErr> {
        Ok(PyLock(
            self.ra
                .lock()
                .unwrap()
                .get_lock(path)
                .map_err(map_svn_error_to_py_err)?,
        ))
    }

    #[pyo3(signature = (path, revision, dirent_fields))]
    fn get_dir(
        &self,
        py: Python<'_>,
        path: &'_ str,
        revision: u64,
        dirent_fields: i64,
    ) -> Result<(u64, HashMap<String, PyDirent>, HashMap<String, PyObject>), PyErr> {
        let (revnum, dirents, props) = self
            .ra
            .lock()
            .unwrap()
            .get_dir(path, revision.into())
            .map_err(map_svn_error_to_py_err)?;

        let dirents = dirents.into_iter().map(|(k, v)| (k, PyDirent(v))).collect();

        let props = props
            .into_iter()
            .map(|(k, v)| (k, PyBytes::new_bound(py, &v).to_object(py)))
            .collect();

        Ok((revnum.into(), dirents, props))
    }

    #[pyo3(signature = (path, stream, revnum))]
    fn get_file(
        &self,
        py: Python,
        path: &str,
        stream: &Bound<PyAny>,
        revnum: u64,
    ) -> Result<(u64, HashMap<String, PyObject>), PyErr> {
        let revnum: Revnum = revnum.into();
        let mut stream = common::stream_from_object(py, stream.to_object(py))?;
        let (rev, props) = self
            .ra
            .lock()
            .unwrap()
            .get_file(path, revnum, &mut stream)
            .map_err(map_svn_error_to_py_err)?;
        Ok((
            rev.into(),
            props
                .into_iter()
                .map(|(k, v)| (k, PyBytes::new_bound(py, &v).to_object(py)))
                .collect(),
        ))
    }

    #[pyo3(signature = (revnum, name, old_value, new_value))]
    fn change_rev_prop(
        &self,
        revnum: u64,
        name: &str,
        old_value: Option<&[u8]>,
        new_value: &[u8],
    ) -> Result<(), PyErr> {
        Ok(self
            .ra
            .lock()
            .unwrap()
            .change_revprop(revnum.into(), name, old_value, new_value)
            .map_err(map_svn_error_to_py_err)?)
    }

    #[pyo3(signature = (revprops, commit_callback, lock_tokens=None, keep_locks=false))]
    fn get_commit_editor(
        &self,
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
                    commit_callback
                        .call1((ci,))
                        .map_err(map_py_err_to_svn_err)?;
                    Ok(())
                },
                lock_tokens.unwrap_or_default(),
                keep_locks,
            )
            .unwrap();

        Ok(WrapEditor(editor))
    }

    #[pyo3(signature = (revnum))]
    fn rev_proplist(&self, py: Python, revnum: u64) -> Result<HashMap<String, PyObject>, PyErr> {
        let revprops = self.ra.lock().unwrap().rev_proplist(revnum.into()).unwrap();

        Ok(revprops
            .into_iter()
            .map(|(k, v)| (k, PyBytes::new_bound(py, &v).to_object(py)))
            .collect())
    }

    #[pyo3(signature = (revision, low_water_mark, update_editor, send_deltas=false))]
    fn replay(
        &self,
        py: Python,
        revision: u64,
        low_water_mark: u64,
        update_editor: &Bound<PyAny>,
        send_deltas: bool,
    ) -> Result<(), PyErr> {
        let mut editor = PyEditor(update_editor.to_object(py));
        self.ra
            .lock()
            .unwrap()
            .replay(
                revision.into(),
                low_water_mark.into(),
                send_deltas,
                &mut editor,
            )
            .map_err(map_svn_error_to_py_err)
    }

    #[pyo3(signature = (start_rev, end_rev, low_water_mark, cbs, send_deltas=false))]
    fn replay_range(
        &self,
        py: Python,
        start_rev: u64,
        end_rev: u64,
        low_water_mark: u64,
        cbs: (PyObject, PyObject),
        send_deltas: bool,
    ) -> Result<(), PyErr> {
        let (start_rev_cb, end_rev_cb) = cbs;
        self.ra
            .lock()
            .unwrap()
            .replay_range(
                start_rev.into(),
                end_rev.into(),
                low_water_mark.into(),
                send_deltas,
                &|revnum: Revnum,
                  props: &'_ HashMap<String, Vec<u8>>|
                 -> Result<Box<dyn subversion::delta::Editor>, subversion::Error> {
                    let revnum = Into::<u64>::into(revnum);
                    let props = props
                        .into_iter()
                        .map(|(k, v)| (k, PyBytes::new_bound(py, &v).to_object(py)))
                        .collect::<HashMap<_, _>>();
                    let editor = start_rev_cb
                        .call1(py, (revnum, props))
                        .map_err(map_py_err_to_svn_err)?;
                    Ok(Box::new(PyEditor(editor.to_object(py))))
                },
                &|revnum: Revnum,
                  editor: &'_ dyn subversion::delta::Editor,
                  props: &'_ HashMap<String, Vec<u8>>|
                 -> Result<(), subversion::Error> {
                    let revnum = Into::<u64>::into(revnum);
                    let editor = WrapEditor(unsafe { Box::from_raw(editor as *const _ as *mut _) });
                    let props = props
                        .into_iter()
                        .map(|(k, v)| (k, PyBytes::new_bound(py, &v).to_object(py)))
                        .collect::<HashMap<_, _>>();
                    end_rev_cb
                        .call1(py, (revnum, editor, props))
                        .map_err(map_py_err_to_svn_err)?;
                    Ok(())
                },
            )
            .map_err(map_svn_error_to_py_err)
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
            )
            .map_err(map_svn_error_to_py_err)
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

    #[pyo3(signature = (url, ))]
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
        let auth_providers = providers
            .into_iter()
            .map(|p| (*p).0.as_auth_provider(&mut pool))
            .collect::<Vec<_>>();
        Ok(Auth(
            subversion::auth::AuthBaton::open(auth_providers.as_slice())
                .map_err(map_svn_error_to_py_err)?,
        ))
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
fn _ra(_py: Python, m: &Bound<PyModule>) -> PyResult<()> {
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
