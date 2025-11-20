//! Filesystem root Python bindings

use pyo3::prelude::*;
use pyo3::types::PyDict;
use subvertpy_util::error::svn_err_to_py;

/// Normalize a path for filesystem operations.
///
/// The subversion filesystem requires absolute paths (starting with '/').
/// This function prepends '/' to relative paths, while leaving empty
/// strings and already-absolute paths unchanged.
fn normalize_fs_path(path: &str) -> String {
    if path.is_empty() || path.starts_with('/') {
        path.to_string()
    } else {
        format!("/{}", path)
    }
}

/// Subversion filesystem root
#[pyclass(name = "FileSystemRoot", unsendable)]
pub struct FileSystemRoot {
    root: subversion::fs::Root<'static>,
}

impl FileSystemRoot {
    pub fn new<'a>(root: subversion::fs::Root<'a>) -> Self {
        // SAFETY: The caller must ensure the root's source outlives this FileSystemRoot.
        // This is necessary because PyO3 pyclass structs cannot have lifetime parameters.
        let root: subversion::fs::Root<'static> = unsafe { std::mem::transmute(root) };
        Self { root }
    }
}

#[pymethods]
impl FileSystemRoot {
    /// Get paths that changed in this revision
    fn paths_changed(&self) -> PyResult<pyo3::Py<pyo3::PyAny>> {
        let changes = self.root.paths_changed().map_err(|e| svn_err_to_py(e))?;

        Python::attach(|py| {
            let dict = PyDict::new(py);
            for (path, change) in changes {
                let change_dict = PyDict::new(py);
                change_dict.set_item("change_kind", format!("{:?}", change.change_kind()))?;
                change_dict.set_item("text_mod", change.text_modified())?;
                change_dict.set_item("prop_mod", change.props_modified())?;
                let node_kind = change.node_kind();
                change_dict.set_item("node_kind", format!("{:?}", node_kind))?;

                dict.set_item(path.to_string(), change_dict)?;
            }
            Ok(dict.into_any().unbind())
        })
    }

    /// Check if a path is a directory
    fn is_dir(&self, path: &str) -> PyResult<bool> {
        let normalized = normalize_fs_path(path);
        self.root
            .is_dir(normalized.as_str())
            .map_err(|e| svn_err_to_py(e))
    }

    /// Check if a path is a file
    fn is_file(&self, path: &str) -> PyResult<bool> {
        let normalized = normalize_fs_path(path);
        self.root
            .is_file(normalized.as_str())
            .map_err(|e| svn_err_to_py(e))
    }

    /// Get the length of a file
    fn file_length(&self, path: &str) -> PyResult<i64> {
        let normalized = normalize_fs_path(path);
        let length = self
            .root
            .file_length(normalized.as_str())
            .map_err(|e| svn_err_to_py(e))?;
        Ok(length)
    }

    /// Get properties for a node (file or directory)
    fn proplist(&self, path: &str) -> PyResult<pyo3::Py<pyo3::PyAny>> {
        let normalized = normalize_fs_path(path);
        let props = self
            .root
            .proplist(normalized.as_str())
            .map_err(|e| svn_err_to_py(e))?;

        Python::attach(|py| {
            subvertpy_util::properties::props_to_py_dict(py, &props).map(|d| d.into_any().unbind())
        })
    }

    /// Get properties for a node (file or directory) - alias for proplist
    fn node_proplist(&self, path: &str) -> PyResult<pyo3::Py<pyo3::PyAny>> {
        self.proplist(path)
    }

    /// Get the checksum of a file
    #[pyo3(signature = (path, kind=0, force=true))]
    fn file_checksum(&self, path: &str, kind: i32, force: bool) -> PyResult<Option<String>> {
        let normalized = normalize_fs_path(path);
        let checksum_kind = match kind {
            0 => subversion::ChecksumKind::MD5,
            1 => subversion::ChecksumKind::SHA1,
            _ => {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                    "Invalid checksum kind: {}",
                    kind
                )))
            }
        };

        let checksum = self
            .root
            .file_checksum_force(normalized.as_str(), checksum_kind, force)
            .map_err(|e| svn_err_to_py(e))?;

        match checksum {
            Some(cs) => {
                let pool = apr::Pool::new();
                Ok(Some(cs.to_hex(&pool)))
            }
            None => Ok(None),
        }
    }

    /// Get file contents as a BytesIO-like stream
    fn file_content(&self, path: &str) -> PyResult<pyo3::Py<pyo3::PyAny>> {
        let normalized = normalize_fs_path(path);
        let mut stream = self
            .root
            .file_contents(normalized.as_str())
            .map_err(|e| svn_err_to_py(e))?;

        let mut contents = Vec::new();
        std::io::Read::read_to_end(&mut stream, &mut contents).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyIOError, _>(format!(
                "Failed to read file contents: {}",
                e
            ))
        })?;

        Python::attach(|py| {
            let io_module = py.import("io")?;
            let bytes_io = io_module.call_method1("BytesIO", (contents.as_slice(),))?;
            Ok(bytes_io.unbind())
        })
    }
}
