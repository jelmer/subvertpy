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
from apr cimport apr_pool_t
from types cimport svn_error_t, svn_cancel_func_t, svn_auth_baton_t, svn_revnum_t, svn_boolean_t, svn_commit_info_t
from core cimport Pool, check_error

# Make sure APR is initialized
apr_initialize()

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


cdef void to_opt_revision(arg, svn_opt_revision_t *ret):
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
    ctypedef svn_error_t *(*svn_client_get_commit_log2_t) (char **log_msg, char **tmp_file, apr_array_header_t *commit_items, baton, apr_pool_t *pool)

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
    ctypedef struct svn_client_commit_info_t
    svn_error_t *svn_client_create_context(svn_client_ctx_t **ctx, 
                                           apr_pool_t *pool)

    svn_error_t *svn_client_mkdir(svn_client_commit_info_t **commit_info_p,
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
     
cdef svn_error_t *py_log_msg_func2(char **log_msg, char **tmp_file, apr_array_header_t *commit_items, baton, apr_pool_t *pool):
    py_commit_items = []
    (py_log_msg, py_tmp_file) = baton(py_commit_items)
    #FIXME: *log_msg = py_log_msg
    #FIXME: *tmp_file = py_tmp_file
    return NULL


cdef class Client:
    cdef svn_client_ctx_t *client
    cdef apr_pool_t *pool
    def __init__(self):
        self.pool = Pool(NULL)
        check_error(svn_client_create_context(&self.client, self.pool))

    def set_log_msg_func(self, func):
        self.client.log_msg_func2 = py_log_msg_func2
        self.client.log_msg_baton2 = <void *>func

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
        cdef apr_array_header_t *c_targets
        # FIXME: Fill c_targets
        check_error(svn_client_commit3(&commit_info, c_targets,
                   recurse, keep_locks, self.client, self.pool))

    def mkdir(self, paths):
        cdef apr_array_header_t *apr_paths
        cdef char **el
        cdef svn_client_commit_info_t *commit_info
        apr_paths = apr_array_make(self.pool, len(paths), 4)
        for p in paths:
            el = <char **>apr_array_push(apr_paths)
            # FIXME: *el = p
        check_error(svn_client_mkdir(&commit_info, apr_paths, self.client, 
            self.pool))


