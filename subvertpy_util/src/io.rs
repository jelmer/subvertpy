//! I/O utilities for converting between Python file-like objects and SVN streams

use pyo3::prelude::*;

/// Convert a Python file-like object to a subversion Stream
pub fn py_to_stream(_py: Python, py_obj: &Bound<PyAny>) -> PyResult<subversion::io::Stream> {
    // Use pyo3-filelike to wrap the Python object
    let reader = pyo3_filelike::PyBinaryFile::from(py_obj.clone().unbind());

    // Create a subversion Stream from the reader
    subversion::io::Stream::from_backend(reader).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to create stream: {}", e))
    })
}
