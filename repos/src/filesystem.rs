//! Filesystem Python bindings

use pyo3::prelude::*;
use subvertpy_util::error::svn_err_to_py;

/// Subversion filesystem
#[pyclass(name = "FileSystem", unsendable)]
pub struct FileSystem {
    fs: subversion::fs::Fs<'static>,
}

impl FileSystem {
    pub fn new(fs: subversion::fs::Fs<'static>) -> Self {
        Self { fs }
    }
}

#[pymethods]
impl FileSystem {
    /// Get the filesystem UUID
    fn get_uuid(&self) -> PyResult<String> {
        self.fs.get_uuid().map_err(|e| svn_err_to_py(e))
    }

    /// Get the youngest (most recent) revision number
    fn get_youngest_revision(&self) -> PyResult<i64> {
        let revnum = self.fs.youngest_revision().map_err(|e| svn_err_to_py(e))?;
        Ok(revnum.as_u64() as i64)
    }

    /// Get a revision root for a specific revision
    fn get_revision_root(&self, revnum: i64) -> PyResult<super::fsroot::FileSystemRoot> {
        let rev = subvertpy_util::to_revnum_or_head(revnum);

        let root = self.fs.revision_root(rev).map_err(|e| svn_err_to_py(e))?;

        Ok(super::fsroot::FileSystemRoot::new(root))
    }

    /// Get revision properties for a specific revision
    fn get_revision_proplist(&self, revnum: i64) -> PyResult<pyo3::Py<pyo3::PyAny>> {
        let rev = subvertpy_util::to_revnum_or_head(revnum);

        let props = self
            .fs
            .revision_proplist(rev, false)
            .map_err(|e| svn_err_to_py(e))?;

        Python::attach(|py| {
            subvertpy_util::properties::props_to_py_dict(py, &props).map(|d| d.into_any().unbind())
        })
    }

    /// Alias for get_revision_proplist (C API compatibility)
    fn revision_proplist(&self, revnum: i64) -> PyResult<pyo3::Py<pyo3::PyAny>> {
        self.get_revision_proplist(revnum)
    }

    /// Alias for get_revision_root (C API compatibility)
    fn revision_root(&self, revnum: i64) -> PyResult<super::fsroot::FileSystemRoot> {
        self.get_revision_root(revnum)
    }

    /// Alias for get_youngest_revision (C API compatibility)
    fn youngest_revision(&self) -> PyResult<i64> {
        self.get_youngest_revision()
    }
}
