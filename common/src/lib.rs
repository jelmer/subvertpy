use pyo3::import_exception;
use pyo3::prelude::*;

import_exception!(subvertpy, SubversionException);

pub fn map_svn_error_to_py_err(err: subversion::Error) -> PyErr {
    let message = err.best_message();
    let child = err.child().map(|e| map_svn_error_to_py_err(e));
    let apr_err = Into::<u32>::into(err.apr_err());
    SubversionException::new_err((
        message,
        apr_err,
        child,
        err.location().map(|(f, l)| (f.to_string(), l)),
    ))
}

pub fn map_py_object_to_svn_err(py_err: &Bound<PyAny>) -> subversion::Error {
    if let Ok(subversion_exception) = py_err.downcast::<SubversionException>() {
        let (message, apr_err, child, _location) = subversion_exception
            .getattr("args")
            .unwrap()
            .extract::<(String, u32, Option<Bound<PyAny>>, Option<(String, u32)>)>()
            .unwrap();
        subversion::Error::new(
            apr::Status::from(apr_err),
            child.map(|py_err: pyo3::Bound<'_, pyo3::PyAny>| map_py_object_to_svn_err(&py_err)),
            &message,
        )
    } else {
        subversion::Error::new(apr::Status::General, None, &format!("{}", py_err))
    }
}

pub fn map_py_err_to_svn_err(py_err: PyErr) -> subversion::Error {
    Python::with_gil(|py| map_py_object_to_svn_err(py_err.value_bound(py)))
}

pub fn stream_from_object(py: Python, obj: PyObject) -> Result<subversion::io::Stream, PyErr> {
    if let Ok(bytes) = obj.extract::<Vec<u8>>(py) {
        Ok(subversion::io::Stream::from(bytes.as_slice()))
    } else {
        Err(PyErr::new::<SubversionException, _>(
            "Invalid stream object",
        ))
    }
}
