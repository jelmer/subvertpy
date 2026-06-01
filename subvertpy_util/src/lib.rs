//! Shared utilities for subvertpy Rust modules
//!
//! This crate provides common functionality used across all subvertpy modules:
//! - Error handling and conversion between SVN errors and Python exceptions
//! - Type conversions between Python and SVN/APR types
//! - Property dictionary conversions

use pyo3::prelude::*;
use pyo3::types::PyList;
use std::path::Path;

/// Re-export key types for convenience
pub use apr;
pub use pyo3;
pub use subversion;

pub mod auth;
pub mod editor;
pub mod error;
pub mod io;
pub mod properties;

/// Convert a Python revision number (i64) to an Option<Revnum>.
/// Negative values are treated as invalid (None).
pub fn to_revnum(rev: i64) -> Option<subversion::Revnum> {
    if rev < 0 {
        None
    } else {
        Some(subversion::Revnum::from(rev as u64))
    }
}

/// Convert a Python revision number (i64) to a Revnum.
/// Negative values (typically -1) are mapped to Revnum::invalid(),
/// which the SVN C API interprets as HEAD.
pub fn to_revnum_or_head(rev: i64) -> subversion::Revnum {
    if rev < 0 {
        subversion::Revnum::invalid()
    } else {
        subversion::Revnum::from(rev as u64)
    }
}

/// Canonicalize a string as an SVN relative path.
pub fn to_relpath(path: &str) -> PyResult<subversion::ra::RelPath> {
    subversion::ra::RelPath::canonicalize(path).map_err(|e| error::svn_err_to_py(e))
}

/// Convert a Python object to an SVN path or URL
///
/// This handles both filesystem paths (dirents) and URLs (URIs),
/// automatically detecting which one it is and canonicalizing appropriately.
pub fn py_to_svn_path_or_url(obj: &Bound<PyAny>) -> PyResult<String> {
    let path_str = py_to_svn_string(obj)?;

    // Check if it's a URL or a path
    if is_url(&path_str) {
        subversion::uri::canonicalize_uri(&path_str).map_err(|e| error::svn_err_to_py(e))
    } else {
        subversion::dirent::canonicalize_dirent(Path::new(&path_str))
            .map(|p| p.to_string_lossy().to_string())
            .map_err(|e| error::svn_err_to_py(e))
    }
}

/// Check if a string looks like a URL
fn is_url(s: &str) -> bool {
    // Simple heuristic: URLs have a scheme followed by ://
    s.contains("://") || s.starts_with("file:")
}

/// Convert a Python object to an SVN absolute path (dirent)
pub fn py_to_svn_abspath(obj: &Bound<PyAny>) -> PyResult<String> {
    let path_str = py_to_svn_string(obj)?;

    // Convert to absolute path if needed
    let abs_path = if Path::new(&path_str).is_absolute() {
        Path::new(&path_str).to_path_buf()
    } else {
        std::fs::canonicalize(&path_str).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyOSError, _>(format!("Cannot get absolute path: {}", e))
        })?
    };

    // Canonicalize using SVN
    subversion::dirent::canonicalize_dirent(&abs_path)
        .map(|p| p.to_string_lossy().to_string())
        .map_err(|e| error::svn_err_to_py(e))
}

/// Convert a Python object to an SVN dirent (filesystem path)
pub fn py_to_svn_dirent(obj: &Bound<PyAny>) -> PyResult<String> {
    let path_str = py_to_svn_string(obj)?;

    subversion::dirent::canonicalize_dirent(Path::new(&path_str))
        .map(|p| p.to_string_lossy().to_string())
        .map_err(|e| error::svn_err_to_py(e))
}

/// Convert a Python object to an SVN URI
pub fn py_to_svn_uri(obj: &Bound<PyAny>) -> PyResult<String> {
    let uri_str = py_to_svn_string(obj)?;

    subversion::uri::canonicalize_uri(&uri_str).map_err(|e| error::svn_err_to_py(e))
}

/// Convert a Python string to a plain string (for SVN)
pub fn py_to_svn_string(obj: &Bound<PyAny>) -> PyResult<String> {
    if let Ok(s) = obj.extract::<String>() {
        Ok(s)
    } else if let Ok(bytes) = obj.extract::<&[u8]>() {
        String::from_utf8(bytes.to_vec()).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid UTF-8: {}", e))
        })
    } else {
        Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
            "Expected string or bytes",
        ))
    }
}

/// Convert a Python list of strings to a Vec<String>
pub fn py_list_to_vec_string(list: &Bound<PyList>) -> PyResult<Vec<String>> {
    let mut result = Vec::new();
    for item in list.iter() {
        result.push(py_to_svn_string(&item)?);
    }
    Ok(result)
}

/// Convert a Python list of revision numbers to Vec<i64>
pub fn py_list_to_vec_revnum(list: &Bound<PyList>) -> PyResult<Vec<i64>> {
    let mut result = Vec::new();
    for item in list.iter() {
        let revnum: i64 = item.extract()?;
        result.push(revnum);
    }
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;
    use pyo3::types::{PyBytes, PyList, PyString};

    #[test]
    fn test_is_url() {
        assert!(is_url("http://example.com"));
        assert!(is_url("https://example.com"));
        assert!(is_url("svn://example.com"));
        assert!(is_url("file:///path/to/repo"));
        assert!(!is_url("/path/to/dir"));
        assert!(!is_url("relative/path"));
    }

    #[test]
    fn test_is_url_bare_file_scheme() {
        // file: without :// still counts as a URL
        assert!(is_url("file:relative"));
    }

    #[test]
    fn test_is_url_empty() {
        assert!(!is_url(""));
    }

    #[test]
    fn test_to_revnum_negative() {
        assert_eq!(to_revnum(-1), None);
        assert_eq!(to_revnum(-100), None);
    }

    #[test]
    fn test_to_revnum_zero() {
        assert_eq!(to_revnum(0), Some(subversion::Revnum::from(0u64)));
    }

    #[test]
    fn test_to_revnum_positive() {
        assert_eq!(to_revnum(42), Some(subversion::Revnum::from(42u64)));
    }

    #[test]
    fn test_to_revnum_or_head_negative() {
        assert_eq!(to_revnum_or_head(-1), subversion::Revnum::invalid());
    }

    #[test]
    fn test_to_revnum_or_head_positive() {
        assert_eq!(to_revnum_or_head(7), subversion::Revnum::from(7u64));
    }

    #[test]
    fn test_to_revnum_or_head_zero() {
        assert_eq!(to_revnum_or_head(0), subversion::Revnum::from(0u64));
    }

    #[test]
    fn test_py_to_svn_string_from_str() {
        Python::initialize();
        Python::attach(|py| {
            let obj = PyString::new(py, "hello").into_any();
            assert_eq!(py_to_svn_string(&obj).unwrap(), "hello");
        });
    }

    #[test]
    fn test_py_to_svn_string_from_bytes() {
        Python::initialize();
        Python::attach(|py| {
            let obj = PyBytes::new(py, b"world").into_any();
            assert_eq!(py_to_svn_string(&obj).unwrap(), "world");
        });
    }

    #[test]
    fn test_py_to_svn_string_invalid_utf8() {
        Python::initialize();
        Python::attach(|py| {
            let obj = PyBytes::new(py, b"\xff\xfe").into_any();
            assert!(py_to_svn_string(&obj).is_err());
        });
    }

    #[test]
    fn test_py_to_svn_string_wrong_type() {
        Python::initialize();
        Python::attach(|py| {
            let obj = 42i64.into_pyobject(py).unwrap().into_any();
            assert!(py_to_svn_string(&obj).is_err());
        });
    }

    #[test]
    fn test_py_list_to_vec_string() {
        Python::initialize();
        Python::attach(|py| {
            let list = PyList::new(py, ["a", "b", "c"]).unwrap();
            assert_eq!(
                py_list_to_vec_string(&list).unwrap(),
                vec!["a".to_string(), "b".to_string(), "c".to_string()]
            );
        });
    }

    #[test]
    fn test_py_list_to_vec_string_empty() {
        Python::initialize();
        Python::attach(|py| {
            let list = PyList::empty(py);
            assert_eq!(py_list_to_vec_string(&list).unwrap(), Vec::<String>::new());
        });
    }

    #[test]
    fn test_py_list_to_vec_revnum() {
        Python::initialize();
        Python::attach(|py| {
            let list = PyList::new(py, [1i64, 2, 3]).unwrap();
            assert_eq!(py_list_to_vec_revnum(&list).unwrap(), vec![1, 2, 3]);
        });
    }

    #[test]
    fn test_py_list_to_vec_revnum_wrong_type() {
        Python::initialize();
        Python::attach(|py| {
            let list = PyList::new(py, ["not a number"]).unwrap();
            assert!(py_list_to_vec_revnum(&list).is_err());
        });
    }
}
