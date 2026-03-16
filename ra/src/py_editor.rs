//! Python editor wrapper
//!
//! This module wraps a Python editor object to make it usable with
//! subversion-rs functions like do_diff, do_update, etc.

use pyo3::prelude::*;
use pyo3::types::PyBytes;
use subversion::delta::{DirectoryEditor, Editor, FileEditor};
use subvertpy_util::error::py_err_to_svn;

/// Wrapper for a Python editor object
pub struct PyEditorWrapper {
    py_editor: Py<PyAny>,
}

impl PyEditorWrapper {
    pub fn new(py_editor: Py<PyAny>) -> Self {
        Self { py_editor }
    }

    /// Convert to WrapEditor for passing to SVN functions
    pub fn into_wrap_editor(self) -> subversion::delta::WrapEditor<'static> {
        subversion::delta::WrapEditor::from_rust_editor(self)
    }
}

impl Editor for PyEditorWrapper {
    type RootEditor = PyDirectoryEditorWrapper;

    fn set_target_revision(
        &mut self,
        target_revision: Option<subversion::Revnum>,
    ) -> Result<(), subversion::Error<'_>> {
        Python::attach(|py| {
            let rev_num = target_revision.map(|r| r.as_u64() as i64).unwrap_or(-1);
            self.py_editor
                .call_method1(py, "set_target_revision", (rev_num,))
                .map_err(|e| py_err_to_svn(e))?;
            Ok(())
        })
    }

    fn open_root(
        &mut self,
        base_revision: Option<subversion::Revnum>,
    ) -> Result<Self::RootEditor, subversion::Error<'_>> {
        Python::attach(|py| {
            let rev_num = base_revision.map(|r| r.as_u64() as i64).unwrap_or(-1);
            let dir_editor = self
                .py_editor
                .call_method1(py, "open_root", (rev_num,))
                .map_err(|e| py_err_to_svn(e))?;

            Ok(PyDirectoryEditorWrapper::new(dir_editor))
        })
    }

    fn close(&mut self) -> Result<(), subversion::Error<'_>> {
        Python::attach(|py| {
            self.py_editor
                .call_method0(py, "close")
                .map_err(|e| py_err_to_svn(e))?;
            Ok(())
        })
    }

    fn abort(&mut self) -> Result<(), subversion::Error<'_>> {
        Python::attach(|py| {
            self.py_editor
                .call_method0(py, "abort")
                .map_err(|e| py_err_to_svn(e))?;
            Ok(())
        })
    }
}

/// Wrapper for a Python directory editor object
pub struct PyDirectoryEditorWrapper {
    py_dir: Py<PyAny>,
}

impl PyDirectoryEditorWrapper {
    pub fn new(py_dir: Py<PyAny>) -> Self {
        Self { py_dir }
    }
}

impl DirectoryEditor for PyDirectoryEditorWrapper {
    type SubDirectory = PyDirectoryEditorWrapper;
    type File = PyFileEditorWrapper;

    fn add_directory(
        &mut self,
        path: &str,
        copyfrom: Option<(&str, subversion::Revnum)>,
    ) -> Result<Self::SubDirectory, subversion::Error<'_>> {
        Python::attach(|py| {
            let (copyfrom_path, rev_num) = match copyfrom {
                Some((p, r)) => (Some(p), r.as_u64() as i64),
                None => (None, -1),
            };
            let args = (path, copyfrom_path, rev_num);
            let dir_editor = self
                .py_dir
                .call_method1(py, "add_directory", args)
                .map_err(|e| py_err_to_svn(e))?;

            Ok(PyDirectoryEditorWrapper::new(dir_editor))
        })
    }

    fn open_directory(
        &mut self,
        path: &str,
        base_revision: Option<subversion::Revnum>,
    ) -> Result<Self::SubDirectory, subversion::Error<'_>> {
        Python::attach(|py| {
            let rev_num = base_revision.map(|r| r.as_u64() as i64).unwrap_or(-1);
            let dir_editor = self
                .py_dir
                .call_method1(py, "open_directory", (path, rev_num))
                .map_err(|e| py_err_to_svn(e))?;

            Ok(PyDirectoryEditorWrapper::new(dir_editor))
        })
    }

    fn delete_entry(
        &mut self,
        path: &str,
        revision: Option<subversion::Revnum>,
    ) -> Result<(), subversion::Error<'_>> {
        Python::attach(|py| {
            let rev_num = revision.map(|r| r.as_u64() as i64).unwrap_or(-1);
            self.py_dir
                .call_method1(py, "delete_entry", (path, rev_num))
                .map_err(|e| py_err_to_svn(e))?;
            Ok(())
        })
    }

    fn add_file(
        &mut self,
        path: &str,
        copyfrom: Option<(&str, subversion::Revnum)>,
    ) -> Result<Self::File, subversion::Error<'_>> {
        Python::attach(|py| {
            let (copyfrom_path, rev_num) = match copyfrom {
                Some((p, r)) => (Some(p), r.as_u64() as i64),
                None => (None, -1),
            };
            let args = (path, copyfrom_path, rev_num);
            let file_editor = self
                .py_dir
                .call_method1(py, "add_file", args)
                .map_err(|e| py_err_to_svn(e))?;

            Ok(PyFileEditorWrapper::new(file_editor))
        })
    }

    fn open_file(
        &mut self,
        path: &str,
        base_revision: Option<subversion::Revnum>,
    ) -> Result<Self::File, subversion::Error<'_>> {
        Python::attach(|py| {
            let rev_num = base_revision.map(|r| r.as_u64() as i64).unwrap_or(-1);
            let file_editor = self
                .py_dir
                .call_method1(py, "open_file", (path, rev_num))
                .map_err(|e| py_err_to_svn(e))?;

            Ok(PyFileEditorWrapper::new(file_editor))
        })
    }

    fn change_prop(
        &mut self,
        name: &str,
        value: Option<&[u8]>,
    ) -> Result<(), subversion::Error<'_>> {
        Python::attach(|py| {
            let py_value = value.map(|v| PyBytes::new(py, v).into_any());
            self.py_dir
                .call_method1(py, "change_prop", (name, py_value))
                .map_err(|e| py_err_to_svn(e))?;
            Ok(())
        })
    }

    fn close(&mut self) -> Result<(), subversion::Error<'_>> {
        Python::attach(|py| {
            self.py_dir
                .call_method0(py, "close")
                .map_err(|e| py_err_to_svn(e))?;
            Ok(())
        })
    }

    fn absent_directory(&mut self, path: &str) -> Result<(), subversion::Error<'_>> {
        Python::attach(|py| {
            self.py_dir
                .call_method1(py, "absent_directory", (path,))
                .map_err(|e| py_err_to_svn(e))?;
            Ok(())
        })
    }

    fn absent_file(&mut self, path: &str) -> Result<(), subversion::Error<'_>> {
        Python::attach(|py| {
            self.py_dir
                .call_method1(py, "absent_file", (path,))
                .map_err(|e| py_err_to_svn(e))?;
            Ok(())
        })
    }
}

/// Wrapper for a Python file editor object
pub struct PyFileEditorWrapper {
    py_file: Py<PyAny>,
}

impl PyFileEditorWrapper {
    pub fn new(py_file: Py<PyAny>) -> Self {
        Self { py_file }
    }
}

impl FileEditor for PyFileEditorWrapper {
    fn apply_textdelta(
        &mut self,
        base_checksum: Option<&str>,
    ) -> Result<
        Box<
            dyn for<'b> Fn(
                &'b mut subversion::delta::TxDeltaWindow,
            ) -> Result<(), subversion::Error<'static>>,
        >,
        subversion::Error<'static>,
    > {
        Python::attach(|py| {
            let handler = self
                .py_file
                .call_method1(py, "apply_textdelta", (base_checksum,))
                .map_err(|e| py_err_to_svn(e))?;

            if handler.is_none(py) {
                let noop: Box<
                    dyn for<'b> Fn(
                        &'b mut subversion::delta::TxDeltaWindow,
                    ) -> Result<(), subversion::Error<'static>>,
                > = Box::new(|_window| Ok(()));
                return Ok(noop);
            }

            let handler_obj = handler.clone_ref(py);
            let closure: Box<dyn for<'b> Fn(&'b mut subversion::delta::TxDeltaWindow) -> Result<(), subversion::Error<'static>>> =
                Box::new(move |window: &mut subversion::delta::TxDeltaWindow| -> Result<(), subversion::Error<'static>> {
                Python::attach(|py| {
                    if window.as_ptr().is_null() {
                        // End-of-delta signal: call handler with None
                        handler_obj
                            .call1(py, (py.None(),))
                            .map_err(|e| py_err_to_svn(e))?;
                        return Ok(());
                    }
                    let ops: Vec<(i32, u64, u64)> = window.ops();
                    let py_ops = pyo3::types::PyList::new(
                        py,
                        ops.iter().map(|&(action, offset, length)| {
                            (action, offset, length)
                        }),
                    ).map_err(|e| py_err_to_svn(e))?;
                    let new_data = PyBytes::new(py, window.new_data());
                    let py_window = (
                        window.sview_offset(),
                        window.sview_len(),
                        window.tview_len(),
                        window.src_ops(),
                        py_ops,
                        new_data,
                    );
                    handler_obj
                        .call1(py, (py_window,))
                        .map_err(|e| py_err_to_svn(e))?;
                    Ok(())
                })
            });

            Ok(closure)
        })
    }

    fn change_prop(
        &mut self,
        name: &str,
        value: Option<&[u8]>,
    ) -> Result<(), subversion::Error<'static>> {
        Python::attach(|py| {
            let py_value = value.map(|v| PyBytes::new(py, v).into_any());
            self.py_file
                .call_method1(py, "change_prop", (name, py_value))
                .map_err(|e| py_err_to_svn(e))?;
            Ok(())
        })
    }

    fn close(&mut self, text_checksum: Option<&str>) -> Result<(), subversion::Error<'static>> {
        Python::attach(|py| {
            if let Some(checksum) = text_checksum {
                self.py_file
                    .call_method1(py, "close", (checksum,))
                    .map_err(|e| py_err_to_svn(e))?;
            } else {
                self.py_file
                    .call_method0(py, "close")
                    .map_err(|e| py_err_to_svn(e))?;
            }
            Ok(())
        })
    }
}
