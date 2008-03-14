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

from types cimport svn_error_t
from apr cimport apr_initialize, apr_status_t, apr_time_t
from apr cimport apr_pool_t, apr_pool_create, apr_pool_destroy

apr_initialize()

cdef svn_error_t *py_cancel_func(cancel_baton):
    cancel_baton()
    return NULL

class SubversionException(Exception):
    def __init__(self, num, msg):
        self.num = num
        self.msg = msg


cdef check_error(svn_error_t *error):
    if error:
        raise SubversionException(error.apr_err, errormessage)


cdef apr_pool_t *Pool(apr_pool_t *parent):
    cdef apr_status_t status
    cdef apr_pool_t *ret
    ret = NULL
    status = apr_pool_create(&ret, parent)
    if status != 0:
        # FIXME: Clearer error
        raise Exception("APR Error")
    return ret


cdef extern from "svn_time.h":
    char *svn_time_to_cstring(apr_time_t when, apr_pool_t *pool)
    svn_error_t *svn_time_from_cstring(apr_time_t *when, char *data, 
                                       apr_pool_t *pool)

cdef object time_to_cstring(when):
    """Convert a UNIX timestamp to a Subversion CString."""
    cdef apr_pool_t *pool
    pool = Pool(NULL)
    ret = svn_time_to_cstring(when, pool)
    apr_pool_destroy(pool)
    return ret

cdef apr_time_t time_from_cstring(data):
    """Parse a Subversion time string and return a UNIX timestamp."""
    cdef apr_time_t when
    cdef apr_pool_t *pool
    check_error(svn_time_from_cstring(&when, data, pool))
    apr_pool_destroy(pool)
    return when

