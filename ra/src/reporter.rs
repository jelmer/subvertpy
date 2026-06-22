//! Reporter Python bindings

use pyo3::prelude::*;
use subvertpy_util::error::svn_err_to_py;

use crate::session::py_depth_to_svn;

/// Subversion reporter for update/switch/diff operations
#[pyclass(name = "Reporter", unsendable)]
pub struct Reporter {
    reporter: Option<Box<dyn subversion::ra::Reporter + Send>>,
    finished: bool,
    /// Keep the session alive (reporter has pointers back to it)
    #[pyo3(get)]
    _session: Option<Py<PyAny>>,
    /// Keep the editor alive for do_diff (reporter has C pointers to it)
    _editor: Option<Box<subversion::delta::WrapEditor<'static>>>,
    /// Keep an arbitrary Python object alive (e.g. a subvertpy editor whose
    /// WrapEditor is borrowed by the reporter through a capsule).
    _keepalive: Option<Py<PyAny>>,
    /// Heap box backing a raw-reporter capsule handed out to the wc module.
    _raw_reporter_box: Option<*mut (*const std::ffi::c_void, *mut std::ffi::c_void)>,
}

impl Drop for Reporter {
    fn drop(&mut self) {
        if let Some(raw) = self._raw_reporter_box.take() {
            unsafe { drop(Box::from_raw(raw)) };
        }
    }
}

impl Reporter {
    pub fn new(reporter: Box<dyn subversion::ra::Reporter + Send>) -> Self {
        Self {
            reporter: Some(reporter),
            finished: false,
            _session: None,
            _editor: None,
            _keepalive: None,
            _raw_reporter_box: None,
        }
    }

    pub fn new_with_session(
        reporter: Box<dyn subversion::ra::Reporter + Send>,
        session: Py<PyAny>,
    ) -> Self {
        Self {
            reporter: Some(reporter),
            finished: false,
            _session: Some(session),
            _editor: None,
            _keepalive: None,
            _raw_reporter_box: None,
        }
    }

    pub fn new_with_session_and_editor(
        reporter: Box<dyn subversion::ra::Reporter + Send>,
        session: Py<PyAny>,
        editor: Box<subversion::delta::WrapEditor<'static>>,
    ) -> Self {
        Self {
            reporter: Some(reporter),
            finished: false,
            _session: Some(session),
            _editor: Some(editor),
            _keepalive: None,
            _raw_reporter_box: None,
        }
    }

    pub fn new_with_session_and_keepalive(
        reporter: Box<dyn subversion::ra::Reporter + Send>,
        session: Py<PyAny>,
        keepalive: Py<PyAny>,
    ) -> Self {
        Self {
            reporter: Some(reporter),
            finished: false,
            _session: Some(session),
            _editor: None,
            _keepalive: Some(keepalive),
            _raw_reporter_box: None,
        }
    }
}

/// PyCapsule name identifying a borrowed raw SVN reporter.
///
/// Wraps a pointer to a heap `(svn_ra_reporter3_t*, baton)` pair so the ``wc``
/// extension can drive a crawl directly against this reporter instead of
/// bouncing every callback back through Python.
pub const RAW_REPORTER_CAPSULE_NAME: &std::ffi::CStr = c"subvertpy._raw_reporter";

#[pymethods]
impl Reporter {
    /// Return a PyCapsule with a borrowed pointer to the raw SVN reporter, or
    /// None if this reporter is not backed by one.
    fn _raw_reporter_capsule<'py>(
        &mut self,
        py: Python<'py>,
    ) -> PyResult<Option<Bound<'py, pyo3::types::PyCapsule>>> {
        let parts = match self.reporter.as_ref() {
            Some(r) => r.as_raw_reporter(),
            None => None,
        };
        let Some((ptr, baton)) = parts else {
            return Ok(None);
        };
        // Box the pair and hand the capsule a borrowed pointer to it. The
        // pointers borrow from `self.reporter`, which the caller must keep
        // alive; we leak the small box (freed when the reporter is dropped via
        // _raw_reporter_box below) to avoid Send requirements on PyCapsule::new.
        let boxed: Box<(*const std::ffi::c_void, *mut std::ffi::c_void)> = Box::new((ptr, baton));
        let raw = Box::into_raw(boxed);
        self._raw_reporter_box = Some(raw);
        let non_null = std::ptr::NonNull::new(raw as *mut std::ffi::c_void).unwrap();
        let capsule = unsafe {
            pyo3::types::PyCapsule::new_with_pointer(py, non_null, RAW_REPORTER_CAPSULE_NAME)?
        };
        Ok(Some(capsule))
    }

    /// Set a path
    #[pyo3(signature = (path, revision, start_empty, lock_token=None, depth=None))]
    fn set_path(
        &mut self,
        path: &str,
        revision: i64,
        start_empty: bool,
        lock_token: Option<&str>,
        depth: Option<i32>,
    ) -> PyResult<()> {
        if self.finished {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Reporter has already been finished",
            ));
        }

        let reporter = self.reporter.as_mut().ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Reporter has been consumed")
        })?;

        let rev = subvertpy_util::to_revnum_or_head(revision);

        let svn_depth = match depth {
            Some(d) => py_depth_to_svn(d)?,
            None => subversion::Depth::Infinity,
        };

        let token = lock_token.unwrap_or("");
        reporter
            .set_path(path, rev, svn_depth, start_empty, token)
            .map_err(|e| svn_err_to_py(e))
    }

    /// Delete a path
    fn delete_path(&mut self, path: &str) -> PyResult<()> {
        if self.finished {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Reporter has already been finished",
            ));
        }

        let reporter = self.reporter.as_mut().ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Reporter has been consumed")
        })?;

        reporter.delete_path(path).map_err(|e| svn_err_to_py(e))
    }

    /// Link a path
    #[pyo3(signature = (path, url, revision, start_empty, lock_token=None, depth=None))]
    fn link_path(
        &mut self,
        path: &str,
        url: &str,
        revision: i64,
        start_empty: bool,
        lock_token: Option<&str>,
        depth: Option<i32>,
    ) -> PyResult<()> {
        if self.finished {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Reporter has already been finished",
            ));
        }

        let reporter = self.reporter.as_mut().ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Reporter has been consumed")
        })?;

        let rev = subvertpy_util::to_revnum_or_head(revision);

        let svn_depth = match depth {
            Some(d) => py_depth_to_svn(d)?,
            None => subversion::Depth::Infinity,
        };

        let token = lock_token.unwrap_or("");
        reporter
            .link_path(path, url, rev, svn_depth, start_empty, token)
            .map_err(|e| svn_err_to_py(e))
    }

    /// Finish the report
    fn finish(&mut self) -> PyResult<()> {
        if self.finished {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Reporter has already been finished",
            ));
        }

        let reporter = self.reporter.as_mut().ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Reporter has been consumed")
        })?;

        reporter.finish_report().map_err(|e| svn_err_to_py(e))?;

        self.finished = true;
        Ok(())
    }

    /// Abort the report
    fn abort(&mut self) -> PyResult<()> {
        if self.finished {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Reporter has already been finished",
            ));
        }

        let reporter = self.reporter.as_mut().ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Reporter has been consumed")
        })?;

        reporter.abort_report().map_err(|e| svn_err_to_py(e))?;

        self.finished = true;
        Ok(())
    }
}
