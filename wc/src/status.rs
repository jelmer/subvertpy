//! Status Python bindings

use pyo3::prelude::*;

/// Working copy status for a node.
#[pyclass(name = "Status", unsendable)]
pub struct Status {
    #[pyo3(get)]
    pub kind: i32,
    #[pyo3(get)]
    pub depth: i32,
    #[pyo3(get)]
    pub filesize: i64,
    #[pyo3(get)]
    pub versioned: bool,
    #[pyo3(get)]
    pub repos_uuid: Option<String>,
    #[pyo3(get)]
    pub repos_root_url: Option<String>,
    #[pyo3(get)]
    pub repos_relpath: Option<String>,
}

impl Status {
    /// Create a Status from a subversion::wc::Status reference.
    ///
    /// Copies all fields since the SVN Status borrows from an APR pool.
    pub fn from_svn_status(s: &subversion::wc::Status<'_>) -> Self {
        Self {
            kind: s.kind(),
            depth: s.depth(),
            filesize: s.filesize(),
            versioned: s.versioned(),
            repos_uuid: s.repos_uuid(),
            repos_root_url: s.repos_root_url(),
            repos_relpath: s.repos_relpath(),
        }
    }
}
