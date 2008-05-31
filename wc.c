/*
 * Copyright © 2008 Jelmer Vernooij <jelmer@samba.org>
 * -*- coding: utf-8 -*-
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 */
#include <Python.h>
#include <apr_general.h>
#include <svn_wc.h>

from apr cimport apr_pool_t, apr_initialize, apr_hash_t, apr_pool_destroy, apr_time_t, apr_hash_first, apr_hash_next, apr_hash_this, apr_hash_index_t, apr_array_header_t, apr_array_pop, apr_hash_make, apr_hash_set, apr_palloc
from types cimport svn_error_t, svn_version_t, svn_boolean_t, svn_cancel_func_t , svn_string_t, svn_string_ncreate, svn_node_kind_t, svn_revnum_t, svn_prop_t, svn_lock_t
from ra cimport svn_ra_reporter2_t, svn_delta_editor_t, new_editor

from core cimport check_error, Pool, py_cancel_func

def version():
    """Get libsvn_wc version information.

    :return: tuple with major, minor, patch version number and tag.
    """
    cdef svn_version_t *ver
    ver = svn_wc_version()
    return (ver.major, ver.minor, ver.minor, ver.tag)

cdef svn_error_t *py_wc_found_entry(char *path, svn_wc_entry_t *entry, void *walk_baton, apr_pool_t *pool):
    fn = <object>walk_baton
    # FIXME: entry
    fn(path)
    return NULL


cdef svn_wc_entry_callbacks_t py_wc_entry_callbacks
py_wc_entry_callbacks.found_entry = py_wc_found_entry

cdef void py_wc_notify_func(void *baton, svn_wc_notify_t *notify, apr_pool_t *pool):
    pass # FIXME

class Entry:
    def __init__(self, name, revision, url, repos, uuid, kind, schedule, copied=False, deleted=False, absent=False, incomplete=False):
        self.name = name
        self.revision = revision
        self.url = url
        self.uuid = uuid
        self.repos = repos
        self.kind = kind
        self.schedule = schedule
        self.copied = copied
        self.deleted = deleted
        self.absent = absent
        self.incomplete = incomplete

PyObject *py_entry(svn_wc_entry_t *entry)
{
    if (entry.uuid == NULL) {
        uuid = Py_None;
	} else {
        uuid = PyString_FromString(entry.uuid);
	}
    if (entry.url == NULL) {
        url = Py_None;
	} else {
        url = PyString_FromString(entry.url);
	}
    if entry.repos == NULL:
        repos = None
    else:
        repos = entry.repos
    ret = Entry(entry.name, entry.revision, url, repos, uuid, entry.kind, entry.schedule, entry.copied, entry.deleted, entry.absent, entry.incomplete)
    ret.cmt_rev = entry.cmt_rev
    if entry.copyfrom_url != NULL:
        ret.copyfrom_url = entry.copyfrom_url
        ret.copyfrom_rev = entry.copyfrom_rev
    else:
        ret.copyfrom_url = None
        ret.copyfrom_rev = -1
    # FIXME: entry.conflict_old, entry.conflict_new, entry.conflict_wrk, entry.prejfile, entry.text_time, entry.prop_time, entry.checksum, entry.cmt_date, entry.cmt_author, entry.lock_token, entry.lock_owner, entry.lock_comment, entry.lock_creation_date, entry.has_props, entry.has_prop_mods, entry.cachable_props, entry.present_props)
    return ret;
}

cdef class WorkingCopy:
    cdef svn_wc_adm_access_t *adm
    cdef apr_pool_t *pool
    def __init__(self, WorkingCopy associated, char *path, int write_lock=False, int depth=0, 
                 cancel_func=None):
        cdef svn_wc_adm_access_t *parent_wc
        self.pool = Pool(NULL)
        if associated is None:
            parent_wc = NULL
        else:
            parent_wc = associated.adm
        check_error(svn_wc_adm_open3(&self.adm, parent_wc, path, 
                     write_lock, depth, py_cancel_func, cancel_func, 
                     self.pool))

    def access_path(self):
        return svn_wc_adm_access_path(self.adm)

    def locked(self):
        return svn_wc_adm_locked(self.adm)

    def prop_get(self, char *name, char *path):
        cdef svn_string_t *value
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        check_error(svn_wc_prop_get(&value, name, path, self.adm, temp_pool))
        if value == NULL:
            ret = None
        else:
            ret = PyString_FromStringAndSize(value.data, value.len)
        apr_pool_destroy(temp_pool)
        return ret

    def prop_set(self, char *name, char *value, char *path, int skip_checks=False):
        cdef apr_pool_t *temp_pool
        cdef svn_string_t *cvalue
        temp_pool = Pool(self.pool)
        cvalue = svn_string_ncreate(value, len(value), temp_pool)
        check_error(svn_wc_prop_set2(name, cvalue, path, self.adm, 
                    skip_checks, temp_pool))
        apr_pool_destroy(temp_pool)

    def entries_read(self, int show_hidden=False):
        cdef apr_hash_t *entries
        cdef apr_pool_t *temp_pool
        cdef apr_hash_index_t *idx
        cdef char *key
        cdef long klen
        cdef svn_wc_entry_t *entry
        temp_pool = Pool(self.pool)
        check_error(svn_wc_entries_read(&entries, self.adm, 
                     show_hidden, temp_pool))
        py_entries = {}
        idx = apr_hash_first(temp_pool, entries)
        while idx:
            apr_hash_this(idx, <void **>&key, &klen, <void **>&entry)
            py_entries[key] = py_entry(entry)
            idx = apr_hash_next(idx)
        apr_pool_destroy(temp_pool)
        return py_entries

    def walk_entries(self, char *path, callbacks, int show_hidden=False, cancel_func=None):
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        check_error(svn_wc_walk_entries2(path, self.adm, 
                    &py_wc_entry_callbacks, <void *>callbacks,
                    show_hidden, py_cancel_func, <void *>cancel_func,
                    temp_pool))
        apr_pool_destroy(temp_pool)

    def entry(self, char *path, int show_hidden=False):
        cdef apr_pool_t *temp_pool
        cdef svn_wc_entry_t *entry
        temp_pool = Pool(self.pool)
        check_error(svn_wc_entry(&entry, path, self.adm, show_hidden, temp_pool))
        apr_pool_destroy(temp_pool)

        return py_entry(entry)

    def get_prop_diffs(self, char *path):
        cdef apr_pool_t *temp_pool
        cdef apr_array_header_t *propchanges
        cdef apr_hash_t *original_props
        cdef apr_hash_index_t *idx
        cdef svn_string_t *string
        cdef char *key
        cdef long klen
        cdef svn_prop_t *el
        temp_pool = Pool(self.pool)
        check_error(svn_wc_get_prop_diffs(&propchanges, &original_props, 
                    path, self.adm, temp_pool))
        py_propchanges = []
        for i in range(propchanges.nelts):
            el = <svn_prop_t *>propchanges.elts[i]
            py_propchanges.append((el.name, PyString_FromStringAndSize(el.value.data, el.value.len)))
        py_orig_props = {}
        idx = apr_hash_first(temp_pool, original_props)
        while idx:
            apr_hash_this(idx, <void **>&key, &klen, <void **>&string)
            py_orig_props[key] = PyString_FromStringAndSize(string.data, string.len)
            idx = apr_hash_next(idx)
        apr_pool_destroy(temp_pool)
        return (py_propchanges, py_orig_props)

    def add(self, char *path, copyfrom_url=None, int copyfrom_rev=-1, cancel_func=None,
            notify_func=None):
        cdef apr_pool_t *temp_pool
        cdef char *c_copyfrom_url
        temp_pool = Pool(self.pool)
        if copyfrom_url is None:
            c_copyfrom_url = NULL
        else:
            c_copyfrom_url = copyfrom_url
        check_error(svn_wc_add2(path, self.adm, c_copyfrom_url, 
                                copyfrom_rev, py_cancel_func, 
                                <void *>cancel_func,
                                py_wc_notify_func, 
                                <void *>notify_func, 
                                temp_pool))
        apr_pool_destroy(temp_pool)

    def copy(self, char *src, char *dst, cancel_func=None, notify_func=None):
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        check_error(svn_wc_copy2(src, self.adm, dst,
                                py_cancel_func, <void *>cancel_func,
                                py_wc_notify_func, <void *>notify_func, 
                                temp_pool))
        apr_pool_destroy(temp_pool)

    def delete(self, char *path, cancel_func=None, notify_func=None):
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        check_error(svn_wc_delete2(path, self.adm, 
                                py_cancel_func, <void *>cancel_func,
                                py_wc_notify_func, <void *>notify_func, 
                                temp_pool))
        apr_pool_destroy(temp_pool)

    def crawl_revisions(self, char *path, reporter, int restore_files=True, 
                        int recurse=True, int use_commit_times=True,
                        notify_func=None):
        cdef apr_pool_t *temp_pool
        cdef svn_wc_traversal_info_t *traversal_info
        temp_pool = Pool(self.pool)
        traversal_info = svn_wc_init_traversal_info(temp_pool)
        check_error(svn_wc_crawl_revisions2(path, self.adm, 
                    &py_ra_reporter, <void *>reporter, 
                    restore_files, recurse, use_commit_times, 
                    py_wc_notify_func, <void *>notify_func,
                    traversal_info, temp_pool))
        apr_pool_destroy(temp_pool)

    def get_update_editor(self, target, use_commit_times=True, recurse=True, 
                    notify_func=None, cancel_func=None, diff3_cmd=None):
        cdef char *c_diff3_cmd
        cdef svn_delta_editor_t *editor
        cdef void *edit_baton
        cdef apr_pool_t *pool
        cdef svn_revnum_t *latest_revnum
        if diff3_cmd is None:
            c_diff3_cmd = NULL
        else:
            c_diff3_cmd = diff3_cmd
        pool = Pool(NULL)
        latest_revnum = <svn_revnum_t *>apr_palloc(pool, sizeof(svn_revnum_t))
        check_error(svn_wc_get_update_editor2(latest_revnum, self.adm, target, 
                    use_commit_times, recurse, py_wc_notify_func, <void *>notify_func, 
                    py_cancel_func, <void *>cancel_func, c_diff3_cmd, &editor, &edit_baton, 
                    NULL, pool))
        return new_editor(editor, edit_baton, pool)

    def close(self):
        if self.adm != NULL:
            svn_wc_adm_close(self.adm)
            self.adm = NULL

    def __dealloc__(self):
        if self.pool != NULL:
            apr_pool_destroy(self.pool)


def revision_status(char *wc_path, trail_url=None, int committed=False, cancel_func=None):
    """Determine the revision status of a specified working copy.

    :return: Tuple with minimum and maximum revnums found, whether the 
             working copy was switched and whether it was modified.
    """
    cdef svn_wc_revision_status_t *revstatus
    cdef apr_pool_t *temp_pool
    cdef char *c_trail_url
    temp_pool = Pool(NULL)
    if trail_url is None:
        c_trail_url = NULL
    else:
        c_trail_url = trail_url
    check_error(svn_wc_revision_status(&revstatus, wc_path, c_trail_url,
                 committed, py_cancel_func, cancel_func, temp_pool))
    ret = (revstatus.min_rev, revstatus.max_rev, 
            revstatus.switched, revstatus.modified)
    apr_pool_destroy(temp_pool)
    return ret

PyObject *is_normal_prop(char *name)
{
    return svn_wc_is_normal_prop(name);
}

def is_wc_prop(char *name):
    return svn_wc_is_wc_prop(name)

def is_entry_prop(char *name):
    return svn_wc_is_entry_prop(name)

def get_adm_dir():
    cdef apr_pool_t *pool
    pool = Pool(NULL)
    ret = svn_wc_get_adm_dir(pool)
    apr_pool_destroy(pool)
    return ret

def get_pristine_copy_path(char *path):
    cdef apr_pool_t *pool
    cdef char *pristine_path
    pool = Pool(NULL)
    try:
        check_error(svn_wc_get_pristine_copy_path(path, &pristine_path, pool))
        ret = pristine_path
    finally:
        apr_pool_destroy(pool)
    return ret

SCHEDULE_NORMAL = 0
SCHEDULE_ADD = 1
SCHEDULE_DELETE = 2
SCHEDULE_REPLACE = 3


cdef svn_error_t *py_ra_report_set_path(void *baton, char *path, long revision, int start_empty, char *lock_token, apr_pool_t *pool) except *:
    self = <object>baton
    if lock_token == NULL:
        py_lock_token = None
    else:
        py_lock_token = lock_token
    self.set_path(path, revision, start_empty, py_lock_token)
    return NULL

svn_error_t *py_ra_report_delete_path(void *baton, char *path, apr_pool_t *pool)
{
    PyObject *self = (PyObject *)baton;
    self.delete_path(path);
    return NULL;
}

svn_error_t *py_ra_report_link_path(void *report_baton, char *path, char *url, long revision, int start_empty, char *lock_token, apr_pool_t *pool)
{
    PyObject *self = (PyObject *)report_baton;
    if (lock_token == NULL) {
        py_lock_token = None;
	} else { 
        py_lock_token = PyString_FromString(lock_token);
	}
    self.link_path(path, url, revision, start_empty, py_lock_token);
    return NULL;
}

svn_error_t *py_ra_report_finish(void *baton, apr_pool_t *pool)
{
    PyObject *self = (PyObject *)baton;
    self.finish();
    return NULL;
}

svn_error_t *py_ra_report_abort(void *baton, apr_pool_t *pool)
{
    PyObject *self = (PyObject *)baton;
    self.abort();
    return NULL;
}

cdef svn_ra_reporter2_t py_ra_reporter
py_ra_reporter.finish_report = py_ra_report_finish
py_ra_reporter.abort_report = py_ra_report_abort
py_ra_reporter.link_path = py_ra_report_link_path
py_ra_reporter.delete_path = py_ra_report_delete_path
py_ra_reporter.set_path = py_ra_report_set_path

PyObject *get_default_ignores(PyObject *config)
{
    apr_array_header_t *patterns
    apr_pool_t *pool
    char **pattern
    apr_hash_t *hash_config
    pool = Pool(NULL);
    hash_config = apr_hash_make(pool);
    for k, v in config.items():
        apr_hash_set(hash_config, <char *>k, len(k), <char *>v);
    check_error(svn_wc_get_default_ignores(&patterns, hash_config, pool));
    ret = PyList_New();
    pattern = <char **>apr_array_pop(patterns);
    while (pattern != NULL) {
        ret.append(pattern[0]);
        pattern = <char **>apr_array_pop(patterns);
	}
    apr_pool_destroy(pool);
    return ret;
}

def ensure_adm(char *path, char *uuid, char *url, repos=None, svn_revnum_t rev=-1):
    cdef apr_pool_t *pool
    cdef char *c_repos
    pool = Pool(NULL)
    if repos is None:
        c_repos = NULL
    else:
        c_repos = repos
    check_error(svn_wc_ensure_adm2(path, uuid, url, c_repos, rev, pool))
    apr_pool_destroy(pool)

PyObject *check_wc(char *path)
{
    apr_pool_t *pool;
    int wc_format;
    pool = Pool(NULL);
    check_error(svn_wc_check_wc(path, &wc_format, pool))
    apr_pool_destroy(pool);
    return wc_format;
}

void initwc(void)
{
	apr_initialize();
}
