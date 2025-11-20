# Subvertpy C to Rust Port Plan

## Overview

This document outlines the plan for porting the subvertpy C extension modules to Rust using PyO3 and the subversion-rs crate located at `/home/jelmer/src/subversion-rs`.

**Goal**: Port all C extension modules to Rust while maintaining 100% API compatibility with the existing Python interface.

**Strategy**: Port one module at a time, starting with the smallest/most foundational modules and working up to the most complex.

## Current State

### Already Ported to Rust ✅
- **`subr`** module (3 functions):
  - `uri_canonicalize(uri: &str) -> String`
  - `dirent_canonicalize(dirent: &str) -> String`
  - `abspath(path: &str) -> PyResult<String>`

### Existing Infrastructure ✅
- Workspace `Cargo.toml` configured with PyO3 and subversion-rs
- `setuptools_rust` integration in `setup.py`
- Test infrastructure for Rust modules

### Modules to Port (7 modules, ~11,000 LOC)

| Module | Lines | Dependencies | Priority |
|--------|-------|--------------|----------|
| `util.c` | 1,173 | None (shared by all) | **Phase 1** |
| `editor.c` | 1,277 | util | **Phase 2** |
| `repos.c` | 961 | util | **Phase 3a** |
| `_ra_iter_log.c` | 256 | util, _ra | **Phase 3b** |
| `_ra.c` | 3,141 | util, editor | **Phase 4** |
| `wc.c` | 2,075 | util, editor | **Phase 5** |
| `client.c` | 2,078 | util, editor, _ra, wc | **Phase 6** |

**Total C code**: ~11,000 lines
**Total tests**: ~2,100 lines (excellent coverage)

## Port Plan by Phase

---

## Phase 1: Foundation - Utility Module

**Module**: `util.c` (1,173 LOC)
**New Rust module**: `subvertpy/util/src/lib.rs`
**Priority**: CRITICAL - Required by all other modules

### Functionality to Port

The `util.c` file provides shared functionality compiled into multiple modules:

1. **Error Handling**
   - Convert SVN errors to Python `SubversionException`
   - Error message formatting
   - Error chaining (child errors)

2. **APR Pool Management**
   - Pool creation and lifecycle
   - Pool cleanup on Python object destruction
   - Scratch pools for temporary operations

3. **Type Conversions**
   - Python strings ↔ C strings
   - Python paths ↔ SVN paths/URIs
   - Python dicts ↔ APR hash tables (properties)
   - Python lists ↔ APR arrays
   - Python file objects ↔ `svn_stream_t`

4. **Property Handling**
   - Property dictionary conversions
   - Property validation

5. **Stream Handling**
   - Python file-like objects to SVN streams
   - Stream wrappers for callbacks

### subversion-rs Coverage

✅ Available:
- APR pool management (`apr::Pool`)
- Error handling (`subversion::Error`)
- Basic type conversions
- Stream handling (via `pyo3-filelike`)

❓ Need to verify:
- Full property dict conversion utilities
- Python exception integration with PyO3
- Thread state management (PyO3 handles differently than C)

### Testing Strategy
- Port existing `util.c` tests
- Test all type conversions with boundary cases
- Test error handling and exception propagation
- Test pool cleanup and memory management

### Estimated Effort
**Medium-High** (2-3 weeks)
- Complex FFI interactions
- Critical for all other modules
- Need comprehensive testing

---

## Phase 2: Delta Editor

**Module**: `editor.c` (1,277 LOC)
**New Rust module**: `subvertpy/editor/src/lib.rs`
**Priority**: HIGH - Required by `_ra`, `wc`, and `client`

### Functionality to Port

1. **Editor Class** (Root Editor)
   - `open_root()` - Open root directory
   - `set_target_revision()` - Set target revision
   - `close()` - Close editor and apply changes
   - `abort()` - Abort editing
   - Context manager support (`__enter__`, `__exit__`)

2. **DirectoryEditor Class**
   - `add_directory()` - Add new directory
   - `open_directory()` - Open existing directory
   - `delete_entry()` - Delete entry
   - `add_file()` - Add new file
   - `open_file()` - Open existing file
   - `absent_file()` - Mark file as absent
   - `absent_directory()` - Mark directory as absent
   - `change_prop()` - Change property
   - `close()` - Close directory
   - Context manager support

3. **FileEditor Class**
   - `change_prop()` - Change file property
   - `apply_textdelta()` - Apply text delta
   - `close()` - Close file
   - Context manager support

4. **TxDeltaWindowHandler Class**
   - Window handler for receiving delta windows
   - Streaming delta application

5. **Editor Bridging**
   - Python editor callbacks ↔ SVN C editor vtable
   - Baton handling for callbacks

### subversion-rs Coverage

✅ Available:
- Delta editor interface (`subversion::delta`)
- Editor vtable structures
- Text delta handling

❓ Need to verify:
- Python-to-C editor callback bridging
- Context manager support in PyO3
- Window handler streaming API

### Testing Strategy
- Port existing `editor.c` tests
- Test all editor operations with Python callbacks
- Test context manager behavior
- Test abort scenarios
- Test property changes

### Estimated Effort
**Medium** (2-3 weeks)
- Well-defined interface
- Complex callback handling
- Context manager patterns

---

## Phase 3a: Repository Module

**Module**: `repos.c` (961 LOC)
**New Rust module**: `subvertpy/repos/src/lib.rs`
**Priority**: MEDIUM - Smallest independent module

### Functionality to Port

1. **Repository Class**
   - `create()` - Create new repository
   - `fs()` - Get filesystem handle
   - `lock_dir()` - Get lock directory path
   - `get_locks()` - Get locks in repository
   - `dump_fs()` - Dump repository
   - `load_fs()` - Load repository dump
   - `replay()` - Replay revision changes

2. **FileSystem Class**
   - `get_uuid()` - Get repository UUID
   - `youngest_revision()` - Get latest revision
   - `revision_root()` - Get revision root
   - `change_rev_prop()` - Change revision property
   - `revision_prop()` - Get revision property
   - `revision_proplist()` - List revision properties
   - `begin_txn()` - Begin transaction

3. **FileSystemRoot Class**
   - `check_path()` - Check path type
   - `is_dir()` - Check if directory
   - `is_file()` - Check if file
   - `node_created_rev()` - Get node creation revision
   - `node_created_path()` - Get node creation path
   - `node_prop()` - Get node property
   - `node_proplist()` - List node properties
   - `dir_entries()` - List directory entries
   - `file_content()` - Get file content stream
   - `file_length()` - Get file length
   - `get_file_digest()` - Get file checksum
   - `paths_changed()` - Get changed paths
   - `copied_from()` - Get copy source

4. **Stream Class**
   - `read()` - Read from stream
   - `write()` - Write to stream
   - `close()` - Close stream

5. **Module Functions**
   - `create()` - Create repository
   - `version()` - Get version info
   - `api_version()` - Get API version

### subversion-rs Coverage

✅ Available:
- Repository management (`subversion::repos`)
- Filesystem API (`subversion::fs`)
- Path operations
- Property handling
- Stream I/O

❓ Need to verify:
- Dump/load functionality
- Lock handling
- Transaction API completeness

### Testing Strategy
- Port existing `test_repos.py` (152 lines)
- Test repository creation and lifecycle
- Test filesystem operations
- Test transactions
- Test dump/load

### Estimated Effort
**Medium** (2 weeks)
- Relatively independent
- Well-defined API
- Good test coverage

---

## Phase 3b: RA Iterator Helper

**Module**: `_ra_iter_log.c` (256 LOC)
**New Rust module**: Can be integrated into `_ra` module
**Priority**: LOW - Small helper module

### Functionality to Port

This is a small helper module that provides an iterator interface for log entries from the remote access layer.

- Iterator protocol implementation
- Log entry buffering
- Callback handling

### subversion-rs Coverage

✅ Available:
- Log iteration support in RA module
- Iterator patterns in Rust are idiomatic

### Testing Strategy
- Test as part of `_ra` module tests
- Test iteration patterns
- Test early termination

### Estimated Effort
**Low** (2-3 days)
- Very small module
- May integrate directly into `_ra`

---

## Phase 4: Remote Access Module

**Module**: `_ra.c` (3,141 LOC)
**New Rust module**: `subvertpy/_ra/src/lib.rs`
**Priority**: HIGH - Core functionality, largest module

### Functionality to Port

1. **RemoteAccess Class** (Main RA Session)
   - Session management:
     - `get_session_url()` - Get session URL
     - `get_repos_root()` - Get repository root
     - `get_uuid()` - Get repository UUID
     - `reparent()` - Change session URL

   - Revision operations:
     - `get_latest_revnum()` - Get HEAD revision
     - `check_path()` - Check path existence/type
     - `stat()` - Get path information
     - `get_file()` - Fetch file content
     - `get_dir()` - List directory
     - `get_log()` - Get revision log
     - `iter_log()` - Iterate over log entries

   - Revision history:
     - `get_file_revs()` - Get file revision history
     - `get_locations()` - Get path locations
     - `get_location_segments()` - Get location segments

   - Update/switch operations:
     - `do_update()` - Update working copy
     - `do_switch()` - Switch working copy
     - `do_diff()` - Generate diff

   - Commit operations:
     - `get_commit_editor()` - Get editor for committing
     - `change_rev_prop()` - Change revision property

   - Replay:
     - `replay()` - Replay single revision
     - `replay_range()` - Replay revision range

   - Locking:
     - `lock()` - Lock paths
     - `unlock()` - Unlock paths
     - `get_locks()` - Get locks

   - Capabilities:
     - `has_capability()` - Check server capability

   - Merge tracking:
     - `mergeinfo()` - Get merge information

2. **Reporter Class** (Update Reporter)
   - `set_path()` - Set path revision
   - `delete_path()` - Delete path
   - `link_path()` - Link path
   - `finish()` - Finish report
   - `abort()` - Abort report

3. **Auth Class** (Authentication Manager)
   - `set_parameter()` - Set auth parameter
   - `get_parameter()` - Get auth parameter
   - `credentials()` - Get credentials

4. **AuthProvider Class**
   - Base class for authentication providers

5. **CredentialsIter Class**
   - Iterator over credentials

6. **Module Functions**
   - `version()` - Get version
   - `api_version()` - Get API version
   - Auth provider factories:
     - `get_simple_provider()`
     - `get_ssl_client_cert_file_provider()`
     - `get_ssl_client_cert_pw_file_provider()`
     - `get_ssl_server_trust_file_provider()`
     - `get_username_prompt_provider()`
     - `get_simple_prompt_provider()`

### subversion-rs Coverage

✅ Available:
- RA session management (`subversion::ra`)
- Authentication (`subversion::auth`)
- File/directory operations
- Log retrieval
- Update reporters
- Editor integration

❓ Need to verify:
- All authentication provider types
- Replay functionality completeness
- Reporter protocol edge cases
- Capability checks

### Testing Strategy
- Port existing `test_ra.py` (557 lines - most comprehensive tests)
- Test authentication mechanisms
- Test file/directory operations
- Test log iteration
- Test update/switch operations
- Test locking
- Test merge info

### Estimated Effort
**High** (4-5 weeks)
- Largest module
- Complex authentication handling
- Many operations to port
- Critical functionality

---

## Phase 5: Working Copy Module

**Module**: `wc.c` (2,075 LOC)
**New Rust module**: `subvertpy/wc/src/lib.rs`
**Priority**: HIGH - Core functionality

### Functionality to Port

1. **Context Class** (Working Copy Context)
   - Context creation and configuration
   - Various WC operations (details need exploration)

2. **Status3 Class**
   - Working copy status information
   - Status fields (text status, prop status, etc.)

3. **CommittedQueue Class**
   - Queue for processing committed items

4. **Module Functions**
   - Various working copy utility functions
   - Version functions

### subversion-rs Coverage

✅ Available:
- Working copy context (`subversion::wc`)
- Status operations
- WC database access

❓ Need to verify:
- Full status structure mapping
- Queue implementations
- All WC operation types

### Testing Strategy
- Port existing `test_wc.py` (75 lines)
- Test status operations
- Test context management
- Test commit queues

### Estimated Effort
**High** (4-5 weeks)
- Large module
- Complex WC operations
- Database interactions

---

## Phase 6: Client Module

**Module**: `client.c` (2,078 LOC)
**New Rust module**: `subvertpy/client/src/lib.rs`
**Priority**: HIGH - Depends on all other modules

### Functionality to Port

1. **Client Class** (High-level Client Operations)
   - Basic operations:
     - `add()` - Add files/directories
     - `delete()` - Delete files/directories
     - `copy()` - Copy files/directories
     - `move()` - Move files/directories
     - `mkdir()` - Create directory

   - Working copy operations:
     - `checkout()` - Checkout from repository
     - `update()` - Update working copy
     - `switch()` - Switch working copy
     - `revert()` - Revert changes
     - `cleanup()` - Cleanup working copy
     - `relocate()` - Relocate working copy

   - Commit operations:
     - `commit()` - Commit changes
     - `import_()` - Import into repository

   - Information:
     - `info()` - Get path information
     - `status()` - Get status (via status function)
     - `list()` - List directory
     - `log()` - Get log
     - `blame()` - Get blame/annotation

   - Export/Cat:
     - `export()` - Export from repository
     - `cat()` - Output file contents

   - Diff:
     - `diff()` - Generate diff

   - Properties:
     - `propset()` - Set property
     - `propget()` - Get property
     - `proplist()` - List properties

   - Locking:
     - `lock()` - Lock paths
     - `unlock()` - Unlock paths

   - Conflict resolution:
     - `resolve()` - Resolve conflicts

2. **Config Class**
   - `get_default_ignores()` - Get default ignores

3. **Module Functions**
   - `get_config()` - Get configuration
   - `version()` - Get version
   - `api_version()` - Get API version

### subversion-rs Coverage

✅ Available:
- Client context (`subversion::client::Context`)
- All major client operations
- Configuration management
- Conflict resolution

❓ Need to verify:
- All callback types
- Complete config API
- All operation options

### Testing Strategy
- Port existing `test_client.py` (268 lines)
- Test all CRUD operations
- Test checkout/update/commit workflow
- Test property operations
- Test locking
- Test conflict resolution

### Estimated Effort
**High** (5-6 weeks)
- Very large module
- Depends on all other modules
- Many high-level operations
- Complex callback handling

---

## Pure Python Modules (No Porting Needed)

These modules are already in pure Python and should remain as-is:

1. **`subvertpy.ra`** - High-level RA wrapper with URL routing
2. **`subvertpy.delta`** - Pure Python txdelta operations
3. **`subvertpy.marshall`** - SVN protocol marshalling
4. **`subvertpy.properties`** - Property utilities
5. **`subvertpy.server`** - Server implementation
6. **`subvertpy.ra_svn`** - RA SVN protocol

---

## Technical Considerations

### 1. APR Memory Management

**Challenge**: C code uses APR pools extensively for memory management.

**Solution**:
- Use `apr::Pool` from subversion-rs crate
- Create pool wrappers in Rust modules
- Ensure pools live long enough (lifetime management)
- Use Python object lifecycle to trigger pool cleanup

### 2. Callback Handling

**Challenge**: Complex callback systems from Python → Rust → C → SVN.

**Solution**:
- Use PyO3's `PyObject` and `Py<PyAny>` for storing Python callbacks
- Use `py.allow_threads()` for releasing GIL during C calls
- Store callbacks in Rust structs with proper Send/Sync bounds
- Handle Python exceptions in callbacks and convert to SVN errors

### 3. Thread Safety & GIL

**Challenge**: C code uses `PyEval_SaveThread()` / `PyEval_RestoreThread()`.

**Solution**:
- PyO3 handles this with `py.allow_threads()` closure
- Wrap long-running C operations in `allow_threads` blocks
- Ensure Python objects are not accessed without GIL

### 4. Context Managers

**Challenge**: Many C objects implement `__enter__` / `__exit__`.

**Solution**:
- Implement `__enter__` and `__exit__` methods in PyO3
- Use `#[pyclass]` with custom methods
- Handle resource cleanup in `__exit__`

### 5. Error Handling

**Challenge**: Converting SVN errors to Python exceptions.

**Solution**:
- Use `subversion::Error` type from subversion-rs
- Convert to `PyErr` in PyO3
- Maintain error chaining (child errors)
- Keep error codes and messages intact

### 6. Stream Handling

**Challenge**: Python file-like objects ↔ `svn_stream_t`.

**Solution**:
- Use `pyo3-filelike` crate (already in dependencies)
- Implement stream wrappers for Python file objects
- Handle seek, read, write operations

### 7. Version Compatibility

**Challenge**: C code uses `ONLY_SINCE_SVN` macros for version compatibility.

**Solution**:
- Use Rust's conditional compilation: `#[cfg(feature = "svn-1-14")]`
- Feature flags in `Cargo.toml` for different SVN versions
- Runtime version checks where needed

---

## Build System

### Current Setup
- Uses `setuptools_rust` in `setup.py`
- Builds both C and Rust extensions
- Supports incremental porting (mix C and Rust)

### Migration Strategy
1. Keep C and Rust modules side-by-side during porting
2. Each phase replaces one C module with Rust equivalent
3. Update `setup.py` to remove C module and add Rust module
4. Ensure binary compatibility (same module names)

---

## Testing Strategy

### Test Coverage
- **Total tests**: ~2,100 lines
- All modules have good test coverage
- Tests will validate Rust port correctness

### Testing Approach
1. Run existing tests against Rust modules
2. Tests should pass without modification (API compatible)
3. Add additional tests for Rust-specific concerns (memory safety, etc.)
4. Use `pytest` for all testing

### CI/CD
- Run tests for both C and Rust modules during transition
- Ensure no regressions
- Test on multiple Python versions
- Test on multiple platforms (Linux, macOS, Windows)

---

## Timeline Estimate

| Phase | Module | Effort | Duration |
|-------|--------|--------|----------|
| 1 | `util` | Medium-High | 2-3 weeks |
| 2 | `editor` | Medium | 2-3 weeks |
| 3a | `repos` | Medium | 2 weeks |
| 3b | `_ra_iter_log` | Low | 2-3 days |
| 4 | `_ra` | High | 4-5 weeks |
| 5 | `wc` | High | 4-5 weeks |
| 6 | `client` | High | 5-6 weeks |

**Total estimated time**: 20-26 weeks (~5-6 months)

This estimate assumes:
- One developer working full-time
- Familiarity with PyO3 and Rust
- Access to subversion-rs crate maintainer for questions
- Parallel testing and documentation work

---

## Dependencies on subversion-rs

### Currently Available

The subversion-rs crate provides extensive coverage:

✅ **Core functionality**:
- APR pool management
- Error handling
- Type conversions
- Basic string utilities

✅ **Module-specific**:
- `subversion::ra` - Remote access
- `subversion::client` - Client operations
- `subversion::wc` - Working copy
- `subversion::repos` - Repository
- `subversion::fs` - Filesystem
- `subversion::delta` - Delta editor
- `subversion::auth` - Authentication
- `subversion::config` - Configuration

✅ **PyO3 integration**:
- `pyo3` feature for Python interop
- Type conversions for common types
- Stream handling via `pyo3-filelike`

### Potential Gaps (To Be Verified)

The following may need additions to subversion-rs:

❓ **Utility functions**:
- Complete property dictionary conversions
- All stream wrapper types
- Python-specific helper functions

❓ **Editor**:
- Full Python callback bridging
- All editor callback types

❓ **RA**:
- All authentication provider types
- Complete capability checking
- All reporter operations

❓ **WC**:
- Complete status structure
- All context operations
- Queue implementations

❓ **Client**:
- All callback types
- Complete configuration API

### Process for Missing Functionality

When functionality is missing in subversion-rs:

1. **Document in `TODO.subversion-rs.md`** (see below)
2. **Temporary workaround**:
   - Use unsafe FFI calls directly from subversion-sys
   - Add TODO comment in Rust code
   - Create issue in subversion-rs repo
3. **Long-term**:
   - Contribute to subversion-rs crate
   - Replace unsafe FFI with safe wrappers
   - Submit PR to subversion-rs

---

## Success Criteria

The port will be considered successful when:

1. ✅ All C modules are replaced with Rust equivalents
2. ✅ All existing tests pass without modification
3. ✅ Python API remains 100% compatible
4. ✅ No performance regressions
5. ✅ Memory safety improvements (no leaks, no crashes)
6. ✅ Documentation updated
7. ✅ CI/CD pipeline passes
8. ✅ Binary packages build correctly (wheels, etc.)

---

## Risk Mitigation

### Risk: Missing functionality in subversion-rs

**Mitigation**:
- Early exploration phase to identify gaps
- Use unsafe FFI as temporary solution
- Contribute back to subversion-rs
- Document all workarounds

### Risk: API incompatibilities

**Mitigation**:
- Comprehensive test suite validates compatibility
- Port one module at a time
- Test against real-world usage
- Beta testing period

### Risk: Performance regressions

**Mitigation**:
- Benchmark C vs Rust implementations
- Profile critical paths
- Optimize Rust code
- Consider using release builds for testing

### Risk: Build complexity

**Mitigation**:
- Keep C and Rust builds separate
- Use feature flags for gradual rollout
- Test on multiple platforms early
- Good CI/CD coverage

---

## Next Steps

1. **Validate subversion-rs capabilities**:
   - Review subversion-rs API in detail
   - Test PyO3 integration
   - Identify missing features
   - Create initial TODO.subversion-rs.md

2. **Set up development environment**:
   - Configure Rust workspace
   - Set up testing framework
   - Configure CI/CD

3. **Begin Phase 1 (util module)**:
   - Create util Rust module
   - Port utility functions
   - Port tests
   - Validate against existing tests

4. **Iterate through phases**:
   - Complete each phase sequentially
   - Update documentation
   - Keep TODO.subversion-rs.md updated
   - Regular testing and validation
