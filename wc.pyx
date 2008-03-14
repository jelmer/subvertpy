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

from apr cimport apr_pool_t, apr_initialize, apr_hash_t, apr_pool_destroy
from types cimport svn_error_t, svn_version_t, svn_boolean_t, svn_cancel_func_t , svn_string_t, svn_string_ncreate

from core cimport check_error, Pool, py_cancel_func

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
                                  object cancel_baton,
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
                       object cancel_baton,
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
    svn_error_t *svn_wc_prop_set2(char *name,
                              svn_string_t *value,
                              char *path,
                              svn_wc_adm_access_t *adm_access,
                              svn_boolean_t skip_checks,
                              apr_pool_t *pool)

    svn_boolean_t svn_wc_is_normal_prop(char *name)
    svn_boolean_t svn_wc_is_wc_prop(char *name)
    svn_boolean_t svn_wc_is_entry_prop(char *name)

def version():
    """Get libsvn_wc version information.

    :return: tuple with major, minor, patch version number and tag.
    """
    return (svn_ra_version().major, svn_ra_version().minor, 
            svn_ra_version().minor, svn_ra_version().tag)

cdef class WorkingCopy:
    cdef svn_wc_adm_access_t *adm
    cdef apr_pool_t *pool
    def __init__(self, associated, path, write_lock=False, depth=0, 
                 cancel_func=None):
        self.pool = Pool(NULL)
        # FIXME: Use associated
        check_error(svn_wc_adm_open3(&self.adm, NULL, path, 
                     write_lock, depth, py_cancel_func, cancel_func, 
                     self.pool))

    def access_path(self):
        return svn_wc_adm_access_path(self.adm)

    def locked(self):
        return svn_wc_adm_locked(self.adm)

    def prop_get(self, name, path):
        cdef svn_string_t *value
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        check_error(svn_wc_prop_get(&value, name, path, self.adm, temp_pool))
        ret = PyString_FromStringAndSize(value.data, value.len)
        apr_pool_destroy(temp_pool)
        return ret

    def prop_set(self, name, value, path, skip_checks=False):
        cdef apr_pool_t *temp_pool
        cdef svn_string_t *cvalue
        temp_pool = Pool(self.pool)
        cvalue = svn_string_ncreate(value, len(value), temp_pool)
        check_error(svn_wc_prop_set2(name, cvalue, path, self.adm, 
                    skip_checks, temp_pool))
        apr_pool_destroy(temp_pool)

    def entries_read(self, show_hidden):
        cdef apr_hash_t *entries
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        check_error(svn_wc_entries_read(&entries, self.adm, 
                     show_hidden, temp_pool))
        # FIXME: Create py_entries
        py_entries = {}
        apr_pool_destroy(temp_pool)
        return py_entries

    def __dealloc__(self):
        svn_wc_adm_close(self.adm)


def revision_status(wc_path, trail_url, committed, cancel_func=None):
    cdef svn_wc_revision_status_t *revstatus
    cdef apr_pool_t *temp_pool
    temp_pool = Pool(NULL)
    check_error(svn_wc_revision_status(&revstatus, wc_path, trail_url,
                 committed, py_cancel_func, cancel_func, temp_pool))
    ret = (revstatus.min_rev, revstatus.max_rev, 
            revstatus.switched, revstatus.modified)
    apr_pool_destroy(temp_pool)
    return ret

cdef is_normal_prop(name):
    return svn_wc_is_normal_prop(name)

cdef is_wc_prop(name):
    return svn_wc_is_wc_prop(name)

cdef is_entry_prop(name):
    return svn_wc_is_entry_prop(name)
