//! Lock Python bindings

use pyo3::prelude::*;

/// Represents a lock in the working copy.
#[pyclass(name = "Lock", unsendable)]
pub struct Lock {
    path: Option<String>,
    token: Option<Vec<u8>>,
}

#[pymethods]
impl Lock {
    #[new]
    #[pyo3(signature = (token=None))]
    fn init(token: Option<&Bound<PyAny>>) -> PyResult<Self> {
        let token = match token {
            Some(obj) => {
                if let Ok(bytes) = obj.extract::<Vec<u8>>() {
                    Some(bytes)
                } else if let Ok(s) = obj.extract::<String>() {
                    Some(s.into_bytes())
                } else {
                    return Err(pyo3::exceptions::PyTypeError::new_err(
                        "Expected bytes or str for token",
                    ));
                }
            }
            None => None,
        };
        Ok(Self { path: None, token })
    }

    /// Get the lock path as a string.
    #[getter]
    fn get_path(&self) -> Option<&str> {
        self.path.as_deref()
    }

    /// Set the lock path from bytes or str.
    #[setter]
    fn set_path(&mut self, value: &Bound<PyAny>) -> PyResult<()> {
        if value.is_none() {
            self.path = None;
        } else {
            self.path = Some(subvertpy_util::py_to_svn_string(value)?);
        }
        Ok(())
    }

    /// Get the lock token as bytes.
    #[getter]
    fn get_token(&self) -> Option<&[u8]> {
        self.token.as_deref()
    }

    /// Set the lock token from bytes or str.
    #[setter]
    fn set_token(&mut self, value: &Bound<PyAny>) -> PyResult<()> {
        if value.is_none() {
            self.token = None;
        } else if let Ok(bytes) = value.extract::<Vec<u8>>() {
            self.token = Some(bytes);
        } else if let Ok(s) = value.extract::<String>() {
            self.token = Some(s.into_bytes());
        } else {
            return Err(pyo3::exceptions::PyTypeError::new_err(
                "Expected bytes or str for token",
            ));
        }
        Ok(())
    }
}

impl Lock {
    /// Convert to a subversion::wc::Lock for use with Context methods.
    /// Returns None if neither path nor token is set.
    pub fn to_svn_lock(&self) -> Option<(Option<&str>, Option<&[u8]>)> {
        Some((self.path.as_deref(), self.token.as_deref()))
    }
}
