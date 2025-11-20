//! Configuration types

use pyo3::prelude::*;
use pyo3::types::PyList;

/// Subversion configuration object
#[pyclass(name = "Config", unsendable)]
pub struct Config {
    _config: subversion::config::Config,
    _servers: subversion::config::Config,
    config_dir: Option<std::path::PathBuf>,
}

#[pymethods]
impl Config {
    /// String representation
    fn __repr__(&self) -> PyResult<String> {
        Ok("<Config>".to_string())
    }

    /// Get default ignore patterns
    fn get_default_ignores(&self, py: Python) -> PyResult<Py<PyList>> {
        // Get the builtin default ignores
        let mut patterns = subversion::wc::get_default_ignores()
            .map_err(|e| subvertpy_util::error::svn_err_to_py(e))?;

        // Add custom global-ignores from config
        if let Ok(config_value) = self
            ._config
            .get(subversion::config::ConfigOption::GlobalIgnores(""))
        {
            if let Some(global_ignores) = config_value.as_string() {
                // Split by whitespace and add to patterns
                for pattern in global_ignores.split_whitespace() {
                    patterns.push(pattern.to_string());
                }
            }
        }

        let py_list = PyList::empty(py);
        for pattern in patterns {
            py_list.append(pattern.as_bytes())?;
        }
        Ok(py_list.unbind())
    }
}

impl Config {
    /// Create a new Config from subversion Config objects
    pub fn new(
        config: subversion::config::Config,
        servers: subversion::config::Config,
        config_dir: Option<&std::path::Path>,
    ) -> Self {
        Self {
            _config: config,
            _servers: servers,
            config_dir: config_dir.map(|p| p.to_path_buf()),
        }
    }

    /// Get a ConfigHash suitable for passing to a client context
    pub fn get_config_hash(
        &self,
    ) -> Result<subversion::config::ConfigHash, subversion::Error<'static>> {
        subversion::config::get_config_hash(self.config_dir.as_deref())
    }
}

/// Configuration item
#[pyclass(name = "ConfigItem", unsendable)]
pub struct ConfigItem {
    // TODO: Store actual config item data
}

#[pymethods]
impl ConfigItem {
    /// String representation
    fn __repr__(&self) -> PyResult<String> {
        Ok("<ConfigItem>".to_string())
    }
}
