//! Status Python bindings

use pyo3::prelude::*;

/// Working copy status for a node.
#[pyclass(name = "Status", unsendable)]
pub struct Status {
    inner: subversion::wc::Status<'static>,
}

#[pymethods]
impl Status {
    #[getter]
    fn node_status(&self) -> u32 {
        self.inner.node_status() as u32
    }

    #[getter]
    fn text_status(&self) -> u32 {
        self.inner.text_status() as u32
    }

    #[getter]
    fn prop_status(&self) -> u32 {
        self.inner.prop_status() as u32
    }

    #[getter]
    fn copied(&self) -> bool {
        self.inner.copied()
    }

    #[getter]
    fn switched(&self) -> bool {
        self.inner.switched()
    }

    #[getter]
    fn locked(&self) -> bool {
        self.inner.locked()
    }

    #[getter]
    fn revision(&self) -> i64 {
        self.inner.revision().as_i64()
    }

    #[getter]
    fn changed_rev(&self) -> i64 {
        self.inner.changed_rev().as_i64()
    }

    #[getter]
    fn kind(&self) -> i32 {
        self.inner.kind()
    }

    #[getter]
    fn depth(&self) -> i32 {
        self.inner.depth()
    }

    #[getter]
    fn filesize(&self) -> i64 {
        self.inner.filesize()
    }

    #[getter]
    fn versioned(&self) -> bool {
        self.inner.versioned()
    }

    #[getter]
    fn repos_uuid(&self) -> Option<String> {
        self.inner.repos_uuid()
    }

    #[getter]
    fn repos_root_url(&self) -> Option<String> {
        self.inner.repos_root_url()
    }

    #[getter]
    fn repos_relpath(&self) -> Option<String> {
        self.inner.repos_relpath()
    }
}

impl Status {
    /// Wrap an owned SVN Status.
    pub fn from_owned(s: subversion::wc::Status<'static>) -> Self {
        Self { inner: s }
    }

    /// Dup a borrowed SVN Status into an owned copy.
    pub fn from_svn_status(s: &subversion::wc::Status<'_>) -> Self {
        Self { inner: s.dup() }
    }
}
