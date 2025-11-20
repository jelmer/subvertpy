use pyo3::prelude::*;

#[pyfunction]
fn uri_canonicalize(uri: &str) -> PyResult<String> {
    subversion::uri::canonicalize_uri(uri).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("Failed to canonicalize URI: {}", e))
    })
}

#[pyfunction]
fn dirent_canonicalize(dirent: &str) -> PyResult<String> {
    let path = std::path::Path::new(dirent);
    subversion::dirent::canonicalize_dirent(path)
        .map(|p| p.to_string_lossy().to_string())
        .map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!("Failed to canonicalize dirent: {}", e))
        })
}

#[pyfunction]
fn abspath(path: &str) -> PyResult<String> {
    let dirent = subversion::dirent::Dirent::new(path).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("Failed to create dirent: {}", e))
    })?;

    let absolute = dirent.get_absolute().map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("Failed to get absolute path: {}", e))
    })?;

    Ok(absolute.as_str().to_string())
}

#[pymodule]
fn subr(_py: Python, m: &Bound<PyModule>) -> PyResult<()> {
    m.add_wrapped(wrap_pyfunction!(uri_canonicalize))?;
    m.add_wrapped(wrap_pyfunction!(dirent_canonicalize))?;
    m.add_wrapped(wrap_pyfunction!(abspath))?;
    Ok(())
}
