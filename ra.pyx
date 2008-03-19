# Copyright (C) 2008 Jelmer Vernooij <jelmer@samba.org>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from apr cimport apr_pool_t, apr_pool_destroy, apr_palloc
from apr cimport apr_hash_t, apr_hash_make, apr_hash_index_t, apr_hash_first, apr_hash_next, apr_hash_this, apr_hash_set
from apr cimport apr_array_header_t, apr_array_make, apr_array_push
from apr cimport apr_file_t, apr_off_t, apr_size_t, apr_uint32_t
from apr cimport apr_initialize, apr_pstrdup
from core cimport check_error, Pool, wrap_lock, string_list_to_apr_array, py_svn_log_wrapper, new_py_stream, prop_hash_to_dict, py_svn_error
from core import SubversionException
from constants import PROP_REVISION_LOG, PROP_REVISION_AUTHOR, PROP_REVISION_DATE
from types cimport svn_error_t, svn_revnum_t, svn_string_t, svn_version_t
from types cimport svn_string_ncreate, svn_lock_t, svn_auth_baton_t, svn_auth_open, svn_auth_set_parameter, svn_auth_get_parameter, svn_node_kind_t, svn_commit_info_t, svn_filesize_t, svn_dirent_t, svn_log_message_receiver_t
from types cimport svn_stream_t, svn_auth_get_simple_provider, svn_auth_provider_object_t, svn_auth_get_ssl_server_trust_file_provider, svn_auth_get_ssl_client_cert_file_provider, svn_auth_get_ssl_client_cert_pw_file_provider, svn_auth_get_username_provider, svn_auth_get_username_prompt_provider, svn_auth_cred_username_t, svn_auth_get_simple_prompt_provider, svn_auth_cred_simple_t, svn_auth_get_ssl_server_trust_prompt_provider, svn_auth_ssl_server_cert_info_t, svn_auth_cred_ssl_server_trust_t, svn_boolean_t, svn_auth_get_ssl_client_cert_pw_prompt_provider, svn_auth_cred_ssl_client_cert_pw_t 

apr_initialize()

cdef extern from "Python.h":
    object PyString_FromStringAndSize(char *, unsigned long)
    void Py_INCREF(object)
    void Py_DECREF(object)


cdef extern from "svn_types.h":
    ctypedef svn_error_t *(*svn_commit_callback2_t) (svn_commit_info_t *commit_info, baton, apr_pool_t *pool) except *

cdef svn_error_t *py_commit_callback(svn_commit_info_t *commit_info, baton, apr_pool_t *pool) except *:
    baton(commit_info.revision, commit_info.date, commit_info.author)

cdef extern from "svn_ra.h":
    svn_version_t *svn_ra_version()

    ctypedef void (*svn_ra_progress_notify_func_t)(apr_off_t progress, 
            apr_off_t total, void *baton, apr_pool_t *pool) except *

    ctypedef svn_error_t *(*svn_ra_get_wc_prop_func_t)(void *baton,
                                                  char *relpath,
                                                  char *name,
                                                  svn_string_t **value,
                                                  apr_pool_t *pool) except *

    ctypedef svn_error_t *(*svn_ra_set_wc_prop_func_t)(void *baton,
                                                  char *path,
                                                  char *name,
                                                  svn_string_t *value,
                                                  apr_pool_t *pool) except *

    ctypedef svn_error_t *(*svn_ra_push_wc_prop_func_t)(void *baton,
                                                   char *path,
                                                   char *name,
                                                   svn_string_t *value,
                                                   apr_pool_t *pool) except *

    ctypedef svn_error_t *(*svn_ra_invalidate_wc_props_func_t)(void *baton,
                                                          char *path,
                                                          char *name,
                                                          apr_pool_t *pool) except *

    ctypedef struct svn_ra_callbacks2_t:
        svn_error_t *(*open_tmp_file)(apr_file_t **fp, 
                void *callback_baton, apr_pool_t *pool) except *
        svn_auth_baton_t *auth_baton
        svn_ra_get_wc_prop_func_t get_wc_prop
        svn_ra_set_wc_prop_func_t set_wc_prop
        svn_ra_push_wc_prop_func_t push_wc_prop
        svn_ra_invalidate_wc_props_func_t invalidate_wc_props
        svn_ra_progress_notify_func_t progress_func
        void *progress_baton

    svn_error_t *svn_ra_create_callbacks(svn_ra_callbacks2_t **callbacks,
                            apr_pool_t *pool)

    ctypedef struct svn_ra_session_t

    svn_error_t *svn_ra_open2(svn_ra_session_t **session_p,
                          char *repos_URL,
                          svn_ra_callbacks2_t *callbacks,
                          callback_baton,
                          apr_hash_t *config,
                          apr_pool_t *pool)

    svn_error_t *svn_ra_reparent(svn_ra_session_t *ra_session, char *url, 
            apr_pool_t *pool)

    svn_error_t *svn_ra_get_latest_revnum(svn_ra_session_t *session,
                                      long *latest_revnum,
                                      apr_pool_t *pool)

    svn_error_t *svn_ra_get_uuid(svn_ra_session_t *session,
                             char **uuid,
                             apr_pool_t *pool)

    svn_error_t *svn_ra_get_repos_root(svn_ra_session_t *session,
                             char **root,
                             apr_pool_t *pool)

    svn_error_t *svn_ra_get_log(svn_ra_session_t *session,
                                apr_array_header_t *paths,
                                long start,
                                long end,
                                int limit,
                                int discover_changed_paths,
                                int strict_node_history,
                                svn_log_message_receiver_t receiver,
                                receiver_baton,
                                apr_pool_t *pool)

    svn_error_t *svn_ra_do_update(svn_ra_session_t *session,
                              svn_ra_reporter2_t **reporter,
                              void **report_baton,
                              long revision_to_update_to,
                              char *update_target,
                              int recurse,
                              svn_delta_editor_t *update_editor,
                              update_baton,
                              apr_pool_t *pool)

    svn_error_t *svn_ra_do_switch(svn_ra_session_t *session,
                                      svn_ra_reporter2_t **reporter,
                                      void **report_baton,
                                      long revision_to_switch_to,
                                      char *switch_target,
                                      int recurse,
                                      char *switch_url,
                                      svn_delta_editor_t *switch_editor,
                                      switch_baton,
                                      apr_pool_t *pool)

    svn_error_t *svn_ra_replay(svn_ra_session_t *session,
                                   svn_revnum_t revision,
                                   svn_revnum_t low_water_mark,
                                   int send_deltas,
                                   svn_delta_editor_t *editor,
                                   edit_baton,
                                   apr_pool_t *pool)

    svn_error_t *svn_ra_rev_proplist(svn_ra_session_t *session,
                                     svn_revnum_t rev,
                                     apr_hash_t **props,
                                     apr_pool_t *pool)

    svn_error_t *svn_ra_get_commit_editor2(svn_ra_session_t *session,
                                           svn_delta_editor_t **editor,
                                           void **edit_baton,
                                           char *log_msg,
                                           svn_commit_callback2_t callback,
                                           callback_baton,
                                           apr_hash_t *lock_tokens,
                                           int keep_locks,
                                           apr_pool_t *pool)

    svn_error_t *svn_ra_change_rev_prop(svn_ra_session_t *session,
                                    svn_revnum_t rev,
                                    char *name,
                                    svn_string_t *value,
                                    apr_pool_t *pool)

    svn_error_t *svn_ra_get_dir2(svn_ra_session_t *session,
                                 apr_hash_t **dirents,
                                 svn_revnum_t *fetched_rev,
                                 apr_hash_t **props,
                                 char *path,
                                 svn_revnum_t revision,
                                 long dirent_fields,
                                 apr_pool_t *pool)

    svn_error_t *svn_ra_get_lock(svn_ra_session_t *session,
                                 svn_lock_t **lock,
                                 char *path,
                                 apr_pool_t *pool)

    svn_error_t *svn_ra_check_path(svn_ra_session_t *session,
                                   char *path,
                                   long revision,
                                   svn_node_kind_t *kind,
                                   apr_pool_t *pool)

    svn_error_t *svn_ra_has_capability(svn_ra_session_t *session,
                          int *has, char *capability, apr_pool_t *pool)

    ctypedef svn_error_t *(*svn_ra_lock_callback_t)(baton, char *path,
                                               int do_lock,
                                               svn_lock_t *lock,
                                               svn_error_t *ra_err,
                                               apr_pool_t *pool) except *

    svn_error_t * svn_ra_unlock(svn_ra_session_t *session,
                  apr_hash_t *path_tokens,
                  int break_lock,
                  svn_ra_lock_callback_t lock_func,
                  lock_baton,
                  apr_pool_t *pool)

    svn_error_t *svn_ra_lock(svn_ra_session_t *session,
                apr_hash_t *path_revs,
                char *comment,
                int steal_lock,
                svn_ra_lock_callback_t lock_func,
                lock_baton,
                apr_pool_t *pool)


cdef svn_error_t *py_lock_func (baton, char *path, int do_lock, 
                                svn_lock_t *lock, svn_error_t *ra_err, 
                                apr_pool_t *pool) except *:
    py_ra_err = None
    if ra_err != NULL:
        py_ra_err = SubversionException(ra_err.apr_err, ra_err.message)
    # FIXME: Pass lock
    baton(path, do_lock, py_ra_err)

cdef void py_progress_func(apr_off_t progress, apr_off_t total, void *baton, apr_pool_t *pool) except *:
    fn = <object>baton
    if fn is None:
        return
    fn(progress, total)

cdef char *c_lock_token(object py_lock_token):
    if py_lock_token is None:
        return NULL
    else:
        return py_lock_token


cdef class Reporter:
    """Change reporter."""
    cdef svn_ra_reporter2_t *reporter
    cdef void *report_baton
    cdef apr_pool_t *pool

    def set_path(self, char *path, svn_revnum_t revision, int start_empty, lock_token=None):
        check_error(self.reporter.set_path(self.report_baton, path, revision, 
                     start_empty, c_lock_token(lock_token), self.pool))

    def delete_path(self, char *path):
        check_error(self.reporter.delete_path(self.report_baton, path, 
                     self.pool))

    def link_path(self, char *path, char *url, svn_revnum_t revision, int start_empty, lock_token=None):
        check_error(self.reporter.link_path(self.report_baton, path, url, 
                    revision, start_empty, c_lock_token(lock_token), self.pool))

    def finish(self):
        check_error(self.reporter.finish_report(self.report_baton, self.pool))

    def abort(self):
        check_error(self.reporter.abort_report(self.report_baton, self.pool))

    def __dealloc__(self):
        # FIXME: Warn the user if abort_report/finish_report wasn't called?
        apr_pool_destroy(self.pool)

cdef class TxDeltaWindowHandler:
    cdef svn_txdelta_window_handler_t txdelta
    cdef void *txbaton

cdef class FileEditor:
    cdef void *file_baton
    cdef svn_delta_editor_t *editor
    cdef apr_pool_t *pool

    def apply_textdelta(self, base_checksum=None):
        cdef char *c_base_checksum
        cdef svn_txdelta_window_handler_t txdelta_handler
        cdef void *txdelta_baton
        cdef TxDeltaWindowHandler py_txdelta
        if base_checksum is None:
            c_base_checksum = NULL
        else:
            c_base_checksum = base_checksum
        check_error(self.editor.apply_textdelta(self.file_baton,
                    c_base_checksum, self.pool, 
                    &txdelta_handler, &txdelta_baton))
        py_txdelta = TxDeltaWindowHandler()
        py_txdelta.txdelta = txdelta_handler
        py_txdelta.txbaton = txdelta_baton
        return py_txdelta

    def change_prop(self, char *name, char *value):
        cdef svn_string_t c_value, *p_c_value
        if value is None:
            p_c_value = NULL
        else:
            c_value.data = value
            c_value.len = len(value)
            p_c_value = &c_value
        check_error(self.editor.change_file_prop(self.file_baton, name, 
                    p_c_value, self.pool))

    def close(self, checksum=None):
        cdef char *c_checksum
        if checksum is None:
            c_checksum = NULL
        else:
            c_checksum = checksum
        check_error(self.editor.close_file(self.file_baton, c_checksum, 
                    self.pool))

cdef class DirectoryEditor:
    cdef svn_delta_editor_t *editor
    cdef void *dir_baton
    cdef apr_pool_t *pool

    def delete_entry(self, char *path, svn_revnum_t revision=-1):
        check_error(self.editor.delete_entry(path, revision, self.dir_baton,
                                             self.pool))

    def add_directory(self, char *path, copyfrom_path=None, int copyfrom_rev=-1):
        cdef void *child_baton
        cdef char *c_copyfrom_path
        if copyfrom_path is None:
            c_copyfrom_path = NULL
        else:
            c_copyfrom_path = copyfrom_path
        check_error(self.editor.add_directory(path, self.dir_baton,
                    c_copyfrom_path, copyfrom_rev, self.pool, &child_baton))
        return new_dir_editor(self.editor, child_baton, self.pool)

    def open_directory(self, char *path, int base_revision=-1):
        cdef void *child_baton
        check_error(self.editor.open_directory(path, self.dir_baton,
                    base_revision, self.pool, &child_baton))
        return new_dir_editor(self.editor, child_baton, self.pool)

    def change_prop(self, char *name, char *value):
        cdef svn_string_t c_value, *p_c_value
        if value is None:
            p_c_value = NULL
        else:
            c_value.data = value
            c_value.len = len(value)
            p_c_value = &c_value
        check_error(self.editor.change_dir_prop(self.dir_baton, name, 
                    p_c_value, self.pool))

    def close(self):
        check_error(self.editor.close_directory(self.dir_baton, self.pool))

    def absent_directory(self, char *path):
        check_error(self.editor.absent_directory(path, self.dir_baton, 
                    self.pool))

    def add_file(self, char *path, copy_path=None, int copy_rev=-1):
        cdef void *file_baton
        cdef FileEditor py_file_editor
        cdef char *c_copy_path
        if copy_path is None:
            c_copy_path = NULL
        else:
            c_copy_path = copy_path
        check_error(self.editor.add_file(path, self.dir_baton, c_copy_path,
                    copy_rev, self.pool, &file_baton))
        py_file_editor = FileEditor()
        py_file_editor.editor = self.editor
        py_file_editor.file_baton = file_baton
        py_file_editor.pool = self.pool
        return py_file_editor

    def open_file(self, char *path, int base_revision=-1):
        cdef void *file_baton
        cdef FileEditor py_file_editor
        check_error(self.editor.open_file(path, self.dir_baton, 
                    base_revision, self.pool, &file_baton))
        py_file_editor = FileEditor()
        py_file_editor.editor = self.editor
        py_file_editor.file_baton = file_baton
        py_file_editor.pool = self.pool
        return py_file_editor

    def absent_file(self, char *path):
        check_error(self.editor.absent_file(path, self.dir_baton, self.pool))

cdef new_dir_editor(svn_delta_editor_t *editor, void *child_baton, apr_pool_t *pool):
    cdef DirectoryEditor py_dir_editor
    py_dir_editor = DirectoryEditor()
    py_dir_editor.editor = editor
    py_dir_editor.dir_baton = child_baton
    py_dir_editor.pool = pool
    return py_dir_editor


cdef class Editor:
    cdef svn_delta_editor_t *editor
    cdef void *edit_baton
    cdef apr_pool_t *pool

    def set_target_revision(self, int target_revision):
        check_error(self.editor.set_target_revision(self.edit_baton,
                    target_revision, self.pool))
    
    def open_root(self, int base_revision=-1):
        cdef void *root_baton
        check_error(self.editor.open_root(self.edit_baton, base_revision,
                    self.pool, &root_baton))
        return new_dir_editor(self.editor, root_baton, self.pool)

    def close(self):
        check_error(self.editor.close_edit(self.edit_baton, self.pool))

    def abort(self):
        check_error(self.editor.abort_edit(self.edit_baton, self.pool))

    def __dealloc__(self):
        apr_pool_destroy(self.pool)


def version():
    """Get libsvn_ra version information.

    :return: tuple with major, minor, patch version number and tag.
    """
    cdef svn_version_t *ver
    ver = svn_ra_version()
    return (ver.major, ver.minor, ver.minor, ver.tag)

cdef svn_error_t *py_editor_set_target_revision(void *edit_baton, svn_revnum_t target_revision, apr_pool_t *pool) except *:
    self = <object>edit_baton
    self.set_target_revision(target_revision)
    return NULL

cdef svn_error_t *py_editor_open_root(void *edit_baton, svn_revnum_t base_revision, apr_pool_t *dir_pool, void **root_baton):
    root_baton[0] = NULL
    self = <object>edit_baton
    ret = self.open_root(base_revision)
    Py_INCREF(ret)
    root_baton[0] = <void *>ret
    return NULL

cdef svn_error_t *py_editor_delete_entry(char *path, long revision, void *parent_baton, apr_pool_t *pool):
    self = <object>parent_baton
    self.delete_entry(path, revision)
    return NULL

cdef svn_error_t *py_editor_add_directory(char *path, void *parent_baton, char *copyfrom_path, long copyfrom_revision, apr_pool_t *dir_pool, void **child_baton):
    child_baton[0] = NULL
    self = <object>parent_baton
    if copyfrom_path == NULL:
        ret = self.add_directory(path)
    else:
        ret = self.add_directory(path, copyfrom_path, copyfrom_revision)
    Py_INCREF(ret)
    child_baton[0] = <void *>ret
    return NULL

cdef svn_error_t *py_editor_open_directory(char *path, void *parent_baton, long base_revision, apr_pool_t *dir_pool, void **child_baton):
    child_baton[0] = NULL
    self = <object>parent_baton
    ret = self.open_directory(path, base_revision)
    Py_INCREF(ret)
    child_baton[0] = <void *>ret 
    return NULL

cdef svn_error_t *py_editor_change_dir_prop(void *dir_baton, char *name, svn_string_t *value, apr_pool_t *pool):
    self = <object>dir_baton
    if value != NULL:
        self.change_prop(name, PyString_FromStringAndSize(value.data, value.len))
    else:
        self.change_prop(name, None)
    return NULL

cdef svn_error_t *py_editor_close_directory(void *dir_baton, apr_pool_t *pool):
    self = <object>dir_baton
    self.close()
    Py_DECREF(self)
    return NULL

cdef svn_error_t *py_editor_absent_directory(char *path, void *parent_baton, apr_pool_t *pool):
    self = <object>parent_baton
    self.absent_directory(path)
    return NULL

cdef svn_error_t *py_editor_add_file(char *path, void *parent_baton, char *copy_path, long copy_revision, apr_pool_t *file_pool, void **file_baton):
    file_baton[0] = NULL
    self = <object>parent_baton
    if copy_path == NULL:
        ret = self.add_file(path)
    else:
        ret = self.add_file(path, copy_path, copy_revision)
    Py_INCREF(ret)
    file_baton[0] = <void *>ret
    return NULL

cdef svn_error_t *py_editor_open_file(char *path, void *parent_baton, long base_revision, apr_pool_t *file_pool, void **file_baton):
    file_baton[0] = NULL
    self = <object>parent_baton
    ret = self.open_file(path, base_revision)
    Py_INCREF(ret)
    file_baton[0] = <void *>ret
    return NULL

cdef svn_error_t *py_txdelta_window_handler(svn_txdelta_window_t *window, void *baton):
    fn = <object>baton
    if window == NULL:
        # Signals all delta windows have been received
        Py_DECREF(fn)
        return NULL
    if fn is None:
        # User doesn't care about deltas
        return NULL
    ops = []
    for i in range(window.num_ops):
        ops.append((window.ops[i].action_code, window.ops[i].offset, window.ops[i].length))
    fn((window.sview_offset, window.sview_len, window.tview_len, window.src_ops, ops, PyString_FromStringAndSize(window.new_data.data, window.new_data.len)))
    return NULL
    

cdef svn_error_t *py_editor_apply_textdelta(void *file_baton, char *base_checksum, apr_pool_t *pool, svn_txdelta_window_handler_t *handler, void **handler_baton):
    handler_baton[0] = NULL
    self = <object>file_baton
    if base_checksum == NULL:
        ret = self.apply_textdelta()
    else:
        ret = self.apply_textdelta(base_checksum)
    Py_INCREF(ret)
    handler_baton[0] = <void *>ret
    handler[0] = py_txdelta_window_handler
    return NULL

cdef svn_error_t *py_editor_change_file_prop(void *file_baton, char *name, svn_string_t *value, apr_pool_t *pool):
    self = <object>file_baton
    if value != NULL:
        self.change_prop(name, PyString_FromStringAndSize(value.data, value.len))
    else:
        self.change_prop(name, None)
    return NULL

cdef svn_error_t *py_editor_close_file(void *file_baton, char *text_checksum, apr_pool_t *pool):
    self = <object>file_baton
    if text_checksum != NULL:
        self.close()
    else:
        self.close(text_checksum)
    Py_DECREF(self)
    return NULL

cdef svn_error_t *py_editor_absent_file(char *path, void *parent_baton, apr_pool_t *pool):
    self = <object>parent_baton
    self.absent_file(path)
    return NULL

cdef svn_error_t *py_editor_close_edit(void *edit_baton, apr_pool_t *pool):
    self = <object>edit_baton
    self.close()
    return NULL

cdef svn_error_t *py_editor_abort_edit(void *edit_baton, apr_pool_t *pool):
    self = <object>edit_baton
    self.abort()
    return NULL

cdef svn_delta_editor_t py_editor
py_editor.set_target_revision = py_editor_set_target_revision
py_editor.open_root = py_editor_open_root
py_editor.delete_entry = py_editor_delete_entry
py_editor.add_directory = py_editor_add_directory
py_editor.open_directory = py_editor_open_directory
py_editor.change_dir_prop = py_editor_change_dir_prop
py_editor.close_directory = py_editor_close_directory
py_editor.absent_directory = py_editor_absent_directory
py_editor.add_file = py_editor_add_file
py_editor.open_file = py_editor_open_file
py_editor.apply_textdelta = py_editor_apply_textdelta
py_editor.change_file_prop = py_editor_change_file_prop
py_editor.close_file = py_editor_close_file
py_editor.absent_file = py_editor_absent_file
py_editor.close_edit = py_editor_close_edit
py_editor.abort_edit = py_editor_abort_edit

cdef class Auth

cdef class RemoteAccess:
    """Connection to a remote Subversion repository."""
    cdef svn_ra_session_t *ra
    cdef apr_pool_t *pool
    cdef char *url
    cdef object progress_func
    cdef Auth auth
    def __init__(self, char *url, progress_cb=None, Auth auth=None, config={}):
        """Connect to a remote Subversion repository. 

        :param url: URL of the repository
        :param progress_cb: Progress callback function
        :param config: Optional configuration
        """
        cdef svn_error_t *error
        cdef svn_ra_callbacks2_t *callbacks2
        cdef apr_hash_t *config_hash
        if auth is None:
            auth = Auth()
        self.auth = auth
        self.url = url
        self.pool = Pool(NULL)
        assert self.pool != NULL
        check_error(svn_ra_create_callbacks(&callbacks2, self.pool))
        callbacks2.progress_func = py_progress_func
        Py_INCREF(self.auth)
        callbacks2.auth_baton = self.auth.auth_baton
        self.progress_func = progress_cb
        callbacks2.progress_baton = <void *>self.progress_func
        config_hash = apr_hash_make(self.pool)
        for (key, val) in config.items():
            apr_hash_set(config_hash, key, len(key), val)
        check_error(svn_ra_open2(&self.ra, url, callbacks2, None, config_hash, 
                     self.pool))

    def get_uuid(self):
        """Obtain the globally unique identifier for this repository."""
        cdef char *uuid
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        check_error(svn_ra_get_uuid(self.ra, &uuid, temp_pool))
        apr_pool_destroy(temp_pool)
        return uuid

    def reparent(self, char *url):
        """Switch to a different url."""
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        check_error(svn_ra_reparent(self.ra, url, temp_pool))
        apr_pool_destroy(temp_pool)

    def get_latest_revnum(self):
        """Obtain the number of the latest committed revision in the 
        connected repository.
        """
        cdef long latest_revnum
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        check_error(svn_ra_get_latest_revnum(self.ra, &latest_revnum, 
                     temp_pool))
        apr_pool_destroy(temp_pool)
        return latest_revnum

    def get_log(self, callback, paths, svn_revnum_t start, svn_revnum_t end, int limit=0, 
                int discover_changed_paths=True, int strict_node_history=True,
                revprops=[PROP_REVISION_LOG,PROP_REVISION_AUTHOR,PROP_REVISION_DATE]):
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(NULL)
        check_error(svn_ra_get_log(self.ra, 
            string_list_to_apr_array(temp_pool, paths), start, end, limit,
            discover_changed_paths, strict_node_history, py_svn_log_wrapper, 
            callback, temp_pool))
        apr_pool_destroy(temp_pool)

    def get_repos_root(self):
        """Obtain the URL of the root of this repository."""
        cdef char *root
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        check_error(svn_ra_get_repos_root(self.ra, &root, 
                     temp_pool))
        apr_pool_destroy(temp_pool)
        return root

    def do_update(self, svn_revnum_t revision_to_update_to, char *update_target, int recurse, 
                  update_editor):
        cdef svn_ra_reporter2_t *reporter
        cdef void *report_baton
        cdef apr_pool_t *temp_pool
        cdef Reporter ret
        temp_pool = Pool(self.pool)
        check_error(svn_ra_do_update(self.ra, &reporter, &report_baton, 
                     revision_to_update_to, update_target, recurse, 
                     &py_editor, update_editor, temp_pool))
        ret = Reporter()
        ret.reporter = reporter
        ret.report_baton = report_baton
        ret.pool = temp_pool
        return ret

    def do_switch(self, svn_revnum_t revision_to_update_to, char *update_target, int recurse, 
                  char *switch_url, update_editor):
        cdef svn_ra_reporter2_t *reporter
        cdef void *report_baton
        cdef apr_pool_t *temp_pool
        cdef Reporter ret
        temp_pool = Pool(self.pool)
        check_error(svn_ra_do_switch(self.ra, &reporter, &report_baton, 
                     revision_to_update_to, update_target, recurse, 
                     switch_url,
                     &py_editor, update_editor, temp_pool))
        ret = Reporter()
        ret.reporter = reporter
        ret.report_baton = report_baton
        ret.pool = temp_pool
        return ret

    def replay(self, svn_revnum_t revision, svn_revnum_t low_water_mark, update_editor, int send_deltas=True):
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        check_error(svn_ra_replay(self.ra, revision, low_water_mark,
                     send_deltas, &py_editor, update_editor, temp_pool))
        apr_pool_destroy(temp_pool)

    def rev_proplist(self, svn_revnum_t rev):
        cdef apr_pool_t *temp_pool
        cdef apr_hash_t *props
        temp_pool = Pool(self.pool)
        check_error(svn_ra_rev_proplist(self.ra, rev, &props, temp_pool))
        py_props = prop_hash_to_dict(props)
        apr_pool_destroy(temp_pool)
        return py_props

    def get_commit_editor(self, revprops, commit_callback, lock_tokens, 
                          int keep_locks):
        cdef apr_pool_t *temp_pool
        cdef svn_delta_editor_t *editor
        cdef void *edit_baton
        cdef apr_hash_t *hash_lock_tokens
        cdef Editor py_editor
        temp_pool = Pool(self.pool)
        if lock_tokens is None:
            hash_lock_tokens = NULL
        else:
            hash_lock_tokens = apr_hash_make(temp_pool)
            for k, v in lock_tokens.items():
                apr_hash_set(hash_lock_tokens, k, len(k), <char *>v)
        check_error(svn_ra_get_commit_editor2(self.ra, &editor, 
            &edit_baton, revprops[PROP_REVISION_LOG], py_commit_callback, 
            commit_callback, hash_lock_tokens, keep_locks, temp_pool))
        py_editor = Editor()
        py_editor.editor = editor
        py_editor.edit_baton = edit_baton
        py_editor.pool = temp_pool
        return py_editor

    def change_rev_prop(self, svn_revnum_t rev, char *name, char *value):
        cdef apr_pool_t *temp_pool
        cdef svn_string_t *val_string
        temp_pool = Pool(self.pool)
        val_string = svn_string_ncreate(value, len(value), temp_pool)
        check_error(svn_ra_change_rev_prop(self.ra, rev, name, 
                     val_string, temp_pool))
        apr_pool_destroy(temp_pool)
    
    def get_dir(self, char *path, svn_revnum_t revision=-1, int dirent_fields=0):
        cdef apr_pool_t *temp_pool
        cdef apr_hash_t *dirents
        cdef apr_hash_index_t *idx
        cdef apr_hash_t *props
        cdef long fetch_rev
        cdef char *key
        cdef svn_dirent_t *dirent
        cdef long klen
        temp_pool = Pool(self.pool)
        check_error(svn_ra_get_dir2(self.ra, &dirents, &fetch_rev, &props,
                     path, revision, dirent_fields, temp_pool))

        if dirents == NULL:
            py_dirents = None
        else:
            py_dirents = {}
            idx = apr_hash_first(temp_pool, dirents)
            while idx:
                apr_hash_this(idx, <void **>&key, &klen, <void **>&dirent)
                py_dirent = {}
                if dirent_fields & 0x1:
                    py_dirent['kind'] = dirent.kind
                if dirent_fields & 0x2:
                    py_dirent['size'] = dirent.size
                if dirent_fields & 0x4:
                    py_dirent['has_props'] = dirent.has_props
                if dirent_fields & 0x8:
                    py_dirent['created_rev'] = dirent.created_rev
                if dirent_fields & 0x10:
                    py_dirent['time'] = dirent.time
                if dirent_fields & 0x20:
                    py_dirent['last_author'] = dirent.last_author
                py_dirents[key] = py_dirent
                idx = apr_hash_next(idx)

        py_props = prop_hash_to_dict(props)
        apr_pool_destroy(temp_pool)
        return (py_dirents, fetch_rev, py_props)

    def get_lock(self, char *path):
        cdef svn_lock_t *lock
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        check_error(svn_ra_get_lock(self.ra, &lock, path, temp_pool))
        apr_pool_destroy(temp_pool)
        return wrap_lock(lock)

    def check_path(self, char *path, svn_revnum_t revision):
        cdef svn_node_kind_t kind
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        check_error(svn_ra_check_path(self.ra, path, revision, &kind, 
                     temp_pool))
        apr_pool_destroy(temp_pool)
        return kind

    def has_capability(self, char *capability):
        cdef apr_pool_t *temp_pool
        cdef int has
        temp_pool = Pool(self.pool)
        # FIXME: Svn 1.5 only
        # check_error(svn_ra_has_capability(self.ra, &has, capability, 
        #             temp_pool))
        apr_pool_destroy(temp_pool)
        return has

    def unlock(self, path_tokens, int break_lock, lock_func):
        cdef apr_pool_t *temp_pool
        cdef apr_hash_t *hash_path_tokens
        temp_pool = Pool(self.pool)
        hash_path_tokens = apr_hash_make(temp_pool)
        for k, v in path_tokens:
            apr_hash_set(hash_path_tokens, k, len(k), <char *>v)
        check_error(svn_ra_unlock(self.ra, hash_path_tokens, break_lock,
                     py_lock_func, lock_func, temp_pool))
        apr_pool_destroy(temp_pool)

    def lock(self, path_revs, char *comment, int steal_lock, lock_func):
        cdef apr_pool_t *temp_pool
        cdef apr_hash_t *hash_path_revs
        cdef svn_revnum_t *rev
        temp_pool = Pool(self.pool)
        if path_revs is None:
            hash_path_revs = NULL
        else:
            hash_path_revs = apr_hash_make(temp_pool)
            for k, v in path_revs.items():
                rev = <svn_revnum_t *>apr_palloc(temp_pool, sizeof(svn_revnum_t))
                rev[0] = v
                apr_hash_set(hash_path_revs, k, len(k), v)
        check_error(svn_ra_lock(self.ra, hash_path_revs, comment, steal_lock,
                     py_lock_func, lock_func, temp_pool))
        apr_pool_destroy(temp_pool)

    def __dealloc__(self):
        if self.pool != NULL:
            apr_pool_destroy(self.pool)
        Py_DECREF(self.auth)

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.url)

cdef class AuthProvider:
    cdef apr_pool_t *pool
    cdef svn_auth_provider_object_t *provider

    def __dealloc__(self):
        apr_pool_destroy(self.pool)

cdef class Auth:
    cdef svn_auth_baton_t *auth_baton
    cdef apr_pool_t *pool
    def __init__(self, providers=[]):
        cdef apr_array_header_t *c_providers    
        cdef AuthProvider provider
        cdef svn_auth_provider_object_t **el
        self.pool = Pool(NULL)
        c_providers = apr_array_make(self.pool, len(providers), 4)
        for p in providers:
            el = <svn_auth_provider_object_t **>apr_array_push(c_providers)
            provider = p
            el[0] = provider.provider
        svn_auth_open(&self.auth_baton, c_providers, self.pool)

    def set_parameter(self, char *name, char *value):
        svn_auth_set_parameter(self.auth_baton, name, <char *>value)

    def get_parameter(self, char *name):
        return <char *>svn_auth_get_parameter(self.auth_baton, name)

    def __dealloc__(self):
        if self.pool != NULL:
            apr_pool_destroy(self.pool)

cdef svn_error_t *py_username_prompt(svn_auth_cred_username_t **cred, void *baton, char *realm, int may_save, apr_pool_t *pool):
    fn = <object>baton
    (username, cred[0].may_save) = fn(realm, may_save)
    cred[0].username = apr_pstrdup(pool, username)
    return NULL

def get_username_prompt_provider(prompt_func, int retry_limit):
    cdef AuthProvider auth
    auth = AuthProvider()
    auth.pool = Pool(NULL)
    svn_auth_get_username_prompt_provider (&auth.provider, py_username_prompt, <void *>prompt_func, retry_limit, auth.pool)
    return auth

cdef svn_error_t *py_simple_prompt(svn_auth_cred_simple_t **cred, void *baton, char *realm, char *username, int may_save, apr_pool_t *pool):
    fn = <object>baton
    (py_username, password, cred[0].may_save) = fn(realm, may_save)
    cred[0].username = apr_pstrdup(pool, py_username)
    cred[0].password = apr_pstrdup(pool, password)
    return NULL

def get_simple_prompt_provider(prompt_func, int retry_limit):
    cdef AuthProvider auth
    auth = AuthProvider()
    auth.pool = Pool(NULL)
    svn_auth_get_simple_prompt_provider (&auth.provider, py_simple_prompt, <void *>prompt_func, retry_limit, auth.pool)
    return auth

cdef svn_error_t *py_ssl_server_trust_prompt(svn_auth_cred_ssl_server_trust_t **cred, void *baton, char *realm, apr_uint32_t failures, svn_auth_ssl_server_cert_info_t *cert_info, svn_boolean_t may_save, apr_pool_t *pool):
    fn = <object>baton
    (cred[0].may_save, cred[0].accepted_failures) = fn(realm, failures, (cert_info.hostname, cert_info.fingerprint, cert_info.valid_from, cert_info.valid_until, cert_info.issuer_dname, cert_info.ascii_cert), may_save)
    return NULL

def get_ssl_server_trust_prompt_provider(prompt_func):
    cdef AuthProvider auth
    auth = AuthProvider()
    auth.pool = Pool(NULL)
    svn_auth_get_ssl_server_trust_prompt_provider (&auth.provider, py_ssl_server_trust_prompt, <void *>prompt_func, auth.pool)
    return auth

cdef svn_error_t *py_ssl_client_cert_pw_prompt(svn_auth_cred_ssl_client_cert_pw_t **cred, void *baton, char *realm, svn_boolean_t may_save, apr_pool_t *pool):
    fn = <object>baton
    (password, cred[0].may_save) = fn(realm, may_save)
    cred[0].password = apr_pstrdup(pool, password)
    return NULL

def get_ssl_client_cert_pw_prompt_provider(prompt_func, int retry_limit):
    cdef AuthProvider auth
    auth = AuthProvider()
    auth.pool = Pool(NULL)
    svn_auth_get_ssl_client_cert_pw_prompt_provider (&auth.provider, py_ssl_client_cert_pw_prompt, <void *>prompt_func, retry_limit, auth.pool)
    return auth

def get_username_provider():
    cdef AuthProvider auth
    auth = AuthProvider()
    auth.pool = Pool(NULL)
    svn_auth_get_username_provider(&auth.provider, auth.pool)
    return auth

def get_simple_provider():
    cdef AuthProvider auth
    auth = AuthProvider()
    auth.pool = Pool(NULL)
    svn_auth_get_simple_provider(&auth.provider, auth.pool)
    return auth

def get_ssl_server_trust_file_provider():
    cdef AuthProvider auth
    auth = AuthProvider()
    auth.pool = Pool(NULL)
    svn_auth_get_ssl_server_trust_file_provider(&auth.provider, auth.pool)
    return auth

def get_ssl_client_cert_file_provider():
    cdef AuthProvider auth
    auth = AuthProvider()
    auth.pool = Pool(NULL)
    svn_auth_get_ssl_client_cert_file_provider(&auth.provider, auth.pool)
    return auth

def get_ssl_client_cert_pw_file_provider():
    cdef AuthProvider auth
    auth = AuthProvider()
    auth.pool = Pool(NULL)
    svn_auth_get_ssl_client_cert_pw_file_provider(&auth.provider, auth.pool)
    return auth

def txdelta_send_stream(stream, TxDeltaWindowHandler handler):
    cdef unsigned char digest[16] 
    cdef apr_pool_t *pool
    pool = Pool(NULL)
    check_error(svn_txdelta_send_stream(new_py_stream(pool, stream), handler.txdelta, handler.txbaton, <unsigned char *>digest, pool))
    apr_pool_destroy(pool)
    return PyString_FromStringAndSize(<char *>digest, 16)


cdef new_editor(svn_delta_editor_t *editor, void *edit_baton, apr_pool_t *pool):
    cdef Editor ret
    ret = Editor()
    ret.editor = editor
    ret.edit_baton = edit_baton
    ret.pool = pool
    return ret
