//! Property conversions between Python dicts and SVN/APR property hashes

use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};
use std::collections::HashMap;

/// Convert a Python dict to a HashMap of properties
///
/// Properties are String -> Vec<u8> (property values can be binary)
pub fn py_dict_to_props(dict: &Bound<PyDict>) -> PyResult<HashMap<String, Vec<u8>>> {
    let mut props = HashMap::new();

    for (key, value) in dict.iter() {
        let key_str: String = key.extract()?;

        // Property values can be strings or bytes
        let value_bytes = if let Ok(s) = value.extract::<String>() {
            s.into_bytes()
        } else if let Ok(bytes) = value.extract::<&[u8]>() {
            bytes.to_vec()
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(format!(
                "Property value for '{}' must be string or bytes",
                key_str
            )));
        };

        props.insert(key_str, value_bytes);
    }

    Ok(props)
}

/// Convert a HashMap of properties to a Python dict
///
/// Property values are always returned as bytes for compatibility with the old API
pub fn props_to_py_dict<'py>(
    py: Python<'py>,
    props: &HashMap<String, Vec<u8>>,
) -> PyResult<Bound<'py, PyDict>> {
    let dict = PyDict::new(py);

    for (key, value) in props {
        // Always return property values as bytes for API compatibility
        dict.set_item(key, PyBytes::new(py, value))?;
    }

    Ok(dict)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_py_dict_to_props() {
        pyo3::prepare_freethreaded_python();

        Python::with_gil(|py| {
            let dict = PyDict::new(py);
            dict.set_item("key1", "value1").unwrap();
            dict.set_item("key2", PyBytes::new(py, b"binary\x00value"))
                .unwrap();

            let props = py_dict_to_props(dict.bind(py)).unwrap();
            assert_eq!(props.get("key1").unwrap(), b"value1");
            assert_eq!(props.get("key2").unwrap(), b"binary\x00value");
        });
    }

    #[test]
    fn test_props_to_py_dict() {
        pyo3::prepare_freethreaded_python();

        Python::with_gil(|py| {
            let mut props = HashMap::new();
            props.insert("key1".to_string(), b"value1".to_vec());
            props.insert("key2".to_string(), b"binary\x00value".to_vec());

            let dict = props_to_py_dict(py, &props).unwrap();

            let val1: String = dict.get_item("key1").unwrap().unwrap().extract().unwrap();
            assert_eq!(val1, "value1");

            // Binary value should be bytes
            let val2 = dict.get_item("key2").unwrap().unwrap();
            assert!(val2.cast::<PyBytes>().is_ok());
        });
    }
}
