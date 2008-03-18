# Copyright (C) 2008 Jelmer Vernooij <jelmer@samba.org>
# vim: ft=pyrex

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

from types cimport svn_error_t, svn_filesize_t, svn_string_t, svn_revnum_t, svn_stream_t
from apr cimport apr_pool_t, apr_size_t

cdef extern from "svn_ra.h":
    ctypedef struct svn_ra_reporter2_t:
        svn_error_t *(*set_path)(void *report_baton,
                           char *path,
                           long revision,
                           int start_empty,
                           char *lock_token,
                           apr_pool_t *pool) except *

        svn_error_t *(*delete_path)(void *report_baton, 
                char *path, apr_pool_t *pool) except *

        svn_error_t *(*link_path)(void *report_baton,
                                char *path,
                                char *url,
                                long revision,
                                int start_empty,
                                char *lock_token,
                                apr_pool_t *pool) except *

        svn_error_t *(*finish_report)(void *report_baton, apr_pool_t *pool) except *

        svn_error_t *(*abort_report)(void *report_baton, apr_pool_t *pool) except *

cdef extern from "svn_delta.h":
    ctypedef enum svn_delta_action:
        svn_txdelta_source
        svn_txdelta_target
        svn_txdelta_new

    ctypedef struct svn_txdelta_op_t:
        svn_delta_action action_code
        apr_size_t offset
        apr_size_t length

    ctypedef struct svn_txdelta_window_t:
        svn_filesize_t sview_offset
        apr_size_t sview_len
        apr_size_t tview_len
        int num_ops
        int src_ops
        svn_txdelta_op_t *ops
        svn_string_t *new_data

    ctypedef svn_error_t *(*svn_txdelta_window_handler_t) (svn_txdelta_window_t *window, void *baton)

    ctypedef struct svn_delta_editor_t:
        svn_error_t *(*set_target_revision)(void *edit_baton, 
                svn_revnum_t target_revision, apr_pool_t *pool) except * 
        svn_error_t *(*open_root)(void *edit_baton, svn_revnum_t base_revision, 
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

    svn_error_t *svn_txdelta_send_stream(svn_stream_t *stream,
                                     svn_txdelta_window_handler_t handler,
                                     void *handler_baton,
                                     unsigned char *digest,
                                     apr_pool_t *pool)

cdef new_editor(svn_delta_editor_t *editor, void *edit_baton, apr_pool_t *pool)
