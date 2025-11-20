//! Context Python bindings

use pyo3::prelude::*;
use subvertpy_util::error::svn_err_to_py;

fn depth_to_py(depth: subversion::Depth) -> i32 {
    match depth {
        subversion::Depth::Unknown => -2,
        subversion::Depth::Exclude => -1,
        subversion::Depth::Empty => 0,
        subversion::Depth::Files => 1,
        subversion::Depth::Immediates => 2,
        subversion::Depth::Infinity => 3,
    }
}

pub(crate) fn depth_from_py(depth: i32) -> subversion::Depth {
    match depth {
        -2 => subversion::Depth::Unknown,
        -1 => subversion::Depth::Exclude,
        0 => subversion::Depth::Empty,
        1 => subversion::Depth::Files,
        2 => subversion::Depth::Immediates,
        _ => subversion::Depth::Infinity,
    }
}

/// Create a Rust notify closure from an optional Python callback.
///
/// The Python callback receives the SVN error as an exception object
/// when the notification indicates an error.
fn make_notify_closure(
    py_notify: Option<Py<PyAny>>,
) -> Option<Box<dyn Fn(&subversion::wc::Notify)>> {
    py_notify.map(|py_func| -> Box<dyn Fn(&subversion::wc::Notify)> {
        Box::new(move |notify: &subversion::wc::Notify| {
            if let Some(err) = notify.err() {
                Python::attach(|py| {
                    let py_err = svn_err_to_py(err);
                    let _ = py_func.call1(py, (py_err,));
                });
            }
        })
    })
}

/// Working copy context.
#[pyclass(name = "Context", unsendable)]
pub struct Context {
    pub(crate) inner: subversion::wc::Context,
}

#[pymethods]
impl Context {
    #[new]
    fn init() -> PyResult<Self> {
        let ctx = subversion::wc::Context::new().map_err(svn_err_to_py)?;
        Ok(Self { inner: ctx })
    }

    /// Check whether a path is locked.
    fn locked(&mut self, path: &Bound<PyAny>) -> PyResult<(bool, bool)> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        self.inner.locked(&path_str).map_err(svn_err_to_py)
    }

    /// Check format version of a working copy.
    fn check_wc(&mut self, path: &Bound<PyAny>) -> PyResult<i32> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        self.inner.check_wc(&path_str).map_err(svn_err_to_py)
    }

    /// Check whether text of a file is modified against base.
    fn text_modified(&mut self, path: &Bound<PyAny>) -> PyResult<bool> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        self.inner.text_modified(&path_str).map_err(svn_err_to_py)
    }

    /// Check whether props of a file are modified against base.
    fn props_modified(&mut self, path: &Bound<PyAny>) -> PyResult<bool> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        self.inner.props_modified(&path_str).map_err(svn_err_to_py)
    }

    /// Check whether a path is conflicted.
    fn conflicted(&mut self, path: &Bound<PyAny>) -> PyResult<(bool, bool, bool)> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        self.inner.conflicted(&path_str).map_err(svn_err_to_py)
    }

    /// Get the status of a path.
    fn status(&mut self, path: &Bound<PyAny>) -> PyResult<crate::status::Status> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        let wc_path = std::path::Path::new(&path_str);
        let svn_status = self.inner.status(wc_path).map_err(svn_err_to_py)?;
        Ok(crate::status::Status::from_svn_status(&svn_status))
    }

    /// Walk status of a path tree, calling receiver for each entry.
    #[pyo3(signature = (path, receiver, depth=3, get_all=true, no_ignore=false, ignore_text_mode=false, ignore_patterns=None))]
    fn walk_status(
        &mut self,
        py: Python,
        path: &Bound<PyAny>,
        receiver: Py<PyAny>,
        depth: i32,
        get_all: bool,
        no_ignore: bool,
        ignore_text_mode: bool,
        ignore_patterns: Option<Vec<String>>,
    ) -> PyResult<()> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        let wc_path = std::path::Path::new(&path_str);

        let pattern_refs: Option<Vec<&str>> = ignore_patterns
            .as_ref()
            .map(|v| v.iter().map(|s| s.as_str()).collect());

        let receiver_ref = receiver.clone_ref(py);
        self.inner
            .walk_status(
                wc_path,
                depth_from_py(depth),
                get_all,
                no_ignore,
                ignore_text_mode,
                pattern_refs.as_deref(),
                |local_abspath: &str, svn_status: &subversion::wc::Status<'_>| {
                    let py_status = crate::status::Status::from_svn_status(svn_status);
                    Python::attach(|py| {
                        receiver_ref
                            .call1(py, (local_abspath, py_status))
                            .map(|_| ())
                            .map_err(subvertpy_util::error::py_err_to_svn)
                    })
                },
            )
            .map_err(svn_err_to_py)
    }

    /// Get property diffs for a path.
    fn get_prop_diffs(
        &mut self,
        py: Python,
        path: &Bound<PyAny>,
    ) -> PyResult<(Py<PyAny>, Py<PyAny>)> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        let wc_path = std::path::Path::new(&path_str);
        let (changes, original) = self.inner.get_prop_diffs(wc_path).map_err(svn_err_to_py)?;

        // Convert original props to Python dict
        let orig_dict = pyo3::types::PyDict::new(py);
        if let Some(orig) = original {
            for (k, v) in &orig {
                orig_dict.set_item(k, pyo3::types::PyBytes::new(py, v))?;
            }
        }

        // Convert changes to Python list of (name, value) tuples
        let changes_list = pyo3::types::PyList::empty(py);
        for change in &changes {
            let value: Py<PyAny> = match &change.value {
                Some(v) => pyo3::types::PyBytes::new(py, v)
                    .into_pyobject(py)?
                    .into_any()
                    .unbind(),
                None => py.None(),
            };
            let tuple = pyo3::types::PyTuple::new(
                py,
                &[
                    change.name.clone().into_pyobject(py)?.into_any().unbind(),
                    value,
                ],
            )?;
            changes_list.append(tuple)?;
        }

        Ok((
            orig_dict.into_pyobject(py)?.into_any().unbind(),
            changes_list.into_pyobject(py)?.into_any().unbind(),
        ))
    }

    /// Ensure an administrative area exists.
    #[pyo3(signature = (local_abspath, url, repos_root_url, repos_uuid, revnum, depth=3))]
    fn ensure_adm(
        &mut self,
        local_abspath: &str,
        url: &str,
        repos_root_url: &str,
        repos_uuid: &str,
        revnum: i64,
        depth: i32,
    ) -> PyResult<()> {
        let d = match depth {
            0 => subversion::Depth::Empty,
            1 => subversion::Depth::Files,
            2 => subversion::Depth::Immediates,
            _ => subversion::Depth::Infinity,
        };
        self.inner
            .ensure_adm(
                local_abspath,
                url,
                repos_root_url,
                repos_uuid,
                subversion::Revnum::from_raw(revnum).unwrap_or(subversion::Revnum::invalid()),
                d,
            )
            .map_err(svn_err_to_py)
    }

    /// Add a lock to the working copy.
    fn add_lock(&mut self, path: &Bound<PyAny>, lock: &crate::lock::Lock) -> PyResult<()> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        let wc_path = std::path::Path::new(&path_str);
        let (lock_path, lock_token) = lock
            .to_svn_lock()
            .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("Invalid lock"))?;
        let svn_lock = subversion::wc::Lock::new(lock_path, lock_token);
        self.inner
            .add_lock(wc_path, &svn_lock)
            .map_err(svn_err_to_py)
    }

    /// Remove a lock from the working copy.
    fn remove_lock(&mut self, path: &Bound<PyAny>) -> PyResult<()> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        let wc_path = std::path::Path::new(&path_str);
        self.inner.remove_lock(wc_path).map_err(svn_err_to_py)
    }

    /// Add a file from disk to the working copy.
    #[pyo3(signature = (path, props=None, skip_checks=false, notify=None))]
    fn add_from_disk(
        &mut self,
        path: &Bound<PyAny>,
        props: Option<&Bound<PyAny>>,
        skip_checks: bool,
        notify: Option<Py<PyAny>>,
    ) -> PyResult<()> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        let wc_path = std::path::Path::new(&path_str);

        // Convert Python dict {str|bytes: bytes} to HashMap
        let rust_props = if let Some(dict) = props {
            let dict: &Bound<pyo3::types::PyDict> = dict.cast()?;
            let mut map = std::collections::HashMap::with_capacity(dict.len());
            for (key, val) in dict.iter() {
                let name: String = if let Ok(s) = key.extract::<String>() {
                    s
                } else {
                    let bytes: Vec<u8> = key.extract()?;
                    String::from_utf8(bytes).map_err(|e| {
                        pyo3::exceptions::PyValueError::new_err(format!(
                            "property name is not valid UTF-8: {e}"
                        ))
                    })?
                };
                let value: Vec<u8> = val.extract()?;
                map.insert(name, value);
            }
            Some(map)
        } else {
            None
        };

        let notify_fn = make_notify_closure(notify);
        self.inner
            .add_from_disk(
                wc_path,
                rust_props.as_ref(),
                skip_checks,
                notify_fn.as_deref(),
            )
            .map_err(svn_err_to_py)
    }

    /// Process the committed queue.
    fn process_committed_queue(
        &mut self,
        queue: &mut crate::committed::CommittedQueue,
        revnum: i64,
        date: &str,
        author: &str,
    ) -> PyResult<()> {
        self.inner
            .process_committed_queue(
                &mut queue.inner,
                subversion::Revnum::from_raw(revnum).unwrap_or(subversion::Revnum::invalid()),
                Some(date),
                Some(author),
            )
            .map_err(svn_err_to_py)
    }

    /// Crawl working copy revisions, calling reporter methods.
    #[pyo3(signature = (path, reporter, restore_files=true, depth=3, honor_depth_exclude=true, depth_compatibility_trick=false, use_commit_times=false, notify=None))]
    fn crawl_revisions(
        &mut self,
        _py: Python,
        path: &Bound<PyAny>,
        reporter: Py<PyAny>,
        restore_files: bool,
        depth: i32,
        honor_depth_exclude: bool,
        depth_compatibility_trick: bool,
        use_commit_times: bool,
        notify: Option<Py<PyAny>>,
    ) -> PyResult<()> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;

        let py_reporter = PyReporterBridge { reporter };
        let mut wrap_reporter = subversion::ra::WrapReporter::from_rust_reporter(py_reporter);

        let notify_fn = make_notify_closure(notify);
        subversion::wc::crawl_revisions5(
            &mut self.inner,
            &path_str,
            &mut wrap_reporter,
            restore_files,
            depth_from_py(depth),
            honor_depth_exclude,
            depth_compatibility_trick,
            use_commit_times,
            notify_fn.as_deref(),
        )
        .map_err(svn_err_to_py)
    }

    /// Get an editor for updating the working copy.
    #[pyo3(signature = (
        anchor_abspath, target_basename, use_commit_times=false, depth=3,
        depth_is_sticky=false, allow_unver_obstructions=true, adds_as_modification=false,
        server_performs_filtering=false, clean_checkout=false, diff3_cmd=None,
        preserved_exts=None, dirents_func=None, conflict_func=None, external_func=None,
        notify_func=None
    ))]
    fn get_update_editor(
        slf: &Bound<Self>,
        anchor_abspath: &Bound<PyAny>,
        target_basename: &str,
        use_commit_times: bool,
        depth: i32,
        depth_is_sticky: bool,
        allow_unver_obstructions: bool,
        adds_as_modification: bool,
        server_performs_filtering: bool,
        clean_checkout: bool,
        diff3_cmd: Option<&str>,
        preserved_exts: Option<Vec<String>>,
        dirents_func: Option<Py<PyAny>>,
        conflict_func: Option<Py<PyAny>>,
        external_func: Option<Py<PyAny>>,
        notify_func: Option<Py<PyAny>>,
    ) -> PyResult<subvertpy_util::editor::PyEditor> {
        if conflict_func.is_some() {
            return Err(pyo3::exceptions::PyNotImplementedError::new_err(
                "conflict_func is not currently supported",
            ));
        }
        if external_func.is_some() {
            return Err(pyo3::exceptions::PyNotImplementedError::new_err(
                "external_func is not currently supported",
            ));
        }
        if dirents_func.is_some() {
            return Err(pyo3::exceptions::PyNotImplementedError::new_err(
                "dirents_func is not currently supported",
            ));
        }

        let path_str = subvertpy_util::py_to_svn_abspath(anchor_abspath)?;

        let svn_depth = match depth {
            -2 => subversion::Depth::Unknown,
            -1 => subversion::Depth::Exclude,
            0 => subversion::Depth::Empty,
            1 => subversion::Depth::Files,
            2 => subversion::Depth::Immediates,
            _ => subversion::Depth::Infinity,
        };

        let ext_refs: Vec<&str> = preserved_exts
            .as_ref()
            .map(|v| v.iter().map(|s| s.as_str()).collect())
            .unwrap_or_default();

        let options = subversion::wc::UpdateEditorOptions {
            use_commit_times,
            depth: svn_depth,
            depth_is_sticky,
            allow_unver_obstructions,
            adds_as_modification,
            server_performs_filtering,
            clean_checkout,
            diff3_cmd,
            preserved_exts: ext_refs,
            fetch_dirents_func: None,
            conflict_func: None,
            external_func: None,
            cancel_func: None,
            notify_func: notify_func.map(|py_func| -> Box<dyn Fn(&subversion::wc::Notify)> {
                Box::new(move |notify: &subversion::wc::Notify| {
                    if let Some(err) = notify.err() {
                        Python::attach(|py| {
                            let py_err = svn_err_to_py(err);
                            let _ = py_func.call1(py, (py_err,));
                        });
                    }
                })
            }),
        };

        let mut this = slf.borrow_mut();
        let (editor, _target_rev) = subversion::wc::get_update_editor4(
            &mut this.inner,
            &path_str,
            target_basename,
            options,
        )
        .map_err(svn_err_to_py)?;

        let wrap_editor = editor.into_wrap_editor();
        let parent = slf.clone().into_any().unbind();
        Ok(subvertpy_util::editor::PyEditor::new_with_parent(
            wrap_editor,
            parent,
        ))
    }
}

/// Bridge between a Python reporter object and the Rust Reporter trait.
///
/// The Python reporter object must have methods:
/// - set_path(path, revision, start_empty, lock_token, depth)
/// - delete_path(path)
/// - link_path(path, url, revision, start_empty, lock_token, depth)
/// - finish()
/// - abort()
struct PyReporterBridge {
    reporter: Py<PyAny>,
}

impl subversion::ra::Reporter for PyReporterBridge {
    fn set_path(
        &mut self,
        path: &str,
        rev: subversion::Revnum,
        depth: subversion::Depth,
        start_empty: bool,
        lock_token: &str,
    ) -> Result<(), subversion::Error<'static>> {
        let lock_token_opt = if lock_token.is_empty() {
            None
        } else {
            Some(lock_token.to_owned())
        };
        Python::attach(|py| {
            self.reporter
                .call_method1(
                    py,
                    "set_path",
                    (
                        path,
                        rev.as_i64(),
                        start_empty,
                        lock_token_opt,
                        depth_to_py(depth),
                    ),
                )
                .map(|_| ())
                .map_err(subvertpy_util::error::py_err_to_svn)
        })
    }

    fn delete_path(&mut self, path: &str) -> Result<(), subversion::Error<'static>> {
        Python::attach(|py| {
            self.reporter
                .call_method1(py, "delete_path", (path,))
                .map(|_| ())
                .map_err(subvertpy_util::error::py_err_to_svn)
        })
    }

    fn link_path(
        &mut self,
        path: &str,
        url: &str,
        rev: subversion::Revnum,
        depth: subversion::Depth,
        start_empty: bool,
        lock_token: &str,
    ) -> Result<(), subversion::Error<'static>> {
        let lock_token_opt = if lock_token.is_empty() {
            None
        } else {
            Some(lock_token.to_owned())
        };
        Python::attach(|py| {
            self.reporter
                .call_method1(
                    py,
                    "link_path",
                    (
                        path,
                        url,
                        rev.as_i64(),
                        start_empty,
                        lock_token_opt,
                        depth_to_py(depth),
                    ),
                )
                .map(|_| ())
                .map_err(subvertpy_util::error::py_err_to_svn)
        })
    }

    fn finish_report(&mut self) -> Result<(), subversion::Error<'static>> {
        Python::attach(|py| {
            self.reporter
                .call_method0(py, "finish")
                .map(|_| ())
                .map_err(subvertpy_util::error::py_err_to_svn)
        })
    }

    fn abort_report(&mut self) -> Result<(), subversion::Error<'static>> {
        Python::attach(|py| {
            self.reporter
                .call_method0(py, "abort")
                .map(|_| ())
                .map_err(subvertpy_util::error::py_err_to_svn)
        })
    }
}
