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
    /// :param path: Path to the working copy directory.
    /// :param write_lock: If True, acquire a write lock.
    /// :param depth: Levels to lock: 0 = just this dir, -1 = infinite.
    #[new]
    #[pyo3(signature = (path, write_lock=false, depth=0))]
    fn init(path: &Bound<PyAny>, write_lock: bool, depth: i32) -> PyResult<Self> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        let adm = subversion::wc::Adm::open(&path_str, write_lock, depth).map_err(svn_err_to_py)?;
        Ok(Self { inner: adm })
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
    ///
    /// Calls the deprecated ``svn_wc_process_committed_queue`` which takes
    /// an ``svn_wc_adm_access_t`` rather than an ``svn_wc_context_t``.
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
        // Drop closes the adm baton automatically
        Ok(false)
    }
}
