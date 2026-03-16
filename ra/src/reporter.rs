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
}

impl Reporter {
    pub fn new(reporter: Box<dyn subversion::ra::Reporter + Send>) -> Self {
        Self {
            reporter: Some(reporter),
            finished: false,
            _session: None,
            _editor: None,
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
        }
    }
}

#[pymethods]
impl Reporter {
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

        let rev = subvertpy_util::to_revnum(revision)
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Invalid revision"))?;

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

        let rev = subvertpy_util::to_revnum(revision)
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Invalid revision"))?;

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
