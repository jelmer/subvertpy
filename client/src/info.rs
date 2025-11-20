//! Info types

use pyo3::prelude::*;

/// Client info object
#[pyclass(name = "Info", unsendable)]
pub struct Info {
    #[pyo3(get)]
    pub url: String,
    #[pyo3(get)]
    pub revision: i64,
    #[pyo3(get)]
    pub kind: String,
    #[pyo3(get)]
    pub repos_root_url: String,
    #[pyo3(get)]
    pub repos_uuid: String,
    #[pyo3(get)]
    pub last_changed_rev: i64,
    #[pyo3(get)]
    pub last_changed_date: String,
    #[pyo3(get)]
    pub last_changed_author: String,
    #[pyo3(get)]
    pub size: i64,
    #[pyo3(get)]
    pub wc_info: Option<Py<WCInfo>>,
}

#[pymethods]
impl Info {
    fn __repr__(&self) -> PyResult<String> {
        Ok(format!("<Info url={} rev={}>", self.url, self.revision))
    }
}

/// Working copy info object
#[pyclass(name = "WCInfo", unsendable)]
pub struct WCInfo {
    inner: subversion::client::OwnedWcInfo,
}

#[pymethods]
impl WCInfo {
    #[getter]
    fn schedule(&self) -> i32 {
        self.inner.schedule() as i32
    }

    #[getter]
    fn copyfrom_url(&self) -> Option<&str> {
        self.inner.copyfrom_url()
    }

    #[getter]
    fn copyfrom_rev(&self) -> i64 {
        self.inner.copyfrom_rev().map(|r| r.as_i64()).unwrap_or(-1)
    }

    #[getter]
    fn changelist(&self) -> Option<&str> {
        self.inner.changelist()
    }

    #[getter]
    fn recorded_size(&self) -> i64 {
        self.inner.recorded_size()
    }

    #[getter]
    fn recorded_time(&self) -> i64 {
        self.inner.recorded_time().as_micros()
    }

    #[getter]
    fn wcroot_abspath(&self) -> Option<&str> {
        self.inner.wcroot_abspath()
    }

    fn __repr__(&self) -> PyResult<String> {
        Ok(format!(
            "<WCInfo schedule={} copyfrom_url={:?}>",
            self.inner.schedule() as i32,
            self.inner.copyfrom_url()
        ))
    }
}

impl WCInfo {
    pub fn from_svn(wc_info: &subversion::client::WcInfo) -> Self {
        Self {
            inner: wc_info.dup(),
        }
    }
}
