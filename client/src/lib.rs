use pyo3::import_exception;
use pyo3::prelude::*;
use std::collections::HashMap;
use subversion::client::Context;
use subversion::{CommitInfo, Depth, Revision, Revnum};

#[pyclass(unsendable)]
pub struct Client(Context);

import_exception!(subversion, Error);

fn error_to_pyerr(e: subversion::Error) -> PyErr {
    todo!()
}

#[pymethods]
impl Client {
    #[new]
    fn new() -> PyResult<Self> {
        Ok(Client(Context::new().map_err(error_to_pyerr)?))
    }

    fn add(
        &self,
        path: std::path::PathBuf,
        depth: Option<Depth>,
        force: Option<bool>,
        no_ignore: Option<bool>,
        add_parents: Option<bool>,
        no_autoprops: Option<bool>,
    ) -> PyResult<()> {
        self.0
            .add(
                path.as_path(),
                depth.unwrap_or(Depth::Infinity),
                force.unwrap_or(false),
                no_ignore.unwrap_or(false),
                add_parents.unwrap_or(false),
                no_autoprops.unwrap_or(false),
            )
            .map_err(error_to_pyerr)
    }

    fn checkout(
        &mut self,
        url: &str,
        path: std::path::PathBuf,
        rev: Option<Revision>,
        peg_revision: Option<Revision>,
        depth: Option<Depth>,
        ignore_externals: Option<bool>,
        allow_unver_obstructions: Option<bool>,
    ) -> PyResult<Revnum> {
        self.0
            .checkout(
                url,
                path.as_path(),
                rev.unwrap_or(Revision::Unspecified),
                peg_revision.unwrap_or(Revision::Unspecified),
                depth.unwrap_or(Depth::Infinity),
                ignore_externals.unwrap_or(false),
                allow_unver_obstructions.unwrap_or(false),
            )
            .map_err(error_to_pyerr)
    }

    fn export(
        &self,
        from: &str,
        to: std::path::PathBuf,
        rev: Option<Revision>,
        peg_rev: Option<Revision>,
        depth: Option<Depth>,
        ignore_externals: Option<bool>,
        overwrite: Option<bool>,
        native_eol: Option<bool>,
        ignore_keywords: Option<bool>,
    ) -> PyResult<Revnum> {
        self.0
            .export(
                from,
                to.as_path(),
                rev.unwrap_or(Revision::Unspecified),
                peg_rev.unwrap_or(Revision::Unspecified),
                depth.unwrap_or(Depth::Infinity),
                ignore_externals.unwrap_or(false),
                overwrite.unwrap_or(false),
                native_eol.unwrap_or(false),
                ignore_keywords.unwrap_or(false),
            )
            .map_err(error_to_pyerr)
    }

    fn cat(
        &self,
        path: &str,
        output_stream: PyObject,
        rev: Option<Revision>,
        peg_rev: Option<Revision>,
        expand_keywords: Option<bool>,
    ) -> PyResult<()> {
        self.0
            .cat(
                path,
                output_stream,
                rev.unwrap_or(Revision::Unspecified),
                peg_rev.unwrap_or(Revision::Unspecified),
                expand_keywords.unwrap_or(false),
            )
            .map_err(error_to_pyerr)
    }

    fn delete(
        &self,
        paths: Vec<&str>,
        force: Option<bool>,
        keep_local: Option<bool>,
        revprops: Option<HashMap<&str, &str>>,
        commit_cb: Option<PyObject>,
    ) -> PyResult<()> {
        self.0
            .delete(
                paths.as_slice(),
                force.unwrap_or(false),
                keep_local.unwrap_or(false),
                revprops.unwrap_or(HashMap::new()),
                |info| {
                    commit_cb
                        .as_ref()
                        .map(|cb| cb.call1((info,)))
                        .unwrap_or(Ok(None))
                        .map_err(error_to_pyerr)
                },
            )
            .map_err(error_to_pyerr)
    }
}

#[pyfunction]
fn version() -> PyResult<(i32, i32, i32, &'static str)> {
    let version = subversion::client::version();
    Ok((
        version.major(),
        version.minor(),
        version.patch(),
        version.tag(),
    ))
}

#[pymodule]
fn client(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<Client>()?;
    m.add_wrapped(wrap_pyfunction!(version))?;
    Ok(())
}
