use pyo3::import_exception;
use pyo3::prelude::*;
use std::collections::HashMap;
use subversion::client::Context;
use subversion::{Depth, Revision, Revnum};

#[pyclass(unsendable)]
pub struct Client(Context);

#[pyclass(unsendable)]
pub struct CommitInfo(subversion::CommitInfo);

#[pymethods]
impl CommitInfo {
    #[getter]
    fn revision(&self) -> PyResult<Revnum> {
        Ok(self.0.revision())
    }

    #[getter]
    fn date(&self) -> PyResult<&str> {
        Ok(self.0.date())
    }

    #[getter]
    fn author(&self) -> PyResult<&str> {
        Ok(self.0.author())
    }

    #[getter]
    fn post_commit_err(&self) -> PyResult<Option<&str>> {
        Ok(self.0.post_commit_err())
    }
}

import_exception!(subversion, Error);

fn error_to_pyerr(_e: subversion::Error) -> PyErr {
    todo!()
}

fn pyerr_to_error(_e: PyErr) -> subversion::Error {
    todo!()
}

#[pymethods]
impl Client {
    #[new]
    fn new() -> PyResult<Self> {
        Ok(Client(Context::new().map_err(error_to_pyerr)?))
    }

    fn add(
        &mut self,
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
        &mut self,
        from: &str,
        to: std::path::PathBuf,
        rev: Option<Revision>,
        peg_rev: Option<Revision>,
        depth: Option<Depth>,
        ignore_externals: Option<bool>,
        overwrite: Option<bool>,
        native_eol: Option<&str>,
        ignore_keywords: Option<bool>,
    ) -> PyResult<Revnum> {
        self.0
            .export(
                from,
                to.as_path(),
                peg_rev.unwrap_or(Revision::Unspecified),
                rev.unwrap_or(Revision::Unspecified),
                overwrite.unwrap_or(false),
                ignore_externals.unwrap_or(false),
                ignore_keywords.unwrap_or(false),
                depth.unwrap_or(Depth::Infinity),
                match native_eol {
                    Some("LF") => subversion::NativeEOL::LF,
                    Some("CR") => subversion::NativeEOL::CR,
                    Some("CRLF") => subversion::NativeEOL::CRLF,
                    None => subversion::NativeEOL::Standard,
                    _ => {
                        return Err(pyo3::exceptions::PyValueError::new_err(
                            "native_eol must be one of 'LF', 'CR', 'CRLF' or None",
                        ))
                    }
                },
            )
            .map_err(error_to_pyerr)
    }

    fn cat(
        &mut self,
        path: &str,
        output_stream: PyObject,
        rev: Option<Revision>,
        peg_rev: Option<Revision>,
        expand_keywords: Option<bool>,
    ) -> PyResult<HashMap<String, Vec<u8>>> {
        let mut output_stream =
            pyo3_file::PyFileLikeObject::with_requirements(output_stream, false, true, false)?;
        self.0
            .cat(
                path,
                &mut output_stream,
                rev.unwrap_or(Revision::Unspecified),
                peg_rev.unwrap_or(Revision::Unspecified),
                expand_keywords.unwrap_or(false),
            )
            .map_err(error_to_pyerr)
    }

    fn delete(
        &mut self,
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
                &|info| -> Result<(), subversion::Error> {
                    Python::with_gil(|py| {
                        let commit_info = CommitInfo(info.clone());
                        commit_cb
                            .as_ref()
                            .map(|cb| cb.call1(py, (commit_info,)))
                            .transpose()
                            .map_err(pyerr_to_error)
                            .map(|_| ())
                    })
                },
            )
            .map_err(error_to_pyerr)
    }

    pub fn mkdir(
        &mut self,
        paths: Vec<&str>,
        make_parents: Option<bool>,
        revprops: Option<HashMap<&str, &[u8]>>,
        commit_cb: Option<PyObject>,
    ) -> PyResult<()> {
        self.0
            .mkdir(
                paths.as_slice(),
                make_parents.unwrap_or(false),
                revprops.unwrap_or(HashMap::new()),
                &|info| -> Result<(), subversion::Error> {
                    Python::with_gil(|py| {
                        let commit_info = CommitInfo(info.clone());
                        commit_cb
                            .as_ref()
                            .map(|cb| cb.call1(py, (commit_info,)))
                            .transpose()
                            .map_err(pyerr_to_error)
                            .map(|_| ())
                    })
                },
            )
            .map_err(error_to_pyerr)
    }
}

#[pyfunction]
fn version() -> PyResult<(i32, i32, i32, String)> {
    let version = subversion::client::version();
    Ok((
        version.major(),
        version.minor(),
        version.patch(),
        version.tag().to_string(),
    ))
}

#[pymodule]
fn client(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<Client>()?;
    m.add_wrapped(wrap_pyfunction!(version))?;
    Ok(())
}
