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

from apr cimport apr_initialize, apr_hash_t
from apr cimport apr_array_header_t, apr_array_make, apr_array_push
from apr cimport apr_pool_t
from types cimport svn_error_t, svn_cancel_func_t
from core cimport Pool, check_error

apr_initialize()

cdef extern from "svn_client.h":
	ctypedef struct svn_client_ctx_t:
		svn_auth_baton_t *auth_baton
		svn_client_get_commit_log_t log_msg_func
		void *log_msg_baton
		apr_hash_t *config
		svn_cancel_func_t cancel_func
		void *cancel_baton
		svn_wc_notify_func2_t notify_func2
		void *notify_baton2
		svn_client_get_commit_log2_t log_msg_func2
		void *log_msg_baton2
		svn_ra_progress_notify_func_t progress_func
		void *progress_baton
    ctypedef struct svn_client_commit_info_t
    svn_error_t *svn_client_create_context(svn_client_ctx_t **ctx, 
                                           apr_pool_t *pool)

    svn_error_t *svn_client_mkdir(svn_client_commit_info_t **commit_info_p,
                     apr_array_header_t *paths,
                     svn_client_ctx_t *ctx,
                     apr_pool_t *pool)
     

cdef class Client:
    cdef svn_client_ctx_t *client
    cdef apr_pool_t *pool
    def __init__(self):
        self.pool = Pool(NULL)
        check_error(svn_client_create_context(&self.client, self.pool))

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

