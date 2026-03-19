//! Remote Access Session Python bindings

use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};
use std::cell::Cell;
use std::sync::mpsc::{self, Receiver};
use subvertpy_util::error::svn_err_to_py;

/// Convert a Python depth integer to subversion::Depth
pub(crate) fn py_depth_to_svn(depth: i32) -> PyResult<subversion::Depth> {
    match depth {
        -2 => Ok(subversion::Depth::Unknown),
        -1 => Ok(subversion::Depth::Exclude),
        0 => Ok(subversion::Depth::Empty),
        1 => Ok(subversion::Depth::Files),
        2 => Ok(subversion::Depth::Immediates),
        3 => Ok(subversion::Depth::Infinity),
        _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
            "Invalid depth value: {}",
            depth
        ))),
    }
}

/// Convert a subversion::NodeKind to the Python integer constant
fn node_kind_to_py(kind: subversion::NodeKind) -> i32 {
    match kind {
        subversion::NodeKind::None => 0,
        subversion::NodeKind::File => 1,
        subversion::NodeKind::Dir => 2,
        subversion::NodeKind::Unknown => 3,
        subversion::NodeKind::Symlink => 4,
    }
}

/// Convert a LogEntry to a Python tuple (changed_paths, revision, revprops, has_children)
fn log_entry_to_py(py: Python, log_entry: &subversion::LogEntry) -> PyResult<Py<PyAny>> {
    let changed_paths: pyo3::Py<pyo3::PyAny> = match log_entry.changed_paths() {
        None => py.None(),
        Some(paths) => {
            let dict = PyDict::new(py);
            for (path, change) in paths {
                let action = change.action.to_string();
                let copyfrom_path: pyo3::Py<pyo3::PyAny> = match change.copyfrom_path {
                    Some(p) => p
                        .into_pyobject(py)
                        .map_err(|e| {
                            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("{}", e))
                        })?
                        .unbind()
                        .into_any(),
                    None => py.None(),
                };
                let copyfrom_rev = change.copyfrom_rev.map(|r| r.as_u64() as i64).unwrap_or(-1);
                let node_kind = node_kind_to_py(change.node_kind);
                dict.set_item(&path, (action, copyfrom_path, copyfrom_rev, node_kind))?;
            }
            dict.into_any().unbind()
        }
    };

    let revision = log_entry
        .revision()
        .map(|r| r.as_u64() as i64)
        .unwrap_or(-1);

    let revprops_dict = PyDict::new(py);
    for (key, value) in log_entry.revprops() {
        revprops_dict.set_item(&key, PyBytes::new(py, &value))?;
    }

    let has_children = log_entry.has_children();

    let tuple = (
        changed_paths,
        revision,
        revprops_dict.into_any().unbind(),
        has_children,
    )
        .into_pyobject(py)
        .map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Failed to convert: {}", e))
        })?;

    Ok(tuple.unbind().into_any())
}

/// Subversion remote access session
#[pyclass(name = "RemoteAccess", unsendable)]
pub struct RemoteAccess {
    session: subversion::ra::Session<'static>,
    url: String,
    busy: Cell<bool>,
    /// Keep the Auth object alive so the borrowed auth baton pointer remains valid
    _auth: Option<Py<PyAny>>,
}

impl RemoteAccess {
    /// Check if session is busy and raise BusyException if so
    fn check_busy(&self) -> PyResult<()> {
        if self.busy.get() {
            Err(PyErr::new::<crate::BusyException, _>("Session is busy"))
        } else {
            Ok(())
        }
    }

    /// Mark session as busy (for editor operations)
    fn set_busy(&self, busy: bool) {
        self.busy.set(busy);
    }
}

/// Iterator for log entries
#[pyclass(name = "LogIterator", unsendable)]
pub struct LogIterator {
    receiver: Receiver<PyResult<Py<PyAny>>>,
    _session: Py<RemoteAccess>,
}

#[pymethods]
impl LogIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(&mut self) -> PyResult<Option<Py<PyAny>>> {
        match self.receiver.recv() {
            Ok(Ok(item)) => Ok(Some(item)),
            Ok(Err(e)) => Err(e),
            Err(_) => Ok(None), // Channel closed, iteration done
        }
    }
}

#[pymethods]
impl RemoteAccess {
    /// Create a new RA session
    #[new]
    #[pyo3(signature = (url, auth=None, **_kwargs))]
    fn init(
        url: &str,
        auth: Option<Bound<crate::auth::Auth>>,
        _kwargs: Option<&Bound<'_, PyDict>>,
    ) -> PyResult<Self> {
        let callbacks = Box::new(subversion::ra::Callbacks::new().map_err(|e| svn_err_to_py(e))?);

        // Leak the callbacks box to get a 'static reference
        // This is intentional - the callbacks need to live for the lifetime of the session
        let callbacks_ref: &'static mut subversion::ra::Callbacks = Box::leak(callbacks);

        if let Some(ref auth_obj) = auth {
            auth_obj.borrow().with_baton_mut(|baton| {
                // Safety: the Auth Python object is kept alive via _auth field below,
                // so the baton pointer remains valid for the lifetime of the session.
                unsafe { callbacks_ref.set_auth_baton_borrowed(baton) };
            });
        }

        let url = subversion::uri::canonicalize_uri(url).map_err(|e| svn_err_to_py(e))?;
        let (session, _corrected_url, _repos_root) = subversion::ra::Session::open(
            &url,
            None, // config_dir
            Some(callbacks_ref),
            None, // config
        )
        .map_err(|e| svn_err_to_py(e))?;

        Ok(Self {
            session,
            url: url.to_string(),
            busy: Cell::new(false),
            _auth: auth.map(|a| a.unbind().into_any()),
        })
    }

    /// Get the original URL used to create this session
    #[getter]
    fn url(&self) -> PyResult<String> {
        Ok(self.url.clone())
    }

    /// Whether the session is busy (e.g., an editor or reporter is active)
    #[getter]
    fn busy(&self) -> bool {
        self.busy.get()
    }

    /// Get the repository UUID
    fn get_uuid(&mut self) -> PyResult<String> {
        self.session.get_uuid().map_err(|e| svn_err_to_py(e))
    }

    /// Get the repository root URL
    fn get_repos_root(&mut self) -> PyResult<String> {
        self.session.get_repos_root().map_err(|e| svn_err_to_py(e))
    }

    /// Get the session URL
    fn get_session_url(&mut self) -> PyResult<String> {
        self.session.get_session_url().map_err(|e| svn_err_to_py(e))
    }

    /// Get the latest revision number
    fn get_latest_revnum(&mut self) -> PyResult<i64> {
        let revnum = self
            .session
            .get_latest_revnum()
            .map_err(|e| svn_err_to_py(e))?;
        Ok(revnum.as_u64() as i64)
    }

    /// Reparent the session to a new URL
    fn reparent(&mut self, url: &str) -> PyResult<()> {
        let url = subversion::uri::canonicalize_uri(url).map_err(|e| svn_err_to_py(e))?;
        self.session.reparent(&url).map_err(|e| svn_err_to_py(e))?;
        self.url = url;
        Ok(())
    }

    /// Check if the repository has a capability
    fn has_capability(&mut self, capability: &str) -> PyResult<bool> {
        self.session
            .has_capability(capability)
            .map_err(|e| svn_err_to_py(e))
    }

    /// Check the type of a path
    fn check_path(&mut self, path: &str, revnum: i64) -> PyResult<i32> {
        let rev = subvertpy_util::to_revnum_or_head(revnum);
        let path = subvertpy_util::to_relpath(path)?;

        let node_kind = self
            .session
            .check_path(path.as_str(), rev)
            .map_err(|e| svn_err_to_py(e))?;

        Ok(node_kind_to_py(node_kind))
    }

    /// Get revision properties
    fn rev_proplist(&mut self, revnum: i64) -> PyResult<pyo3::Py<pyo3::PyAny>> {
        let rev = subvertpy_util::to_revnum_or_head(revnum);

        let props = self
            .session
            .rev_proplist(rev)
            .map_err(|e| svn_err_to_py(e))?;

        Python::attach(|py| {
            subvertpy_util::properties::props_to_py_dict(py, &props).map(|d| d.into_any().unbind())
        })
    }

    /// Change a revision property
    #[pyo3(signature = (revnum, name, value, old_value=None))]
    fn change_rev_prop(
        &mut self,
        revnum: i64,
        name: &str,
        value: Option<Bound<pyo3::PyAny>>,
        old_value: Option<Bound<pyo3::PyAny>>,
    ) -> PyResult<()> {
        let rev = subvertpy_util::to_revnum_or_head(revnum);

        let extract_bytes = |v: &Bound<pyo3::PyAny>| -> PyResult<Vec<u8>> {
            if let Ok(b) = v.cast::<pyo3::types::PyBytes>() {
                Ok(b.as_bytes().to_vec())
            } else if let Ok(s) = v.extract::<String>() {
                Ok(s.into_bytes())
            } else {
                Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                    "value must be str or bytes",
                ))
            }
        };

        let value_bytes: Option<Vec<u8>> = match value {
            None => None,
            Some(ref v) => Some(extract_bytes(v)?),
        };

        let old_value_bytes: Option<Vec<u8>> = match old_value {
            None => None,
            Some(ref v) => {
                if v.is_none() {
                    Some(Vec::new())
                } else {
                    Some(extract_bytes(v)?)
                }
            }
        };

        self.session
            .change_rev_prop2(
                rev,
                name,
                old_value_bytes.as_deref(),
                value_bytes.as_deref(),
            )
            .map_err(|e| svn_err_to_py(e))
    }

    /// Get a file from the repository
    fn get_file(
        &mut self,
        path: &str,
        stream: Bound<pyo3::PyAny>,
        revnum: Option<i64>,
    ) -> PyResult<(Option<i64>, pyo3::Py<pyo3::PyAny>)> {
        let path = subvertpy_util::to_relpath(path)?;

        let rev = revnum
            .and_then(|r| subvertpy_util::to_revnum(r))
            .unwrap_or_else(|| subversion::Revnum::invalid());

        let mut buffer: Vec<u8> = Vec::new();
        let mut svn_stream =
            subversion::io::wrap_write(&mut buffer).map_err(|e| svn_err_to_py(e))?;

        let (fetched_rev, props) = self
            .session
            .get_file(path.as_str(), rev, &mut svn_stream)
            .map_err(|e| svn_err_to_py(e))?;

        svn_stream.close().map_err(|e| svn_err_to_py(e))?;

        use std::io::Write;
        let mut filelike = pyo3_filelike::PyBinaryFile::from(stream);
        filelike
            .write_all(&buffer)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;
        filelike
            .flush()
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;

        let py_props = Python::attach(|py| {
            subvertpy_util::properties::props_to_py_dict(py, &props).map(|d| d.into_any().unbind())
        })?;

        let rev_num = fetched_rev.map(|r| r.as_u64() as i64);

        Ok((rev_num, py_props))
    }

    /// Get directory entries
    #[pyo3(signature = (path, revision, fields=None))]
    fn get_dir(
        &mut self,
        path: &str,
        revision: i64,
        fields: Option<i64>,
    ) -> PyResult<(pyo3::Py<pyo3::PyAny>, i64, pyo3::Py<pyo3::PyAny>)> {
        let rev = subvertpy_util::to_revnum_or_head(revision);
        let path = subvertpy_util::to_relpath(path)?;

        let dirent_fields = match fields {
            Some(f) => subversion::DirentField::from_bits_truncate(f as u32),
            None => subversion::DirentField::all(),
        };

        let (fetched_rev, dirents, props) = self
            .session
            .get_dir(path.as_str(), rev, dirent_fields)
            .map_err(|e| svn_err_to_py(e))?;

        Python::attach(|py| {
            let dirents_dict = pyo3::types::PyDict::new(py);
            for (name, dirent) in dirents {
                let entry = pyo3::types::PyDict::new(py);
                entry.set_item("kind", dirent.kind() as i32)?;
                entry.set_item("size", dirent.size())?;
                entry.set_item("has_props", dirent.has_props())?;
                entry.set_item(
                    "created_rev",
                    dirent
                        .created_rev()
                        .map(|r| r.as_u64() as i64)
                        .unwrap_or(-1),
                )?;
                entry.set_item("time", dirent.time().as_micros())?;
                entry.set_item("last_author", dirent.last_author())?;
                dirents_dict.set_item(name, entry)?;
            }

            let props_dict = subvertpy_util::properties::props_to_py_dict(py, &props)?;

            Ok((
                dirents_dict.into_any().unbind(),
                fetched_rev.as_u64() as i64,
                props_dict.into_any().unbind(),
            ))
        })
    }

    /// Get file/directory status information
    fn stat(&mut self, path: &str, revnum: i64) -> PyResult<pyo3::Py<pyo3::PyAny>> {
        let rev = subvertpy_util::to_revnum_or_head(revnum);
        let path = subvertpy_util::to_relpath(path)?;

        let dirent = self
            .session
            .stat(path.as_str(), rev)
            .map_err(|e| svn_err_to_py(e))?;

        Python::attach(|py| {
            let dict = pyo3::types::PyDict::new(py);
            dict.set_item("kind", dirent.kind() as i32)?;
            dict.set_item("size", dirent.size())?;
            dict.set_item("has_props", dirent.has_props())?;
            dict.set_item(
                "created_rev",
                dirent
                    .created_rev()
                    .map(|r| r.as_u64() as i64)
                    .unwrap_or(-1),
            )?;
            dict.set_item("time", dirent.time().as_micros())?;
            dict.set_item("last_author", dirent.last_author())?;
            Ok(dict.into_any().unbind())
        })
    }

    /// Lock paths in the repository
    fn lock(
        &mut self,
        path_revs: Bound<PyDict>,
        comment: &str,
        steal_lock: bool,
        lock_func: Bound<pyo3::PyAny>,
    ) -> PyResult<()> {
        use std::collections::HashMap;

        let mut path_rev_map = HashMap::new();
        for (key, value) in path_revs.iter() {
            let path_str = subvertpy_util::py_to_svn_string(&key)?;
            let revnum: i64 = value.extract()?;
            let rev = subvertpy_util::to_revnum_or_head(revnum);
            path_rev_map.insert(path_str, rev);
        }

        let py_lock_func = lock_func.clone();
        let lock_callback = |path: &str,
                             do_lock: bool,
                             lock: Option<&subversion::Lock>,
                             err: Option<&subversion::Error>|
         -> Result<(), subversion::Error> {
            Python::attach(|py| {
                let py_lock: pyo3::Bound<pyo3::PyAny> = match lock {
                    Some(lock) => (
                        lock.path(),
                        lock.token(),
                        lock.owner(),
                        lock.comment(),
                        lock.creation_date(),
                    )
                        .into_pyobject(py)
                        .map_err(|e| {
                            subversion::Error::from_message(&format!(
                                "Failed to convert lock: {}",
                                e
                            ))
                        })?
                        .into_any(),
                    None => py.None().into_bound(py),
                };

                let py_err: pyo3::Bound<pyo3::PyAny> = if let Some(e) = err {
                    let message = e.message().unwrap_or("Unknown SVN error");
                    let owned_err = subversion::Error::from_message(message);
                    let err = svn_err_to_py(owned_err);
                    err.into_pyobject(py).unwrap().into_any()
                } else {
                    py.None().into_bound(py)
                };

                py_lock_func
                    .call1((path, do_lock, py_lock, py_err))
                    .map_err(|e| {
                        subversion::Error::from_message(&format!("Python callback error: {}", e))
                    })?;

                Ok(())
            })
        };

        self.session
            .lock(&path_rev_map, comment, steal_lock, lock_callback)
            .map_err(|e| svn_err_to_py(e))?;

        Ok(())
    }

    /// Unlock paths in the repository
    fn unlock(
        &mut self,
        path_tokens: Bound<PyDict>,
        break_lock: bool,
        lock_func: Bound<pyo3::PyAny>,
    ) -> PyResult<()> {
        use std::collections::HashMap;

        let mut path_token_map = HashMap::new();
        for (key, value) in path_tokens.iter() {
            let path_str = subvertpy_util::py_to_svn_string(&key)?;
            let token_str = subvertpy_util::py_to_svn_string(&value)?;
            path_token_map.insert(path_str, token_str);
        }

        let py_lock_func = lock_func.clone();
        let lock_callback = |path: &str,
                             do_lock: bool,
                             lock: Option<&subversion::Lock>,
                             err: Option<&subversion::Error>|
         -> Result<(), subversion::Error> {
            Python::attach(|py| {
                let py_lock: pyo3::Bound<pyo3::PyAny> = match lock {
                    Some(lock) => (
                        lock.path(),
                        lock.token(),
                        lock.owner(),
                        lock.comment(),
                        lock.creation_date(),
                    )
                        .into_pyobject(py)
                        .map_err(|e| {
                            subversion::Error::from_message(&format!(
                                "Failed to convert lock: {}",
                                e
                            ))
                        })?
                        .into_any(),
                    None => py.None().into_bound(py),
                };

                let py_err: pyo3::Bound<pyo3::PyAny> = if let Some(e) = err {
                    let message = e.message().unwrap_or("Unknown SVN error");
                    let owned_err = subversion::Error::from_message(message);
                    let err = svn_err_to_py(owned_err);
                    err.into_pyobject(py).unwrap().into_any()
                } else {
                    py.None().into_bound(py)
                };

                py_lock_func
                    .call1((path, do_lock, py_lock, py_err))
                    .map_err(|e| {
                        subversion::Error::from_message(&format!("Python callback error: {}", e))
                    })?;

                Ok(())
            })
        };

        self.session
            .unlock(&path_token_map, break_lock, lock_callback)
            .map_err(|e| svn_err_to_py(e))?;

        Ok(())
    }

    /// Get lock for a path (singular)
    fn get_lock(&mut self, path: &str) -> PyResult<Option<pyo3::Py<pyo3::PyAny>>> {
        let path = subvertpy_util::to_relpath(path)?;
        let lock_opt = self
            .session
            .get_lock(path.as_str())
            .map_err(|e| svn_err_to_py(e))?;

        match lock_opt {
            Some(lock) => Python::attach(|py| {
                let lock_tuple = (
                    lock.path(),
                    lock.token(),
                    lock.owner(),
                    lock.comment(),
                    lock.is_dav_comment(),
                    lock.creation_date(),
                    lock.expiration_date().as_micros(),
                )
                    .into_pyobject(py)
                    .map_err(|e| {
                        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                            "Failed to convert lock: {}",
                            e
                        ))
                    })?;
                Ok(Some(lock_tuple.into_any().unbind()))
            }),
            None => Ok(None),
        }
    }

    /// Get locks for a path
    #[pyo3(signature = (path, depth=None))]
    fn get_locks(&mut self, path: &str, depth: Option<i32>) -> PyResult<pyo3::Py<pyo3::PyAny>> {
        let svn_depth = match depth {
            Some(d) => py_depth_to_svn(d)?,
            None => subversion::Depth::Infinity,
        };

        let locks = self
            .session
            .get_locks(path, svn_depth)
            .map_err(|e| svn_err_to_py(e))?;

        Python::attach(|py| {
            let locks_dict = PyDict::new(py);
            for (path, lock) in locks {
                let lock_tuple = (
                    lock.path(),
                    lock.token(),
                    lock.owner(),
                    lock.comment(),
                    lock.is_dav_comment(),
                    lock.creation_date(),
                    lock.expiration_date().as_micros(),
                )
                    .into_pyobject(py)
                    .map_err(|e| {
                        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                            "Failed to convert lock: {}",
                            e
                        ))
                    })?;
                locks_dict.set_item(path, lock_tuple.into_any())?;
            }
            Ok(locks_dict.into_any().unbind())
        })
    }

    /// Get log entries
    #[pyo3(signature = (callback, paths, start, end, limit=0, discover_changed_paths=false, strict_node_history=true, include_merged_revisions=false, revprops=None))]
    fn get_log(
        &mut self,
        callback: Bound<pyo3::PyAny>,
        paths: Option<Vec<String>>,
        start: i64,
        end: i64,
        limit: Option<usize>,
        discover_changed_paths: Option<bool>,
        strict_node_history: Option<bool>,
        include_merged_revisions: Option<bool>,
        revprops: Option<Vec<String>>,
    ) -> PyResult<()> {
        let start_rev = subvertpy_util::to_revnum_or_head(start);
        let end_rev = subvertpy_util::to_revnum_or_head(end);

        // When paths is None, pass [""] to SVN (meaning "the session root"),
        // matching the old C subvertpy behavior.
        let paths: Vec<subversion::ra::RelPath> = paths
            .unwrap_or_else(|| vec![String::new()])
            .iter()
            .map(|p| subvertpy_util::to_relpath(p))
            .collect::<PyResult<Vec<_>>>()?;
        let path_refs: Vec<&str> = paths.iter().map(|s| s.as_str()).collect();

        let revprop_strs: Option<Vec<String>> = revprops;
        let revprop_refs: Option<Vec<&str>> = revprop_strs
            .as_ref()
            .map(|v| v.iter().map(|s| s.as_str()).collect());

        let py_callback = callback.unbind();
        let py_error = std::cell::RefCell::new(None::<PyErr>);
        let mut log_receiver = |log_entry: &subversion::LogEntry| -> Result<(), subversion::Error> {
            Python::attach(|py| {
                let args = log_entry_to_py(py, log_entry)
                    .map_err(|e| subversion::Error::from_message(&format!("{}", e)))?;
                let args_bound = args.bind(py);
                let args_tuple = args_bound
                    .cast::<pyo3::types::PyTuple>()
                    .map_err(|e| subversion::Error::from_message(&format!("{}", e)))?;

                match py_callback.bind(py).call1(args_tuple) {
                    Ok(_) => Ok(()),
                    Err(e) => {
                        *py_error.borrow_mut() = Some(e);
                        Err(subversion::Error::from_message("Operation cancelled"))
                    }
                }
            })
        };

        let options = subversion::ra::GetLogOptions {
            limit: limit.unwrap_or(0),
            discover_changed_paths: discover_changed_paths.unwrap_or(false),
            strict_node_history: strict_node_history.unwrap_or(true),
            include_merged_revisions: include_merged_revisions.unwrap_or(false),
            revprops: revprop_refs.as_deref(),
        };
        let result =
            self.session
                .get_log(&path_refs, start_rev, end_rev, &options, &mut log_receiver);

        if let Some(err) = py_error.borrow_mut().take() {
            return Err(err);
        }

        result.map_err(|e| svn_err_to_py(e))?;

        Ok(())
    }

    /// Iterator version of get_log - returns an iterator that yields log entries
    #[pyo3(signature = (paths, start, end, limit=0, discover_changed_paths=false, strict_node_history=true, include_merged_revisions=false, revprops=None))]
    fn iter_log(
        slf: Bound<'_, Self>,
        paths: Option<Vec<String>>,
        start: i64,
        end: i64,
        limit: Option<usize>,
        discover_changed_paths: Option<bool>,
        strict_node_history: Option<bool>,
        include_merged_revisions: Option<bool>,
        revprops: Option<Vec<String>>,
    ) -> PyResult<Py<LogIterator>> {
        let py = slf.py();
        let session_ref = slf.clone().unbind();

        let start_rev = subvertpy_util::to_revnum_or_head(start);
        let end_rev = subvertpy_util::to_revnum_or_head(end);

        // When paths is None, pass [""] to SVN (meaning "the session root"),
        // matching the old C subvertpy behavior.
        let paths: Vec<subversion::ra::RelPath> = paths
            .unwrap_or_else(|| vec![String::new()])
            .iter()
            .map(|p| subvertpy_util::to_relpath(p))
            .collect::<PyResult<Vec<_>>>()?;
        let path_refs: Vec<&str> = paths.iter().map(|s| s.as_str()).collect();

        let revprop_strs: Option<Vec<String>> = revprops;
        let revprop_refs: Option<Vec<&str>> = revprop_strs
            .as_ref()
            .map(|v| v.iter().map(|s| s.as_str()).collect());

        let options = subversion::ra::GetLogOptions {
            limit: limit.unwrap_or(0),
            discover_changed_paths: discover_changed_paths.unwrap_or(false),
            strict_node_history: strict_node_history.unwrap_or(true),
            include_merged_revisions: include_merged_revisions.unwrap_or(false),
            revprops: revprop_refs.as_deref(),
        };

        let (sender, receiver) = mpsc::channel();

        let mut binding = slf.borrow_mut();
        let iter = binding
            .session
            .iter_logs(&path_refs, start_rev, end_rev, &options);

        for result in iter {
            match result {
                Ok(entry) => {
                    let py_entry = log_entry_to_py(py, &entry)?;
                    let _ = sender.send(Ok(py_entry));
                }
                Err(e) => {
                    let _ = sender.send(Err(svn_err_to_py(e)));
                    break;
                }
            }
        }

        drop(binding);
        drop(sender);

        let iterator = LogIterator {
            receiver,
            _session: session_ref,
        };

        Py::new(py, iterator)
    }

    /// Get locations for a path across revisions
    fn get_locations(
        &mut self,
        path: &str,
        peg_revision: i64,
        location_revisions: Vec<i64>,
    ) -> PyResult<pyo3::Py<pyo3::PyAny>> {
        let path = subvertpy_util::to_relpath(path)?;
        let peg_rev = subvertpy_util::to_revnum_or_head(peg_revision);

        let mut revnums = Vec::new();
        for revnum in location_revisions {
            let rev = subvertpy_util::to_revnum_or_head(revnum);
            revnums.push(rev);
        }

        let locations = self
            .session
            .get_locations(path.as_str(), peg_rev, &revnums)
            .map_err(|e| svn_err_to_py(e))?;

        Python::attach(|py| {
            let locations_dict = PyDict::new(py);
            for (rev, path) in locations {
                locations_dict.set_item(rev.as_u64() as i64, path)?;
            }
            Ok(locations_dict.into_any().unbind())
        })
    }

    /// Get location segments for a path
    fn get_location_segments(
        &mut self,
        path: &str,
        peg_revision: i64,
        start_revision: i64,
        end_revision: i64,
        receiver: Bound<pyo3::PyAny>,
    ) -> PyResult<()> {
        let path = subvertpy_util::to_relpath(path)?;
        let peg_rev = subvertpy_util::to_revnum_or_head(peg_revision);
        let start_rev = subvertpy_util::to_revnum_or_head(start_revision);
        let end_rev = subvertpy_util::to_revnum_or_head(end_revision);

        let py_receiver = receiver.clone();
        let location_receiver =
            |segment: &subversion::LocationSegment| -> Result<(), subversion::Error> {
                Python::attach(|py| {
                    let range = segment.range();
                    let args = (
                        range.start.as_u64() as i64,
                        range.end.as_u64() as i64,
                        segment.path(),
                    )
                        .into_pyobject(py)
                        .map_err(|e| {
                            subversion::Error::from_message(&format!(
                                "Failed to convert segment: {}",
                                e
                            ))
                        })?;

                    py_receiver.call1(&args).map_err(|e| {
                        subversion::Error::from_message(&format!("Python callback error: {}", e))
                    })?;

                    Ok(())
                })
            };

        self.session
            .get_location_segments(
                path.as_str(),
                peg_rev,
                start_rev,
                end_rev,
                &location_receiver,
            )
            .map_err(|e| svn_err_to_py(e))?;

        Ok(())
    }

    /// Get file revisions
    #[pyo3(signature = (path, start, end, handler, include_merged_revisions=false))]
    fn get_file_revs(
        &mut self,
        path: &str,
        start: i64,
        end: i64,
        handler: Bound<pyo3::PyAny>,
        include_merged_revisions: Option<bool>,
    ) -> PyResult<()> {
        let path = subvertpy_util::to_relpath(path)?;
        let start_rev = subvertpy_util::to_revnum_or_head(start);
        let end_rev = subvertpy_util::to_revnum_or_head(end);

        let py_handler = handler.clone();
        let file_rev_callback = |path: &str,
                                 rev: subversion::Revnum,
                                 rev_props: &std::collections::HashMap<String, Vec<u8>>,
                                 result_of_merge: bool,
                                 _old_path_rev: Option<(&str, subversion::Revnum)>,
                                 _new_path_rev: Option<(&str, subversion::Revnum)>,
                                 _prop_diffs: &std::collections::HashMap<String, Vec<u8>>|
         -> Result<(), subversion::Error> {
            Python::attach(|py| {
                let py_rev_props = subvertpy_util::properties::props_to_py_dict(py, rev_props)
                    .map_err(|e| {
                        subversion::Error::from_message(&format!("Failed to convert props: {}", e))
                    })?;

                let args = (
                    path,
                    rev.as_u64() as i64,
                    py_rev_props.into_any(),
                    result_of_merge,
                )
                    .into_pyobject(py)
                    .map_err(|e| {
                        subversion::Error::from_message(&format!("Failed to convert args: {}", e))
                    })?;

                py_handler.call1(&args).map_err(|e| {
                    subversion::Error::from_message(&format!("Python callback error: {}", e))
                })?;

                Ok(())
            })
        };

        self.session
            .get_file_revs(
                path.as_str(),
                start_rev,
                end_rev,
                include_merged_revisions.unwrap_or(false),
                file_rev_callback,
            )
            .map_err(|e| svn_err_to_py(e))?;

        Ok(())
    }

    fn __repr__(&mut self) -> PyResult<String> {
        let url = self.get_session_url()?;
        Ok(format!("RemoteAccess(\"{}\")", url))
    }

    /// Get a commit editor
    #[pyo3(signature = (revprops, callback=None, lock_tokens=None, keep_locks=false))]
    fn get_commit_editor(
        slf: Bound<'_, Self>,
        revprops: std::collections::HashMap<String, Bound<pyo3::PyAny>>,
        callback: Option<Bound<pyo3::PyAny>>,
        lock_tokens: Option<std::collections::HashMap<String, String>>,
        keep_locks: bool,
    ) -> PyResult<subvertpy_util::editor::PyEditor> {
        {
            let session = slf.borrow();
            session.check_busy()?;
            session.set_busy(true);
        }

        let mut revprop_table: std::collections::HashMap<String, Vec<u8>> =
            std::collections::HashMap::new();
        for (k, v) in revprops {
            let bytes = if let Ok(b) = v.cast::<pyo3::types::PyBytes>() {
                b.as_bytes().to_vec()
            } else if let Ok(s) = v.extract::<String>() {
                s.into_bytes()
            } else {
                return Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                    "revprops values must be str or bytes",
                ));
            };
            revprop_table.insert(k, bytes);
        }

        let lock_tokens = lock_tokens.unwrap_or_default();

        let callback_obj = callback.map(|c| c.unbind());

        let commit_callback = Box::new(
            move |info: &subversion::CommitInfo| -> Result<(), subversion::Error> {
                if let Some(ref cb) = callback_obj {
                    Python::attach(|py| {
                        let rev = info.revision().as_u64() as i64;
                        let date = info.date();
                        let author = info.author();
                        let _ = cb.call1(py, (rev, date, author));
                    });
                }
                Ok(())
            },
        );

        // Convert to raw pointer so we can reclaim ownership in on_close
        let commit_callback_ptr = Box::into_raw(commit_callback);
        // SAFETY: we reclaim this pointer in on_close below
        let commit_callback_ref: &'static mut _ = unsafe { &mut *commit_callback_ptr };

        // SAFETY: `slf` is kept alive via PyEditor._parent
        let session_ptr = &mut slf.borrow_mut().session as *mut subversion::ra::Session<'static>;
        let editor = unsafe {
            (*session_ptr)
                .get_commit_editor(revprop_table, commit_callback_ref, lock_tokens, keep_locks)
                .map_err(|e| svn_err_to_py(e))?
        };

        let session_py: Py<RemoteAccess> = slf.clone().unbind();
        let session_parent = slf.clone().unbind().into_any();
        let mut py_editor =
            subvertpy_util::editor::PyEditor::new_with_parent(editor, session_parent);

        py_editor.set_on_close(move || {
            // SAFETY: reclaim the commit callback allocated above
            unsafe { drop(Box::from_raw(commit_callback_ptr)) };
            Python::attach(|py| {
                session_py.borrow(py).set_busy(false);
            });
        });

        Ok(py_editor)
    }

    /// Perform a diff operation using a Python editor
    #[pyo3(signature = (revision, diff_target, versus_url, diff_editor, recurse=true, ignore_ancestry=false, text_deltas=false))]
    fn do_diff(
        slf: Bound<Self>,
        revision: i64,
        diff_target: &str,
        versus_url: &str,
        diff_editor: Py<PyAny>,
        recurse: bool,
        ignore_ancestry: bool,
        text_deltas: bool,
    ) -> PyResult<crate::reporter::Reporter> {
        let rev = subvertpy_util::to_revnum_or_head(revision);
        let diff_target = subvertpy_util::to_relpath(diff_target)?;

        let py_editor = crate::py_editor::PyEditorWrapper::new(diff_editor);
        let wrap_editor = py_editor.into_wrap_editor();

        let boxed_editor = Box::new(wrap_editor);
        let editor_ptr: *mut subversion::delta::WrapEditor = Box::into_raw(boxed_editor);

        // SAFETY: We just created this pointer and will keep it alive in Reporter
        let reporter = unsafe {
            let editor_ref = &mut *editor_ptr;
            let depth = if recurse {
                subversion::Depth::Infinity
            } else {
                subversion::Depth::Files
            };

            let mut options = subversion::ra::DoDiffOptions::new(versus_url, editor_ref);
            options.depth = depth;
            options.ignore_ancestry = ignore_ancestry;
            options.text_deltas = text_deltas;

            let session_ptr =
                &mut slf.borrow_mut().session as *mut subversion::ra::Session<'static>;
            let raw_reporter = (*session_ptr)
                .do_diff(rev, diff_target.as_str(), &mut options)
                .map_err(|e| svn_err_to_py(e))?;

            // Transmute the reporter's lifetime from 's to 'static
            // SAFETY: The reporter's actual lifetime dependencies are:
            // 1. Session - we keep alive via Reporter._session
            // 2. Editor - we keep alive via Reporter._editor
            // 3. versus_url - only used during do_diff call, SVN copies it
            std::mem::transmute::<
                Box<dyn subversion::ra::Reporter + Send>,
                Box<dyn subversion::ra::Reporter + Send + 'static>,
            >(raw_reporter)
        };

        // SAFETY: Convert the raw pointer back to Box with 'static lifetime
        // This is safe because:
        // 1. We store the box in Reporter._editor to keep it alive
        // 2. The C pointers in reporter point to this memory
        // 3. When Reporter is dropped, the editor is dropped, cleaning up properly
        let boxed_editor_static: Box<subversion::delta::WrapEditor<'static>> =
            unsafe { Box::from_raw(editor_ptr as *mut subversion::delta::WrapEditor<'static>) };

        Ok(crate::reporter::Reporter::new_with_session_and_editor(
            reporter,
            slf.unbind().into_any(),
            boxed_editor_static,
        ))
    }

    /// Perform an update operation using a Python editor
    #[pyo3(signature = (revision, update_target, recurse, update_editor, send_copyfrom_args=false, ignore_ancestry=false))]
    fn do_update(
        slf: Bound<Self>,
        revision: i64,
        update_target: &str,
        recurse: bool,
        update_editor: Py<PyAny>,
        send_copyfrom_args: bool,
        ignore_ancestry: bool,
    ) -> PyResult<crate::reporter::Reporter> {
        let rev = subvertpy_util::to_revnum_or_head(revision);
        let update_target = subvertpy_util::to_relpath(update_target)?;

        let py_editor = crate::py_editor::PyEditorWrapper::new(update_editor);
        let wrap_editor = py_editor.into_wrap_editor();

        let boxed_editor = Box::new(wrap_editor);
        let editor_ptr: *mut subversion::delta::WrapEditor = Box::into_raw(boxed_editor);

        let depth = if recurse {
            subversion::Depth::Infinity
        } else {
            subversion::Depth::Files
        };

        let reporter = unsafe {
            let editor_ref = &mut *editor_ptr;

            let session_ptr =
                &mut slf.borrow_mut().session as *mut subversion::ra::Session<'static>;
            let raw_reporter = (*session_ptr)
                .do_update(
                    rev,
                    update_target.as_str(),
                    depth,
                    send_copyfrom_args,
                    ignore_ancestry,
                    editor_ref,
                )
                .map_err(|e| svn_err_to_py(e))?;

            std::mem::transmute::<
                Box<dyn subversion::ra::Reporter + Send>,
                Box<dyn subversion::ra::Reporter + Send + 'static>,
            >(raw_reporter)
        };

        let boxed_editor_static: Box<subversion::delta::WrapEditor<'static>> =
            unsafe { Box::from_raw(editor_ptr as *mut subversion::delta::WrapEditor<'static>) };

        Ok(crate::reporter::Reporter::new_with_session_and_editor(
            reporter,
            slf.unbind().into_any(),
            boxed_editor_static,
        ))
    }

    /// Perform a switch operation using a Python editor
    #[pyo3(signature = (revision, switch_target, recurse, switch_url, switch_editor, send_copyfrom_args=false, ignore_ancestry=false))]
    fn do_switch(
        slf: Bound<Self>,
        revision: i64,
        switch_target: &str,
        recurse: bool,
        switch_url: &str,
        switch_editor: Py<PyAny>,
        send_copyfrom_args: bool,
        ignore_ancestry: bool,
    ) -> PyResult<crate::reporter::Reporter> {
        let rev = subvertpy_util::to_revnum_or_head(revision);
        let switch_target = subvertpy_util::to_relpath(switch_target)?;

        let py_editor = crate::py_editor::PyEditorWrapper::new(switch_editor);
        let wrap_editor = py_editor.into_wrap_editor();

        let boxed_editor = Box::new(wrap_editor);
        let editor_ptr: *mut subversion::delta::WrapEditor = Box::into_raw(boxed_editor);

        let depth = if recurse {
            subversion::Depth::Infinity
        } else {
            subversion::Depth::Files
        };

        let reporter = unsafe {
            let editor_ref = &mut *editor_ptr;

            let session_ptr =
                &mut slf.borrow_mut().session as *mut subversion::ra::Session<'static>;
            let raw_reporter = (*session_ptr)
                .do_switch(
                    rev,
                    switch_target.as_str(),
                    depth,
                    switch_url,
                    send_copyfrom_args,
                    ignore_ancestry,
                    editor_ref,
                )
                .map_err(|e| svn_err_to_py(e))?;

            std::mem::transmute::<
                Box<dyn subversion::ra::Reporter + Send>,
                Box<dyn subversion::ra::Reporter + Send + 'static>,
            >(raw_reporter)
        };

        let boxed_editor_static: Box<subversion::delta::WrapEditor<'static>> =
            unsafe { Box::from_raw(editor_ptr as *mut subversion::delta::WrapEditor<'static>) };

        Ok(crate::reporter::Reporter::new_with_session_and_editor(
            reporter,
            slf.unbind().into_any(),
            boxed_editor_static,
        ))
    }

    /// Replay a revision using a Python editor
    #[pyo3(signature = (revision, low_water_mark, editor, send_deltas=true))]
    fn replay(
        slf: Bound<Self>,
        revision: i64,
        low_water_mark: i64,
        editor: Py<PyAny>,
        send_deltas: bool,
    ) -> PyResult<()> {
        let rev = subvertpy_util::to_revnum_or_head(revision);
        let lwm = subvertpy_util::to_revnum_or_head(low_water_mark);

        let py_editor = crate::py_editor::PyEditorWrapper::new(editor);
        let mut wrap_editor = py_editor.into_wrap_editor();

        let session_ptr = &mut slf.borrow_mut().session as *mut subversion::ra::Session<'static>;
        unsafe {
            (*session_ptr)
                .replay(rev, lwm, send_deltas, &mut wrap_editor)
                .map_err(|e| svn_err_to_py(e))?;
        }

        Ok(())
    }

    /// Replay a range of revisions
    #[pyo3(signature = (start_revision, end_revision, low_water_mark, cbs, send_deltas=true))]
    fn replay_range(
        slf: Bound<Self>,
        start_revision: i64,
        end_revision: i64,
        low_water_mark: i64,
        cbs: Bound<pyo3::types::PyTuple>,
        send_deltas: bool,
    ) -> PyResult<()> {
        let start_rev = subvertpy_util::to_revnum_or_head(start_revision);
        let end_rev = subvertpy_util::to_revnum_or_head(end_revision);
        let lwm = subvertpy_util::to_revnum_or_head(low_water_mark);

        if cbs.len() != 2 {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "cbs must be a tuple of (revstart_cb, revfinish_cb)",
            ));
        }

        let revstart_cb = cbs.get_item(0)?.unbind();
        let revfinish_cb = cbs.get_item(1)?.unbind();

        let revstart = move |rev: subversion::Revnum,
                             rev_props: &std::collections::HashMap<String, Vec<u8>>|
              -> Result<
            subversion::delta::WrapEditor<'static>,
            subversion::Error<'static>,
        > {
            Python::attach(|py| {
                let py_rev = rev.as_u64() as i64;
                let py_revprops = subvertpy_util::properties::props_to_py_dict(py, rev_props)
                    .map_err(|e| {
                        subversion::Error::from_message(&format!("Failed to convert: {}", e))
                    })?;

                let result = revstart_cb
                    .call1(py, (py_rev, py_revprops.into_any()))
                    .map_err(|e| {
                        subversion::Error::from_message(&format!("Python callback error: {}", e))
                    })?;

                let py_editor_wrapper = crate::py_editor::PyEditorWrapper::new(result);
                Ok(py_editor_wrapper.into_wrap_editor())
            })
        };

        let revfinish = move |rev: subversion::Revnum,
                              rev_props: &std::collections::HashMap<String, Vec<u8>>,
                              _editor: &mut subversion::delta::WrapEditor<'static>|
              -> Result<(), subversion::Error<'static>> {
            Python::attach(|py| {
                let py_rev = rev.as_u64() as i64;
                let py_revprops = subvertpy_util::properties::props_to_py_dict(py, rev_props)
                    .map_err(|e| {
                        subversion::Error::from_message(&format!("Failed to convert: {}", e))
                    })?;

                // The original C API passes the editor back to revfinish_cb,
                // but we pass py.None() since the Python callback already has
                // a reference to the editor object it returned from revstart_cb
                revfinish_cb
                    .call1(py, (py_rev, py_revprops.into_any(), py.None()))
                    .map_err(|e| {
                        subversion::Error::from_message(&format!("Python callback error: {}", e))
                    })?;

                Ok(())
            })
        };

        let session_ptr = &mut slf.borrow_mut().session as *mut subversion::ra::Session<'static>;
        unsafe {
            (*session_ptr)
                .replay_range(start_rev, end_rev, lwm, send_deltas, revstart, revfinish)
                .map_err(|e| svn_err_to_py(e))?;
        }

        Ok(())
    }

    /// Get mergeinfo for paths
    #[pyo3(signature = (paths, revision=None, inherit=None, include_descendants=false))]
    fn mergeinfo(
        &mut self,
        paths: Vec<String>,
        revision: Option<i64>,
        inherit: Option<i32>,
        include_descendants: bool,
    ) -> PyResult<Option<pyo3::Py<pyo3::PyAny>>> {
        let rev = match revision {
            Some(r) => subvertpy_util::to_revnum_or_head(r),
            None => self
                .session
                .get_latest_revnum()
                .map_err(|e| svn_err_to_py(e))?,
        };

        let inheritance = match inherit {
            Some(0) => subversion::mergeinfo::MergeinfoInheritance::Explicit,
            Some(1) => subversion::mergeinfo::MergeinfoInheritance::Inherited,
            Some(2) => subversion::mergeinfo::MergeinfoInheritance::NearestAncestor,
            None => subversion::mergeinfo::MergeinfoInheritance::Explicit,
            Some(v) => {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                    "Invalid mergeinfo inheritance value: {}",
                    v
                )));
            }
        };

        let path_refs: Vec<&str> = paths.iter().map(|s| s.as_str()).collect();

        let result = self
            .session
            .get_mergeinfo(&path_refs, rev, inheritance, include_descendants)
            .map_err(|e| svn_err_to_py(e))?;

        if result.is_empty() {
            return Ok(None);
        }

        Python::attach(|py| {
            let dict = PyDict::new(py);
            for (path, mergeinfo) in &result {
                let mi_str = mergeinfo.to_string().map_err(|e| svn_err_to_py(e))?;
                dict.set_item(path, mi_str)?;
            }
            Ok(Some(dict.into_any().unbind()))
        })
    }

    /// Set the progress callback function
    #[setter]
    fn set_progress_func(&mut self, _callback: Bound<pyo3::PyAny>) -> PyResult<()> {
        // The progress_func needs to be set on the Callbacks object before session creation.
        // Since the session is already created, we cannot easily set it retroactively
        // in the current architecture. Accept the setter silently for compatibility.
        Ok(())
    }
}
