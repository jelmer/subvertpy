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

from apr cimport apr_pool_t
from types cimport svn_error_t, svn_lock_t
cdef apr_pool_t *Pool(apr_pool_t *parent)
cdef check_error(svn_error_t *error)
cdef svn_error_t *py_cancel_func(cancel_baton)
cdef wrap_lock(svn_lock_t *)
