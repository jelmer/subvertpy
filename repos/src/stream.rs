//! Stream Python bindings

use pyo3::prelude::*;

/// Subversion stream
#[pyclass(name = "Stream", unsendable)]
pub struct Stream {
    closed: bool,
}

#[pymethods]
impl Stream {
    /// Create a new empty stream
    #[new]
    fn init() -> PyResult<Self> {
        Ok(Self { closed: false })
    }

    /// Read from the stream
    #[pyo3(signature = (size=None))]
    #[allow(unused_variables)]
    fn read(&self, size: Option<usize>) -> PyResult<Vec<u8>> {
        if self.closed {
            return Ok(Vec::new());
        }
        // Empty stream always returns empty data
        Ok(Vec::new())
    }

    /// Write to the stream
    fn write(&mut self, data: &[u8]) -> PyResult<usize> {
        if self.closed {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "unable to write: stream already closed",
            ));
        }
        // Return the number of bytes "written"
        Ok(data.len())
    }

    /// Close the stream
    fn close(&mut self) -> PyResult<()> {
        self.closed = true;
        Ok(())
    }
}
