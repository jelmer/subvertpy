//! Delta editor Python bindings
//!
//! This module provides Python wrappers for SVN delta editors, which are used
//! to apply changes to repository trees. The editor types can be used by
//! multiple Python modules (client, _ra, wc).

use std::cell::Cell;
use std::rc::Rc;

use pyo3::prelude::*;
use pyo3::types::PyTuple;
use pyo3::Bound;
use subversion::delta::{
    DirectoryEditor, Editor, FileEditor, TxDeltaWindow, WrapDirectoryEditor, WrapEditor,
    WrapFileEditor, WrapTxdeltaWindowHandler,
};
use subversion::Revnum;

/// Python-callable editor that wraps a Rust Editor implementation
#[pyclass(name = "Editor", unsendable)]
pub struct PyEditor {
    editor: WrapEditor<'static>,
    /// Reference to parent object (e.g., Session) that must outlive the editor
    #[pyo3(get)]
    _parent: Option<Py<PyAny>>,
    /// Whether the editor has been closed
    closed: bool,
    /// Callback to invoke when editor is closed/aborted
    on_close: Option<Box<dyn FnOnce()>>,
}

impl PyEditor {
    /// Create a new PyEditor from a WrapEditor
    ///
    /// # Safety
    /// The caller must ensure that the source of the editor (e.g., the Session)
    /// outlives this PyEditor. The lifetime is erased here for PyO3 compatibility.
    /// Use `new_with_parent` to automatically keep the parent alive.
    pub fn new<'a>(editor: WrapEditor<'a>) -> Self {
        // SAFETY: The caller must ensure the editor's source outlives this PyEditor.
        // This is necessary because PyO3 pyclass structs cannot have lifetime parameters.
        let editor: WrapEditor<'static> = unsafe { std::mem::transmute(editor) };
        Self {
            editor,
            _parent: None,
            closed: false,
            on_close: None,
        }
    }

    /// Create a new PyEditor that keeps a reference to its parent object
    pub fn new_with_parent<'a>(editor: WrapEditor<'a>, parent: Py<PyAny>) -> Self {
        let editor: WrapEditor<'static> = unsafe { std::mem::transmute(editor) };
        Self {
            editor,
            _parent: Some(parent),
            closed: false,
            on_close: None,
        }
    }

    /// Set a callback to be invoked when the editor is closed or aborted
    pub fn set_on_close<F>(&mut self, callback: F)
    where
        F: FnOnce() + 'static,
    {
        self.on_close = Some(Box::new(callback));
    }
}

#[pymethods]
impl PyEditor {
    fn set_target_revision(&mut self, _py: Python, revision: Option<i64>) -> PyResult<()> {
        let revnum = revision.and_then(|r| Revnum::from_raw(r));
        self.editor
            .set_target_revision(revnum)
            .map_err(|e| crate::error::svn_err_to_py(e))
    }

    #[pyo3(signature = (base_revision=None))]
    fn open_root(
        &mut self,
        _py: Python,
        base_revision: Option<i64>,
    ) -> PyResult<PyDirectoryEditor> {
        let revnum = base_revision.and_then(|r| Revnum::from_raw(r));
        let dir_editor = self
            .editor
            .open_root(revnum)
            .map_err(|e| crate::error::svn_err_to_py(e))?;

        // SAFETY: The dir_editor's lifetime is tied to self.editor which is 'static
        let dir_editor: WrapDirectoryEditor<'static> = unsafe { std::mem::transmute(dir_editor) };

        Ok(PyDirectoryEditor {
            editor: dir_editor,
            closed: false,
            has_active_child: Rc::new(Cell::new(false)),
            parent_active_child: None,
        })
    }

    fn close(&mut self, _py: Python) -> PyResult<()> {
        if self.closed {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Editor already closed",
            ));
        }

        let result = self
            .editor
            .close()
            .map_err(|e| crate::error::svn_err_to_py(e));

        if result.is_ok() {
            self.closed = true;
            // Call on_close callback if set
            if let Some(callback) = self.on_close.take() {
                callback();
            }
        }

        result
    }

    fn abort(&mut self, _py: Python) -> PyResult<()> {
        if self.closed {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Editor already closed",
            ));
        }

        let result = self
            .editor
            .abort()
            .map_err(|e| crate::error::svn_err_to_py(e));

        if result.is_ok() {
            self.closed = true;
            // Call on_close callback if set
            if let Some(callback) = self.on_close.take() {
                callback();
            }
        }

        result
    }

    fn __enter__<'py>(slf: Bound<'py, Self>) -> Bound<'py, Self> {
        slf
    }

    fn __exit__(
        &mut self,
        py: Python,
        _exc_type: Bound<pyo3::PyAny>,
        _exc_value: Bound<pyo3::PyAny>,
        _traceback: Bound<pyo3::PyAny>,
    ) -> PyResult<bool> {
        self.close(py)?;
        Ok(false)
    }
}

/// Python directory editor
#[pyclass(name = "DirectoryEditor", unsendable)]
pub struct PyDirectoryEditor {
    editor: WrapDirectoryEditor<'static>,
    closed: bool,
    has_active_child: Rc<Cell<bool>>,
    /// Reference to parent's active_child flag, reset to false on close
    parent_active_child: Option<Rc<Cell<bool>>>,
}

#[pymethods]
impl PyDirectoryEditor {
    #[pyo3(signature = (path, revision=None))]
    fn delete_entry(&mut self, _py: Python, path: &str, revision: Option<i64>) -> PyResult<()> {
        let revnum = revision.and_then(|r| Revnum::from_raw(r));
        self.editor
            .delete_entry(path, revnum)
            .map_err(|e| crate::error::svn_err_to_py(e))
    }

    #[pyo3(signature = (path, copyfrom_path=None, copyfrom_rev=None))]
    fn add_directory(
        &mut self,
        _py: Python,
        path: &str,
        copyfrom_path: Option<&str>,
        copyfrom_rev: Option<i64>,
    ) -> PyResult<PyDirectoryEditor> {
        if self.has_active_child.get() {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Directory editor already has an active child",
            ));
        }

        let copyfrom = match (copyfrom_path, copyfrom_rev) {
            (Some(p), Some(r)) => Revnum::from_raw(r).map(|rev| (p, rev)),
            _ => None,
        };

        let child_editor = self
            .editor
            .add_directory(path, copyfrom)
            .map_err(|e| crate::error::svn_err_to_py(e))?;

        // SAFETY: child_editor's lifetime is tied to self.editor which is 'static
        let child_editor: WrapDirectoryEditor<'static> =
            unsafe { std::mem::transmute(child_editor) };

        self.has_active_child.set(true);

        Ok(PyDirectoryEditor {
            editor: child_editor,
            closed: false,
            has_active_child: Rc::new(Cell::new(false)),
            parent_active_child: Some(Rc::clone(&self.has_active_child)),
        })
    }

    #[pyo3(signature = (path, base_revision=None))]
    fn open_directory(
        &mut self,
        _py: Python,
        path: &str,
        base_revision: Option<i64>,
    ) -> PyResult<PyDirectoryEditor> {
        if self.has_active_child.get() {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Directory editor already has an active child",
            ));
        }

        let revnum = base_revision.and_then(|r| Revnum::from_raw(r));
        let child_editor = self
            .editor
            .open_directory(path, revnum)
            .map_err(|e| crate::error::svn_err_to_py(e))?;

        // SAFETY: child_editor's lifetime is tied to self.editor which is 'static
        let child_editor: WrapDirectoryEditor<'static> =
            unsafe { std::mem::transmute(child_editor) };

        self.has_active_child.set(true);

        Ok(PyDirectoryEditor {
            editor: child_editor,
            closed: false,
            has_active_child: Rc::new(Cell::new(false)),
            parent_active_child: Some(Rc::clone(&self.has_active_child)),
        })
    }

    fn change_prop(
        &mut self,
        _py: Python,
        name: &str,
        value: Option<Bound<pyo3::PyAny>>,
    ) -> PyResult<()> {
        let value_bytes: Option<Vec<u8>> = match value {
            None => None,
            Some(v) => {
                if let Ok(b) = v.cast::<pyo3::types::PyBytes>() {
                    Some(b.as_bytes().to_vec())
                } else if let Ok(s) = v.extract::<String>() {
                    Some(s.into_bytes())
                } else {
                    return Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                        "value must be str or bytes",
                    ));
                }
            }
        };
        self.editor
            .change_prop(name, value_bytes.as_deref())
            .map_err(|e| crate::error::svn_err_to_py(e))
    }

    fn close(&mut self, _py: Python) -> PyResult<()> {
        if self.closed {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Directory editor already closed",
            ));
        }

        let result = self
            .editor
            .close()
            .map_err(|e| crate::error::svn_err_to_py(e));

        if result.is_ok() {
            self.closed = true;
            if let Some(ref parent_flag) = self.parent_active_child {
                parent_flag.set(false);
            }
        }

        result
    }

    fn absent_directory(&mut self, _py: Python, path: &str) -> PyResult<()> {
        self.editor
            .absent_directory(path)
            .map_err(|e| crate::error::svn_err_to_py(e))
    }

    #[pyo3(signature = (path, copyfrom_path=None, copyfrom_rev=None))]
    fn add_file(
        &mut self,
        _py: Python,
        path: &str,
        copyfrom_path: Option<&str>,
        copyfrom_rev: Option<i64>,
    ) -> PyResult<PyFileEditor> {
        if self.has_active_child.get() {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Directory editor already has an active child",
            ));
        }

        let copyfrom = match (copyfrom_path, copyfrom_rev) {
            (Some(p), Some(r)) => Revnum::from_raw(r).map(|rev| (p, rev)),
            _ => None,
        };

        let file_editor = self
            .editor
            .add_file(path, copyfrom)
            .map_err(|e| crate::error::svn_err_to_py(e))?;

        // SAFETY: file_editor's lifetime is tied to self.editor which is 'static
        let file_editor: WrapFileEditor<'static> = unsafe { std::mem::transmute(file_editor) };

        self.has_active_child.set(true);

        Ok(PyFileEditor {
            editor: file_editor,
            closed: false,
            parent_active_child: Some(Rc::clone(&self.has_active_child)),
        })
    }

    #[pyo3(signature = (path, base_revision=None))]
    fn open_file(
        &mut self,
        _py: Python,
        path: &str,
        base_revision: Option<i64>,
    ) -> PyResult<PyFileEditor> {
        if self.has_active_child.get() {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Directory editor already has an active child",
            ));
        }

        let revnum = base_revision.and_then(|r| Revnum::from_raw(r));
        let file_editor = self
            .editor
            .open_file(path, revnum)
            .map_err(|e| crate::error::svn_err_to_py(e))?;

        // SAFETY: file_editor's lifetime is tied to self.editor which is 'static
        let file_editor: WrapFileEditor<'static> = unsafe { std::mem::transmute(file_editor) };

        self.has_active_child.set(true);

        Ok(PyFileEditor {
            editor: file_editor,
            closed: false,
            parent_active_child: Some(Rc::clone(&self.has_active_child)),
        })
    }

    fn absent_file(&mut self, _py: Python, path: &str) -> PyResult<()> {
        self.editor
            .absent_file(path)
            .map_err(|e| crate::error::svn_err_to_py(e))
    }

    fn __enter__<'py>(slf: Bound<'py, Self>) -> Bound<'py, Self> {
        slf
    }

    fn __exit__(
        &mut self,
        py: Python,
        _exc_type: Bound<pyo3::PyAny>,
        _exc_value: Bound<pyo3::PyAny>,
        _traceback: Bound<pyo3::PyAny>,
    ) -> PyResult<bool> {
        self.close(py)?;
        Ok(false)
    }
}

/// Python file editor
#[pyclass(name = "FileEditor", unsendable)]
pub struct PyFileEditor {
    editor: WrapFileEditor<'static>,
    closed: bool,
    /// Reference to parent's active_child flag, reset to false on close
    parent_active_child: Option<Rc<Cell<bool>>>,
}

#[pymethods]
impl PyFileEditor {
    #[pyo3(signature = (base_checksum=None))]
    fn apply_textdelta(
        &mut self,
        _py: Python,
        base_checksum: Option<&str>,
    ) -> PyResult<PyTxDeltaWindowHandler> {
        let handler = self
            .editor
            .apply_textdelta_raw(base_checksum)
            .map_err(|e| crate::error::svn_err_to_py(e))?;

        Ok(PyTxDeltaWindowHandler { handler })
    }

    fn change_prop(
        &mut self,
        _py: Python,
        name: &str,
        value: Option<Bound<pyo3::PyAny>>,
    ) -> PyResult<()> {
        let value_bytes: Option<Vec<u8>> = match value {
            None => None,
            Some(v) => {
                if let Ok(b) = v.cast::<pyo3::types::PyBytes>() {
                    Some(b.as_bytes().to_vec())
                } else if let Ok(s) = v.extract::<String>() {
                    Some(s.into_bytes())
                } else {
                    return Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                        "value must be str or bytes",
                    ));
                }
            }
        };
        self.editor
            .change_prop(name, value_bytes.as_deref())
            .map_err(|e| crate::error::svn_err_to_py(e))
    }

    #[pyo3(signature = (text_checksum=None))]
    fn close(&mut self, _py: Python, text_checksum: Option<&str>) -> PyResult<()> {
        if self.closed {
            return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "File editor already closed",
            ));
        }

        let result = self
            .editor
            .close(text_checksum)
            .map_err(|e| crate::error::svn_err_to_py(e));

        if result.is_ok() {
            self.closed = true;
            if let Some(ref parent_flag) = self.parent_active_child {
                parent_flag.set(false);
            }
        }

        result
    }

    fn __enter__<'py>(slf: Bound<'py, Self>) -> Bound<'py, Self> {
        slf
    }

    fn __exit__(
        &mut self,
        py: Python,
        _exc_type: Bound<pyo3::PyAny>,
        _exc_value: Bound<pyo3::PyAny>,
        _traceback: Bound<pyo3::PyAny>,
    ) -> PyResult<bool> {
        self.close(py, None)?;
        Ok(false)
    }
}

/// Python-callable txdelta window handler
#[pyclass(name = "TxDeltaWindowHandler", unsendable)]
pub struct PyTxDeltaWindowHandler {
    handler: WrapTxdeltaWindowHandler,
}

#[pymethods]
impl PyTxDeltaWindowHandler {
    fn __call__(&mut self, window: Option<Bound<PyTuple>>) -> PyResult<()> {
        if window.is_none() {
            // Final call with None signals end of delta - call finish to pass NULL window
            self.handler
                .finish()
                .map_err(|e| crate::error::svn_err_to_py(e))?;
            return Ok(());
        }

        // Parse window tuple: (sview_offset, sview_len, tview_len, src_ops, ops, new_data)
        let window_tuple = window.unwrap();
        let (sview_offset, sview_len, tview_len, src_ops, ops, new_data): (
            u64,
            u64,
            u64,
            i32,
            Bound<pyo3::types::PyList>,
            Bound<pyo3::types::PyBytes>,
        ) = window_tuple.extract()?;

        // Parse ops list: [(action_code, offset, length), ...]
        let ops_vec: Vec<(i32, u64, u64)> = ops
            .iter()
            .map(|item| item.extract())
            .collect::<PyResult<Vec<_>>>()?;

        // Create TxDeltaWindow from parts
        let mut delta_window = TxDeltaWindow::from_parts(
            sview_offset,
            sview_len,
            tview_len,
            src_ops,
            &ops_vec,
            new_data.as_bytes(),
        );

        // Call the handler
        self.handler
            .call(&mut delta_window)
            .map_err(|e| crate::error::svn_err_to_py(e))?;

        Ok(())
    }
}

/// Register editor types with a Python module
pub fn register_editor_types(module: &Bound<PyModule>) -> PyResult<()> {
    module.add_class::<PyEditor>()?;
    module.add_class::<PyDirectoryEditor>()?;
    module.add_class::<PyFileEditor>()?;
    module.add_class::<PyTxDeltaWindowHandler>()?;
    Ok(())
}
