//! Deprecated Adm (svn_wc_adm_access_t) Python bindings.

use pyo3::prelude::*;
use subvertpy_util::error::svn_err_to_py;

/// Recover a borrowed [`WrapFileEditor`] from a Python file editor object.
///
/// The file editor produced by ``ra.RemoteAccess.get_commit_editor`` lives in
/// the ``_ra`` extension module, which has its own ``FileEditor`` Python type
/// distinct from the one in this (``wc``) module, so it cannot be downcast
/// directly. Instead we ask it for a PyCapsule wrapping the underlying
/// ``WrapFileEditor`` pointer (see
/// ``subvertpy_util::editor::PyFileEditor::_wrap_file_editor_capsule``) and
/// borrow that.
///
/// # Safety
///
/// The returned reference borrows from the Python file editor object, which the
/// caller (`editor`) keeps alive for the duration of the borrow. The pointers
/// inside belong to the live commit-editor drive, so they line up with the
/// access baton used by the transmit call.
unsafe fn wrap_file_editor_from_py<'a>(
    editor: &'a Bound<'_, PyAny>,
) -> PyResult<&'a subversion::delta::WrapFileEditor<'static>> {
    let capsule = editor.call_method0("_wrap_file_editor_capsule")?;
    let capsule = capsule.cast::<pyo3::types::PyCapsule>().map_err(|_| {
        PyErr::new::<pyo3::exceptions::PyTypeError, _>(
            "editor did not return a file editor capsule",
        )
    })?;
    let name = subvertpy_util::editor::WRAP_FILE_EDITOR_CAPSULE_NAME;
    let ptr = capsule.pointer_checked(Some(name))?;
    // SAFETY: the capsule pointer is a `*const WrapFileEditor<'static>` produced
    // by subvertpy_util, valid while `editor` is alive (no destructor).
    Ok(unsafe { &*(ptr.as_ptr() as *const subversion::delta::WrapFileEditor<'static>) })
}

/// Convert a subversion::NodeKind to the Python integer constant.
fn node_kind_to_py(kind: subversion::NodeKind) -> i32 {
    match kind {
        subversion::NodeKind::None => 0,
        subversion::NodeKind::File => 1,
        subversion::NodeKind::Dir => 2,
        subversion::NodeKind::Unknown => 3,
        subversion::NodeKind::Symlink => 4,
    }
}

/// A deprecated working copy entry (``svn_wc_entry_t``).
///
/// All attributes are read-only copies, safe to use after the access baton
/// is closed.
#[pyclass(name = "Entry")]
pub struct Entry {
    inner: subversion::wc::adm::Entry,
}

#[pymethods]
impl Entry {
    #[getter]
    fn name(&self) -> Option<&str> {
        self.inner.name.as_deref()
    }

    #[getter]
    fn revision(&self) -> i64 {
        self.inner.revision.as_i64()
    }

    #[getter]
    fn url(&self) -> Option<&str> {
        self.inner.url.as_deref()
    }

    #[getter]
    fn repos(&self) -> Option<&str> {
        self.inner.repos.as_deref()
    }

    #[getter]
    fn uuid(&self) -> Option<&str> {
        self.inner.uuid.as_deref()
    }

    #[getter]
    fn kind(&self) -> i32 {
        node_kind_to_py(self.inner.kind)
    }

    #[getter]
    fn schedule(&self) -> u32 {
        self.inner.schedule
    }

    #[getter]
    fn copied(&self) -> bool {
        self.inner.copied
    }

    #[getter]
    fn deleted(&self) -> bool {
        self.inner.deleted
    }

    #[getter]
    fn absent(&self) -> bool {
        self.inner.absent
    }

    #[getter]
    fn incomplete(&self) -> bool {
        self.inner.incomplete
    }

    #[getter]
    fn copyfrom_url(&self) -> Option<&str> {
        self.inner.copyfrom_url.as_deref()
    }

    #[getter]
    fn copyfrom_rev(&self) -> i64 {
        self.inner.copyfrom_rev.as_i64()
    }

    #[getter]
    fn conflict_old(&self) -> Option<&str> {
        self.inner.conflict_old.as_deref()
    }

    #[getter]
    fn conflict_new(&self) -> Option<&str> {
        self.inner.conflict_new.as_deref()
    }

    #[getter]
    fn conflict_wrk(&self) -> Option<&str> {
        self.inner.conflict_wrk.as_deref()
    }

    #[getter]
    fn prejfile(&self) -> Option<&str> {
        self.inner.prejfile.as_deref()
    }

    #[getter]
    fn text_time(&self) -> i64 {
        self.inner.text_time
    }

    #[getter]
    fn prop_time(&self) -> i64 {
        self.inner.prop_time
    }

    #[getter]
    fn checksum(&self) -> Option<&str> {
        self.inner.checksum.as_deref()
    }

    #[getter]
    fn cmt_rev(&self) -> i64 {
        self.inner.cmt_rev.as_i64()
    }

    #[getter]
    fn cmt_date(&self) -> i64 {
        self.inner.cmt_date
    }

    #[getter]
    fn cmt_author(&self) -> Option<&str> {
        self.inner.cmt_author.as_deref()
    }

    #[getter]
    fn lock_token(&self) -> Option<&str> {
        self.inner.lock_token.as_deref()
    }

    #[getter]
    fn lock_owner(&self) -> Option<&str> {
        self.inner.lock_owner.as_deref()
    }

    #[getter]
    fn lock_comment(&self) -> Option<&str> {
        self.inner.lock_comment.as_deref()
    }

    #[getter]
    fn lock_creation_date(&self) -> i64 {
        self.inner.lock_creation_date
    }

    #[getter]
    fn has_props(&self) -> bool {
        self.inner.has_props
    }

    #[getter]
    fn has_prop_mods(&self) -> bool {
        self.inner.has_prop_mods
    }

    #[getter]
    fn changelist(&self) -> Option<&str> {
        self.inner.changelist.as_deref()
    }

    #[getter]
    fn working_size(&self) -> i64 {
        self.inner.working_size
    }

    #[getter]
    fn keep_local(&self) -> bool {
        self.inner.keep_local
    }

    #[getter]
    fn depth(&self) -> i32 {
        crate::context::depth_to_py(self.inner.depth)
    }
}

/// Deprecated working copy administrative access baton.
///
/// Wraps the deprecated ``svn_wc_adm_access_t`` based API.
/// New code should use :class:`Context` instead.
#[pyclass(name = "Adm", unsendable)]
pub struct Adm {
    #[allow(deprecated)]
    pub(crate) inner: subversion::wc::Adm<'static>,
}

#[pymethods]
#[allow(deprecated)]
impl Adm {
    /// Open an access baton for a working copy directory.
    ///
    /// :param associated: Associated access baton (ignored, for backwards compat).
    /// :param path: Path to the working copy directory.
    /// :param write_lock: If True, acquire a write lock.
    /// :param depth: Levels to lock: 0 = just this dir, -1 = infinite.
    #[new]
    #[pyo3(signature = (associated=None, path=None, write_lock=false, depth=0))]
    fn init(
        associated: Option<&Bound<PyAny>>,
        path: Option<&Bound<PyAny>>,
        write_lock: bool,
        depth: i32,
    ) -> PyResult<Self> {
        // Support both Adm(path, write_lock=...) and Adm(None, path, write_lock=...)
        let actual_path = if let Some(p) = path {
            p
        } else if let Some(a) = associated {
            if a.is_none() {
                return Err(pyo3::exceptions::PyTypeError::new_err(
                    "Adm() requires a path argument",
                ));
            }
            a
        } else {
            return Err(pyo3::exceptions::PyTypeError::new_err(
                "Adm() requires a path argument",
            ));
        };
        let path_str = subvertpy_util::py_to_svn_abspath(actual_path)?;
        let adm = subversion::wc::Adm::open(&path_str, write_lock, depth).map_err(svn_err_to_py)?;
        Ok(Self { inner: adm })
    }

    /// Return the path this access baton is for.
    fn access_path(&self) -> PyResult<String> {
        Ok(self.inner.access_path().to_string())
    }

    /// Check if this access baton is locked.
    fn is_locked(&self) -> PyResult<bool> {
        Ok(self.inner.is_locked())
    }

    /// Close the access baton, releasing all resources and locks.
    fn close(&mut self) {
        self.inner.close();
    }

    /// Add a file or directory to version control.
    #[pyo3(signature = (path, copyfrom_url=None, copyfrom_rev=-1))]
    fn add(
        &self,
        path: &Bound<PyAny>,
        copyfrom_url: Option<&str>,
        copyfrom_rev: i64,
    ) -> PyResult<()> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        let rev = subvertpy_util::to_revnum(copyfrom_rev);
        self.inner
            .add(&path_str, copyfrom_url, rev)
            .map_err(svn_err_to_py)
    }

    /// Delete a file or directory from version control.
    #[pyo3(signature = (path, keep_local=false))]
    fn delete(&self, path: &Bound<PyAny>, keep_local: bool) -> PyResult<()> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        self.inner
            .delete(&path_str, keep_local)
            .map_err(svn_err_to_py)
    }

    /// Copy a file or directory in the working copy.
    fn copy(&self, src: &Bound<PyAny>, dst_basename: &str) -> PyResult<()> {
        let src_str = subvertpy_util::py_to_svn_abspath(src)?;
        self.inner
            .copy(&src_str, dst_basename)
            .map_err(svn_err_to_py)
    }

    /// Set a property on a path.
    fn prop_set(&self, name: &str, value: Option<&[u8]>, path: &Bound<PyAny>) -> PyResult<()> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        self.inner
            .prop_set(name, value, &path_str)
            .map_err(svn_err_to_py)
    }

    /// Get a property on a path.
    fn prop_get(
        &self,
        py: Python<'_>,
        name: &str,
        path: &Bound<PyAny>,
    ) -> PyResult<Option<Py<PyAny>>> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        let val = self
            .inner
            .prop_get(name, &path_str)
            .map_err(svn_err_to_py)?;
        match val {
            None => Ok(None),
            Some(v) => Ok(Some(pyo3::types::PyBytes::new(py, &v).into_any().unbind())),
        }
    }

    /// Check if a path has a binary property.
    fn has_binary_prop(&self, path: &Bound<PyAny>) -> PyResult<bool> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        self.inner.has_binary_prop(&path_str).map_err(svn_err_to_py)
    }

    /// Check if the text content of a path has been modified.
    fn text_modified(&self, path: &Bound<PyAny>, force_comparison: bool) -> PyResult<bool> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        self.inner
            .text_modified(&path_str, force_comparison)
            .map_err(svn_err_to_py)
    }

    /// Check if properties of a path have been modified.
    fn props_modified(&self, path: &Bound<PyAny>) -> PyResult<bool> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        self.inner.props_modified(&path_str).map_err(svn_err_to_py)
    }

    /// Check if a path is the root of a working copy.
    fn is_wc_root(&self, path: &Bound<PyAny>) -> PyResult<bool> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        self.inner.is_wc_root(&path_str).map_err(svn_err_to_py)
    }

    /// Check if a path is conflicted.
    fn conflicted(&self, path: &Bound<PyAny>) -> PyResult<(bool, bool, bool)> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        self.inner.conflicted(&path_str).map_err(svn_err_to_py)
    }

    /// Queue a path for post-commit processing using this access baton.
    #[pyo3(signature = (path, queue, recurse=false, remove_lock=false, remove_changelist=false, md5_digest=None))]
    fn queue_committed(
        &self,
        path: &Bound<PyAny>,
        queue: &mut crate::committed::CommittedQueue,
        recurse: bool,
        remove_lock: bool,
        remove_changelist: bool,
        md5_digest: Option<&[u8]>,
    ) -> PyResult<()> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        let digest: Option<[u8; 16]> = md5_digest.map(|d| {
            let mut arr = [0u8; 16];
            arr.copy_from_slice(&d[..16]);
            arr
        });
        self.inner
            .queue_committed(
                &path_str,
                &mut queue.inner,
                recurse,
                remove_lock,
                remove_changelist,
                digest.as_ref(),
            )
            .map_err(svn_err_to_py)
    }

    /// Process the committed queue using this access baton.
    fn process_committed_queue(
        &self,
        queue: &mut crate::committed::CommittedQueue,
        revnum: i64,
        date: &str,
        author: &str,
    ) -> PyResult<()> {
        self.inner
            .process_committed_queue(
                &mut queue.inner,
                subvertpy_util::to_revnum(revnum).unwrap_or(subversion::Revnum::invalid()),
                Some(date),
                Some(author),
            )
            .map_err(svn_err_to_py)
    }

    /// Get a single entry from the working copy.
    ///
    /// Returns ``None`` if the path is not versioned.
    #[pyo3(signature = (path, show_hidden=false))]
    fn entry(&self, path: &Bound<PyAny>, show_hidden: bool) -> PyResult<Option<Entry>> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        let entry = self
            .inner
            .entry(&path_str, show_hidden)
            .map_err(svn_err_to_py)?;
        Ok(entry.map(|inner| Entry { inner }))
    }

    /// Read all entries in this directory, returning a dict of name -> Entry.
    #[pyo3(signature = (show_hidden=false))]
    fn entries_read(&self, py: Python<'_>, show_hidden: bool) -> PyResult<Py<pyo3::types::PyDict>> {
        let entries = self
            .inner
            .entries_read(show_hidden)
            .map_err(svn_err_to_py)?;
        let dict = pyo3::types::PyDict::new(py);
        for (name, inner) in entries {
            dict.set_item(name, Py::new(py, Entry { inner })?)?;
        }
        Ok(dict.unbind())
    }

    /// Try to obtain an access baton for a path, using this baton as parent.
    ///
    /// Returns ``None`` if the path is not a versioned directory. The returned
    /// baton is tied to this baton's lifetime and must not outlive it.
    #[pyo3(signature = (path, write_lock=false, levels_to_lock=0))]
    fn probe_try(
        &mut self,
        path: &Bound<PyAny>,
        write_lock: bool,
        levels_to_lock: i32,
    ) -> PyResult<Option<Adm>> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        let sub = self
            .inner
            .probe_try(&path_str, write_lock, levels_to_lock)
            .map_err(svn_err_to_py)?;
        // SAFETY: the returned Adm is a borrowed baton (it never closes on
        // drop, see the crate's probe_try). Its lifetime is tied to `self`.
        // The caller must keep this Adm alive. We erase the lifetime to
        // 'static to store it in the pyclass.
        Ok(sub.map(|adm| Self {
            inner: unsafe {
                std::mem::transmute::<subversion::wc::Adm<'_>, subversion::wc::Adm<'static>>(adm)
            },
        }))
    }

    /// Get the property differences between the working copy and base revision.
    ///
    /// Returns ``(changes, original_props)`` where ``changes`` is a list of
    /// ``(name, value)`` tuples and ``original_props`` is a dict or ``None``.
    fn get_prop_diffs(
        &self,
        py: Python<'_>,
        path: &Bound<PyAny>,
    ) -> PyResult<(Py<pyo3::types::PyList>, Option<Py<pyo3::types::PyDict>>)> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        let (changes, original) = self
            .inner
            .get_prop_diffs(&path_str)
            .map_err(svn_err_to_py)?;
        let list = pyo3::types::PyList::empty(py);
        for change in changes {
            let value: Py<PyAny> = match change.value {
                None => py.None(),
                Some(v) => pyo3::types::PyBytes::new(py, &v).into_any().unbind(),
            };
            list.append((change.name, value))?;
        }
        let orig = match original {
            None => None,
            Some(props) => {
                let dict = pyo3::types::PyDict::new(py);
                for (name, value) in props {
                    dict.set_item(name, pyo3::types::PyBytes::new(py, &value))?;
                }
                Some(dict.unbind())
            }
        };
        Ok((list.unbind(), orig))
    }

    /// Transmit local text changes through a file delta editor.
    ///
    /// Returns ``(tempfile, digest)`` where ``digest`` is the 16-byte MD5 of
    /// the transmitted fulltext.
    fn transmit_text_deltas(
        &self,
        py: Python<'_>,
        path: &Bound<PyAny>,
        fulltext: bool,
        editor: &Bound<PyAny>,
    ) -> PyResult<(Option<String>, Py<pyo3::types::PyBytes>)> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        // SAFETY: the editor object is alive for the duration of this call.
        let file_editor = unsafe { wrap_file_editor_from_py(editor)? };
        let (tempfile, digest) = self
            .inner
            .transmit_text_deltas(&path_str, fulltext, file_editor)
            .map_err(svn_err_to_py)?;
        Ok((tempfile, pyo3::types::PyBytes::new(py, &digest).unbind()))
    }

    /// Transmit local property changes through a file delta editor.
    ///
    /// Looks up the entry for ``path`` internally. Returns the temporary file
    /// path used, if any.
    fn transmit_prop_deltas(
        &self,
        path: &Bound<PyAny>,
        editor: &Bound<PyAny>,
    ) -> PyResult<Option<String>> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        // SAFETY: the editor object is alive for the duration of this call.
        let file_editor = unsafe { wrap_file_editor_from_py(editor)? };
        self.inner
            .transmit_prop_deltas(&path_str, file_editor)
            .map_err(svn_err_to_py)
    }

    /// Crawl working copy revisions, reporting to a reporter object.
    ///
    /// ``reporter`` must provide ``set_path``, ``delete_path``, ``link_path``,
    /// ``finish`` and ``abort`` methods.
    #[pyo3(signature = (path, reporter, restore_files=true, depth=3, honor_depth_exclude=true, depth_compatibility_trick=false, use_commit_times=false, notify_func=None))]
    #[allow(clippy::too_many_arguments)]
    fn crawl_revisions(
        &self,
        path: &Bound<PyAny>,
        reporter: Py<PyAny>,
        restore_files: bool,
        depth: i32,
        honor_depth_exclude: bool,
        depth_compatibility_trick: bool,
        use_commit_times: bool,
        notify_func: Option<Py<PyAny>>,
    ) -> PyResult<()> {
        let path_str = subvertpy_util::py_to_svn_abspath(path)?;
        let py_reporter = crate::context::PyReporterBridge { reporter };
        let wrap_reporter = subversion::ra::WrapReporter::from_rust_reporter(py_reporter);
        let notify_fn = crate::context::make_notify_closure(notify_func);
        self.inner
            .crawl_revisions(
                &path_str,
                &wrap_reporter,
                restore_files,
                crate::context::depth_from_py(depth),
                honor_depth_exclude,
                depth_compatibility_trick,
                use_commit_times,
                notify_fn.as_deref(),
            )
            .map_err(svn_err_to_py)
    }

    /// Get an editor for switching this working copy to a different URL.
    ///
    /// Anchored on this (deprecated) access baton, which holds the lock.
    #[pyo3(signature = (target, switch_url, use_commit_times=false, depth=3,
        notify_func=None, diff3_cmd=None, depth_is_sticky=false,
        allow_unver_obstructions=true))]
    #[allow(clippy::too_many_arguments)]
    fn get_switch_editor(
        slf: &Bound<Self>,
        target: &str,
        switch_url: &str,
        use_commit_times: bool,
        depth: i32,
        notify_func: Option<Py<PyAny>>,
        diff3_cmd: Option<&str>,
        depth_is_sticky: bool,
        allow_unver_obstructions: bool,
    ) -> PyResult<subvertpy_util::editor::PyEditor> {
        let _ = notify_func;
        let switch_url = subversion::uri::canonicalize_uri(switch_url).map_err(svn_err_to_py)?;
        let this = slf.borrow();
        let (editor, _target_rev) = this
            .inner
            .get_switch_editor(
                target,
                &switch_url,
                use_commit_times,
                crate::context::depth_from_py(depth),
                depth_is_sticky,
                allow_unver_obstructions,
                diff3_cmd,
            )
            .map_err(svn_err_to_py)?;
        drop(this);
        let parent = slf.clone().into_any().unbind();
        Ok(subvertpy_util::editor::PyEditor::new_with_parent(
            editor, parent,
        ))
    }

    fn __enter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __exit__(
        &mut self,
        _exc_type: Option<&Bound<PyAny>>,
        _exc_val: Option<&Bound<PyAny>>,
        _exc_tb: Option<&Bound<PyAny>>,
    ) -> PyResult<bool> {
        self.inner.close();
        Ok(false)
    }
}
