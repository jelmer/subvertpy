//! Subversion Remote Access (RA) module

use pyo3::create_exception;
use pyo3::prelude::*;
use subvertpy_util::error::svn_err_to_py;

create_exception!(_ra, BusyException, pyo3::exceptions::PyException);

mod auth;
mod py_editor;
mod reporter;
mod session;

use auth::{
    get_platform_specific_client_providers, get_simple_prompt_provider, get_simple_provider,
    get_ssl_client_cert_file_provider, get_ssl_client_cert_prompt_provider,
    get_ssl_client_cert_pw_file_provider, get_ssl_client_cert_pw_prompt_provider,
    get_ssl_server_trust_file_provider, get_ssl_server_trust_prompt_provider,
    get_username_prompt_provider, get_username_provider,
};
use auth::{Auth, AuthProvider, CredentialsIter};
use reporter::Reporter;
use session::{LogIterator, RemoteAccess};

/// Get the SVN library version
#[pyfunction]
fn version() -> (i32, i32, i32, Option<String>) {
    let ver = subversion::ra::version();
    let tag = ver.tag();
    let tag_opt = if tag.is_empty() {
        None
    } else {
        Some(tag.to_string())
    };
    (ver.major(), ver.minor(), ver.patch(), tag_opt)
}

/// Get the API version
#[pyfunction]
fn api_version() -> (i32, i32, i32, Option<String>) {
    let (major, minor, patch) = subversion::ra::api_version();
    (major, minor, patch, None)
}

/// Get available RA modules
#[pyfunction]
fn get_modules() -> PyResult<String> {
    subversion::ra::modules().map_err(|e| svn_err_to_py(e))
}

/// Print available RA modules (returns bytes for compatibility)
#[pyfunction]
fn print_modules() -> PyResult<pyo3::Py<pyo3::types::PyBytes>> {
    let modules = subversion::ra::modules().map_err(|e| svn_err_to_py(e))?;
    Python::attach(|py| Ok(pyo3::types::PyBytes::new(py, modules.as_bytes()).unbind()))
}

#[pymodule]
fn _ra(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<RemoteAccess>()?;
    m.add_class::<Reporter>()?;
    m.add_class::<LogIterator>()?;
    m.add_class::<Auth>()?;
    m.add_class::<AuthProvider>()?;
    m.add_class::<CredentialsIter>()?;

    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(api_version, m)?)?;
    m.add_function(wrap_pyfunction!(get_modules, m)?)?;
    m.add_function(wrap_pyfunction!(print_modules, m)?)?;

    m.add("BusyException", m.py().get_type::<BusyException>())?;
    m.add_function(wrap_pyfunction!(get_simple_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_username_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_ssl_server_trust_file_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_ssl_client_cert_file_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_ssl_client_cert_pw_file_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_platform_specific_client_providers, m)?)?;
    m.add_function(wrap_pyfunction!(get_username_prompt_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_simple_prompt_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_ssl_server_trust_prompt_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_ssl_client_cert_prompt_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_ssl_client_cert_pw_prompt_provider, m)?)?;

    m.add("DIRENT_KIND", subversion::DirentField::Kind.bits())?;
    m.add("DIRENT_SIZE", subversion::DirentField::Size.bits())?;
    m.add("DIRENT_HAS_PROPS", subversion::DirentField::HasProps.bits())?;
    m.add(
        "DIRENT_CREATED_REV",
        subversion::DirentField::CreatedRevision.bits(),
    )?;
    m.add("DIRENT_TIME", subversion::DirentField::Time.bits())?;
    m.add(
        "DIRENT_LAST_AUTHOR",
        subversion::DirentField::LastAuthor.bits(),
    )?;
    m.add("DIRENT_ALL", subversion::DirentField::all().bits())?;

    m.add("NODE_NONE", 0)?;
    m.add("NODE_FILE", 1)?;
    m.add("NODE_DIR", 2)?;
    m.add("NODE_UNKNOWN", 3)?;
    m.add("NODE_SYMLINK", 4)?;

    m.add("DEPTH_UNKNOWN", -2i32)?;
    m.add("DEPTH_EXCLUDE", -1i32)?;
    m.add("DEPTH_EMPTY", 0i32)?;
    m.add("DEPTH_FILES", 1i32)?;
    m.add("DEPTH_IMMEDIATES", 2i32)?;
    m.add("DEPTH_INFINITY", 3i32)?;

    m.add("MERGEINFO_EXPLICIT", 0i32)?;
    m.add("MERGEINFO_INHERITED", 1i32)?;
    m.add("MERGEINFO_NEAREST_ANCESTOR", 2i32)?;

    // SVN_REVISION constant - the SVN library revision number
    {
        let ver = subversion::ra::version();
        // The tag contains the revision info like " (r1922182)"
        // Extract revision from tag, or use 0 if not available
        let tag = ver.tag();
        let revision: i64 = if let Some(start) = tag.find('r') {
            let rest = &tag[start + 1..];
            if let Some(end) = rest.find(|c: char| !c.is_ascii_digit()) {
                rest[..end].parse().unwrap_or(0)
            } else {
                rest.parse().unwrap_or(0)
            }
        } else {
            0
        };
        m.add("SVN_REVISION", revision)?;
    }

    Ok(())
}
