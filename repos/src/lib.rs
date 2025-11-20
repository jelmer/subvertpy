//! Subversion repository module
//!
//! This module provides Python bindings for Subversion repository operations,
//! including repository creation, access, and filesystem operations.

use pyo3::prelude::*;
use subvertpy_util::{error::svn_err_to_py, py_to_svn_dirent};

mod filesystem;
mod fsroot;
mod repository;
mod stream;

use filesystem::FileSystem;
use fsroot::FileSystemRoot;
use repository::Repository;
use stream::Stream;

/// Create a new Subversion repository
#[pyfunction]
#[pyo3(signature = (path, config=None, fs_config=None))]
fn create(
    py: Python,
    path: &str,
    config: Option<Bound<pyo3::PyAny>>,
    fs_config: Option<Bound<pyo3::PyAny>>,
) -> PyResult<Repository> {
    // TODO: Pass config (a Config object) and fs_config to Repos::create_with_config.
    // The old C bindings only supported config (not fs_config).
    let _ = (config, fs_config);

    let py_str = pyo3::types::PyString::new(py, path);
    let repos_path = py_to_svn_dirent(&py_str.as_any())?;
    let path_buf = std::path::Path::new(&repos_path);

    let repos = subversion::repos::Repos::create(path_buf).map_err(|e| svn_err_to_py(e))?;

    Ok(Repository::new(repos))
}

/// Delete a Subversion repository
#[pyfunction]
fn delete(py: Python, path: &str) -> PyResult<()> {
    let py_str = pyo3::types::PyString::new(py, path);
    let repos_path = py_to_svn_dirent(&py_str.as_any())?;
    let path_buf = std::path::Path::new(&repos_path);

    subversion::repos::delete(path_buf).map_err(|e| svn_err_to_py(e))
}

/// Get the SVN library version
#[pyfunction]
fn version() -> (i32, i32, i32, String) {
    let ver = subversion::repos::version();
    (ver.major(), ver.minor(), ver.patch(), ver.tag().to_string())
}

/// Get the API version
#[pyfunction]
fn api_version() -> (i32, i32, i32, String) {
    // Return the API version this module was compiled against
    let ver = subversion::repos::version();
    (ver.major(), ver.minor(), ver.patch(), ver.tag().to_string())
}

/// Hot copy a repository
#[pyfunction]
#[pyo3(signature = (src_path, dest_path, clean_logs=false, incremental=false))]
fn hotcopy(
    py: Python,
    src_path: &str,
    dest_path: &str,
    clean_logs: bool,
    incremental: bool,
) -> PyResult<()> {
    let py_src = pyo3::types::PyString::new(py, src_path);
    let src = py_to_svn_dirent(&py_src.as_any())?;
    let py_dest = pyo3::types::PyString::new(py, dest_path);
    let dest = py_to_svn_dirent(&py_dest.as_any())?;

    let src_path = std::path::Path::new(&src);
    let dest_path = std::path::Path::new(&dest);

    let empty_notify = |_n: &subversion::repos::Notify| {};
    let empty_cancel = || -> Result<(), subversion::Error> { Ok(()) };

    subversion::repos::hotcopy(
        src_path,
        dest_path,
        clean_logs,
        incremental,
        Some(&empty_notify),
        Some(&empty_cancel),
    )
    .map_err(|e| svn_err_to_py(e))
}

#[pymodule]
fn repos(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Repository>()?;
    m.add_class::<FileSystem>()?;
    m.add_class::<FileSystemRoot>()?;
    m.add_class::<Stream>()?;

    m.add_function(wrap_pyfunction!(create, m)?)?;
    m.add_function(wrap_pyfunction!(delete, m)?)?;
    m.add_function(wrap_pyfunction!(hotcopy, m)?)?;
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(api_version, m)?)?;

    m.add("LOAD_UUID_DEFAULT", 0i32)?;
    m.add("LOAD_UUID_IGNORE", 1i32)?;
    m.add("LOAD_UUID_FORCE", 2i32)?;

    m.add("CHECKSUM_MD5", 0i32)?;
    m.add("CHECKSUM_SHA1", 1i32)?;

    m.add("PATH_CHANGE_MODIFY", 0i32)?;
    m.add("PATH_CHANGE_ADD", 1i32)?;
    m.add("PATH_CHANGE_DELETE", 2i32)?;
    m.add("PATH_CHANGE_REPLACE", 3i32)?;

    Ok(())
}
