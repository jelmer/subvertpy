# Copyright © 2008 Jelmer Vernooij <jelmer@samba.org>
# -*- coding: utf-8 -*-

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

from types cimport svn_error_t, svn_node_kind_t, svn_node_dir, svn_node_file, svn_node_unknown, svn_node_none, svn_error_create, svn_log_message_receiver_t, svn_log_changed_path_t
from apr cimport apr_initialize, apr_status_t, apr_time_t, apr_hash_t, apr_size_t
from apr cimport apr_pool_t, apr_pool_create, apr_pool_destroy
from apr cimport apr_array_header_t, apr_array_make, apr_array_push
from apr cimport apr_hash_index_t, apr_hash_this, apr_hash_first, apr_hash_next, apr_strerror
import constants
from constants import PROP_REVISION_LOG, PROP_REVISION_AUTHOR, PROP_REVISION_DATE
from types cimport svn_stream_set_read, svn_stream_set_write, svn_stream_set_close, svn_stream_from_stringbuf, svn_stream_create
from types cimport svn_stringbuf_t, svn_stringbuf_ncreate, svn_string_t, svn_revnum_t

cdef extern from "Python.h":
    void Py_INCREF(object)
    void Py_DECREF(object)
    object PyString_FromStringAndSize(char *, unsigned long)
    char *PyString_AS_STRING(object)
    
cdef extern from "string.h":
    ctypedef unsigned long size_t 
    void *memcpy(void *dest, void *src, size_t len)

apr_initialize()

cdef svn_error_t *py_svn_error(exc):
    cdef svn_error_t *ret
    msg = "Python exception occurred: " + str(exc)
    ret = svn_error_create(424242, NULL, msg)
    return ret

cdef svn_error_t *py_cancel_func(cancel_baton):
    if cancel_baton is not None:
        if cancel_baton():
            return svn_error_create(constants.ERR_CANCELLED, NULL, NULL)
    return NULL

class SubversionException(Exception):
    def __init__(self, msg, num):
        Exception.__init__(self, msg, num)
        self.num = num
        self.msg = msg


cdef wrap_lock(svn_lock_t *lock):
    return (lock.path, lock.token, lock.owner, lock.comment, lock.is_dav_comment, lock.creation_date, lock.expiration_date)

cdef check_error(svn_error_t *error):
    if error:
        if error.apr_err == 424242:
            return
        if error.message != NULL:
            raise SubversionException(error.message, error.apr_err)
        else:
            raise SubversionException(None, error.apr_err)

cdef apr_pool_t *Pool(apr_pool_t *parent):
    cdef apr_status_t status
    cdef apr_pool_t *ret
    cdef char errmsg[1024]
    ret = NULL
    status = apr_pool_create(&ret, parent)
    if status != 0:
        raise Exception(apr_strerror(status, errmsg, sizeof(errmsg)))
    return ret


cdef extern from "svn_time.h":
    char *svn_time_to_cstring(apr_time_t when, apr_pool_t *pool)
    svn_error_t *svn_time_from_cstring(apr_time_t *when, char *data, 
                                       apr_pool_t *pool)

def time_to_cstring(apr_time_t when):
    """Convert a UNIX timestamp to a Subversion CString."""
    cdef apr_pool_t *pool
    pool = Pool(NULL)
    ret = svn_time_to_cstring(when, pool)
    apr_pool_destroy(pool)
    return ret

def time_from_cstring(char *data):
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

cdef apr_array_header_t *revnum_list_to_apr_array(apr_pool_t *pool, object l):
    cdef apr_array_header_t *ret
    cdef svn_revnum_t *el
    if l is None:
        return NULL
    ret = apr_array_make(pool, len(l), sizeof(svn_revnum_t))
    for i in l:
        el = <svn_revnum_t *>apr_array_push(ret)
        el[0] = i
    return ret

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

cdef svn_error_t *py_svn_log_wrapper(baton, apr_hash_t *changed_paths, long revision, char *author, char *date, char *message, apr_pool_t *pool) except *:
    cdef apr_hash_index_t *idx
    cdef char *key
    cdef long klen
    cdef svn_log_changed_path_t *val
    if changed_paths == NULL:
        py_changed_paths = None
    else:
        py_changed_paths = {}
        idx = apr_hash_first(pool, changed_paths)
        while idx:
            apr_hash_this(idx, <void **>&key, &klen, <void **>&val)
            if val.copyfrom_path != NULL:
                py_changed_paths[key] = (chr(val.action), val.copyfrom_path, 
                                         val.copyfrom_rev)
            else:
                py_changed_paths[key] = (chr(val.action), None, -1)
            idx = apr_hash_next(idx)
    revprops = {}    
    if message != NULL:
        revprops[PROP_REVISION_LOG] = message
    if author != NULL:
        revprops[PROP_REVISION_AUTHOR] = author
    if date != NULL:
        revprops[PROP_REVISION_DATE] = date
    baton(py_changed_paths, revision, revprops)
    return NULL

cdef svn_error_t *py_stream_read(void *baton, char *buffer, apr_size_t *length):
    self = <object>baton
    ret = self.read(length[0])
    length[0] = len(ret)
    memcpy(buffer, PyString_AS_STRING(ret), len(ret))
    return NULL

cdef svn_error_t *py_stream_write(void *baton, char *data, apr_size_t *len):
    self = <object>baton
    self.write(PyString_FromStringAndSize(data, len[0]))
    return NULL

cdef svn_error_t *py_stream_close(void *baton):
    self = <object>baton
    self.close()
    Py_DECREF(self)

cdef svn_stream_t *string_stream(apr_pool_t *pool, text):
    cdef svn_stringbuf_t *buf
    buf = svn_stringbuf_ncreate(text, len(text), pool)
    return svn_stream_from_stringbuf(buf, pool)

cdef svn_stream_t *new_py_stream(apr_pool_t *pool, object py):
    cdef svn_stream_t *stream
    Py_INCREF(py)
    stream = svn_stream_create(<void *>py, pool)
    svn_stream_set_read(stream, py_stream_read)
    svn_stream_set_write(stream, py_stream_write)
    svn_stream_set_close(stream, py_stream_close)
    return stream

cdef prop_hash_to_dict(apr_hash_t *props):
    cdef char *key
    cdef apr_hash_index_t *idx
    cdef long klen
    cdef svn_string_t *val
    cdef apr_pool_t *pool
    if props == NULL:
        return None
    pool = Pool(NULL)
    py_props = {}
    idx = apr_hash_first(pool, props)
    while idx:
        apr_hash_this(idx, <void **>&key, &klen, <void **>&val)
        py_props[key] = PyString_FromStringAndSize(val.data, val.len)
        idx = apr_hash_next(idx)
    apr_pool_destroy(pool)
    return py_props
