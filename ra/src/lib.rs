use pyo3::prelude::*;

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

    fn get_session_url(&self) -> String {
        unimplemented!()
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

    fn has_capability(&self, _name: &str) -> bool {
        unimplemented!()
    }

    fn check_path(&self, _path: &str, _revnum: i64) -> i64 {
        unimplemented!()
    }

    fn stat(&self, _path: &str, _revnum: i64) {
        unimplemented!()
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

    fn change_rev_prop(&self, _revnum: i64, _name: &str, _value: &str) {
        unimplemented!()
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

    fn rev_proplist(&self, _revnum: i64) {
        unimplemented!()
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
        _revision_to_update_to: i64,
        _update_target: &str,
        _recurse: bool,
        _update_editor: &Bound<PyAny>,
        _send_copyfrom_args: bool,
        _ignore_ancestry: bool,
    ) {
        unimplemented!()
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

    fn get_repos_root(&self) -> String {
        unimplemented!()
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

    fn get_latest_revnum(&self) -> i64 {
        unimplemented!()
    }

    fn reparent(&self, _url: &str) {
        unimplemented!()
    }

    fn get_uuid(&self) -> String {
        unimplemented!()
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
