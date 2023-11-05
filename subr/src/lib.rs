use pyo3::prelude::*;

#[pyfunction]
fn uri_canonicalize(uri: &str) -> String {
    let uri = std::ffi::CString::new(uri).unwrap();
    subversion::uri::Uri::from_cstr(uri.as_c_str())
        .canonicalize()
        .to_string()
}

#[pyfunction]
fn dirent_canonicalize(dirent: &str) -> String {
    let dirent = std::ffi::CString::new(dirent).unwrap();
    subversion::dirent::Dirent::from_cstr(dirent.as_c_str())
        .canonicalize()
        .to_string()
}

#[pyfunction]
fn abspath(path: &str) -> PyResult<String> {
    let dirent = std::ffi::CString::new(path).unwrap();
    subversion::dirent::Dirent::from_cstr(dirent.as_c_str())
        .absolute()
        .map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "Failed to get absolute path of '{}': {}",
                path, e
            ))
        })
        .map(|d| d.to_string())
}

#[pymodule]
fn subr(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_wrapped(wrap_pyfunction!(uri_canonicalize))?;
    m.add_wrapped(wrap_pyfunction!(dirent_canonicalize))?;
    m.add_wrapped(wrap_pyfunction!(abspath))?;
    Ok(())
}
