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

# APR stuff

cdef extern from "apr_errno.h":
    ctypedef int apr_status_t

cdef extern from "apr_general.h":
    apr_status_t apr_initialize()

cdef extern from "apr_file_io.h":
    ctypedef struct apr_file_t 
    ctypedef long long apr_off_t

cdef extern from "apr_pools.h":
    ctypedef struct apr_pool_t
    ctypedef unsigned long apr_size_t
    void apr_pool_destroy(apr_pool_t *)
    apr_status_t apr_pool_create(apr_pool_t **newpool, apr_pool_t *parent)
    void *apr_palloc(apr_pool_t *, apr_size_t)

cdef extern from "apr_tables.h":
    ctypedef struct apr_array_header_t
    apr_array_header_t *apr_array_make(apr_pool_t *p, int nelts, int elt_size)
    void *apr_array_push(apr_array_header_t *arr)
    void *apr_array_pop(apr_array_header_t *arr)

cdef extern from "apr_hash.h":
    ctypedef struct apr_hash_t
    ctypedef struct apr_hash_index_t
    apr_hash_t *apr_hash_make(apr_pool_t *pool)
    void apr_hash_set(apr_hash_t *ht, char *key, long klen, char *val)
    apr_hash_index_t *apr_hash_first(apr_pool_t *p, apr_hash_t *ht)
    apr_hash_index_t * apr_hash_next(apr_hash_index_t *hi)
    void apr_hash_this(apr_hash_index_t *hi, void **key, 
                                long *klen, void **val)

cdef extern from "apr_time.h":
    ctypedef unsigned long long apr_time_t


