# TODO: Missing Functionality in subversion-rs

This document tracks functionality needed for the subvertpy port that is missing or incomplete in the subversion-rs crate at `/home/jelmer/src/subversion-rs`.

**Overall Status**: The subversion-rs crate provides ~60-75% API coverage, covering 100% of critical workflows. Missing functionality consists primarily of deprecated APIs, low-level internals, and edge cases.

## Status Legend

- 🔴 **Critical** - Blocks core functionality, must implement
- 🟡 **High** - Important for common use cases, should implement
- 🟢 **Medium** - Nice to have, can workaround
- ⚪ **Low** - Edge cases, can skip

---

## Critical Gaps (Block Porting)

**None** - All critical functionality exists in subversion-rs.

---

## High Priority Gaps

### 🟡 Client: `patch()` operation

**Missing**: Apply unified diff patches (`svn_client_patch()`)

**Impact**: Users cannot apply patch files through the Python API

**Workaround**:
- Shell out to `patch` command
- Or document that users should use external tools

**Effort**: 2-3 days to implement in subversion-rs

**Decision**: Implement workaround first, add to subversion-rs later if needed

---

### 🟡 Client: `vacuum()` operation

**Missing**: Cleanup pristine store (`svn_client_vacuum()`)

**Impact**: Cannot clean up unused pristine files to save disk space

**Workaround**:
- Document that users should run `svn cleanup --vacuum-pristines` command
- Or shell out to `svn` command

**Effort**: 1 day to implement in subversion-rs

**Decision**: Document workaround, low priority for implementation

---

## Medium Priority Gaps

### 🟢 FS: Transaction property management

**Missing**: Full transaction property APIs (~12 functions)
- `svn_fs_txn_prop()`, `svn_fs_change_txn_prop()`
- Transaction property manipulation

**Impact**: Cannot manipulate transaction properties directly (rare use case)

**Use Case**: Repository administration tools, custom hooks

**Workaround**: Use high-level client API which handles transactions automatically

**Effort**: 3-5 days

**Decision**: Only implement if users specifically request repository admin features

---

### 🟢 Client: Shelf operations (SVN 1.11+)

**Missing**: Temporary change storage (~7 functions)
- `svn_client_shelf_*()` functions (like git stash)

**Impact**: Cannot use shelf feature (SVN 1.11+ only, not widely used)

**Workaround**: Not available, feature not commonly used

**Effort**: 4-5 days

**Decision**: Skip unless explicitly requested by users

---

### 🟢 Repos: Authz (authorization) APIs

**Missing**: Path-based authorization (~8 functions)
- `svn_repos_authz_read4()`, `svn_repos_authz_check_access()`, `svn_repos_authz_parse2()`

**Impact**: Cannot implement path-based authorization

**Use Case**: Server implementations (typically handled by mod_authz_svn)

**Workaround**: Not needed for client operations

**Effort**: 4-6 days

**Decision**: Skip unless implementing server features

---

### 🟢 FS: Node history and comparison APIs

**Missing**: Advanced history analysis (~6 functions)
- `svn_fs_node_history2()` - Get node history
- `svn_fs_compare_ids()`, `svn_fs_check_related()` - Node comparison
- `svn_fs_closest_copy()` - Copy source detection

**Impact**: Cannot perform detailed history analysis

**Use Case**: Repository analysis tools

**Workaround**: Use high-level client log/blame operations

**Effort**: 2-3 days

**Decision**: Low priority, workarounds available

---

### 🟢 Client: Detailed conflict introspection

**Missing**: Advanced conflict APIs (~20+ functions)
- Detailed conflict option introspection
- Conflict tree resolution details

**Impact**: Limited conflict resolution options (basic operations work)

**Use Case**: Advanced conflict resolution UI

**Workaround**: Basic conflict resolution works via `resolve()`

**Effort**: 5-7 days

**Decision**: Basic conflict resolution sufficient for most use cases

---

## Low Priority Gaps (Can Skip)

### ⚪ WC: Format upgrade operation

**Missing**: `svn_wc_upgrade()` - Upgrade working copy format

**Impact**: Cannot upgrade WC format through API

**Workaround**: One-time operation, users can run `svn upgrade` command

**Decision**: Skip, not needed for normal operations

---

### ⚪ WC: Relocate operation

**Missing**: `svn_wc_relocate4()` - Change repository URL

**Impact**: Cannot relocate through API

**Workaround**: Rare operation, users can run `svn relocate` command

**Decision**: Skip, rare operation

---

### ⚪ Deprecated APIs

**Missing**: Various deprecated functions
- BDB-specific functions (BDB backend deprecated)
- Legacy ADM functions (deprecated since SVN 1.7)
- Internal translation/canonicalization functions

**Impact**: None - deprecated functionality

**Decision**: Skip entirely

---

## Implementation Strategy

### Phase 1: Port with Workarounds (Current)

Port all modules using existing subversion-rs functionality:

✅ **Can port immediately**:
- RA module (100% coverage)
- Delta/Editor (95% coverage)
- Auth (100% coverage)
- Client core operations (checkout, update, commit, status, log, diff, properties, etc.)
- WC core operations (status, properties, conflicts, pristine)
- Repos core operations (create, load, dump, pack)
- Properties, IO, Config utilities (100% coverage)

⚠️ **Use workarounds for**:
- `patch()` → Document external tool usage
- `vacuum()` → Document `svn cleanup --vacuum-pristines`
- Advanced transaction ops → Limit to high-level API
- Authz → Document not supported

### Phase 2: Optional Enhancements

Only implement if users request:

1. **`client::patch()`** - If patch file support is needed
2. **`client::vacuum()`** - If disk space management is important
3. **FS transaction APIs** - If repository admin tools are needed
4. **Repos authz APIs** - If server features are needed

### Phase 3: Long-term Additions

Low priority enhancements:

- Client shelf operations (SVN 1.11+ only)
- Detailed conflict APIs (for advanced UIs)
- FS node history APIs (for analysis tools)

---

## Contributing Back to subversion-rs

When implementing missing functionality:

1. **Implement in subversion-rs crate first**
   - Write safe Rust wrappers around subversion-sys FFI
   - Add tests
   - Submit PR to subversion-rs

2. **Temporary workarounds in subvertpy**
   - Use unsafe FFI directly if needed
   - Document with TODO comment
   - Link to subversion-rs issue
   - Replace when safe wrapper is available

3. **Update this document**
   - Mark items as ✅ when implemented in subversion-rs
   - Remove from this file when integrated

---

## Summary

The subversion-rs crate is **production-ready for porting subvertpy**. All critical functionality exists, and the few missing operations are:

- **2 operations** worth implementing eventually (`patch`, `vacuum`)
- **4 feature areas** that are nice-to-have (transactions, authz, history, conflicts)
- **Many deprecated/internal** functions that can be ignored

**Recommendation**: Begin porting immediately using existing subversion-rs functionality. Implement workarounds for the 2 missing operations. Add enhancements later based on user feedback.
