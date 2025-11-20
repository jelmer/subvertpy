//! CommittedQueue Python bindings

use pyo3::prelude::*;
use subvertpy_util::error::svn_err_to_py;

/// Queue for post-commit processing.
#[pyclass(name = "CommittedQueue", unsendable)]
pub struct CommittedQueue {
    pub(crate) inner: subversion::wc::CommittedQueue,
}

#[pymethods]
impl CommittedQueue {
    #[new]
    fn init() -> Self {
        Self {
            inner: subversion::wc::CommittedQueue::new(),
        }
    }

    fn __repr__(&self) -> String {
        "<wc.CommittedQueue>".to_string()
    }

    /// Queue a path for post-commit processing.
    #[pyo3(signature = (path, adm, recurse=false, wcprop_changes=None, remove_lock=false, remove_changelist=false, md5_digest=None, sha1_digest=None))]
    fn queue(
        &mut self,
        path: &Bound<PyAny>,
        adm: &mut crate::context::Context,
        recurse: bool,
        wcprop_changes: Option<&Bound<PyAny>>,
        remove_lock: bool,
        remove_changelist: bool,
        md5_digest: Option<&[u8]>,
        sha1_digest: Option<&[u8]>,
    ) -> PyResult<()> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        let path = std::path::Path::new(&path_str);

        // Convert Python dict of {str: bytes|None} to Vec<PropChange>
        let prop_changes = if let Some(dict) = wcprop_changes {
            let dict: &Bound<pyo3::types::PyDict> = dict.cast()?;
            let mut changes = Vec::with_capacity(dict.len());
            for (key, val) in dict.iter() {
                let name: String = key.extract()?;
                let value: Option<Vec<u8>> = if val.is_none() {
                    None
                } else {
                    Some(val.extract::<Vec<u8>>()?)
                };
                changes.push(subversion::wc::PropChange { name, value });
            }
            Some(changes)
        } else {
            None
        };

        // Build the checksum if provided (sha1 preferred, md5 as fallback)
        let pool = apr::Pool::new();
        let checksum = if let Some(digest) = sha1_digest {
            Some(
                subversion::Checksum::from_digest(subversion::ChecksumKind::SHA1, digest, &pool)
                    .map_err(svn_err_to_py)?,
            )
        } else if let Some(digest) = md5_digest {
            Some(
                subversion::Checksum::from_digest(subversion::ChecksumKind::MD5, digest, &pool)
                    .map_err(svn_err_to_py)?,
            )
        } else {
            None
        };

        adm.inner
            .queue_committed(
                path,
                recurse,
                true, // is_committed
                &mut self.inner,
                prop_changes.as_deref(),
                remove_lock,
                remove_changelist,
                checksum.as_ref(),
            )
            .map_err(svn_err_to_py)
    }
}
