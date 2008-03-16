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

from apr cimport apr_initialize, apr_hash_t, apr_time_t
from apr cimport apr_array_header_t, apr_array_make, apr_array_push
from apr cimport apr_pool_t, apr_pool_destroy
from types cimport svn_error_t, svn_cancel_func_t, svn_auth_baton_t, svn_revnum_t, svn_boolean_t, svn_commit_info_t, svn_string_t, svn_log_message_receiver_t
from core cimport Pool, check_error, string_list_to_apr_array, py_svn_log_wrapper

# Make sure APR is initialized
apr_initialize()

cdef extern from "Python.h":
    void Py_INCREF(object)
    void Py_DECREF(object)
    object PyString_FromStringAndSize(char *, unsigned long)

cdef extern from "svn_opt.h":
    ctypedef enum svn_opt_revision_kind:
        svn_opt_revision_unspecified
        svn_opt_revision_number,
        svn_opt_revision_date,
        svn_opt_revision_committed,
        svn_opt_revision_previous,
        svn_opt_revision_base,
        svn_opt_revision_working,
        svn_opt_revision_head

    ctypedef union svn_opt_revision_value_t:
        svn_revnum_t number
        apr_time_t date

    ctypedef struct svn_opt_revision_t:
        svn_opt_revision_kind kind
        svn_opt_revision_value_t value


cdef void to_opt_revision(arg, svn_opt_revision_t *ret) except *:
    if isinstance(arg, int):
        ret.kind = svn_opt_revision_number
        ret.value.number = arg
    elif arg is None:
        ret.kind = svn_opt_revision_unspecified
    elif arg == "HEAD":
        ret.kind = svn_opt_revision_head
    elif arg == "WORKING":
        ret.kind = svn_opt_revision_working
    elif arg == "BASE":
        ret.kind = svn_opt_revision_base
    else:
        raise Exception("Unable to parse revision %r" % arg)


cdef extern from "svn_client.h":
    ctypedef svn_error_t *(*svn_client_get_commit_log2_t) (char **log_msg, char **tmp_file, apr_array_header_t *commit_items, baton, apr_pool_t *pool) except *

    ctypedef struct svn_client_ctx_t:
        svn_auth_baton_t *auth_baton
        apr_hash_t *config
        svn_cancel_func_t cancel_func
        void *cancel_baton
        #svn_wc_notify_func2_t notify_func2
        #void *notify_baton2
        svn_client_get_commit_log2_t log_msg_func2
        void *log_msg_baton2
        #svn_ra_progress_notify_func_t progress_func
        #void *progress_baton
    svn_error_t *svn_client_create_context(svn_client_ctx_t **ctx, 
                                           apr_pool_t *pool)

    svn_error_t *svn_client_mkdir2(svn_commit_info_t **commit_info_p,
                     apr_array_header_t *paths,
                     svn_client_ctx_t *ctx,
                     apr_pool_t *pool)
    svn_error_t *svn_client_checkout2(svn_revnum_t *result_rev,
                     char *URL,
                     char *path,
                     svn_opt_revision_t *peg_revision,
                     svn_opt_revision_t *revision,
                     svn_boolean_t recurse,
                     svn_boolean_t ignore_externals,
                     svn_client_ctx_t *ctx,
                     apr_pool_t *pool)

    svn_error_t *svn_client_add3(char *path, svn_boolean_t recursive,
                svn_boolean_t force, svn_boolean_t no_ignore, 
                svn_client_ctx_t *ctx, apr_pool_t *pool)

    svn_error_t *svn_client_commit3(svn_commit_info_t **commit_info_p,
                   apr_array_header_t *targets,
                   svn_boolean_t recurse,
                   svn_boolean_t keep_locks,
                   svn_client_ctx_t *ctx,
                   apr_pool_t *pool)

    svn_error_t *svn_client_delete2(svn_commit_info_t **commit_info_p,
                   apr_array_header_t *paths,
                   svn_boolean_t force,
                   svn_client_ctx_t *ctx,
                   apr_pool_t *pool)

    svn_error_t *svn_client_copy3(svn_commit_info_t **commit_info_p,
                 char *src_path,
                 svn_opt_revision_t *src_revision,
                 char *dst_path,
                 svn_client_ctx_t *ctx,
                 apr_pool_t *pool)

    svn_error_t *svn_client_propset2(char *propname,
                    svn_string_t *propval,
                    char *target,
                    svn_boolean_t recurse,
                    svn_boolean_t skip_checks,
                    svn_client_ctx_t *ctx,
                    apr_pool_t *pool)

    svn_error_t *svn_client_update2(apr_array_header_t **result_revs,
                   apr_array_header_t *paths,
                   svn_opt_revision_t *revision,
                   svn_boolean_t recurse,
                   svn_boolean_t ignore_externals,
                   svn_client_ctx_t *ctx,
                   apr_pool_t *pool)

    svn_error_t *svn_client_revprop_get(char *propname,
                       svn_string_t **propval,
                       char *URL,
                       svn_opt_revision_t *revision,
                       svn_revnum_t *set_rev,
                       svn_client_ctx_t *ctx,
                       apr_pool_t *pool)

    svn_error_t *svn_client_revprop_set(char *propname,
                       svn_string_t *propval,
                       char *URL,
                       svn_opt_revision_t *revision,
                       svn_revnum_t *set_rev,
                       svn_boolean_t force,
                       svn_client_ctx_t *ctx,
                       apr_pool_t *pool)

    svn_error_t *svn_client_revprop_list(apr_hash_t **props,
                        char *URL,
                        svn_opt_revision_t *revision,
                        svn_revnum_t *set_rev,
                        svn_client_ctx_t *ctx,
                        apr_pool_t *pool)

    svn_error_t *svn_client_log3(apr_array_header_t *targets,
                svn_opt_revision_t *peg_revision,
                svn_opt_revision_t *start,
                svn_opt_revision_t *end,
                int limit,
                svn_boolean_t discover_changed_paths,
                svn_boolean_t strict_node_history,
                svn_log_message_receiver_t receiver,
                receiver_baton,
                svn_client_ctx_t *ctx,
                apr_pool_t *pool)
     
cdef svn_error_t *py_log_msg_func2(char **log_msg, char **tmp_file, apr_array_header_t *commit_items, baton, apr_pool_t *pool) except *:
    if baton is None:
        return NULL
    py_commit_items = []
    ret = baton(py_commit_items)
    if isinstance(ret, tuple):
        (py_log_msg, py_tmp_file) = ret
    else:
        py_tmp_file = None
        py_log_msg = ret
    if py_log_msg is not None:
        log_msg[0] = py_log_msg
    if py_tmp_file is not None:
        tmp_file[0] = py_tmp_file
    return NULL

cdef object py_commit_info_tuple(svn_commit_info_t *ci):
    if ci == NULL:
        return None
    if ci.author == NULL:
        py_author = None
    else:
        py_author = ci.author
    if ci.date == NULL:
        py_date = None
    else:
        py_date = ci.date
    return (ci.revision, py_date, py_author)

cdef class Client:
    cdef svn_client_ctx_t *client
    cdef apr_pool_t *pool
    cdef object callbacks
    def __init__(self):
        self.pool = Pool(NULL)
        check_error(svn_client_create_context(&self.client, self.pool))
        self.callbacks = []

    def __dealloc__(self):
        apr_pool_destroy(self.pool)
        self.pool = NULL

    def set_log_msg_func(self, func):
        self.client.log_msg_func2 = py_log_msg_func2
        self.client.log_msg_baton2 = <void *>func
        self.callbacks.append(func)

    def add(self, path, recursive=True, force=False, no_ignore=False):
        check_error(svn_client_add3(path, recursive, force, no_ignore, 
                    self.client, self.pool))

    def checkout(self, url, path, peg_rev=None, rev=None, recurse=True, 
                 ignore_externals=False):
        cdef svn_revnum_t result_rev
        cdef svn_opt_revision_t c_peg_rev, c_rev
        to_opt_revision(peg_rev, &c_peg_rev)
        to_opt_revision(rev, &c_rev)
        check_error(svn_client_checkout2(&result_rev, url, path, 
            &c_peg_rev, &c_rev, recurse, 
            ignore_externals, self.client, self.pool))
        return result_rev

    def commit(self, targets, recurse=True, keep_locks=True):
        cdef svn_commit_info_t *commit_info
        check_error(svn_client_commit3(&commit_info, 
                   string_list_to_apr_array(self.pool, targets),
                   recurse, keep_locks, self.client, self.pool))
        return py_commit_info_tuple(commit_info)

    def mkdir(self, paths):
        cdef svn_commit_info_t *commit_info
        check_error(svn_client_mkdir2(&commit_info, 
                    string_list_to_apr_array(self.pool, paths), 
                    self.client, self.pool))
        return py_commit_info_tuple(commit_info)

    def delete(self, paths, force=False):
        cdef svn_commit_info_t *commit_info
        check_error(svn_client_delete2(&commit_info, 
                    string_list_to_apr_array(self.pool, paths),
                    force, self.client, self.pool))
        return py_commit_info_tuple(commit_info)

    def copy(self, src_path, dst_path, src_rev=None):
        cdef svn_commit_info_t *commit_info
        cdef svn_opt_revision_t c_src_rev
        to_opt_revision(src_rev, &c_src_rev)
        commit_info = NULL
        check_error(svn_client_copy3(&commit_info, src_path, 
                    &c_src_rev, dst_path, self.client, self.pool))
        return py_commit_info_tuple(commit_info)

    def propset(self, propname, propval, target, recurse=True, 
            skip_checks=False):
        cdef svn_string_t c_propval
        c_propval.data = propval
        c_propval.len = len(propval)
        check_error(svn_client_propset2(propname, &c_propval,
                    target, recurse, skip_checks, self.client, self.pool))
    
    def update(self, paths, rev=None, recurse=True, ignore_externals=False):
        cdef apr_array_header_t *result_revs
        cdef svn_opt_revision_t c_rev
        to_opt_revision(rev, &c_rev)
        check_error(svn_client_update2(&result_revs, 
                string_list_to_apr_array(self.pool, paths), &c_rev, 
                recurse, ignore_externals, self.client, self.pool))
        # FIXME: Convert and return result_revs

    def revprop_get(self,propname, propval, url, rev=None):
        cdef svn_revnum_t set_rev
        cdef svn_opt_revision_t c_rev
        cdef svn_string_t *c_val
        to_opt_revision(rev, &c_rev)
        check_error(svn_client_revprop_get(propname, &c_val, url, 
                    &c_rev, &set_rev, self.client, self.pool))
        return (PyString_FromStringAndSize(c_val.data, c_val.len), set_rev)

    def revprop_set(self,propname, propval, url, rev=None, force=False):
        cdef svn_revnum_t set_rev
        cdef svn_opt_revision_t c_rev
        cdef svn_string_t c_val
        to_opt_revision(rev, &c_rev)
        c_val.data = propval
        c_val.len = len(propval)
        check_error(svn_client_revprop_set(propname, &c_val, url, 
                    &c_rev, &set_rev, force, self.client, self.pool))
        return set_rev

    def log(self, targets, callback, peg_revision=None, start=None, end=None,
            limit=0, discover_changed_paths=True, strict_node_history=True):
        cdef svn_opt_revision_t c_peg_rev, c_start_rev, c_end_rev
        to_opt_revision(peg_revision, &c_peg_rev)
        to_opt_revision(start, &c_start_rev)
        to_opt_revision(end, &c_end_rev)
        check_error(svn_client_log3(string_list_to_apr_array(self.pool, targets),
                    &c_peg_rev, &c_start_rev, &c_end_rev, limit, discover_changed_paths, strict_node_history, py_svn_log_wrapper, callback, self.client, self.pool))
