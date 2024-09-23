use pyo3::prelude::*;
use pyo3::types::PyBytes;
use std::collections::HashMap;
use subversion::delta::{Editor, DirectoryEditor, FileEditor, TextDelta};

#[pyfunction]
fn version() -> (i32, i32, i32, String) {
    let version = subversion::ra::version();
    (
        version.major(),
        version.minor(),
        version.patch(),
        version.tag().to_string(),
    )
}

#[pyfunction]
fn get_ssl_client_cert_pw_file_provider() {
    unimplemented!()
}

#[pyfunction]
fn get_ssl_client_cert_file_provider() {
    unimplemented!()
}

#[pyfunction]
fn get_ssl_server_trust_file_provider() {
    unimplemented!()
}

#[pyfunction]
fn get_simple_provider() {
    unimplemented!()
}

#[pyfunction]
fn get_windows_simple_provider() {
    unimplemented!()
}

#[pyfunction]
fn get_windows_ssl_server_trust_provider() {
    unimplemented!()
}

#[pyfunction]
fn get_username_prompt_provider() {
    unimplemented!()
}

#[pyfunction]
fn get_simple_prompt_provider() {
    unimplemented!()
}

#[pyfunction]
fn get_ssl_server_trust_prompt_provider() {
    unimplemented!()
}

#[pyfunction]
fn get_ssl_client_cert_prompt_provider() {
    unimplemented!()
}

#[pyfunction]
fn get_ssl_client_cert_pw_prompt_provider() {
    unimplemented!()
}

#[pyfunction]
fn get_username_provider() {
    unimplemented!()
}

#[pyfunction]
fn get_platform_specific_client_providers() {
    unimplemented!()
}

#[pyfunction]
fn print_modules() {
    unimplemented!()
}

#[pyclass]
struct RemoteAccess {
    ra: std::sync::Mutex<subversion::ra::Session>,
    corrected_url: String,
}

#[pyclass]
struct PyDirent(subversion::ra::Dirent);

struct PyEditor(PyObject);

impl Editor for PyEditor {
    fn set_target_revision(&mut self, revision: i64) -> Result<(), crate::Error> {
        Python::with_gil(|py| {
            self.0.call_method1(py, "set_target_revision", (revision,))?;
            Ok(())
        })
    }

    fn open_root<'a>(
        &'a mut self,
        base_revision: i64,
    ) -> Result<Box<dyn DirectoryEditor + 'a>, crate::Error> {
        let directory = Python::with_gil(|py| self.0.call_method1(py, "open_root", (base_revision,)))?;
        Ok(Box::new(PyDirectoryEditor(directory)))
    }

    fn close(&mut self) -> Result<(), crate::Error> {
        Python::with_gil(|py| {
            self.0.call_method0(py, "close")?;
            Ok(())
        })
    }

    fn abort(&mut self) -> Result<(), crate::Error> {
        Python::with_gil(|py| {
            self.0.call_method0(py, "abort")?;
            Ok(())
        })
    }
}

struct PyDirectoryEditor(PyObject);

impl subversion::delta::DirectoryEditor for PyDirectoryEditor {
    fn delete_entry(&mut self, path: &str, revision: Option<i64>) -> Result<(), crate::Error> {
        Python::with_gil(|py| {
            self.0.call_method1(py, "delete_entry", (path, revision))?;
            Ok(())
        })
    }

    fn add_directory<'a>(
        &'a mut self,
        path: &str,
        copyfrom: Option<(&str, i64)>,
    ) -> Result<Box<dyn DirectoryEditor + 'a>, crate::Error> {
        let directory = Python::with_gil(|py| self.0.call_method1(py, "add_directory", (path, copyfrom)))?;
        Ok(Box::new(PyDirectoryEditor(directory)))
    }

    fn open_directory<'a>(
        &'a mut self,
        path: &str,
        base_revision: Option<i64>,
    ) -> Result<Box<dyn DirectoryEditor + 'a>, crate::Error> {
        let directory = Python::with_gil(|py| self.0.call_method1(py, "open_directory", (path, base_revision)))?;
        Ok(Box::new(PyDirectoryEditor(directory)))
    }

    fn change_prop(&mut self, name: &str, value: &[u8]) -> Result<(), crate::Error> {
        Python::with_gil(|py| {
            self.0.call_method1(py, "change_prop", (name, value))?;
            Ok(())
        })
    }

    fn close(&mut self) -> Result<(), crate::Error> {
        Python::with_gil(|py| {
            self.0.call_method0(py, "close")?;
            Ok(())
        })
    }

    fn absent_directory(&mut self, path: &str) -> Result<(), crate::Error> {
        Python::with_gil(|py| {
            self.0.call_method1(py, "absent_directory", (path,))?;
            Ok(())
        })
    }

    fn add_file<'a>(
        &'a mut self,
        path: &str,
        copyfrom: Option<(&str, i64)>,
    ) -> Result<Box<dyn FileEditor + 'a>, crate::Error> {
        let file = Python::with_gil(|py| self.0.call_method1(py, "add_file", (path, copyfrom)))?;
        Ok(Box::new(PyFileEditor(file)))
    }

    fn open_file<'a>(
        &'a mut self,
        path: &str,
        base_revision: Option<i64>,
    ) -> Result<Box<dyn FileEditor + 'a>, crate::Error> {
        let file = Python::with_gil(|py| self.0.call_method1(py, "open_file", (path, base_revision)))?;
        Ok(Box::new(PyFileEditor(file)))
    }

    fn absent_file(&mut self, path: &str) -> Result<(), crate::Error> {
        Python::with_gil(|py| {
            self.0.call_method1(py, "absent_file", (path,))?;
            Ok(())
        })
    }
}

struct PyFileEditor(PyObject);

struct PyTextDelta(PyObject);

impl TextDelta for PyTextDelta {
    fn apply(&mut self, window: &[u8]) -> Result<(), crate::Error> {
        Python::with_gil(|py| {
            self.0.call_method1(py, "apply", (window,))?;
            Ok(())
        })
    }

    fn close(&mut self) -> Result<(), crate::Error> {
        Python::with_gil(|py| {
            self.0.call_method0(py, "close")?;
            Ok(())
        })
    }
}

impl FileEditor for PyFileEditor {
    fn apply_textdelta(&mut self, base_checksum: Option<&str>) -> Result<Box<dyn TextDelta + '_>, crate::Error> {
        let text_delta = Python::with_gil(|py| self.0.call_method1(py, "apply_textdelta", (base_checksum,)))?;
        Ok(Box::new(PyTextDelta(text_delta)))
    }

    fn change_prop(&mut self, name: &str, value: &[u8]) -> Result<(), crate::Error> {
        Python::with_gil(|py| {
            self.0.call_method1(py, "change_prop", (name, value))?;
            Ok(())
        })
    }

    fn close(&mut self, text_checksum: Option<&str>) -> Result<(), crate::Error> {
        Python::with_gil(|py| {
            self.0.call_method1(py, "close", (text_checksum,))?;
            Ok(())
        })
    }
}

#[pymethods]
impl RemoteAccess {
    #[getter]
    fn busy(&mut self) -> bool {
        self.ra.lock().is_err()
    }

    #[getter]
    fn corrected_url(&self) -> &str {
        &self.corrected_url
    }

    #[getter]
    fn get_progress_func(&self) {
        unimplemented!()
    }

    #[setter]
    fn set_progress_func(&self, _progress_func: &Bound<PyAny>) {
        unimplemented!()
    }

    fn get_session_url(&self) -> Result<String, PyErr> {
        Ok(self.ra.lock().unwrap().get_session_url().unwrap())
    }

    fn get_file_revs(&self, _path: &str, _start_rev: i64, _end_revs: i64, _handler: &Bound<PyAny>) {
        unimplemented!()
    }

    fn get_locations(&self, _path: &str, _peg_revision: i64, _location_revisions: i64) {
        unimplemented!()
    }

    fn get_locks(&self, _path: &str, _depth: i64) {
        unimplemented!()
    }

    fn lock(&self, _path_revs: &str, _comment: &str, _steal_lock: bool, _lock_func: &Bound<PyAny>) {
        unimplemented!()
    }

    fn unlock(&self, _path_tokens: &str, _break_lock: bool, _lock_func: &Bound<PyAny>) {
        unimplemented!()
    }

    fn mergeinfo(&self, _paths: &str, _revision: i64, _inherit: bool, _include_descendants: bool) {
        unimplemented!()
    }

    fn get_location_segments(
        &self,
        _path: &str,
        _peg_revision: i64,
        _start_revision: i64,
        _end_revision: i64,
        _rcvr: &Bound<PyAny>,
    ) {
        unimplemented!()
    }

    fn has_capability(&self, name: &str) -> bool {
        self.ra.lock().unwrap().has_capability(name).unwrap()
    }

    fn check_path(&self, path: &str, revnum: i64) -> i64 {
        match self.ra.lock().unwrap().check_path(path, revnum).unwrap() {
            subversion::NodeKind::None => 0,
            subversion::NodeKind::File => 1,
            subversion::NodeKind::Dir => 2,
            subversion::NodeKind::Symlink => 3,
            subversion::NodeKind::Unknown => 4,
        }
    }

    fn stat(&self, path: &str, revnum: i64) -> Result<PyDirent, PyErr> {
        Ok(PyDirent(self.ra.lock().unwrap().stat(path, revnum).unwrap()))
    }

    fn get_lock(&self, _path: &str) {
        unimplemented!()
    }

    fn get_dir(&self, _path: &str, _revision: i64, _dirent_fields: i64) {
        unimplemented!()
    }

    fn get_file(&self, _path: &str, _stream: &Bound<PyAny>, _revnum: i64) {
        unimplemented!()
    }

    #[pyo3(signature = (revnum, name, old_value, new_value))]
    fn change_rev_prop(&self, revnum: i64, name: &str, old_value: Option<&[u8]>, new_value: &[u8]) -> Result<(), PyErr> {
        Ok(self.ra.lock().unwrap().change_revprop(revnum, name, old_value, new_value).unwrap())
    }

    fn get_commit_editor(
        &self,
        _revprops: &str,
        _commit_callback: &Bound<PyAny>,
        _lock_tokens: &str,
        _keep_locks: bool,
    ) {
        unimplemented!()
    }

    fn rev_proplist(&self, py: Python, revnum: i64) -> Result<HashMap<String, PyObject>, PyErr> {
        let revprops = self.ra.lock().unwrap().rev_proplist(revnum).unwrap();

        Ok(revprops
            .into_iter()
            .map(|(k, v)| (k, PyBytes::new_bound(py, &v).to_object(py)))
            .collect())
    }

    fn replay(
        &self,
        _revision: i64,
        _low_water_mark: i64,
        _update_editor: &Bound<PyAny>,
        _send_deltas: bool,
    ) {
        unimplemented!()
    }

    fn replay_range(
        &self,
        _start_rev: i64,
        _end_rev: i64,
        _low_water_mark: i64,
        _cbs: &Bound<PyAny>,
        _send_deltas: bool,
    ) {
        unimplemented!()
    }

    fn do_switch(
        &self,
        _revision_to_update_to: i64,
        _update_target: &str,
        _recurse: bool,
        _switch_url: &str,
        _update_editor: &Bound<PyAny>,
        _send_copyfrom_args: bool,
        _ignore_ancestry: bool,
    ) {
        unimplemented!()
    }

    fn do_update(
        &self,
        revision_to_update_to: i64,
        update_target: &str,
        recurse: bool,
        update_editor: &Bound<PyAny>,
        send_copyfrom_args: bool,
        ignore_ancestry: bool,
    ) {
        self.ra
            .lock()
            .unwrap()
            .do_update(
                revision_to_update_to,
                update_target,
                recurse,
                PyEditor(update_editor),
                send_copyfrom_args,
                ignore_ancestry,
            )
            .unwrap();
    }

    fn do_diff(
        &self,
        _revision_to_update_to: i64,
        _diff_target: &str,
        _versus_url: &str,
        _diff_editor: &Bound<PyAny>,
        _recurse: bool,
        _ignore_ancestry: bool,
        _text_deltas: bool,
    ) {
        unimplemented!()
    }

    fn get_repos_root(&self) -> Result<String, PyErr> {
        Ok(self.ra.lock().unwrap().get_repos_root().unwrap())
    }

    fn get_log(
        &self,
        _callback: &Bound<PyAny>,
        _paths: &str,
        _start: i64,
        _end: i64,
        _limit: i64,
        _discover_changed_paths: bool,
        _strict_node_history: bool,
        _include_merged_revisions: bool,
        _revprops: &str,
    ) {
        unimplemented!()
    }

    fn iter_log(
        &self,
        _paths: &str,
        _start: i64,
        _end: i64,
        _limit: i64,
        _discover_changed_paths: bool,
        _strict_node_history: bool,
        _include_merged_revisions: bool,
        _revprops: &str,
    ) {
        unimplemented!()
    }

    fn get_latest_revnum(&self) -> Result<i64, PyErr> {
        Ok(self.ra.lock().unwrap().get_latest_revnum().unwrap())
    }

    fn reparent(&self, url: &str) -> Result<(), PyErr> {
        Ok(self.ra.lock().unwrap().reparent(url).unwrap())
    }

    fn get_uuid(&self) -> Result<String, PyErr> {
        Ok(self.ra.lock().unwrap().get_uuid().unwrap())
    }
}

#[pyclass]
pub struct Auth(subversion::auth::AuthBaton);

#[pymethods]
impl Auth {
    fn set_parameter(&mut self, _name: &str, _value: &str) {
        unimplemented!()
    }

    fn get_parameter(&self, _name: &str) -> String {
        unimplemented!()
    }

    fn credentials(&self) {
        unimplemented!()
    }
}

#[pymodule]
fn ra(_py: Python, m: &Bound<PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(get_ssl_client_cert_pw_file_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_ssl_client_cert_file_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_ssl_server_trust_file_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_simple_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_windows_simple_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_windows_ssl_server_trust_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_username_prompt_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_simple_prompt_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_ssl_server_trust_prompt_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_ssl_client_cert_prompt_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_ssl_client_cert_pw_prompt_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_username_provider, m)?)?;
    m.add_function(wrap_pyfunction!(get_platform_specific_client_providers, m)?)?;
    m.add_function(wrap_pyfunction!(print_modules, m)?)?;

    m.add_class::<RemoteAccess>()?;
    m.add_class::<Auth>()?;
    Ok(())
}
