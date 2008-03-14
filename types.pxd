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

from apr cimport apr_status_t, apr_pool_t, apr_time_t

cdef extern from "svn_version.h":
    ctypedef struct svn_version_t:
        int major
        int minor
        int patch
        char *tag


cdef extern from "svn_error.h":
    ctypedef struct svn_error_t:
        apr_status_t apr_err
        char *message
        char *file
        char *line


cdef extern from "svn_types.h":
    ctypedef int svn_boolean_t
    ctypedef svn_error_t *(*svn_cancel_func_t)(cancel_baton)
    ctypedef long svn_revnum_t
    ctypedef struct svn_lock_t:
        char *path
        char *token
        char *owner
        char *comment
        svn_boolean_t is_dav_comment
        apr_time_t creation_date
        apr_time_t expiration_date


cdef extern from "svn_string.h":
    ctypedef struct svn_string_t:
        char *data
        long len
    svn_string_t *svn_string_ncreate(char *bytes, long size, apr_pool_t *pool)


