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

cdef extern from "svn_version.h":
    ctypedef struct svn_version_t:
        int major
        int minor
        int patch
        char *tag


cdef extern from "svn_types.h":
    ctypedef int svn_boolean_t
    ctypedef svn_error_t *(*svn_cancel_func_t)(cancel_baton)

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


def version():
    """Get libsvn_wc version information.

    :return: tuple with major, minor, patch version number and tag.
    """
    return (svn_ra_version().major, svn_ra_version().minor, 
            svn_ra_version().minor, svn_ra_version().tag)

cdef class WorkingCopy:
    cdef svn_wc_adm_access_t *adm
    def __init__(self, path, associated=None, write_lock=False, depth=0, 
                 cancel_func=None):
        self.pool = Pool(NULL)
        _check_error(svn_wc_adm_open3(&self.adm, associated, path, 
                     write_lock, depth, py_cancel_func, cancel_func, 
                     self.pool))

    def access_path(self):
        return svn_wc_adm_access_path(self.adm)

    def locked(self):
        return svn_wc_adm_locked(self.adm)

    def __dealloc__(self):
        svn_wc_adm_close(self.adm)
