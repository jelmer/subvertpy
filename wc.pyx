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

from core import check_error, Pool

cdef svn_error_t *py_cancel_func(cancel_baton):
    cancel_baton()
    return NULL

apr_initialize()

cdef extern from "svn_wc.h":
    ctypedef struct svn_wc_adm_access_t
    svn_version_t *svn_wc_version()
    svn_error_t *svn_wc_adm_open3(svn_wc_adm_access_t **adm_access,
                                  svn_wc_adm_access_t *associated,
                                  char *path,
                                  svn_boolean_t write_lock,
                                  int depth,
                                  svn_cancel_func_t cancel_func,
                                  cancel_baton,
                                  apr_pool_t *pool)
    svn_error_t *svn_wc_adm_close(svn_wc_adm_access_t *adm_access)
    char *svn_wc_adm_access_path(svn_wc_adm_access_t *adm_access)
    svn_boolean_t svn_wc_adm_locked(svn_wc_adm_access_t *adm_access)
    svn_error_t *svn_wc_locked(svn_boolean_t *locked, char *path, apr_pool_t *pool)
    ctypedef struct svn_wc_revision_status_t:
        long min_rev
        long max_rev
        int switched
        int modified
    svn_error_t *svn_wc_revision_status(svn_wc_revision_status_t **result_p,
                       char *wc_path,
                       char *trail_url,
                       svn_boolean_t committed,
                       svn_cancel_func_t cancel_func,
                       void *cancel_baton,
                       apr_pool_t *pool)
    svn_error_t *svn_wc_prop_get(svn_string_t **value,
                             char *name,
                             char *path,
                             svn_wc_adm_access_t *adm_access,
                             apr_pool_t *pool)
    svn_error_t *svn_wc_entries_read(apr_hash_t **entries,
                                 svn_wc_adm_access_t *adm_access,
                                 svn_boolean_t show_hidden,
                                 apr_pool_t *pool)

def version():
    """Get libsvn_wc version information.

    :return: tuple with major, minor, patch version number and tag.
    """
    return (svn_ra_version().major, svn_ra_version().minor, 
            svn_ra_version().minor, svn_ra_version().tag)

cdef class WorkingCopy:
    cdef svn_wc_adm_access_t *adm
    cdef apr_pool_t *pool
    def __init__(self, path, associated=None, write_lock=False, depth=0, 
                 cancel_func=None):
        self.pool = Pool(NULL)
        check_error(svn_wc_adm_open3(&self.adm, associated, path, 
                     write_lock, depth, py_cancel_func, cancel_func, 
                     self.pool))

    def access_path(self):
        return svn_wc_adm_access_path(self.adm)

    def locked(self):
        return svn_wc_adm_locked(self.adm)

    def prop_get(self, name, path):
        cdef svn_string_t *value
        check_error(svn_wc_prop_get(&value, name, path, self.adm, temp_pool))
        return PyString_FromStringAndSize(value.data, value.len)

    def entries_read(self, show_hidden):
        cdef apr_hash_t *entries
        check_error(svn_wc_entries_read(&entries, self.adm, 
                     show_hidden, temp_pool))
        # FIXME: Create py_entries
        py_entries = {}
        return py_entries

    def __dealloc__(self):
        svn_wc_adm_close(self.adm)


def revision_status(wc_path, trail_url, committed, cancel_func=None):
    cdef svn_wc_revision_status_t *revstatus
    check_error(svn_wc_revision_status(&revstatus, wc_path, trail_url,
                 committed, py_cancel_func, cancel_func, temp_pool))
    return (revstatus.min_rev, revstatus.max_rev, 
            revstatus.switched, revstatus.modified)


