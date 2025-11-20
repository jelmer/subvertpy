//! Subversion working copy module
//!
//! This module provides Python bindings for Subversion working copy operations.

use pyo3::prelude::*;
use subvertpy_util::error::svn_err_to_py;

mod committed;
mod context;
mod lock;
mod status;

use committed::CommittedQueue;
use context::Context;
use lock::Lock;
use status::Status;

/// Get runtime libsvn_wc version information.
#[pyfunction]
fn version() -> (i32, i32, i32, String) {
    let ver = subversion::wc::version();
    (ver.major(), ver.minor(), ver.patch(), ver.tag().to_string())
}

/// Get compile-time libsvn_wc version information.
#[pyfunction]
fn api_version() -> (i32, i32, i32, String) {
    let ver = subversion::wc::version();
    (ver.major(), ver.minor(), ver.patch(), ver.tag().to_string())
}

/// Check whether path contains a Subversion working copy.
#[pyfunction]
fn check_wc(_py: Python, path: &Bound<PyAny>) -> PyResult<i32> {
    let path_str = subvertpy_util::py_to_svn_dirent(path)?;
    let path = std::path::Path::new(&path_str);
    let result = subversion::wc::check_wc(path).map_err(svn_err_to_py)?;
    Ok(result.unwrap_or(0))
}

/// Clean up a working copy.
#[pyfunction]
#[pyo3(signature = (path, diff3_cmd=None))]
fn cleanup(path: &Bound<PyAny>, diff3_cmd: Option<&str>) -> PyResult<()> {
    if diff3_cmd.is_some() {
        return Err(pyo3::exceptions::PyNotImplementedError::new_err(
            "diff3_cmd is no longer supported by the SVN working copy API",
        ));
    }
    let path_str = subvertpy_util::py_to_svn_abspath(path)?;
    let wc_path = std::path::Path::new(&path_str);
    subversion::wc::cleanup(wc_path, true, true, true, true, false).map_err(svn_err_to_py)
}

/// Ensure an administrative area exists.
#[pyfunction]
#[pyo3(signature = (path, uuid, url, repos=None, rev=-1, depth=3))]
fn ensure_adm(
    path: &Bound<PyAny>,
    uuid: &str,
    url: &str,
    repos: Option<&str>,
    rev: i64,
    depth: i32,
) -> PyResult<()> {
    let path_str = subvertpy_util::py_to_svn_abspath(path)?;
    let repos_root = repos.unwrap_or(url);
    let svn_depth = context::depth_from_py(depth);
    let revnum = subversion::Revnum::from_raw(rev).unwrap_or(subversion::Revnum::invalid());
    let mut ctx = subversion::wc::Context::new().map_err(svn_err_to_py)?;
    ctx.ensure_adm(&path_str, url, repos_root, uuid, revnum, svn_depth)
        .map_err(svn_err_to_py)
}

/// Get the admin directory name.
#[pyfunction]
fn get_adm_dir() -> String {
    subversion::wc::get_adm_dir()
}

/// Set the admin directory name.
#[pyfunction]
fn set_adm_dir(name: &Bound<PyAny>) -> PyResult<()> {
    let name_str = subvertpy_util::py_to_svn_string(name)?;
    subversion::wc::set_adm_dir(&name_str).map_err(svn_err_to_py)
}

/// Check if a name is the admin directory.
#[pyfunction]
fn is_adm_dir(name: &Bound<PyAny>) -> PyResult<bool> {
    let name_str = subvertpy_util::py_to_svn_string(name)?;
    Ok(subversion::wc::is_adm_dir(&name_str))
}

/// Check if a property name is a "normal" property.
#[pyfunction]
fn is_normal_prop(name: &str) -> bool {
    subversion::wc::is_normal_prop(name)
}

/// Check if a property name is an "entry" property.
#[pyfunction]
fn is_entry_prop(name: &str) -> bool {
    subversion::wc::is_entry_prop(name)
}

/// Check if a property name is a "wc" property.
#[pyfunction]
fn is_wc_prop(name: &str) -> bool {
    subversion::wc::is_wc_prop(name)
}

/// Match a string against an ignore list of patterns.
#[pyfunction]
fn match_ignore_list(s: &str, patterns: Vec<String>) -> PyResult<bool> {
    let pattern_refs: Vec<&str> = patterns.iter().map(|s| s.as_str()).collect();
    subversion::wc::match_ignore_list(s, &pattern_refs).map_err(svn_err_to_py)
}

/// Get the actual target of a path.
#[pyfunction]
fn get_actual_target(path: &Bound<PyAny>) -> PyResult<(String, String)> {
    let path_str = subvertpy_util::py_to_svn_dirent(path)?;
    let wc_path = std::path::Path::new(&path_str);
    subversion::wc::get_actual_target(wc_path).map_err(svn_err_to_py)
}

/// Get the pristine copy path (deprecated).
#[pyfunction]
fn get_pristine_copy_path(py: Python, path: &Bound<PyAny>) -> PyResult<String> {
    use pyo3::exceptions::PyDeprecationWarning;
    PyErr::warn(
        py,
        &py.get_type::<PyDeprecationWarning>().into_any(),
        c"get_pristine_copy_path is deprecated. Use get_pristine_contents instead.",
        2,
    )?;
    let path_str = subvertpy_util::py_to_svn_abspath(path)?;
    let wc_path = std::path::Path::new(&path_str);
    subversion::wc::get_pristine_copy_path(wc_path)
        .map(|p| p.to_string_lossy().into_owned())
        .map_err(svn_err_to_py)
}

/// Get the pristine contents of a file.
#[pyfunction]
fn get_pristine_contents(py: Python, path: &Bound<PyAny>) -> PyResult<Option<Py<PyAny>>> {
    let path_str = subvertpy_util::py_to_svn_abspath(path)?;
    let wc_path = std::path::Path::new(&path_str);
    let result = subversion::wc::get_pristine_contents(wc_path).map_err(svn_err_to_py)?;
    match result {
        Some(mut stream) => {
            use std::io::Read;
            let mut data = Vec::new();
            stream
                .read_to_end(&mut data)
                .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;
            let bytes = pyo3::types::PyBytes::new(py, &data);
            let io = py.import("io")?;
            let py_stream = io.call_method1("BytesIO", (bytes,))?;
            Ok(Some(py_stream.into_pyobject(py)?.into_any().unbind()))
        }
        None => Ok(None),
    }
}

/// Determine the revision status of a working copy.
#[pyfunction]
#[pyo3(signature = (wc_path, trail_url=None, committed=false))]
fn revision_status(
    wc_path: &Bound<PyAny>,
    trail_url: Option<&str>,
    committed: bool,
) -> PyResult<(i64, i64, bool, bool)> {
    let path_str = subvertpy_util::py_to_svn_dirent(wc_path)?;
    let wc_path = std::path::Path::new(&path_str);
    subversion::wc::revision_status(wc_path, trail_url, committed).map_err(svn_err_to_py)
}

/// Python module initialization
#[pymodule]
fn wc(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Context>()?;
    m.add_class::<CommittedQueue>()?;
    m.add_class::<Lock>()?;
    m.add_class::<Status>()?;

    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(api_version, m)?)?;
    m.add_function(wrap_pyfunction!(check_wc, m)?)?;
    m.add_function(wrap_pyfunction!(cleanup, m)?)?;
    m.add_function(wrap_pyfunction!(ensure_adm, m)?)?;
    m.add_function(wrap_pyfunction!(get_adm_dir, m)?)?;
    m.add_function(wrap_pyfunction!(set_adm_dir, m)?)?;
    m.add_function(wrap_pyfunction!(is_adm_dir, m)?)?;
    m.add_function(wrap_pyfunction!(is_normal_prop, m)?)?;
    m.add_function(wrap_pyfunction!(is_entry_prop, m)?)?;
    m.add_function(wrap_pyfunction!(is_wc_prop, m)?)?;
    m.add_function(wrap_pyfunction!(match_ignore_list, m)?)?;
    m.add_function(wrap_pyfunction!(get_actual_target, m)?)?;
    m.add_function(wrap_pyfunction!(get_pristine_copy_path, m)?)?;
    m.add_function(wrap_pyfunction!(get_pristine_contents, m)?)?;
    m.add_function(wrap_pyfunction!(revision_status, m)?)?;

    // Schedule constants
    m.add("SCHEDULE_NORMAL", subversion::wc::SCHEDULE_NORMAL)?;
    m.add("SCHEDULE_ADD", subversion::wc::SCHEDULE_ADD)?;
    m.add("SCHEDULE_DELETE", subversion::wc::SCHEDULE_DELETE)?;
    m.add("SCHEDULE_REPLACE", subversion::wc::SCHEDULE_REPLACE)?;

    // Conflict choice constants
    m.add("CONFLICT_CHOOSE_POSTPONE", 0i32)?;
    m.add("CONFLICT_CHOOSE_BASE", 1i32)?;
    m.add("CONFLICT_CHOOSE_THEIRS_FULL", 2i32)?;
    m.add("CONFLICT_CHOOSE_MINE_FULL", 3i32)?;
    m.add("CONFLICT_CHOOSE_THEIRS_CONFLICT", 4i32)?;
    m.add("CONFLICT_CHOOSE_MINE_CONFLICT", 5i32)?;
    m.add("CONFLICT_CHOOSE_MERGED", 6i32)?;

    // Status constants
    m.add("STATUS_NONE", subversion::wc::STATUS_NONE)?;
    m.add("STATUS_UNVERSIONED", subversion::wc::STATUS_UNVERSIONED)?;
    m.add("STATUS_NORMAL", subversion::wc::STATUS_NORMAL)?;
    m.add("STATUS_ADDED", subversion::wc::STATUS_ADDED)?;
    m.add("STATUS_MISSING", subversion::wc::STATUS_MISSING)?;
    m.add("STATUS_DELETED", subversion::wc::STATUS_DELETED)?;
    m.add("STATUS_REPLACED", subversion::wc::STATUS_REPLACED)?;
    m.add("STATUS_MODIFIED", subversion::wc::STATUS_MODIFIED)?;
    m.add("STATUS_MERGED", subversion::wc::STATUS_MERGED)?;
    m.add("STATUS_CONFLICTED", subversion::wc::STATUS_CONFLICTED)?;
    m.add("STATUS_IGNORED", subversion::wc::STATUS_IGNORED)?;
    m.add("STATUS_OBSTRUCTED", subversion::wc::STATUS_OBSTRUCTED)?;
    m.add("STATUS_EXTERNAL", subversion::wc::STATUS_EXTERNAL)?;
    m.add("STATUS_INCOMPLETE", subversion::wc::STATUS_INCOMPLETE)?;

    // Translate constants
    m.add("TRANSLATE_FROM_NF", 0x00i32)?;
    m.add("TRANSLATE_TO_NF", 0x01i32)?;
    m.add("TRANSLATE_FORCE_EOL_REPAIR", 0x02i32)?;
    m.add("TRANSLATE_NO_OUTPUT_CLEANUP", 0x04i32)?;
    m.add("TRANSLATE_FORCE_COPY", 0x08i32)?;
    m.add("TRANSLATE_USE_GLOBAL_TMP", 0x10i32)?;

    Ok(())
}
