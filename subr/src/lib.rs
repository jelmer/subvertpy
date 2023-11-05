use pyo3::prelude::*;

#[pyfunction]
fn uri_canonicalize(uri: &str) -> String {
    subversion::uri::Uri::new(uri).canonicalize().to_string()
}

#[pyfunction]
fn dirent_canonicalize(dirent: &str) -> String {
    subversion::dirent::Dirent::new(dirent)
        .canonicalize()
        .to_string()
}

#[pyfunction]
fn abspath(path: &str) -> PyResult<String> {
    subversion::dirent::Dirent::new(path)
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
