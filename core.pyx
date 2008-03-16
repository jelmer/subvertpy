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

from types cimport svn_error_t, svn_node_kind_t, svn_node_dir, svn_node_file, svn_node_unknown, svn_node_none, svn_error_create
from apr cimport apr_initialize, apr_status_t, apr_time_t, apr_hash_t
from apr cimport apr_pool_t, apr_pool_create, apr_pool_destroy
from apr cimport apr_array_header_t, apr_array_make, apr_array_push
from apr cimport apr_hash_index_t, apr_hash_this, apr_hash_first, apr_hash_next

apr_initialize()

cdef svn_error_t *py_cancel_func(cancel_baton):
    if cancel_baton is not None:
        if cancel_baton():
            return svn_error_create(200015, NULL, NULL) # cancelled
    return NULL

class SubversionException(Exception):
    def __init__(self, num, msg):
        Exception.__init__(self, msg, num)
        self.num = num
        self.msg = msg


cdef wrap_lock(svn_lock_t *lock):
    return (lock.path, lock.token, lock.owner, lock.comment, lock.is_dav_comment, lock.creation_date, lock.expiration_date)

cdef check_error(svn_error_t *error):
    if error:
        if error.message != NULL:
            raise SubversionException(error.apr_err, error.message)
        else:
            raise SubversionException(error.apr_err, None)

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

def time_to_cstring(when):
    """Convert a UNIX timestamp to a Subversion CString."""
    cdef apr_pool_t *pool
    pool = Pool(NULL)
    ret = svn_time_to_cstring(when, pool)
    apr_pool_destroy(pool)
    return ret

def time_from_cstring(data):
    """Parse a Subversion time string and return a UNIX timestamp."""
    cdef apr_time_t when
    cdef apr_pool_t *pool
    pool = Pool(NULL)
    check_error(svn_time_from_cstring(&when, data, pool))
    apr_pool_destroy(pool)
    return when


cdef extern from "svn_config.h":
    svn_error_t *svn_config_get_config(apr_hash_t **cfg_hash,
                                       char *config_dir,
                                       apr_pool_t *pool)

def get_config(config_dir=None):
    cdef apr_pool_t *pool
    cdef apr_hash_t *cfg_hash
    cdef apr_hash_index_t *idx
    cdef char *c_config_dir
    cdef char *key
    cdef char *val
    cdef long klen
    pool = Pool(NULL)
    if config_dir is None:
        c_config_dir = NULL
    else:
        c_config_dir = config_dir
    check_error(svn_config_get_config(&cfg_hash, c_config_dir, pool))
    ret = {}
    idx = apr_hash_first(pool, cfg_hash)
    while idx:
        apr_hash_this(idx, <void **>&key, &klen, <void **>&val)
        ret[key] = val
        idx = apr_hash_next(idx)
    apr_pool_destroy(pool)
    return ret


NODE_DIR = svn_node_dir
NODE_FILE = svn_node_file
NODE_UNKNOWN = svn_node_unknown
NODE_NONE = svn_node_none

cdef apr_array_header_t *string_list_to_apr_array(apr_pool_t *pool, object l):
    cdef apr_array_header_t *ret
    cdef char **el
    if l is None:
        return NULL
    ret = apr_array_make(pool, len(l), 4)
    for i in l:
        el = <char **>apr_array_push(ret)
        el[0] = i
    return ret
