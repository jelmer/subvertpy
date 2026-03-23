//! Error handling utilities for converting between SVN errors and Python exceptions

use pyo3::prelude::*;
use subversion::Error as SvnError;

/// Convert an SVN error to a Python exception
///
/// This creates a `SubversionException` with the error code, message,
/// and any child errors from the SVN error chain.
pub fn svn_err_to_py(err: SvnError) -> PyErr {
    Python::attach(|py| {
        let message = err.message().unwrap_or("Unknown SVN error");
        let code = err.raw_apr_err();

        let module = py
            .import("subvertpy")
            .expect("Failed to import subvertpy module");

        // Look up a specific subclass for this error code, falling back to SubversionException
        let fallback = module
            .getattr("SubversionException")
            .expect("SubversionException not found");
        let exc_class = module
            .getattr("_error_code_to_class")
            .ok()
            .and_then(|mapping| mapping.get_item(code).ok())
            .unwrap_or(fallback);

        let exc_instance = exc_class
            .call1((message, code))
            .expect("Failed to create exception");
        PyErr::from_value(exc_instance)
    })
}

/// Convert a PyErr to an SVN error
///
/// This is useful when calling Python callbacks from SVN code.
pub fn py_err_to_svn(err: PyErr) -> SvnError<'static> {
    Python::attach(|py| {
        let message = format!("Python error: {}", err.value(py));
        SvnError::from_message(&message)
    })
}

/// Check if a Python callback raised an exception and convert to SVN error
pub fn check_py_err() -> Result<(), SvnError<'static>> {
    Python::attach(|py| {
        if let Some(err) = PyErr::take(py) {
            Err(py_err_to_svn(err))
        } else {
            Ok(())
        }
    })
}

/// Macro for running SVN operations with GIL release
///
/// This releases the GIL before running the SVN operation (which may
/// take a long time) and re-acquires it afterward.
#[macro_export]
macro_rules! run_svn {
    ($py:expr, $op:expr) => {{
        $py.allow_threads(|| $op)
            .map_err(|e| $crate::error::svn_err_to_py(e))
    }};
}

/// Macro for running SVN operations that return Result
#[macro_export]
macro_rules! run_svn_result {
    ($py:expr, $op:expr) => {{
        let result = $py.allow_threads(|| $op);
        result.map_err(|e| $crate::error::svn_err_to_py(e))?
    }};
}
