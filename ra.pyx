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

include "apr.pxi"
include "types.pxi"

apr_initialize()

cdef apr_pool_t *Pool(apr_pool_t *parent):
    cdef apr_status_t status
    cdef apr_pool_t *ret
    ret = NULL
    status = apr_pool_create(&ret, parent)
    if status != 0:
        # FIXME: Clearer error
        raise Exception("APR Error")
    return ret

cdef extern from "svn_auth.h":
    ctypedef struct svn_auth_baton_t
    void svn_auth_open(svn_auth_baton_t **auth_baton,
                       apr_array_header_t *providers,
                       apr_pool_t *pool)
    void svn_auth_set_parameter(svn_auth_baton_t *auth_baton, 
                                char *name, void *value)
    void * svn_auth_get_parameter(svn_auth_baton_t *auth_baton,
                                  char *name)

    ctypedef struct svn_auth_provider_t:
        char *cred_kind
        svn_error_t * (*first_credentials)(void **credentials,
                                            void **iter_baton,
                                             void *provider_baton,
                                             apr_hash_t *parameters,
                                             char *realmstring,
                                             apr_pool_t *pool)
        svn_error_t * (*next_credentials)(void **credentials,
                                            void *iter_baton,
                                            void *provider_baton,
                                            apr_hash_t *parameters,
                                            char *realmstring,
                                            apr_pool_t *pool)
         
        svn_error_t * (*save_credentials)(int *saved,
                                    void *credentials,
                                    void *provider_baton,
                                    apr_hash_t *parameters,
                                    char *realmstring,
                                    apr_pool_t *pool)

    ctypedef struct svn_auth_provider_object_t:
        svn_auth_provider_t *vtable
        void *provider_baton

    ctypedef struct svn_auth_cred_simple_t:
        char *username
        char *password
        int may_save

    ctypedef svn_error_t *(*svn_auth_simple_prompt_func_t) (svn_auth_cred_simple_t **cred, void *baton, char *realm, char *username, int may_save, apr_pool_t *pool)

    void svn_auth_get_simple_prompt_provider(
            svn_auth_provider_object_t **provider, svn_auth_simple_prompt_func_t prompt_func, void *prompt_baton, int retry_limit, apr_pool_t *pool)


cdef extern from "svn_delta.h":
    ctypedef struct svn_txdelta_window_t
    ctypedef svn_error_t *(*svn_txdelta_window_handler_t) (svn_txdelta_window_t *window, void *baton)

    ctypedef struct svn_delta_editor_t:
        svn_error_t *(*set_target_revision)(void *edit_baton, long target_revision, apr_pool_t *pool)
        svn_error_t *(*open_root)(void *edit_baton, long base_revision, 
                                  apr_pool_t *dir_pool, void **root_baton)

        svn_error_t *(*delete_entry)(char *path, long revision, 
                                     void *parent_baton, apr_pool_t *pool)

        svn_error_t *(*add_directory)(char *path,
                                void *parent_baton,
                                char *copyfrom_path,
                                long copyfrom_revision,
                                apr_pool_t *dir_pool,
                                void **child_baton)

        svn_error_t *(*open_directory)(char *path, void *parent_baton,
                                 long base_revision,
                                 apr_pool_t *dir_pool,
                                 void **child_baton)

        svn_error_t *(*change_dir_prop)(void *dir_baton,
                                  char *name,
                                  svn_string_t *value,
                                  apr_pool_t *pool)

        svn_error_t *(*close_directory)(void *dir_baton,
                                  apr_pool_t *pool)

        svn_error_t *(*absent_directory)(char *path, void *parent_baton, 
                                     apr_pool_t *pool)

        svn_error_t *(*add_file)(char *path,
                           void *parent_baton,
                           char *copy_path,
                           long copy_revision,
                           apr_pool_t *file_pool,
                           void **file_baton)

        svn_error_t *(*open_file)(char *path,
                            void *parent_baton,
                            long base_revision,
                            apr_pool_t *file_pool,
                            void **file_baton)

        svn_error_t *(*apply_textdelta)(void *file_baton,
                                  char *base_checksum,
                                  apr_pool_t *pool,
                                  svn_txdelta_window_handler_t *handler,
                                  void **handler_baton)
        svn_error_t *(*change_file_prop)(void *file_baton,
                                   char *name,
                                   svn_string_t *value,
                                   apr_pool_t *pool)

        svn_error_t *(*close_file)(void *file_baton,
                             char *text_checksum,
                             apr_pool_t *pool)

        svn_error_t *(*absent_file)(char *path,
                              void *parent_baton,
                              apr_pool_t *pool)

        svn_error_t *(*close_edit)(void *edit_baton, apr_pool_t *pool)

        svn_error_t *(*abort_edit)(void *edit_baton, apr_pool_t *pool)


cdef extern from "svn_types.h":
    ctypedef svn_error_t *(*svn_log_message_receiver_t) (baton, apr_hash_t *changed_paths, long revision, char *author, char *date, char *message, apr_pool_t *pool) except *
    ctypedef enum svn_node_kind_t:
        svn_node_node
        svn_node_file
        svn_node_dir
        svn_node_unknown
    ctypedef struct svn_commit_info_t:
        long revision
        char *date
        char *author
        char *post_commit_err
    ctypedef svn_error_t *(*svn_commit_callback2_t) (svn_commit_info_t *commit_info, baton, apr_pool_t *pool) except *


cdef svn_error_t *py_commit_callback(svn_commit_info_t *commit_info, baton, apr_pool_t *pool) except *:
    baton(commit_info.revision, commit_info.date, commit_info.author, commit_info.post_commit_err)

cdef svn_error_t *py_svn_log_wrapper(baton, apr_hash_t *changed_paths, long revision, char *author, char *date, char *message, apr_pool_t *pool) except *:
    cdef apr_hash_index_t *idx
    if changed_paths == NULL:
        py_changed_paths = None
    else:
        py_changed_paths = {}
        idx = apr_hash_first(pool, changed_paths)
        while idx:
            # FIXME: apr_hash_this(idx, key, val
            idx = apr_hash_next(idx)
    baton(py_changed_paths, revision, {
        SVN_PROP_REVISION_LOG: message, 
        SVN_PROP_REVISION_AUTHOR: author, 
        SVN_PROP_REVISION_DATE: date})

cdef extern from "svn_ra.h":
    ctypedef struct svn_lock_t
    svn_version_t *svn_ra_version()

    ctypedef struct svn_ra_reporter2_t:
        svn_error_t *(*set_path)(void *report_baton,
                           char *path,
                           long revision,
                           int start_empty,
                           char *lock_token,
                           apr_pool_t *pool)

        svn_error_t *(*delete_path)(void *report_baton, 
                char *path, apr_pool_t *pool)

        svn_error_t *(*link_path)(void *report_baton,
                                char *path,
                                char *url,
                                long revision,
                                int start_empty,
                                char *lock_token,
                                apr_pool_t *pool)

        svn_error_t *(*finish_report)(void *report_baton, apr_pool_t *pool)

        svn_error_t *(*abort_report)(void *report_baton, apr_pool_t *pool)

    ctypedef struct svn_ra_callbacks2_t:
        svn_error_t *(*open_tmp_file)(apr_file_t **fp, 
                                      void *callback_baton, apr_pool_t *pool)
        svn_auth_baton_t *auth_baton

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
                                   long revision,
                                   long low_water_mark,
                                   int send_deltas,
                                   svn_delta_editor_t *editor,
                                   edit_baton,
                                   apr_pool_t *pool)

    svn_error_t *svn_ra_rev_proplist(svn_ra_session_t *session,
                                     long rev,
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
                                    long rev,
                                    char *name,
                                    svn_string_t *value,
                                    apr_pool_t *pool)

    svn_error_t *svn_ra_get_dir2(svn_ra_session_t *session,
                                 apr_hash_t **dirents,
                                 long *fetched_rev,
                                 apr_hash_t **props,
                                 char *path,
                                 long revision,
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
                                               apr_pool_t *pool)

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
                                apr_pool_t *pool):
    # FIXME: pass lock and ra_err, too
    baton(path, do_lock)


cdef class Reporter:
    """Change reporter."""
    cdef svn_ra_reporter2_t *reporter
    cdef void *report_baton
    cdef apr_pool_t *pool

    def set_path(self, path, revision, start_empty, lock_token):
        _check_error(self.reporter.set_path(self.report_baton, path, revision, 
                     start_empty, lock_token, self.pool))

    def delete_path(self, path):
        _check_error(self.reporter.delete_path(self.report_baton, path, 
                     self.pool))

    def link_path(self, path, url, revision, start_empty, lock_token):
        _check_error(self.reporter.link_path(self.report_baton, path, url, 
                     revision, start_empty, lock_token, self.pool))

    def finish_report(self):
        _check_error(self.reporter.finish_report(self.report_baton, self.pool))

    def abort_report(self):
        _check_error(self.reporter.abort_report(self.report_baton, self.pool))


def version():
    """Get libsvn_ra version information.

    :return: tuple with major, minor, patch version number and tag.
    """
    return (svn_ra_version().major, svn_ra_version().minor, 
            svn_ra_version().minor, svn_ra_version().tag)

cdef void _check_error(svn_error_t *error):
    if error:
        # FIXME
        raise Exception("SVN error")

cdef class RemoteAccess:
    cdef svn_ra_session_t *ra
    cdef apr_pool_t *pool
    cdef char *url
    def __init__(self, url, callbacks=object(), config={}):
        """Connect to a remote Subversion repository. 

        :param url: URL of the repository
        :param callbacks: Object to report progress and errors to.
        :param config: Optional configuration
        """
        cdef svn_error_t *error
        cdef svn_ra_callbacks2_t *callbacks2
        cdef apr_hash_t *config_hash
        self.url = url
        self.pool = Pool(NULL)
        assert self.pool != NULL
        _check_error(svn_ra_create_callbacks(&callbacks2, self.pool))
        config_hash = apr_hash_make(self.pool)
        for (key, val) in config.items():
            apr_hash_set(config_hash, key, len(key), val)
        _check_error(svn_ra_open2(&self.ra, url, callbacks2, None, config_hash, 
                     self.pool))

    def get_uuid(self):
        """Obtain the globally unique identifier for this repository."""
        cdef char *uuid
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        _check_error(svn_ra_get_uuid(self.ra, &uuid, temp_pool))
        apr_pool_destroy(temp_pool)
        return uuid

    def reparent(self, url):
        """Switch to a different url."""
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        _check_error(svn_ra_reparent(self.ra, url, temp_pool))
        apr_pool_destroy(temp_pool)

    def get_latest_revnum(self):
        """Obtain the number of the latest committed revision in the 
        connected repository.
        """
        cdef long latest_revnum
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        _check_error(svn_ra_get_latest_revnum(self.ra, &latest_revnum, 
                     temp_pool))
        apr_pool_destroy(temp_pool)
        return latest_revnum

    def get_log(self, callback, paths, start, end, limit=0, 
                discover_changed_paths=True, strict_node_history=True,
                revprops=[SVN_PROP_REVISION_LOG,SVN_PROP_REVISION_AUTHOR,SVN_PROP_REVISION_DATE]):
        cdef apr_array_header_t *paths_array
        cdef apr_pool_t *temp_pool
        _check_error(svn_ra_get_log(self.ra, paths_array, start, end, limit,
            discover_changed_paths, strict_node_history, py_svn_log_wrapper, 
            callback, temp_pool))
        apr_pool_destroy(temp_pool)

    def get_repos_root(self):
        """Obtain the URL of the root of this repository."""
        cdef char *root
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        _check_error(svn_ra_get_repos_root(self.ra, &root, 
                     temp_pool))
        apr_pool_destroy(temp_pool)
        return root

    def do_update(self, revision_to_update_to, update_target, recurse, 
                  update_editor):
        cdef svn_ra_reporter2_t *reporter
        cdef void *report_baton
        cdef apr_pool_t *temp_pool
        cdef svn_delta_editor_t *editor
        temp_pool = Pool(self.pool)
        _check_error(svn_ra_do_update(self.ra, &reporter, &report_baton, 
                     revision_to_update_to, update_target, recurse, 
                     editor, update_editor, temp_pool))
        apr_pool_destroy(temp_pool)
        ret = Reporter()
        ret.reporter = reporter
        ret.report_baton = report_baton
        ret.pool = temp_pool
        return ret

    def do_switch(self, revision_to_update_to, update_target, recurse, 
                  update_editor):
        cdef svn_ra_reporter2_t *reporter
        cdef void *report_baton
        cdef apr_pool_t *temp_pool
        cdef svn_delta_editor_t *editor
        temp_pool = Pool(self.pool)
        _check_error(svn_ra_do_update(self.ra, &reporter, &report_baton, 
                     revision_to_update_to, update_target, recurse, 
                     editor, update_editor, temp_pool))
        apr_pool_destroy(temp_pool)
        return Reporter(reporter, report_baton, temp_pool)

    def replay(self, revision, low_water_mark, send_deltas, update_editor):
        cdef svn_ra_reporter2_t *reporter
        cdef void *report_baton
        cdef apr_pool_t *temp_pool
        cdef svn_delta_editor_t *editor
        temp_pool = Pool(self.pool)
        _check_error(svn_ra_replay(self.ra, revision, low_water_mark,
                     send_deltas, editor, update_editor, temp_pool))
        apr_pool_destroy(temp_pool)
        return Reporter(reporter, report_baton, temp_pool)

    def rev_proplist(self, rev):
        cdef apr_pool_t *temp_pool
        cdef apr_hash_t *props
        temp_pool = Pool(self.pool)
        _check_error(svn_ra_rev_proplist(self.ra, rev, &props, temp_pool))
        py_props = {}
        # FIXME: Convert props to py_props
        apr_pool_destroy(temp_pool)
        return py_props

    def get_commit_editor(self, revprops, commit_callback, lock_tokens, 
                          keep_locks):
        cdef apr_pool_t *temp_pool
        cdef svn_delta_editor_t *editor
        cdef void *edit_baton
        cdef apr_hash_t *hash_lock_tokens
        temp_pool = Pool(self.pool)
        _check_error(svn_ra_get_commit_editor2(self.ra, &editor, 
            &edit_baton, revprops[SVN_PROP_REVISION_LOG], py_commit_callback, 
            commit_callback, hash_lock_tokens, keep_locks, temp_pool))
        apr_pool_destroy(temp_pool)
        return None # FIXME: convert editor

    def change_rev_prop(self, rev, name, value):
        cdef apr_pool_t *temp_pool
        cdef svn_string_t *val_string
        temp_pool = Pool(self.pool)
        val_string = svn_string_ncreate(value, len(value), temp_pool)
        _check_error(svn_ra_change_rev_prop(self.ra, rev, name, 
                     val_string, temp_pool))
        apr_pool_destroy(temp_pool)
    
    def get_dir(self, path, revision, dirent_fields):
        cdef apr_pool_t *temp_pool
        cdef apr_hash_t *dirents
        cdef apr_hash_t *props
        cdef long fetch_rev
        temp_pool = Pool(self.pool)
        _check_error(svn_ra_get_dir2(self.ra, &dirents, &fetch_rev, &props,
                     path, revision, dirent_fields, temp_pool))
        # FIXME: Convert dirents to python hash
        # FIXME: Convert props to python hash
        py_dirents = {}
        py_props = {}
        apr_pool_destroy(temp_pool)
        return (py_dirents, fetch_rev, py_props)

    def get_lock(self, path):
        cdef svn_lock_t *lock
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        _check_error(svn_ra_get_lock(self.ra, &lock, path, temp_pool))
        apr_pool_destroy(temp_pool)
        return lock

    def check_path(self, path, revision):
        cdef svn_node_kind_t kind
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        _check_error(svn_ra_check_path(self.ra, path, revision, &kind, 
                     temp_pool))
        apr_pool_destroy(temp_pool)
        return kind

    def has_capability(self, capability):
        cdef apr_pool_t *temp_pool
        cdef int has
        temp_pool = Pool(self.pool)
        _check_error(svn_ra_has_capability(self.ra, &has, capability, 
                     temp_pool))
        apr_pool_destroy(temp_pool)
        return has

    def unlock(self, path_tokens, break_lock, lock_func):
        cdef apr_pool_t *temp_pool
        cdef apr_hash_t *hash_path_tokens
        temp_pool = Pool(self.pool)
        # FIXME: Convert path_tokens to a apr_hash
        _check_error(svn_ra_unlock(self.ra, hash_path_tokens, break_lock,
                     py_lock_func, lock_func, temp_pool))
        apr_pool_destroy(temp_pool)

    def lock(self, path_revs, comment, steal_lock, lock_func):
        cdef apr_pool_t *temp_pool
        cdef apr_hash_t *hash_path_revs
        # FIXME: Create hash_path_revs
        temp_pool = Pool(self.pool)
        _check_error(svn_ra_lock(self.ra, hash_path_revs, comment, steal_lock,
                     py_lock_func, lock_func, temp_pool))
        apr_pool_destroy(temp_pool)

    def __dealloc__(self):
        if self.pool != NULL:
            apr_pool_destroy(self.pool)

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.url)

SVN_PROP_REVISION_LOG = "svn:log"
SVN_PROP_REVISION_AUTHOR = "svn:author"
SVN_PROP_REVISION_DATE = "svn:date"
