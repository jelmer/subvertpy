//! Deprecated Adm (svn_wc_adm_access_t) Python bindings.

use pyo3::prelude::*;
use subvertpy_util::error::svn_err_to_py;

/// Deprecated working copy administrative access baton.
///
/// Wraps the deprecated ``svn_wc_adm_access_t`` based API.
/// New code should use :class:`Context` instead.
#[pyclass(name = "Adm", unsendable)]
pub struct Adm {
    #[allow(deprecated)]
    pub(crate) inner: subversion::wc::Adm,
}

#[pymethods]
#[allow(deprecated)]
impl Adm {
    /// Open an access baton for a working copy directory.
    ///
    /// :param associated: Associated access baton (ignored, for backwards compat).
    /// :param path: Path to the working copy directory.
    /// :param write_lock: If True, acquire a write lock.
    /// :param depth: Levels to lock: 0 = just this dir, -1 = infinite.
    #[new]
    #[pyo3(signature = (associated=None, path=None, write_lock=false, depth=0))]
    fn init(
        associated: Option<&Bound<PyAny>>,
        path: Option<&Bound<PyAny>>,
        write_lock: bool,
        depth: i32,
    ) -> PyResult<Self> {
        // Support both Adm(path, write_lock=...) and Adm(None, path, write_lock=...)
        let actual_path = if let Some(p) = path {
            p
        } else if let Some(a) = associated {
            if a.is_none() {
                return Err(pyo3::exceptions::PyTypeError::new_err(
                    "Adm() requires a path argument",
                ));
            }
            a
        } else {
            return Err(pyo3::exceptions::PyTypeError::new_err(
                "Adm() requires a path argument",
            ));
        };
        let path_str = subvertpy_util::py_to_svn_abspath(actual_path)?;
        let adm = subversion::wc::Adm::open(&path_str, write_lock, depth).map_err(svn_err_to_py)?;
        Ok(Self { inner: adm })
    }

    /// Return the path this access baton is for.
    fn access_path(&self) -> PyResult<String> {
        Ok(self.inner.access_path().to_string())
    }

    /// Check if this access baton is locked.
    fn is_locked(&self) -> PyResult<bool> {
        Ok(self.inner.is_locked())
    }

    /// Close the access baton, releasing all resources and locks.
    fn close(&mut self) {
        self.inner.close();
    }

    /// Add a file or directory to version control.
    #[pyo3(signature = (path, copyfrom_url=None, copyfrom_rev=-1))]
    fn add(
        &self,
        path: &Bound<PyAny>,
        copyfrom_url: Option<&str>,
        copyfrom_rev: i64,
    ) -> PyResult<()> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        let rev = subvertpy_util::to_revnum(copyfrom_rev);
        self.inner
            .add(&path_str, copyfrom_url, rev)
            .map_err(svn_err_to_py)
    }

    /// Delete a file or directory from version control.
    #[pyo3(signature = (path, keep_local=false))]
    fn delete(&self, path: &Bound<PyAny>, keep_local: bool) -> PyResult<()> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        self.inner
            .delete(&path_str, keep_local)
            .map_err(svn_err_to_py)
    }

    /// Copy a file or directory in the working copy.
    fn copy(&self, src: &Bound<PyAny>, dst_basename: &str) -> PyResult<()> {
        let src_str = subvertpy_util::py_to_svn_abspath(src)?;
        self.inner
            .copy(&src_str, dst_basename)
            .map_err(svn_err_to_py)
    }

    /// Set a property on a path.
    fn prop_set(&self, name: &str, value: Option<&[u8]>, path: &Bound<PyAny>) -> PyResult<()> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        self.inner
            .prop_set(name, value, &path_str)
            .map_err(svn_err_to_py)
    }

    /// Get a property on a path.
    fn prop_get(
        &self,
        py: Python<'_>,
        name: &str,
        path: &Bound<PyAny>,
    ) -> PyResult<Option<Py<PyAny>>> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        let val = self
            .inner
            .prop_get(name, &path_str)
            .map_err(svn_err_to_py)?;
        match val {
            None => Ok(None),
            Some(v) => Ok(Some(pyo3::types::PyBytes::new(py, &v).into_any().unbind())),
        }
    }

    /// Check if a path has a binary property.
    fn has_binary_prop(&self, path: &Bound<PyAny>) -> PyResult<bool> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        self.inner.has_binary_prop(&path_str).map_err(svn_err_to_py)
    }

    /// Check if the text content of a path has been modified.
    fn text_modified(&self, path: &Bound<PyAny>, force_comparison: bool) -> PyResult<bool> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        self.inner
            .text_modified(&path_str, force_comparison)
            .map_err(svn_err_to_py)
    }

    /// Check if properties of a path have been modified.
    fn props_modified(&self, path: &Bound<PyAny>) -> PyResult<bool> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        self.inner.props_modified(&path_str).map_err(svn_err_to_py)
    }

    /// Check if a path is the root of a working copy.
    fn is_wc_root(&self, path: &Bound<PyAny>) -> PyResult<bool> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        self.inner.is_wc_root(&path_str).map_err(svn_err_to_py)
    }

    /// Check if a path is conflicted.
    fn conflicted(&self, path: &Bound<PyAny>) -> PyResult<(bool, bool, bool)> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        self.inner.conflicted(&path_str).map_err(svn_err_to_py)
    }

    /// Queue a path for post-commit processing using this access baton.
    #[pyo3(signature = (path, queue, recurse=false, remove_lock=false, remove_changelist=false, md5_digest=None))]
    fn queue_committed(
        &self,
        path: &Bound<PyAny>,
        queue: &mut crate::committed::CommittedQueue,
        recurse: bool,
        remove_lock: bool,
        remove_changelist: bool,
        md5_digest: Option<&[u8]>,
    ) -> PyResult<()> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        let digest: Option<[u8; 16]> = md5_digest.map(|d| {
            let mut arr = [0u8; 16];
            arr.copy_from_slice(&d[..16]);
            arr
        });
        self.inner
            .queue_committed(
                &path_str,
                &mut queue.inner,
                recurse,
                remove_lock,
                remove_changelist,
                digest.as_ref(),
            )
            .map_err(svn_err_to_py)
    }

    /// Process the committed queue using this access baton.
    fn process_committed_queue(
        &self,
        queue: &mut crate::committed::CommittedQueue,
        revnum: i64,
        date: &str,
        author: &str,
    ) -> PyResult<()> {
        self.inner
            .process_committed_queue(
                &mut queue.inner,
                subvertpy_util::to_revnum(revnum).unwrap_or(subversion::Revnum::invalid()),
                Some(date),
                Some(author),
            )
            .map_err(svn_err_to_py)
    }

    fn __enter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __exit__(
        &mut self,
        _exc_type: Option<&Bound<PyAny>>,
        _exc_val: Option<&Bound<PyAny>>,
        _exc_tb: Option<&Bound<PyAny>>,
    ) -> PyResult<bool> {
        self.inner.close();
        Ok(false)
    }
}
