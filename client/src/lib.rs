//! Subversion Client module
//!
//! This module provides Python bindings for Subversion client operations.

use pyo3::prelude::*;

mod config;
mod context;
mod info;

use config::{Config, ConfigItem};
use context::{Client, ClientLogIterator};
use info::{Info, WCInfo};

/// Get the SVN client library version
#[pyfunction]
fn version() -> (i32, i32, i32, String) {
    let ver = subversion::client::version();
    (ver.major(), ver.minor(), ver.patch(), ver.tag().to_string())
}

/// Get the API version
#[pyfunction]
fn api_version() -> (i32, i32, i32, String) {
    // Return the API version this module was compiled against
    let ver = subversion::client::version();
    (ver.major(), ver.minor(), ver.patch(), ver.tag().to_string())
}

/// Get SVN configuration
#[pyfunction]
#[pyo3(signature = (config_dir=None))]
fn get_config(config_dir: Option<String>) -> PyResult<Config> {
    let path = config_dir.as_deref().map(std::path::Path::new);
    let (config, servers) = subversion::config::get_config(path)
        .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;
    Ok(Config::new(config, servers, path))
}

/// Python module initialization
#[pymodule]
fn client(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Client>()?;
    m.add_class::<ClientLogIterator>()?;
    m.add_class::<Config>()?;
    m.add_class::<ConfigItem>()?;
    m.add_class::<Info>()?;
    m.add_class::<WCInfo>()?;

    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(api_version, m)?)?;
    m.add_function(wrap_pyfunction!(get_config, m)?)?;

    Ok(())
}
