//! Client context implementation

use pyo3::prelude::*;
use std::sync::mpsc::{self, Receiver};

/// Parse a revision from Python - can be a string ("HEAD", "BASE", etc.) or integer
fn parse_revision(_py: Python, rev: &Bound<PyAny>) -> PyResult<subversion::Revision> {
    if let Ok(s) = rev.extract::<String>() {
        match s.to_uppercase().as_str() {
            "HEAD" => Ok(subversion::Revision::Head),
            "BASE" => Ok(subversion::Revision::Base),
            "WORKING" => Ok(subversion::Revision::Working),
            "COMMITTED" => Ok(subversion::Revision::Committed),
            "PREV" => Ok(subversion::Revision::Previous),
            _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Invalid revision string: {}",
                s
            ))),
        }
    } else if let Ok(n) = rev.extract::<i64>() {
        let revnum = subvertpy_util::to_revnum(n).ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>("Invalid revision number")
        })?;
        Ok(subversion::Revision::Number(revnum))
    } else {
        Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
            "Revision must be a string or integer",
        ))
    }
}

/// Iterator for client log entries
#[pyclass(name = "ClientLogIterator", unsendable)]
pub struct ClientLogIterator {
    receiver: Receiver<PyResult<Py<PyAny>>>,
}

#[pymethods]
impl ClientLogIterator {
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

/// Subversion client context
#[pyclass(name = "Client", unsendable)]
pub struct Client {
    ctx: subversion::client::Context,
    #[pyo3(get, set)]
    auth: Option<Py<PyAny>>,
    #[pyo3(get, set)]
    log_msg_func: Option<Py<PyAny>>,
    #[pyo3(get, set)]
    notify_func: Option<Py<PyAny>>,
    config: Option<Py<PyAny>>,
}

#[pymethods]
impl Client {
    /// Create a new client context
    #[new]
    #[pyo3(signature = (auth=None, config_dir=None, log_msg_func=None, notify_func=None))]
    fn init(
        auth: Option<Bound<PyAny>>,
        config_dir: Option<&str>,
        log_msg_func: Option<Bound<PyAny>>,
        notify_func: Option<Bound<PyAny>>,
    ) -> PyResult<Self> {
        let config_dir_path = config_dir.map(std::path::Path::new);
        let mut ctx = subversion::client::Context::with_config_dir(config_dir_path)
            .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;

        let auth_py = if let Some(ref auth_obj) = auth {
            subvertpy_util::auth::with_baton_from_py(auth_obj, |baton| {
                // Safety: the Auth Python object is kept alive via auth_py below,
                // so the baton pointer remains valid for the lifetime of the Client.
                unsafe { ctx.set_auth_unchecked(baton) };
            })?;
            Some(auth_obj.clone().unbind())
        } else {
            None
        };

        let log_msg_func_py = log_msg_func.map(|f| f.unbind());
        let notify_func_py = notify_func.map(|f| f.unbind());

        Ok(Self {
            ctx,
            auth: auth_py,
            log_msg_func: log_msg_func_py,
            notify_func: notify_func_py,
            config: None,
        })
    }

    fn __repr__(&self) -> PyResult<String> {
        Ok("<Client>".to_string())
    }

    #[getter]
    fn get_config(&self, py: Python) -> Option<Py<PyAny>> {
        self.config.as_ref().map(|c| c.clone_ref(py))
    }

    #[setter]
    fn set_config(&mut self, py: Python, value: Option<Py<PyAny>>) -> PyResult<()> {
        if let Some(ref config_obj) = value {
            let bound = config_obj.bind(py);
            if let Ok(config) = bound.cast::<super::config::Config>() {
                let config_hash = config
                    .borrow()
                    .get_config_hash()
                    .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;
                self.ctx.set_config(config_hash);
            }
        }
        self.config = value;
        Ok(())
    }

    /// Checkout a working copy from a repository
    #[pyo3(signature = (url, path, rev=None, peg_rev=None, recurse=true, ignore_externals=false, allow_unver_obstructions=false))]
    fn checkout(
        &mut self,
        py: Python,
        url: &str,
        path: &str,
        rev: Option<Bound<PyAny>>,
        peg_rev: Option<Bound<PyAny>>,
        recurse: bool,
        ignore_externals: bool,
        allow_unver_obstructions: bool,
    ) -> PyResult<i64> {
        let revision = if let Some(r) = rev {
            parse_revision(py, &r)?
        } else {
            subversion::Revision::Head
        };

        let peg_revision = if let Some(r) = peg_rev {
            parse_revision(py, &r)?
        } else {
            subversion::Revision::Head
        };

        let depth = if recurse {
            subversion::Depth::Infinity
        } else {
            subversion::Depth::Files
        };

        let options = subversion::client::CheckoutOptions {
            peg_revision,
            revision,
            depth,
            ignore_externals,
            allow_unver_obstructions,
        };

        let result_rev = self
            .ctx
            .checkout(url, path, &options)
            .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;

        Ok(result_rev.as_u64() as i64)
    }

    /// Update a working copy
    #[pyo3(signature = (path, rev=None, recurse=true, ignore_externals=false, depth_is_sticky=false, allow_unver_obstructions=false, adds_as_modification=false, make_parents=false))]
    fn update(
        &mut self,
        py: Python,
        path: Bound<PyAny>,
        rev: Option<Bound<PyAny>>,
        recurse: bool,
        ignore_externals: bool,
        depth_is_sticky: bool,
        allow_unver_obstructions: bool,
        adds_as_modification: bool,
        make_parents: bool,
    ) -> PyResult<Vec<i64>> {
        let paths_vec: Vec<String> = if let Ok(s) = path.extract::<String>() {
            vec![s]
        } else if let Ok(v) = path.extract::<Vec<String>>() {
            v
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                "path must be a string or list of strings",
            ));
        };

        let revision = if let Some(r) = rev {
            parse_revision(py, &r)?
        } else {
            subversion::Revision::Head
        };

        let depth = if recurse {
            subversion::Depth::Infinity
        } else {
            subversion::Depth::Files
        };

        let options = subversion::client::UpdateOptions {
            depth,
            depth_is_sticky,
            ignore_externals,
            allow_unver_obstructions,
            adds_as_modifications: adds_as_modification,
            make_parents,
        };

        let path_refs: Vec<&str> = paths_vec.iter().map(|s| s.as_str()).collect();
        let result_revs = self
            .ctx
            .update(&path_refs, revision, &options)
            .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;

        Ok(result_revs.iter().map(|r| r.as_u64() as i64).collect())
    }

    /// Add a file or directory to version control
    #[pyo3(signature = (path, recursive=true, force=false, no_ignore=false, add_parents=false, no_autoprops=false, depth=None))]
    fn add(
        &mut self,
        py: Python,
        path: &str,
        recursive: bool,
        force: bool,
        no_ignore: bool,
        add_parents: bool,
        no_autoprops: bool,
        depth: Option<Bound<PyAny>>,
    ) -> PyResult<()> {
        let svn_depth = if let Some(d) = depth {
            parse_depth(py, &d)?
        } else if recursive {
            subversion::Depth::Infinity
        } else {
            subversion::Depth::Empty
        };

        let options = subversion::client::AddOptions {
            depth: svn_depth,
            force,
            no_ignore,
            no_autoprops,
            add_parents,
        };

        self.ctx
            .add(path, &options)
            .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;

        Ok(())
    }

    /// Delete files or directories
    #[pyo3(signature = (paths, force=false, keep_local=false, revprops=None, callback=None))]
    fn delete(
        &mut self,
        paths: Vec<String>,
        force: bool,
        keep_local: bool,
        revprops: Option<Bound<PyAny>>,
        callback: Option<Bound<PyAny>>,
    ) -> PyResult<()> {
        let path_refs: Vec<&str> = paths.iter().map(|s| s.as_str()).collect();

        let revprop_map = build_string_revprop_map(revprops.as_ref())?;

        let callback_py = callback.map(|cb| cb.unbind());
        let mut commit_callback_fn =
            |info: &subversion::CommitInfo| -> Result<(), subversion::Error> {
                if let Some(ref cb) = callback_py {
                    Python::attach(|py| {
                        let cb_bound = cb.bind(py);
                        let rev = info.revision().as_u64() as i64;
                        let date = info.date().map(|s| s.to_string());
                        let author = info.author().map(|s| s.to_string());
                        cb_bound
                            .call1((rev, date.as_deref(), author.as_deref()))
                            .map_err(|e| {
                                subversion::Error::from_message(&format!("Callback failed: {}", e))
                            })?;
                        Ok(())
                    })
                } else {
                    Ok(())
                }
            };

        let mut options = subversion::client::DeleteOptions {
            force,
            keep_local,
            commit_callback: if callback_py.is_some() {
                Some(&mut commit_callback_fn)
            } else {
                None
            },
        };

        let revprop_refs: std::collections::HashMap<&str, &str> = revprop_map
            .iter()
            .map(|(k, v)| (k.as_str(), v.as_str()))
            .collect();

        self.ctx
            .delete(&path_refs, revprop_refs, &mut options)
            .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;

        Ok(())
    }

    /// Commit changes to the repository
    #[pyo3(signature = (targets, recurse=true, keep_locks=true, keep_changelist=false, commit_as_operations=false, include_file_externals=false, include_dir_externals=false, revprops=None, callback=None))]
    fn commit(
        &mut self,
        targets: Vec<String>,
        recurse: bool,
        keep_locks: bool,
        keep_changelist: bool,
        commit_as_operations: bool,
        include_file_externals: bool,
        include_dir_externals: bool,
        revprops: Option<Bound<pyo3::PyAny>>,
        callback: Option<Bound<pyo3::PyAny>>,
    ) -> PyResult<Option<(i64, Option<String>, Option<String>)>> {
        let target_refs: Vec<&str> = targets.iter().map(|s| s.as_str()).collect();

        let depth = if recurse {
            subversion::Depth::Infinity
        } else {
            subversion::Depth::Empty
        };

        let options = subversion::client::CommitOptions {
            depth,
            keep_locks,
            keep_changelists: keep_changelist,
            changelists: None,
            commit_as_operations,
            include_file_externals,
            include_dir_externals,
        };

        let mut revprop_strings = std::collections::HashMap::new();

        if let Some(ref rp) = revprops {
            if let Ok(dict) = rp.cast::<pyo3::types::PyDict>() {
                for (key, value) in dict.iter() {
                    let k = key.extract::<String>()?;
                    let v = if let Ok(s) = value.extract::<String>() {
                        s
                    } else if let Ok(b) = value.extract::<&[u8]>() {
                        String::from_utf8(b.to_vec()).map_err(|_| {
                            PyErr::new::<pyo3::exceptions::PyValueError, _>(
                                "Revprop value is not valid UTF-8",
                            )
                        })?
                    } else {
                        return Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                            "Revprop values must be string or bytes",
                        ));
                    };
                    if k != "svn:log" {
                        revprop_strings.insert(k, v);
                    }
                }
            }
        }

        let revprop_map: std::collections::HashMap<&str, &str> = revprop_strings
            .iter()
            .map(|(k, v)| (k.as_str(), v.as_str()))
            .collect();

        let mut commit_rev = None;
        let mut commit_date = None;
        let mut commit_author = None;

        let log_msg_from_revprops = revprops
            .as_ref()
            .and_then(|rp| rp.cast::<pyo3::types::PyDict>().ok())
            .and_then(|dict| dict.get_item("svn:log").ok())
            .flatten()
            .and_then(|item| {
                // Try string first, then bytes
                if let Ok(s) = item.extract::<String>() {
                    Some(s)
                } else if let Ok(b) = item.extract::<&[u8]>() {
                    String::from_utf8(b.to_vec()).ok()
                } else {
                    None
                }
            });

        let mut log_msg_func_wrapper =
            |_items: &[subversion::client::CommitItem]| -> Result<String, subversion::Error> {
                if let Some(ref msg) = log_msg_from_revprops {
                    return Ok(msg.clone());
                }

                if let Some(ref log_msg_func) = self.log_msg_func {
                    Python::attach(|py| {
                        let log_msg_func_bound = log_msg_func.bind(py);
                        let commit_info = pyo3::types::PyDict::new(py);
                        let result = log_msg_func_bound.call1((commit_info,)).map_err(|e| {
                            subversion::Error::from_message(&format!(
                                "Log message callback failed: {}",
                                e
                            ))
                        })?;

                        let msg = if let Ok(s) = result.extract::<String>() {
                            s
                        } else if let Ok(b) = result.extract::<&[u8]>() {
                            String::from_utf8(b.to_vec()).map_err(|e| {
                                subversion::Error::from_message(&format!(
                                    "Log message contains invalid UTF-8: {}",
                                    e
                                ))
                            })?
                        } else {
                            return Err(subversion::Error::from_message(
                                "Log message callback must return string or bytes",
                            ));
                        };
                        Ok(msg)
                    })
                } else {
                    Err(subversion::Error::from_message("No log message provided"))
                }
            };

        let mut commit_callback = |info: &subversion::CommitInfo| -> Result<(), subversion::Error> {
            commit_rev = Some(info.revision());
            commit_date = info.date().map(|s| s.to_string());
            commit_author = info.author().map(|s| s.to_string());
            Ok(())
        };

        let result = self.ctx.commit(
            &target_refs,
            &options,
            revprop_map,
            Some(&mut log_msg_func_wrapper),
            &mut commit_callback,
        );

        result.map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;

        let rev = commit_rev.map(|r| r.as_u64() as i64).unwrap_or(-1);
        let info = (rev, commit_date, commit_author);
        if let Some(cb) = callback {
            cb.call1((info.0, info.1.as_deref(), info.2.as_deref()))?;
            Ok(None)
        } else {
            Ok(Some(info))
        }
    }

    /// Get log messages
    #[pyo3(signature = (callback, path, start_rev=None, end_rev=None, discover_changed_paths=false, strict_node_history=false, limit=0, include_merged_revisions=false))]
    fn log(
        &mut self,
        py: Python,
        callback: Bound<PyAny>,
        path: &str,
        start_rev: Option<Bound<PyAny>>,
        end_rev: Option<Bound<PyAny>>,
        discover_changed_paths: bool,
        strict_node_history: bool,
        limit: i32,
        include_merged_revisions: bool,
    ) -> PyResult<()> {
        let start_revision = if let Some(r) = start_rev {
            parse_revision(py, &r)?
        } else {
            subversion::Revision::Head
        };
        let end_revision = if let Some(r) = end_rev {
            parse_revision(py, &r)?
        } else {
            subversion::Revision::Number(subvertpy_util::to_revnum(1).unwrap())
        };

        let revision_ranges = vec![subversion::RevisionRange {
            start: start_revision,
            end: end_revision,
        }];

        let options = subversion::client::LogOptions {
            peg_revision: subversion::Revision::Unspecified,
            discover_changed_paths,
            strict_node_history,
            include_merged_revisions,
            revprops: Some(vec![
                "svn:log".to_string(),
                "svn:author".to_string(),
                "svn:date".to_string(),
            ]),
            limit: if limit > 0 { Some(limit) } else { None },
        };

        let callback_py = callback.unbind();
        let log_receiver = |entry: &subversion::LogEntry| -> Result<(), subversion::Error> {
            Python::attach(|py| {
                let callback_bound = callback_py.bind(py);

                let changed_paths = if let Some(paths) = entry.changed_paths() {
                    let dict = pyo3::types::PyDict::new(py);
                    for (path_str, change) in paths {
                        let node_kind_str = match change.node_kind {
                            subversion::NodeKind::None => "none",
                            subversion::NodeKind::File => "file",
                            subversion::NodeKind::Dir => "dir",
                            subversion::NodeKind::Unknown => "unknown",
                            subversion::NodeKind::Symlink => "symlink",
                        };

                        let change_tuple = (
                            change.action.to_string(),
                            change.copyfrom_path.clone(),
                            change.copyfrom_rev.map(|r| r.as_u64() as i64).unwrap_or(-1),
                            node_kind_str,
                        );
                        dict.set_item(path_str, change_tuple).map_err(|e| {
                            subversion::Error::from_message(&format!(
                                "Failed to set changed path: {}",
                                e
                            ))
                        })?;
                    }
                    dict.into_any()
                } else {
                    py.None().into_bound(py)
                };

                let revprops = pyo3::types::PyDict::new(py);
                for (key, value) in entry.revprops() {
                    revprops
                        .set_item(key, pyo3::types::PyBytes::new(py, &value))
                        .map_err(|e| {
                            subversion::Error::from_message(&format!(
                                "Failed to set revprop: {}",
                                e
                            ))
                        })?;
                }

                let revision = entry.revision().map(|r| r.as_u64() as i64).unwrap_or(-1);
                callback_bound
                    .call1((changed_paths, revision, revprops, entry.has_children()))
                    .map_err(|e| {
                        subversion::Error::from_message(&format!("Log callback failed: {}", e))
                    })?;

                Ok(())
            })
        };

        self.ctx
            .log(&[path], &revision_ranges, &options, &log_receiver)
            .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;

        Ok(())
    }

    /// Iterator version of log - returns an iterator that yields log entries
    #[pyo3(signature = (path, start_rev=None, end_rev=None, discover_changed_paths=false, strict_node_history=false, limit=0, revprops=None, include_merged_revisions=false))]
    fn iter_log(
        &mut self,
        py: Python,
        path: &str,
        start_rev: Option<Bound<PyAny>>,
        end_rev: Option<Bound<PyAny>>,
        discover_changed_paths: bool,
        strict_node_history: bool,
        limit: i32,
        revprops: Option<Vec<String>>,
        include_merged_revisions: bool,
    ) -> PyResult<Py<ClientLogIterator>> {
        let start_revision = if let Some(r) = start_rev {
            parse_revision(py, &r)?
        } else {
            subversion::Revision::Head
        };
        let end_revision = if let Some(r) = end_rev {
            parse_revision(py, &r)?
        } else {
            subversion::Revision::Number(subvertpy_util::to_revnum(1).unwrap())
        };

        let revision_ranges = vec![subversion::RevisionRange {
            start: start_revision,
            end: end_revision,
        }];

        let revprop_list = revprops.unwrap_or_else(|| {
            vec![
                "svn:log".to_string(),
                "svn:author".to_string(),
                "svn:date".to_string(),
            ]
        });

        let options = subversion::client::LogOptions {
            peg_revision: subversion::Revision::Unspecified,
            discover_changed_paths,
            strict_node_history,
            include_merged_revisions,
            revprops: Some(revprop_list),
            limit: if limit > 0 { Some(limit) } else { None },
        };

        let (sender, receiver) = mpsc::channel();

        let log_receiver = |entry: &subversion::LogEntry| -> Result<(), subversion::Error> {
            Python::attach(|py| {
                let changed_paths = if let Some(paths) = entry.changed_paths() {
                    let dict = pyo3::types::PyDict::new(py);
                    for (path_str, change) in paths {
                        let node_kind_str = match change.node_kind {
                            subversion::NodeKind::None => "none",
                            subversion::NodeKind::File => "file",
                            subversion::NodeKind::Dir => "dir",
                            subversion::NodeKind::Unknown => "unknown",
                            subversion::NodeKind::Symlink => "symlink",
                        };

                        let change_tuple = (
                            change.action.to_string(),
                            change.copyfrom_path.clone(),
                            change.copyfrom_rev.map(|r| r.as_u64() as i64).unwrap_or(-1),
                            node_kind_str,
                        );
                        dict.set_item(path_str, change_tuple).map_err(|e| {
                            subversion::Error::from_message(&format!(
                                "Failed to set changed path: {}",
                                e
                            ))
                        })?;
                    }
                    dict.into_any()
                } else {
                    py.None().into_bound(py)
                };

                let revprops_dict = pyo3::types::PyDict::new(py);
                for (key, value) in entry.revprops() {
                    revprops_dict
                        .set_item(key, pyo3::types::PyBytes::new(py, &value))
                        .map_err(|e| {
                            subversion::Error::from_message(&format!(
                                "Failed to set revprop: {}",
                                e
                            ))
                        })?;
                }

                let revision = entry.revision().map(|r| r.as_u64() as i64).unwrap_or(-1);
                let has_children = entry.has_children();
                let tuple = pyo3::types::PyTuple::new(
                    py,
                    [
                        changed_paths.into_any().unbind(),
                        revision.into_pyobject(py).unwrap().into_any().unbind(),
                        revprops_dict.into_any().unbind(),
                        has_children
                            .into_pyobject(py)
                            .unwrap()
                            .to_owned()
                            .into_any()
                            .unbind(),
                    ],
                )
                .map_err(|e| {
                    subversion::Error::from_message(&format!("Failed to create tuple: {}", e))
                })?;

                let _ = sender.send(Ok(tuple.into_any().unbind()));
                Ok(())
            })
        };

        let result = self
            .ctx
            .log(&[path], &revision_ranges, &options, &log_receiver);

        if let Err(e) = result {
            let _ = sender.send(Err(subvertpy_util::error::svn_err_to_py(e)));
        }

        drop(sender);

        let iterator = ClientLogIterator { receiver };
        Py::new(py, iterator)
    }

    /// Create directory
    #[pyo3(signature = (paths, make_parents=false, revprops=None, callback=None))]
    fn mkdir(
        &mut self,
        _py: Python,
        paths: Bound<PyAny>,
        make_parents: bool,
        revprops: Option<Bound<PyAny>>,
        callback: Option<Bound<PyAny>>,
    ) -> PyResult<()> {
        let paths_vec: Vec<String> = if let Ok(s) = paths.extract::<String>() {
            vec![s]
        } else if let Ok(v) = paths.extract::<Vec<String>>() {
            v
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                "paths must be a string or list of strings",
            ));
        };
        let path_refs: Vec<&str> = paths_vec.iter().map(|s| s.as_str()).collect();
        let mut revprop_map = std::collections::HashMap::new();
        if let Some(ref rp) = revprops {
            if let Ok(dict) = rp.cast::<pyo3::types::PyDict>() {
                for (key, value) in dict.iter() {
                    let k = key.extract::<String>()?;
                    let v = if let Ok(s) = value.extract::<String>() {
                        s.into_bytes()
                    } else if let Ok(b) = value.extract::<&[u8]>() {
                        b.to_vec()
                    } else {
                        return Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                            "Revprop values must be string or bytes",
                        ));
                    };
                    revprop_map.insert(k, v);
                }
            }
        }

        let callback_py = callback.map(|cb| cb.unbind());
        let mut commit_callback_fn =
            |info: &subversion::CommitInfo| -> Result<(), subversion::Error> {
                if let Some(ref cb) = callback_py {
                    Python::attach(|py| {
                        let cb_bound = cb.bind(py);
                        let rev = info.revision().as_u64() as i64;
                        let date = info.date().map(|s| s.to_string());
                        let author = info.author().map(|s| s.to_string());
                        cb_bound
                            .call1((rev, date.as_deref(), author.as_deref()))
                            .map_err(|e| {
                                subversion::Error::from_message(&format!("Callback failed: {}", e))
                            })?;
                        Ok(())
                    })
                } else {
                    Ok(())
                }
            };

        let mut options = subversion::client::MkdirOptions {
            make_parents,
            revprop_table: if revprop_map.is_empty() {
                None
            } else {
                Some(revprop_map)
            },
            commit_callback: if callback_py.is_some() {
                Some(&mut commit_callback_fn)
            } else {
                None
            },
        };

        self.ctx
            .mkdir(&path_refs, &mut options)
            .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;

        Ok(())
    }

    /// Set property on path
    #[pyo3(signature = (propname, propval, path, recurse=false, skip_checks=false, revprops=None, base_revision_for_url=None))]
    fn propset(
        &mut self,
        propname: &str,
        propval: Option<Bound<PyAny>>,
        path: &str,
        recurse: bool,
        skip_checks: bool,
        revprops: Option<Bound<PyAny>>,
        base_revision_for_url: Option<i64>,
    ) -> PyResult<()> {
        let propval_bytes = if let Some(ref v) = propval {
            if let Ok(s) = v.extract::<String>() {
                Some(s.into_bytes())
            } else if let Ok(b) = v.extract::<&[u8]>() {
                Some(b.to_vec())
            } else {
                return Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                    "Property value must be string or bytes",
                ));
            }
        } else {
            None
        };

        let base_rev = if let Some(rev) = base_revision_for_url {
            subvertpy_util::to_revnum(rev).ok_or_else(|| {
                PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                    "Invalid revision number: {}",
                    rev
                ))
            })?
        } else {
            subversion::Revnum::invalid()
        };

        let is_url = path.contains("://");

        if is_url {
            let revprop_table = if let Some(rp) = revprops {
                let dict = rp.cast::<pyo3::types::PyDict>().map_err(|_| {
                    PyErr::new::<pyo3::exceptions::PyTypeError, _>("revprops must be a dict")
                })?;
                let mut map = std::collections::HashMap::new();
                for (k, v) in dict.iter() {
                    let key: String = k.extract()?;
                    let val: String = v.extract()?;
                    map.insert(key, val);
                }
                Some(map)
            } else {
                None
            };

            let mut options = subversion::client::PropSetRemoteOptions {
                skip_checks,
                base_revision_for_url: base_rev,
                revprop_table,
                commit_callback: None,
            };

            self.ctx
                .propset_remote(propname, propval_bytes.as_deref(), path, &mut options)
                .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;
        } else {
            let _ = revprops;

            let depth = if recurse {
                subversion::Depth::Infinity
            } else {
                subversion::Depth::Empty
            };

            let options = subversion::client::PropSetOptions {
                depth,
                skip_checks,
                base_revision_for_url: base_rev,
                changelists: None,
            };

            self.ctx
                .propset(propname, propval_bytes.as_deref(), path, &options)
                .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;
        }

        Ok(())
    }

    /// Get property value(s) from path
    #[pyo3(signature = (propname, path, revision=None, peg_revision=None, recurse=false))]
    fn propget<'py>(
        &mut self,
        py: Python<'py>,
        propname: &str,
        path: &str,
        revision: Option<Bound<PyAny>>,
        peg_revision: Option<Bound<PyAny>>,
        recurse: bool,
    ) -> PyResult<Bound<'py, pyo3::types::PyDict>> {
        let rev = if let Some(r) = revision {
            parse_revision(py, &r)?
        } else {
            subversion::Revision::Working
        };

        let peg_rev = if let Some(r) = peg_revision {
            parse_revision(py, &r)?
        } else {
            subversion::Revision::Unspecified
        };

        let depth = if recurse {
            subversion::Depth::Infinity
        } else {
            subversion::Depth::Empty
        };

        let options = subversion::client::PropGetOptions {
            peg_revision: peg_rev,
            revision: rev,
            depth,
            changelists: None,
        };

        let props = self
            .ctx
            .propget(propname, path, &options, None)
            .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;

        let result_dict = pyo3::types::PyDict::new(py);
        for (path_str, value_bytes) in props {
            result_dict.set_item(path_str, pyo3::types::PyBytes::new(py, &value_bytes))?;
        }

        Ok(result_dict)
    }

    /// List properties on a path
    #[pyo3(signature = (path, revision=None, depth=0))]
    fn proplist<'py>(
        &mut self,
        py: Python<'py>,
        path: &str,
        revision: Option<Bound<PyAny>>,
        depth: i32,
    ) -> PyResult<Vec<Py<PyAny>>> {
        let rev = if let Some(r) = revision {
            parse_revision(py, &r)?
        } else {
            subversion::Revision::Working
        };

        let svn_depth = parse_depth_int(depth);

        let options = subversion::client::ProplistOptions {
            peg_revision: subversion::Revision::Unspecified,
            revision: rev,
            depth: svn_depth,
            changelists: None,
            get_target_inherited_props: false,
        };

        let mut result = Vec::new();
        let receiver = |item_path: &str,
                        props: &std::collections::HashMap<String, Vec<u8>>,
                        _inherited: Option<&[subversion::InheritedItem]>|
         -> Result<(), subversion::Error> {
            Python::attach(|py| {
                let props_dict = pyo3::types::PyDict::new(py);
                for (k, v) in props {
                    props_dict
                        .set_item(k, pyo3::types::PyBytes::new(py, v))
                        .map_err(|e| {
                            subversion::Error::from_message(&format!("Failed to set prop: {}", e))
                        })?;
                }
                let entry = (item_path.to_string(), props_dict.into_any().unbind());
                let tuple = pyo3::types::PyTuple::new(
                    py,
                    [
                        entry.0.into_pyobject(py).unwrap().into_any().unbind(),
                        entry.1,
                    ],
                )
                .map_err(|e| {
                    subversion::Error::from_message(&format!("Failed to create tuple: {}", e))
                })?;
                result.push(tuple.into_any().unbind());
                Ok(())
            })
        };

        self.ctx
            .proplist(path, &options, &mut { receiver })
            .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;

        Ok(result)
    }

    /// Get information about a versioned path
    #[pyo3(signature = (path, revision=None, peg_revision=None, recurse=false, depth=None, fetch_excluded=false, fetch_actual_only=false, include_externals=false))]
    fn info<'py>(
        &mut self,
        py: Python<'py>,
        path: Bound<PyAny>,
        revision: Option<Bound<PyAny>>,
        peg_revision: Option<Bound<PyAny>>,
        recurse: bool,
        depth: Option<i32>,
        fetch_excluded: bool,
        fetch_actual_only: bool,
        include_externals: bool,
    ) -> PyResult<Bound<'py, pyo3::types::PyDict>> {
        let path_str = subvertpy_util::py_to_svn_string(&path)?;
        let path_abs = if std::path::Path::new(&path_str).is_absolute() || path_str.contains("://")
        {
            path_str
        } else {
            let current_dir = std::env::current_dir().map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyIOError, _>(format!(
                    "Failed to get current directory: {}",
                    e
                ))
            })?;
            current_dir.join(&path_str).to_string_lossy().to_string()
        };

        let rev = if let Some(r) = revision {
            parse_revision(py, &r)?
        } else {
            subversion::Revision::Unspecified
        };
        // Match the old C behavior: default unspecified revision to HEAD
        let rev = if matches!(rev, subversion::Revision::Unspecified) {
            subversion::Revision::Head
        } else {
            rev
        };

        let peg_rev = if let Some(r) = peg_revision {
            parse_revision(py, &r)?
        } else {
            subversion::Revision::Unspecified
        };

        let svn_depth = if let Some(d) = depth {
            parse_depth_int(d)
        } else if recurse {
            subversion::Depth::Infinity
        } else {
            subversion::Depth::Empty
        };

        let options = subversion::client::InfoOptions {
            peg_revision: peg_rev,
            revision: rev,
            depth: svn_depth,
            fetch_excluded,
            fetch_actual_only,
            include_externals,
            changelists: None,
        };

        let result_dict = pyo3::types::PyDict::new(py);

        let receiver = |abspath_or_url: &std::path::Path,
                        info: &subversion::client::Info|
         -> Result<(), subversion::Error> {
            Python::attach(|py| {
                let node_kind = subversion::NodeKind::from(info.kind());
                let kind_str = match node_kind {
                    subversion::NodeKind::None => "none",
                    subversion::NodeKind::File => "file",
                    subversion::NodeKind::Dir => "dir",
                    subversion::NodeKind::Unknown => "unknown",
                    subversion::NodeKind::Symlink => "symlink",
                };

                let date_str = format!("{}", info.last_changed_date());

                let wc_info_py = info
                    .wc_info()
                    .map(|wci| Py::new(py, crate::info::WCInfo::from_svn(&wci)).unwrap());

                let info_obj = crate::info::Info {
                    url: info.url().to_string(),
                    revision: info.revision().as_u64() as i64,
                    kind: kind_str.to_string(),
                    repos_root_url: info.repos_root_url().to_string(),
                    repos_uuid: info.repos_uuid().to_string(),
                    last_changed_rev: info
                        .last_changed_rev()
                        .map(|r| r.as_u64() as i64)
                        .unwrap_or(-1),
                    last_changed_date: date_str,
                    last_changed_author: info.last_changed_author().unwrap_or("").to_string(),
                    size: info.size(),
                    wc_info: wc_info_py,
                };

                let path_str = abspath_or_url
                    .file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or(abspath_or_url.to_str().unwrap());

                result_dict.set_item(path_str, info_obj).map_err(|e| {
                    subversion::Error::from_message(&format!("Failed to set info dict item: {}", e))
                })?;

                Ok(())
            })
        };

        self.ctx
            .info(&path_abs, &options, &receiver)
            .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;

        Ok(result_dict.clone())
    }

    /// Export a tree from the repository to a local directory
    #[pyo3(signature = (from_path_or_url, to, rev=None, peg_rev=None, overwrite=false, ignore_externals=false, ignore_keywords=false, recurse=true, native_eol=None))]
    fn export(
        &mut self,
        py: Python,
        from_path_or_url: &str,
        to: Bound<PyAny>,
        rev: Option<Bound<PyAny>>,
        peg_rev: Option<Bound<PyAny>>,
        overwrite: bool,
        ignore_externals: bool,
        ignore_keywords: bool,
        recurse: bool,
        native_eol: Option<&str>,
    ) -> PyResult<i64> {
        let to_path_str = subvertpy_util::py_to_svn_string(&to)?;
        let to_path_abs = if std::path::Path::new(&to_path_str).is_absolute() {
            to_path_str
        } else {
            let current_dir = std::env::current_dir().map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyIOError, _>(format!(
                    "Failed to get current directory: {}",
                    e
                ))
            })?;
            current_dir.join(&to_path_str).to_string_lossy().to_string()
        };

        let revision = if let Some(r) = rev {
            parse_revision(py, &r)?
        } else {
            subversion::Revision::Head
        };

        let peg_revision = if let Some(r) = peg_rev {
            parse_revision(py, &r)?
        } else {
            subversion::Revision::Unspecified
        };

        let depth = if recurse {
            subversion::Depth::Infinity
        } else {
            subversion::Depth::Files
        };

        let native_eol_enum = if let Some(eol) = native_eol {
            match eol {
                "LF" => subversion::NativeEOL::LF,
                "CR" => subversion::NativeEOL::CR,
                "CRLF" => subversion::NativeEOL::CRLF,
                _ => {
                    return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                        "Invalid native_eol value: {}",
                        eol
                    )))
                }
            }
        } else {
            subversion::NativeEOL::Standard
        };

        let options = subversion::client::ExportOptions {
            peg_revision,
            revision,
            overwrite,
            ignore_externals,
            ignore_keywords,
            depth,
            native_eol: native_eol_enum,
        };

        let result_rev = self
            .ctx
            .export(from_path_or_url, to_path_abs.as_str(), &options)
            .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;

        Ok(result_rev.map(|r| r.as_u64() as i64).unwrap_or(-1))
    }

    /// Diff two paths or URLs
    /// Returns a tuple (outf, errf) of file-like objects containing the diff output
    #[pyo3(signature = (rev1, rev2, path1, path2, relative_to_dir=None, diffopts=None, ignore_ancestry=true, no_diff_deleted=true, ignore_content_type=false, encoding=None))]
    fn diff(
        &mut self,
        py: Python,
        rev1: Bound<PyAny>,
        rev2: Bound<PyAny>,
        path1: &str,
        path2: &str,
        relative_to_dir: Option<&str>,
        diffopts: Option<Vec<String>>,
        ignore_ancestry: bool,
        no_diff_deleted: bool,
        ignore_content_type: bool,
        encoding: Option<&str>,
    ) -> PyResult<(Py<PyAny>, Py<PyAny>)> {
        let revision1 = parse_revision(py, &rev1)?;
        let revision2 = parse_revision(py, &rev2)?;

        let options = subversion::client::DiffOptions {
            diff_options: diffopts.unwrap_or_default(),
            depth: subversion::Depth::Infinity,
            ignore_ancestry,
            no_diff_added: false,
            no_diff_deleted,
            show_copies_as_adds: false,
            ignore_content_type,
            ignore_properties: false,
            properties_only: false,
            use_git_diff_format: false,
            pretty_print_mergeinfo: false,
            header_encoding: encoding.unwrap_or("UTF-8").to_string(),
            changelists: None,
        };

        let io_module = py.import("io")?;
        let out_io = io_module.getattr("BytesIO")?.call0()?;
        let err_io = io_module.getattr("BytesIO")?.call0()?;

        let mut out_stream = subvertpy_util::io::py_to_stream(py, &out_io)?;
        let mut err_stream = subvertpy_util::io::py_to_stream(py, &err_io)?;

        self.ctx
            .diff(
                path1,
                &revision1,
                path2,
                &revision2,
                relative_to_dir,
                &mut out_stream,
                &mut err_stream,
                &options,
            )
            .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;

        drop(out_stream);
        drop(err_stream);

        out_io.call_method1("seek", (0,))?;
        err_io.call_method1("seek", (0,))?;

        Ok((out_io.unbind(), err_io.unbind()))
    }

    /// Output file contents
    #[pyo3(signature = (path, stream, revision=None, peg_revision=None, expand_keywords=false))]
    fn cat(
        &mut self,
        py: Python,
        path: &str,
        stream: Bound<PyAny>,
        revision: Option<Bound<PyAny>>,
        peg_revision: Option<Bound<PyAny>>,
        expand_keywords: bool,
    ) -> PyResult<()> {
        let rev = if let Some(r) = revision {
            parse_revision(py, &r)?
        } else {
            subversion::Revision::Working
        };

        let peg_rev = if let Some(r) = peg_revision {
            parse_revision(py, &r)?
        } else {
            rev
        };

        let options = subversion::client::CatOptions {
            peg_revision: peg_rev,
            revision: rev,
            expand_keywords,
        };

        struct PythonWriter {
            stream: pyo3::Py<pyo3::PyAny>,
        }

        impl std::io::Write for PythonWriter {
            fn write(&mut self, buf: &[u8]) -> std::io::Result<usize> {
                Python::attach(|py| {
                    let stream_bound = self.stream.bind(py);
                    stream_bound
                        .call_method1("write", (pyo3::types::PyBytes::new(py, buf),))
                        .map_err(|e| {
                            std::io::Error::new(std::io::ErrorKind::Other, e.to_string())
                        })?;
                    Ok(buf.len())
                })
            }

            fn flush(&mut self) -> std::io::Result<()> {
                Python::attach(|py| {
                    let stream_bound = self.stream.bind(py);
                    stream_bound.call_method0("flush").map_err(|e| {
                        std::io::Error::new(std::io::ErrorKind::Other, e.to_string())
                    })?;
                    Ok(())
                })
            }
        }

        let mut writer = PythonWriter {
            stream: stream.unbind(),
        };

        self.ctx
            .cat(path, &mut writer, &options)
            .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;

        Ok(())
    }

    /// Copy a file or directory
    #[pyo3(signature = (src, dst, src_rev=None, copy_as_child=false, make_parents=false, metadata_only=false, pin_externals=false, callback=None))]
    fn copy(
        &mut self,
        py: Python,
        src: &str,
        dst: &str,
        src_rev: Option<Bound<PyAny>>,
        copy_as_child: bool,
        make_parents: bool,
        metadata_only: bool,
        pin_externals: bool,
        callback: Option<Bound<PyAny>>,
    ) -> PyResult<()> {
        let src_revision = if let Some(r) = src_rev {
            Some(parse_revision(py, &r)?)
        } else {
            None
        };

        let callback_py = callback.map(|cb| cb.unbind());
        let mut commit_callback_fn =
            |info: &subversion::CommitInfo| -> Result<(), subversion::Error> {
                if let Some(ref cb) = callback_py {
                    Python::attach(|py| {
                        let cb_bound = cb.bind(py);
                        let rev = info.revision().as_u64() as i64;
                        let date = info.date().map(|s| s.to_string());
                        let author = info.author().map(|s| s.to_string());
                        cb_bound
                            .call1((rev, date.as_deref(), author.as_deref()))
                            .map_err(|e| {
                                subversion::Error::from_message(&format!("Callback failed: {}", e))
                            })?;
                        Ok(())
                    })
                } else {
                    Ok(())
                }
            };

        let mut options = subversion::client::CopyOptions {
            copy_as_child,
            make_parents,
            ignore_externals: false,
            metadata_only,
            pin_externals,
            externals_to_pin: None,
            revprop_table: None,
            commit_callback: if callback_py.is_some() {
                Some(&mut commit_callback_fn)
            } else {
                None
            },
        };

        self.ctx
            .copy(&[(src, src_revision)], dst, &mut options)
            .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;

        Ok(())
    }

    /// List directory contents
    #[pyo3(signature = (path_or_url, revision=None, depth=0, include_externals=false))]
    fn list<'py>(
        &mut self,
        py: Python<'py>,
        path_or_url: &str,
        revision: Option<Bound<PyAny>>,
        depth: i32,
        include_externals: bool,
    ) -> PyResult<Bound<'py, pyo3::types::PyDict>> {
        let rev = if let Some(r) = revision {
            parse_revision(py, &r)?
        } else {
            subversion::Revision::Head
        };

        let svn_depth = parse_depth_int(depth);

        let options = subversion::client::ListOptions {
            peg_revision: subversion::Revision::Unspecified,
            revision: rev,
            patterns: None,
            depth: svn_depth,
            dirent_fields: 0xFFFFFFFF, // All fields
            fetch_locks: false,
            include_externals,
        };

        let result_dict = pyo3::types::PyDict::new(py);

        let list_func = |path: &str,
                         dirent: &subversion::ra::Dirent,
                         _lock: Option<&subversion::Lock>|
         -> Result<(), subversion::Error> {
            Python::attach(|py| {
                let node_kind_str = match dirent.kind() {
                    subversion::NodeKind::None => "none",
                    subversion::NodeKind::File => "file",
                    subversion::NodeKind::Dir => "dir",
                    subversion::NodeKind::Unknown => "unknown",
                    subversion::NodeKind::Symlink => "symlink",
                };

                let entry_dict = pyo3::types::PyDict::new(py);
                entry_dict
                    .set_item("kind", node_kind_str)
                    .map_err(|e| subversion::Error::from_message(&format!("{}", e)))?;
                entry_dict
                    .set_item("size", dirent.size())
                    .map_err(|e| subversion::Error::from_message(&format!("{}", e)))?;
                entry_dict
                    .set_item("has_props", dirent.has_props())
                    .map_err(|e| subversion::Error::from_message(&format!("{}", e)))?;
                let created_rev = dirent
                    .created_rev()
                    .map(|r| r.as_u64() as i64)
                    .unwrap_or(-1);
                entry_dict
                    .set_item("created_rev", created_rev)
                    .map_err(|e| subversion::Error::from_message(&format!("{}", e)))?;
                entry_dict
                    .set_item("last_author", dirent.last_author())
                    .map_err(|e| subversion::Error::from_message(&format!("{}", e)))?;

                result_dict
                    .set_item(path, entry_dict.into_any().unbind())
                    .map_err(|e| subversion::Error::from_message(&format!("{}", e)))?;

                Ok(())
            })
        };

        self.ctx
            .list(path_or_url, &options, &mut { list_func })
            .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;

        Ok(result_dict)
    }

    /// Lock files in the repository
    #[pyo3(signature = (targets, comment, steal_lock=false))]
    fn lock(&mut self, targets: Vec<String>, comment: &str, steal_lock: bool) -> PyResult<()> {
        let target_refs: Vec<&str> = targets.iter().map(|s| s.as_str()).collect();
        self.ctx
            .lock(&target_refs, comment, steal_lock)
            .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;
        Ok(())
    }

    /// Unlock files in the repository
    #[pyo3(signature = (targets, break_lock=false))]
    fn unlock(&mut self, targets: Vec<String>, break_lock: bool) -> PyResult<()> {
        let target_refs: Vec<&str> = targets.iter().map(|s| s.as_str()).collect();
        self.ctx
            .unlock(&target_refs, break_lock)
            .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;
        Ok(())
    }

    /// Resolve a conflict on a versioned path
    #[pyo3(signature = (path, depth=0, conflict_choice=0))]
    fn resolve(&mut self, path: &str, depth: i32, conflict_choice: i32) -> PyResult<()> {
        let svn_depth = parse_depth_int(depth);
        let choice = parse_conflict_choice(conflict_choice);
        self.ctx
            .resolve(path, svn_depth, choice)
            .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;
        Ok(())
    }
}

/// Parse a depth integer (SVN depth values: 0=empty, 1=files, 2=immediates, 3=infinity)
fn parse_depth_int(depth: i32) -> subversion::Depth {
    match depth {
        0 => subversion::Depth::Empty,
        1 => subversion::Depth::Files,
        2 => subversion::Depth::Immediates,
        _ => subversion::Depth::Infinity,
    }
}

/// Parse a depth from a Python object (integer or string)
fn parse_depth(_py: Python, depth: &Bound<PyAny>) -> PyResult<subversion::Depth> {
    if let Ok(n) = depth.extract::<i32>() {
        Ok(parse_depth_int(n))
    } else if let Ok(s) = depth.extract::<String>() {
        match s.to_lowercase().as_str() {
            "empty" => Ok(subversion::Depth::Empty),
            "files" => Ok(subversion::Depth::Files),
            "immediates" => Ok(subversion::Depth::Immediates),
            "infinity" => Ok(subversion::Depth::Infinity),
            _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Invalid depth value: {}",
                s
            ))),
        }
    } else {
        Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
            "Depth must be an integer or string",
        ))
    }
}

/// Parse conflict choice integer to SVN conflict choice
fn parse_conflict_choice(choice: i32) -> subversion::ConflictChoice {
    match choice {
        0 => subversion::ConflictChoice::Postpone,
        1 => subversion::ConflictChoice::Base,
        2 => subversion::ConflictChoice::TheirsFull,
        3 => subversion::ConflictChoice::MineFull,
        4 => subversion::ConflictChoice::TheirsConflict,
        5 => subversion::ConflictChoice::MineConflict,
        6 => subversion::ConflictChoice::Merged,
        _ => subversion::ConflictChoice::Unspecified,
    }
}

/// Build a HashMap<String, String> from an optional Python dict of revprops
fn build_string_revprop_map(
    revprops: Option<&Bound<PyAny>>,
) -> PyResult<std::collections::HashMap<String, String>> {
    let mut map = std::collections::HashMap::new();
    if let Some(rp) = revprops {
        if let Ok(dict) = rp.cast::<pyo3::types::PyDict>() {
            for (key, value) in dict.iter() {
                let k = key.extract::<String>()?;
                let v = if let Ok(s) = value.extract::<String>() {
                    s
                } else if let Ok(b) = value.extract::<&[u8]>() {
                    String::from_utf8(b.to_vec()).map_err(|_| {
                        PyErr::new::<pyo3::exceptions::PyValueError, _>(
                            "Revprop value is not valid UTF-8",
                        )
                    })?
                } else {
                    return Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                        "Revprop values must be string or bytes",
                    ));
                };
                map.insert(k, v);
            }
        }
    }
    Ok(map)
}
