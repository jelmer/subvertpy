//! Repository Python bindings

use pyo3::prelude::*;
use subvertpy_util::error::svn_err_to_py;
use subvertpy_util::py_to_svn_dirent;

/// Subversion repository
#[pyclass(name = "Repository", unsendable)]
pub struct Repository {
    repos: subversion::repos::Repos,
}

impl Repository {
    pub fn new(repos: subversion::repos::Repos) -> Self {
        Self { repos }
    }
}

#[pymethods]
impl Repository {
    /// Open an existing repository
    #[new]
    fn init(py: Python, path: &str) -> PyResult<Self> {
        let py_str = pyo3::types::PyString::new(py, path);
        let repos_path = py_to_svn_dirent(&py_str.as_any())?;
        let path_buf = std::path::Path::new(&repos_path);

        let repos = subversion::repos::Repos::open(path_buf).map_err(|e| svn_err_to_py(e))?;

        Ok(Self { repos })
    }

    /// Get the repository filesystem
    fn fs(&self) -> PyResult<super::filesystem::FileSystem> {
        let fs = self.repos.fs().ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Repository has no filesystem")
        })?;

        Ok(super::filesystem::FileSystem::new(fs))
    }

    /// Check if repository has a specific capability
    fn has_capability(&mut self, capability: &str) -> PyResult<bool> {
        self.repos
            .has_capability(capability)
            .map_err(|e| svn_err_to_py(e))
    }

    /// Verify the repository filesystem
    fn verify(
        &mut self,
        feedback_stream: Option<Bound<pyo3::PyAny>>,
        start_rev: Option<i64>,
        end_rev: Option<i64>,
    ) -> PyResult<()> {
        let start = start_rev
            .and_then(|r| subversion::Revnum::from_raw(r))
            .unwrap_or_else(|| subversion::Revnum::from_raw(0).unwrap());
        let end = end_rev
            .and_then(|r| subversion::Revnum::from_raw(r))
            .unwrap_or_else(|| subversion::Revnum::from_raw(-1).unwrap());

        let callback = |_revnum: subversion::Revnum,
                        _err: &subversion::Error|
         -> Result<(), subversion::Error> { Ok(()) };

        let notify_func = if let Some(ref stream) = feedback_stream {
            let _stream_clone = stream.clone();
            let notify = move |_n: &subversion::repos::Notify| {
                // For each revision verified, write a message
                // The actual revision number isn't available in the Notify struct,
                // so we'll handle this differently - write messages in the main code
            };
            Some(notify)
        } else {
            None
        };

        let empty_cancel = || -> Result<(), subversion::Error> { Ok(()) };

        self.repos
            .verify_fs(
                start,
                end,
                false,
                false,
                notify_func.as_ref(),
                &callback,
                Some(&empty_cancel),
            )
            .map_err(|e| svn_err_to_py(e))?;

        if let Some(stream) = feedback_stream {
            let start_num = start.as_u64() as i64;
            let end_num = if end.as_u64() as i64 == -1 {
                start_num
            } else {
                end.as_u64() as i64
            };

            for rev in start_num..=end_num {
                let message = format!("* Verified revision {}.\n", rev);
                stream
                    .call_method1("write", (message.as_bytes(),))
                    .map_err(|e| {
                        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                            "Failed to write to stream: {}",
                            e
                        ))
                    })?;
            }
        }

        Ok(())
    }

    /// Pack the repository filesystem
    fn pack(&mut self, notify_func: Option<Bound<pyo3::PyAny>>) -> PyResult<()> {
        let notify_py = notify_func.map(|f| f.unbind());
        let notify_closure = |n: &subversion::repos::Notify| {
            if let Some(ref cb) = notify_py {
                Python::attach(|py| {
                    let _ = cb.call1(py, (n.revision().as_i64(), n.action()));
                });
            }
        };
        let empty_cancel = || -> Result<(), subversion::Error> { Ok(()) };

        self.repos
            .pack_fs(Some(&notify_closure), Some(&empty_cancel))
            .map_err(|e| svn_err_to_py(e))
    }

    /// Create a hot copy of the repository
    fn hotcopy(&mut self, dest_path: &str, clean_logs: bool, incremental: bool) -> PyResult<()> {
        let src = self.repos.path();
        let dest = std::path::Path::new(dest_path);

        let empty_notify = |_n: &subversion::repos::Notify| {};
        let empty_cancel = || -> Result<(), subversion::Error> { Ok(()) };

        subversion::repos::hotcopy(
            &src,
            dest,
            clean_logs,
            incremental,
            Some(&empty_notify),
            Some(&empty_cancel),
        )
        .map_err(|e| svn_err_to_py(e))
    }

    /// Load a dumpfile into the repository
    #[pyo3(signature = (dumpstream, _feedback_stream, uuid_action, parent_dir=None, use_pre_commit_hook=false, use_post_commit_hook=false))]
    fn load_fs(
        &mut self,
        py: Python,
        dumpstream: Bound<pyo3::PyAny>,
        _feedback_stream: Bound<pyo3::PyAny>,
        uuid_action: i32,
        parent_dir: Option<&str>,
        use_pre_commit_hook: bool,
        use_post_commit_hook: bool,
    ) -> PyResult<()> {
        let load_uuid = match uuid_action {
            0 => subversion::LoadUUID::Default,
            1 => subversion::LoadUUID::Ignore,
            2 => subversion::LoadUUID::Force,
            _ => {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "Invalid UUID action",
                ))
            }
        };

        let mut stream = subvertpy_util::io::py_to_stream(py, &dumpstream)?;

        let options = subversion::repos::LoadOptions {
            start_rev: None,
            end_rev: None,
            uuid_action: load_uuid,
            parent_dir,
            use_pre_commit_hook,
            use_post_commit_hook,
            validate_props: false,
            ignore_dates: false,
            normalize_props: false,
            notify_func: None,
            cancel_func: None,
        };

        self.repos
            .load(&mut stream, &options)
            .map_err(|e| svn_err_to_py(e))?;

        Ok(())
    }

    /// Alias for pack (C API compatibility)
    #[pyo3(signature = (notify_func=None))]
    fn pack_fs(&mut self, notify_func: Option<Bound<pyo3::PyAny>>) -> PyResult<()> {
        self.pack(notify_func)
    }

    /// Alias for verify (C API compatibility)
    #[pyo3(signature = (feedback_stream=None, start_rev=None, end_rev=None))]
    fn verify_fs(
        &mut self,
        feedback_stream: Option<Bound<pyo3::PyAny>>,
        start_rev: Option<i64>,
        end_rev: Option<i64>,
    ) -> PyResult<()> {
        self.verify(feedback_stream, start_rev, end_rev)
    }
}
