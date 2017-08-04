/*
 * Copyright © 2008 Jelmer Vernooij <jelmer@jelmer.uk>
 * -*- coding: utf-8 -*-
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2.1 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA
 */
#include <Python.h>
#include <apr_general.h>
#include <svn_wc.h>
#include <svn_path.h>
#include <svn_props.h>
#include <structmember.h>
#include <stdbool.h>
#include <apr_md5.h>
#include <apr_sha1.h>

#include "util.h"
#include "editor.h"
#include "wc.h"

/* Suppress warnings for this specific file, as it
 * provides backwards compatibility with svn < 1.7
 */
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wdeprecated-declarations"

static svn_wc_entry_callbacks2_t py_wc_entry_callbacks2;
static PyObject *py_entry(const svn_wc_entry_t *entry);

typedef struct {
    PyObject_VAR_HEAD
    svn_wc_adm_access_t *adm;
    apr_pool_t *pool;
} AdmObject;

typedef struct {
	PyObject_VAR_HEAD
	apr_pool_t *pool;
	svn_wc_entry_t entry;
} EntryObject;

svn_wc_adm_access_t *Adm_GetAdmAccess(PyObject *obj) {
    AdmObject *adm_obj = (AdmObject *)obj;
    return adm_obj->adm;
}

#define ADM_CHECK_CLOSED(adm_obj) \
    if (adm_obj->adm == NULL) { \
        PyErr_SetString(PyExc_RuntimeError, "WorkingCopy instance already closed"); \
        return NULL; \
    }

svn_wc_adm_access_t *PyObject_GetAdmAccess(PyObject *obj)
{
    return ((AdmObject *)obj)->adm;
}

static PyObject *adm_init(PyTypeObject *self, PyObject *args, PyObject *kwargs)
{
    PyObject *associated, *py_path;
    const char *path;
    bool write_lock=false;
    int depth=0;
    svn_wc_adm_access_t *parent_wc;
    svn_error_t *err;
    AdmObject *ret;
    char *kwnames[] = { "associated", "path", "write_lock", "depth", NULL };

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO|bi", kwnames,
                                     &associated, &py_path, &write_lock, &depth))
        return NULL;

    ret = PyObject_New(AdmObject, &Adm_Type);
    if (ret == NULL)
        return NULL;

    ret->pool = Pool(NULL);
    if (ret->pool == NULL) {
        return NULL;
    }
    if (associated == Py_None) {
        parent_wc = NULL;
    } else {
        parent_wc = ((AdmObject *)associated)->adm;
    }

    path = py_object_to_svn_dirent(py_path, ret->pool);
    if (path == NULL) {
        Py_DECREF(ret);
        return NULL;
    }

    Py_BEGIN_ALLOW_THREADS
        err = svn_wc_adm_open3(&ret->adm, parent_wc,
                               path,
                               write_lock, depth, py_cancel_check, NULL,
                               ret->pool);
    Py_END_ALLOW_THREADS

        if (err != NULL) {
            handle_svn_error(err);
            svn_error_clear(err);
            Py_DECREF(ret);
            return NULL;
        }

    return (PyObject *)ret;
}

static PyObject *adm_access_path(PyObject *self)
{
    AdmObject *admobj = (AdmObject *)self;
    ADM_CHECK_CLOSED(admobj);
    return py_object_from_svn_abspath(svn_wc_adm_access_path(admobj->adm));
}

static const char *py_object_to_adm_abspath(PyObject *obj, PyObject *adm, apr_pool_t *pool)
{
    const char *ret;
    PyObject *bytes_obj = NULL;
    AdmObject *admobj = (AdmObject *)adm;
    ADM_CHECK_CLOSED(admobj);

    if (PyUnicode_Check(obj)) {
        bytes_obj = obj = PyUnicode_AsUTF8String(obj);
        if (obj == NULL) {
            return NULL;
        }
    }

    if (!PyBytes_Check(obj)) {
        PyErr_SetString(PyExc_TypeError,
                        "URIs need to be UTF-8 bytestrings or unicode strings");
        Py_XDECREF(bytes_obj);
        return NULL;
    }

    ret = PyBytes_AsString(obj);
    ret = apr_pstrdup(pool, ret);
    Py_XDECREF(obj);
    if (ret == NULL) {
        return NULL;
    }
#if ONLY_SINCE_SVN(1, 7)
    if (svn_dirent_is_absolute(ret)) {
        return ret;
    } else {
        return svn_dirent_join(svn_wc_adm_access_path(admobj->adm), ret, pool);
    }
#else
    return ret;
#endif
}

static PyObject *adm_locked(PyObject *self)
{
    AdmObject *admobj = (AdmObject *)self;
    ADM_CHECK_CLOSED(admobj);
    return PyBool_FromLong(svn_wc_adm_locked(admobj->adm));
}

static PyObject *adm_prop_get(PyObject *self, PyObject *args)
{
    char *name;
    const char *path;
    AdmObject *admobj = (AdmObject *)self;
    const svn_string_t *value;
    apr_pool_t *temp_pool;
    PyObject *ret, *py_path;

    if (!PyArg_ParseTuple(args, "sO", &name, &py_path))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(temp_pool, svn_wc_prop_get(&value, name, path, admobj->adm, temp_pool));
    if (value == NULL || value->data == NULL) {
        ret = Py_None;
        Py_INCREF(ret);
    } else {
        ret = PyBytes_FromStringAndSize(value->data, value->len);
    }
    apr_pool_destroy(temp_pool);
    return ret;
}

static PyObject *adm_prop_set(PyObject *self, PyObject *args)
{
    char *name, *value;
    const char *path;
    AdmObject *admobj = (AdmObject *)self;
    bool skip_checks=false;
    apr_pool_t *temp_pool;
    int vallen;
    svn_string_t *cvalue;
    PyObject *py_path;
    PyObject *notify_func = Py_None;

    if (!PyArg_ParseTuple(args, "sz#O|bO", &name, &value, &vallen, &py_path, &skip_checks,
                          &notify_func))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

    if (value == NULL) {
        cvalue = NULL;
    } else {
        cvalue = svn_string_ncreate(value, vallen, temp_pool);
    }
#if ONLY_SINCE_SVN(1, 6)
    RUN_SVN_WITH_POOL(temp_pool, svn_wc_prop_set3(name, cvalue, path, admobj->adm,
                                                  skip_checks, py_wc_notify_func, (void *)notify_func,
                                                  temp_pool));
#else
    RUN_SVN_WITH_POOL(temp_pool, svn_wc_prop_set2(name, cvalue, path, admobj->adm,
                                                  skip_checks, temp_pool));
#endif
    apr_pool_destroy(temp_pool);

    Py_RETURN_NONE;
}

static PyObject *adm_entries_read(PyObject *self, PyObject *args)
{
    apr_hash_t *entries;
    AdmObject *admobj = (AdmObject *)self;
    apr_pool_t *temp_pool;
    bool show_hidden=false;
    apr_hash_index_t *idx;
    const char *key;
    apr_ssize_t klen;
    svn_wc_entry_t *entry;
    PyObject *py_entries, *obj;

    if (!PyArg_ParseTuple(args, "|b", &show_hidden))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL)
        return NULL;
    RUN_SVN_WITH_POOL(temp_pool, svn_wc_entries_read(&entries, admobj->adm,
                                                     show_hidden, temp_pool));
    py_entries = PyDict_New();
    if (py_entries == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }
    idx = apr_hash_first(temp_pool, entries);
    while (idx != NULL) {
        apr_hash_this(idx, (const void **)&key, &klen, (void **)&entry);
        if (entry == NULL) {
            obj = Py_None;
            Py_INCREF(obj);
        } else {
            obj = py_entry(entry);
        }
        PyDict_SetItemString(py_entries, key, obj);
        Py_DECREF(obj);
        idx = apr_hash_next(idx);
    }
    apr_pool_destroy(temp_pool);
    return py_entries;
}

static PyObject *adm_walk_entries(PyObject *self, PyObject *args)
{
    const char *path;
    PyObject *callbacks;
    bool show_hidden=false;
    apr_pool_t *temp_pool;
    AdmObject *admobj = (AdmObject *)self;
    svn_depth_t depth = svn_depth_infinity;
    PyObject *py_path;

    if (!PyArg_ParseTuple(args, "OO|bi", &py_path, &callbacks, &show_hidden, &depth))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

#if ONLY_SINCE_SVN(1, 5)
    RUN_SVN_WITH_POOL(temp_pool, svn_wc_walk_entries3(
                                                      path, admobj->adm,
                                                      &py_wc_entry_callbacks2, (void *)callbacks,
                                                      depth, show_hidden, py_cancel_check, NULL,
                                                      temp_pool));
#else
    if (depth != svn_depth_infinity) {
        PyErr_SetString(PyExc_NotImplementedError,
                        "depth != infinity not supported for svn < 1.5");
        apr_pool_destroy(temp_pool);
        return NULL;
    }
    RUN_SVN_WITH_POOL(temp_pool, svn_wc_walk_entries2(
                                                      path, admobj->adm,
                                                      &py_wc_entry_callbacks, (void *)callbacks,
                                                      show_hidden, py_cancel_check, NULL,
                                                      temp_pool));
#endif
    apr_pool_destroy(temp_pool);

    Py_RETURN_NONE;
}

static PyObject *adm_entry(PyObject *self, PyObject *args)
{
    const char *path;
    PyObject *py_path;
    bool show_hidden=false;
    apr_pool_t *temp_pool;
    AdmObject *admobj = (AdmObject *)self;
    const svn_wc_entry_t *entry;
    PyObject *ret;

    if (!PyArg_ParseTuple(args, "O|b", &py_path, &show_hidden))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(temp_pool, svn_wc_entry(&entry, path, admobj->adm, show_hidden, temp_pool));

    if (entry == NULL) {
        PyErr_Format(PyExc_KeyError, "No such entry '%s'", path);
        ret = NULL;
    } else  {
        ret = py_entry(entry);
    }

    apr_pool_destroy(temp_pool);
    return ret;
}

static PyObject *adm_get_prop_diffs(PyObject *self, PyObject *args)
{
    const char *path;
    apr_pool_t *temp_pool;
    apr_array_header_t *propchanges;
    apr_hash_t *original_props;
    PyObject *py_path;
    AdmObject *admobj = (AdmObject *)self;
    svn_prop_t el;
    int i;
    PyObject *py_propchanges, *py_orig_props, *pyval;

    if (!PyArg_ParseTuple(args, "O", &py_path))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }
    RUN_SVN_WITH_POOL(temp_pool, svn_wc_get_prop_diffs(&propchanges, &original_props,
                                                       path, admobj->adm, temp_pool));
    py_propchanges = PyList_New(propchanges->nelts);
    if (py_propchanges == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }
    for (i = 0; i < propchanges->nelts; i++) {
        el = APR_ARRAY_IDX(propchanges, i, svn_prop_t);
        if (el.value != NULL)
            pyval = Py_BuildValue("(sz#)", el.name, el.value->data, el.value->len);
        else
            pyval = Py_BuildValue("(sO)", el.name, Py_None);
        if (pyval == NULL) {
            apr_pool_destroy(temp_pool);
            Py_DECREF(py_propchanges);
            return NULL;
        }
        if (PyList_SetItem(py_propchanges, i, pyval) != 0) {
            Py_DECREF(py_propchanges);
            apr_pool_destroy(temp_pool);
            return NULL;
        }
    }
    py_orig_props = prop_hash_to_dict(original_props);
    apr_pool_destroy(temp_pool);
    if (py_orig_props == NULL) {
        Py_DECREF(py_propchanges);
        return NULL;
    }
    return Py_BuildValue("(NN)", py_propchanges, py_orig_props);
}

static PyObject *adm_add(PyObject *self, PyObject *args, PyObject *kwargs)
{
    const char *path;
    char *copyfrom_url=NULL;
    svn_revnum_t copyfrom_rev=-1;
    char *kwnames[] = { "path", "copyfrom_url", "copyfrom_rev", "notify_func", "depth", NULL };
    PyObject *notify_func=Py_None, *py_path;
    AdmObject *admobj = (AdmObject *)self;
    apr_pool_t *temp_pool;
    svn_depth_t depth = svn_depth_infinity;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|zlOi", kwnames, &py_path,
                                     &copyfrom_url, &copyfrom_rev, &notify_func, &depth))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

#if ONLY_SINCE_SVN(1, 6)
    RUN_SVN_WITH_POOL(temp_pool, svn_wc_add3(
                                             path, admobj->adm,
                                             depth, svn_uri_canonicalize(copyfrom_url, temp_pool),
                                             copyfrom_rev, py_cancel_check, NULL,
                                             py_wc_notify_func,
                                             (void *)notify_func,
                                             temp_pool));
#else
    if (depth != svn_depth_infinity) {
        PyErr_SetString(PyExc_NotImplementedError, "depth != infinity not supported on svn < 1.6");
        apr_pool_destroy(temp_pool);
        return NULL;
    }
    RUN_SVN_WITH_POOL(temp_pool, svn_wc_add2(
                                             path, admobj->adm, copyfrom_url,
                                             copyfrom_rev, py_cancel_check,
                                             py_wc_notify_func,
                                             (void *)notify_func,
                                             temp_pool));
#endif
    apr_pool_destroy(temp_pool);

    Py_RETURN_NONE;
}

static PyObject *adm_copy(PyObject *self, PyObject *args)
{
    AdmObject *admobj = (AdmObject *)self;
    char *src, *dst;
    PyObject *notify_func=Py_None;
    apr_pool_t *temp_pool;

    if (!PyArg_ParseTuple(args, "ss|O", &src, &dst, &notify_func))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL)
        return NULL;
    RUN_SVN_WITH_POOL(temp_pool, svn_wc_copy2(src, admobj->adm, dst,
                                              py_cancel_check, NULL,
                                              py_wc_notify_func, (void *)notify_func,
                                              temp_pool));
    apr_pool_destroy(temp_pool);

    Py_RETURN_NONE;
}

static PyObject *adm_delete(PyObject *self, PyObject *args, PyObject *kwargs)
{
    AdmObject *admobj = (AdmObject *)self;
    apr_pool_t *temp_pool;
    char *kwnames[] = { "path", "notify_func", "keep_local",
        NULL };
    const char *path;
    PyObject *py_path;
    PyObject *notify_func=Py_None;
    bool keep_local = false;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|Ob:delete", kwnames,
                                     &py_path, &notify_func, &keep_local))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

#if ONLY_SINCE_SVN(1, 5)
    RUN_SVN_WITH_POOL(temp_pool, svn_wc_delete3(path, admobj->adm,
                                                py_cancel_check, NULL,
                                                py_wc_notify_func, (void *)notify_func,
                                                keep_local,
                                                temp_pool));
#else
    if (keep_local) {
        PyErr_SetString(PyExc_NotImplementedError,
                        "keep_local not supported on Subversion < 1.5");
        return NULL;
    }

    RUN_SVN_WITH_POOL(temp_pool, svn_wc_delete2(path, admobj->adm,
                                                py_cancel_check, NULL,
                                                py_wc_notify_func, (void *)notify_func,
                                                temp_pool));
#endif
    apr_pool_destroy(temp_pool);

    Py_RETURN_NONE;
}

static PyObject *adm_crawl_revisions(PyObject *self, PyObject *args, PyObject *kwargs)
{
    const char *path;
    PyObject *reporter;
    bool restore_files=true, recurse=true, use_commit_times=true;
    PyObject *notify_func=Py_None;
    apr_pool_t *temp_pool;
    AdmObject *admobj = (AdmObject *)self;
    svn_wc_traversal_info_t *traversal_info;
    bool depth_compatibility_trick = false;
    bool honor_depth_exclude = false;
    char *kwnames[] = { "path", "reporter", "restore_files", "recurse", "use_commit_times", "notify_func", "depth_compatibility_trick", "honor_depth_exclude,", NULL };
    PyObject *py_path;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO|bbbObb", kwnames, &py_path,
                                     &reporter, &restore_files, &recurse, &use_commit_times,
                                     &notify_func, &depth_compatibility_trick, &honor_depth_exclude))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }
    traversal_info = svn_wc_init_traversal_info(temp_pool);
#if ONLY_SINCE_SVN(1, 6)
    RUN_SVN_WITH_POOL(temp_pool, svn_wc_crawl_revisions4(path, admobj->adm,
                                                         &py_ra_reporter3, (void *)reporter,
                                                         restore_files, recurse?svn_depth_infinity:svn_depth_files,
                                                         honor_depth_exclude?TRUE:FALSE,
                                                         depth_compatibility_trick?TRUE:FALSE, use_commit_times,
                                                         py_wc_notify_func, (void *)notify_func,
                                                         traversal_info, temp_pool));
#elif ONLY_SINCE_SVN(1, 5)
    RUN_SVN_WITH_POOL(temp_pool, svn_wc_crawl_revisions3(path, admobj->adm,
                                                         &py_ra_reporter3, (void *)reporter,
                                                         restore_files, recurse?svn_depth_infinity:svn_depth_files,
                                                         depth_compatibility_trick, use_commit_times,
                                                         py_wc_notify_func, (void *)notify_func,
                                                         traversal_info, temp_pool));
#else
    RUN_SVN_WITH_POOL(temp_pool, svn_wc_crawl_revisions2(path, admobj->adm,
                                                         &py_ra_reporter2, (void *)reporter,
                                                         restore_files, recurse, use_commit_times,
                                                         py_wc_notify_func, (void *)notify_func,
                                                         traversal_info, temp_pool));
#endif
    apr_pool_destroy(temp_pool);

    Py_RETURN_NONE;
}

static void wc_done_handler(void *self)
{
    AdmObject *admobj = (AdmObject *)self;

    Py_DECREF(admobj);
}

static PyObject *adm_get_update_editor(PyObject *self, PyObject *args)
{
    char *target;
    bool use_commit_times=true, recurse=true;
    PyObject * notify_func=Py_None;
    char *diff3_cmd=NULL;
    const svn_delta_editor_t *editor;
    AdmObject *admobj = (AdmObject *)self;
    void *edit_baton;
    apr_pool_t *pool;
    svn_revnum_t *latest_revnum;
    svn_error_t *err;
    bool allow_unver_obstructions = false;
    bool depth_is_sticky = false;

    if (!PyArg_ParseTuple(args, "s|bbOzbb", &target, &use_commit_times,
                          &recurse, &notify_func, &diff3_cmd, &depth_is_sticky,
                          &allow_unver_obstructions))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    pool = Pool(NULL);
    if (pool == NULL)
        return NULL;
    latest_revnum = (svn_revnum_t *)apr_palloc(pool, sizeof(svn_revnum_t));
    Py_BEGIN_ALLOW_THREADS
#if ONLY_SINCE_SVN(1, 5)
        /* FIXME: Support all values of depth */
        /* FIXME: Support fetch_func */
        /* FIXME: Support conflict func */
        err = svn_wc_get_update_editor3(latest_revnum, admobj->adm, target,
                                        use_commit_times, recurse?svn_depth_infinity:svn_depth_files,
                                        depth_is_sticky?TRUE:FALSE, allow_unver_obstructions?TRUE:FALSE,
                                        py_wc_notify_func, (void *)notify_func,
                                        py_cancel_check, NULL,
                                        NULL, NULL, NULL, NULL,
                                        diff3_cmd, NULL, &editor, &edit_baton,
                                        NULL, pool);
#else
    if (allow_unver_obstructions) {
        PyErr_SetString(PyExc_NotImplementedError,
                        "allow_unver_obstructions is not supported in svn < 1.5");
        apr_pool_destroy(pool);
        PyEval_RestoreThread(_save);
        return NULL;
    }
    if (depth_is_sticky) {
        PyErr_SetString(PyExc_NotImplementedError,
                        "depth_is_sticky is not supported in svn < 1.5");
        apr_pool_destroy(pool);
        PyEval_RestoreThread(_save);
        return NULL;
    }
    err = svn_wc_get_update_editor2(latest_revnum, admobj->adm, target,
                                    use_commit_times, recurse, py_wc_notify_func, (void *)notify_func,
                                    py_cancel_check, NULL, diff3_cmd, &editor, &edit_baton,
                                    NULL, pool);
#endif
    Py_END_ALLOW_THREADS
        if (err != NULL) {
            handle_svn_error(err);
            svn_error_clear(err);
            apr_pool_destroy(pool);
            return NULL;
        }
    Py_INCREF(admobj);
    return new_editor_object(NULL, editor, edit_baton, pool, &Editor_Type,
                             wc_done_handler, admobj, NULL);
}

static PyObject *adm_has_binary_prop(PyObject *self, PyObject *args)
{
    const char *path;
    svn_boolean_t binary;
    AdmObject *admobj = (AdmObject *)self;
    apr_pool_t *temp_pool;
    PyObject *py_path;

    if (!PyArg_ParseTuple(args, "O", &py_path))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(temp_pool, svn_wc_has_binary_prop(&binary, path, admobj->adm, temp_pool));

    apr_pool_destroy(temp_pool);

    return PyBool_FromLong(binary);
}

static PyObject *adm_process_committed(PyObject *self, PyObject *args, PyObject *kwargs)
{
    const char *path;
    char *rev_date = NULL, *rev_author = NULL;
    bool recurse, remove_lock = false;
    unsigned char *digest = NULL;
    svn_revnum_t new_revnum;
    PyObject *py_wcprop_changes = Py_None, *py_path;
    apr_array_header_t *wcprop_changes = NULL;
    AdmObject *admobj = (AdmObject *)self;
    apr_pool_t *temp_pool;
    int digest_len;
    bool remove_changelist = false;
    char *kwnames[] = { "path", "recurse", "new_revnum", "rev_date", "rev_author",
        "wcprop_changes", "remove_lock", "digest", "remove_changelist", NULL };

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "Oblzz|Obz#b", kwnames,
                                     &py_path, &recurse, &new_revnum, &rev_date,
                                     &rev_author, &py_wcprop_changes,
                                     &remove_lock, &digest, &digest_len, &remove_changelist))
        return NULL;

    PyErr_WarnEx(PyExc_DeprecationWarning, "process_committed is deprecated. Use process_committed_queue instead.", 2);

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

    if (!py_dict_to_wcprop_changes(py_wcprop_changes, temp_pool, &wcprop_changes)) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

#if ONLY_SINCE_SVN(1, 6)
    RUN_SVN_WITH_POOL(temp_pool, svn_wc_process_committed4(
                                                           path, admobj->adm, recurse, new_revnum,
                                                           rev_date, rev_author, wcprop_changes,
                                                           remove_lock, remove_changelist?TRUE:FALSE, digest, temp_pool));
#else
    if (remove_changelist) {
        PyErr_SetString(PyExc_NotImplementedError, "remove_changelist only supported in svn < 1.6");
        apr_pool_destroy(temp_pool);
        return NULL;
    }
    RUN_SVN_WITH_POOL(temp_pool, svn_wc_process_committed3(path, admobj->adm, recurse, new_revnum,
                                                           rev_date, rev_author, wcprop_changes,
                                                           remove_lock, digest, temp_pool));
#endif

    apr_pool_destroy(temp_pool);

    Py_RETURN_NONE;
}

static PyObject *adm_close(PyObject *self)
{
    AdmObject *admobj = (AdmObject *)self;
    if (admobj->adm != NULL) {
#if ONLY_SINCE_SVN(1, 6)
        apr_pool_t *temp_pool = Pool(NULL);
        Py_BEGIN_ALLOW_THREADS
            svn_wc_adm_close2(admobj->adm, temp_pool);
        apr_pool_destroy(temp_pool);
#else
        Py_BEGIN_ALLOW_THREADS
            svn_wc_adm_close(admobj->adm);
#endif
        Py_END_ALLOW_THREADS
            admobj->adm = NULL;
    }

    Py_RETURN_NONE;
}

static void adm_dealloc(PyObject *self)
{
    apr_pool_destroy(((AdmObject *)self)->pool);
    PyObject_Del(self);
}

static PyObject *adm_repr(PyObject *self)
{
    AdmObject *admobj = (AdmObject *)self;

    if (admobj->adm == NULL) {
        return PyRepr_FromFormat("<wc.WorkingCopy (closed) at 0x%p>", admobj);
    } else {
        return PyRepr_FromFormat("<wc.WorkingCopy at '%s'>",
                                 svn_wc_adm_access_path(admobj->adm));
    }
}

static PyObject *adm_remove_lock(PyObject *self, PyObject *args)
{
    const char *path;
    PyObject *py_path;
    AdmObject *admobj = (AdmObject *)self;
    apr_pool_t *temp_pool;

    if (!PyArg_ParseTuple(args, "O", &py_path))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(temp_pool, svn_wc_remove_lock(path, admobj->adm, temp_pool))

        apr_pool_destroy(temp_pool);

    Py_RETURN_NONE;
}

static PyObject *get_ancestry(PyObject *self, PyObject *args)
{
    const char *path;
    char *url;
    svn_revnum_t rev;
    apr_pool_t *temp_pool;
    PyObject *py_path;
    AdmObject *admobj = (AdmObject *)self;

    if (!PyArg_ParseTuple(args, "O", &py_path))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(temp_pool, svn_wc_get_ancestry(&url, &rev, path, admobj->adm, temp_pool));

    apr_pool_destroy(temp_pool);

    return Py_BuildValue("(si)", url, rev);
}

static PyObject *maybe_set_repos_root(PyObject *self, PyObject *args)
{
    char *path, *repos;
    apr_pool_t *temp_pool;
    AdmObject *admobj = (AdmObject *)self;

    if (!PyArg_ParseTuple(args, "ss", &path, &repos))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL)
        return NULL;

    RUN_SVN_WITH_POOL(temp_pool, svn_wc_maybe_set_repos_root(admobj->adm, path, repos, temp_pool));

    Py_RETURN_NONE;
}

static PyObject *add_repos_file(PyObject *self, PyObject *args, PyObject *kwargs)
{
    char *kwnames[] = { "dst_path", "new_base_contents", "new_contents",
        "new_base_props", "new_props", "copyfrom_url", "copyfrom_rev",
        "notify", NULL };
    AdmObject *admobj = (AdmObject *)self;
    apr_pool_t *temp_pool;
    PyObject *py_dst_path;
    char *dst_path, *copyfrom_url = NULL;
    svn_revnum_t copyfrom_rev = -1;
    PyObject *py_new_base_contents, *py_new_contents, *py_new_base_props,
             *py_new_props, *notify = Py_None;
    svn_stream_t *new_contents, *new_base_contents;
    apr_hash_t *new_props, *new_base_props;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OOOOO|zlO", kwnames,
                                     &py_dst_path, &py_new_base_contents, &py_new_contents, &py_new_base_props,
                                     &py_new_props, &copyfrom_url, &copyfrom_rev, &notify))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL)
        return NULL;

    new_base_props = prop_dict_to_hash(temp_pool, py_new_base_props);

    new_props = prop_dict_to_hash(temp_pool, py_new_props);

    new_base_contents = new_py_stream(temp_pool, py_new_base_contents);

    new_contents = new_py_stream(temp_pool, py_new_contents);

    dst_path = py_object_to_svn_dirent(py_dst_path, temp_pool);

#if ONLY_SINCE_SVN(1, 6)
    RUN_SVN_WITH_POOL(temp_pool, svn_wc_add_repos_file3(dst_path, admobj->adm,
                                                        new_base_contents,
                                                        new_contents,
                                                        new_base_props,
                                                        new_props,
                                                        copyfrom_url, copyfrom_rev,
                                                        py_cancel_check, NULL,
                                                        py_wc_notify_func, notify, temp_pool));
#else
    PyErr_SetString(PyExc_NotImplementedError,
                    "add_repos_file3 not supported on svn < 1.6");
    apr_pool_destroy(temp_pool);
#endif

    apr_pool_destroy(temp_pool);

    Py_RETURN_NONE;
}

static PyObject *mark_missing_deleted(PyObject *self, PyObject *args)
{
    const char *path;
    AdmObject *admobj = (AdmObject *)self;
    apr_pool_t *temp_pool;
    PyObject *py_path;

    if (!PyArg_ParseTuple(args, "O", &py_path))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(temp_pool, svn_wc_mark_missing_deleted(path, admobj->adm, temp_pool));

    apr_pool_destroy(temp_pool);

    Py_RETURN_NONE;
}

static PyObject *remove_from_revision_control(PyObject *self, PyObject *args)
{
    char *name;
    bool destroy_wf = false, instant_error = false;
    AdmObject *admobj = (AdmObject *)self;
    apr_pool_t *temp_pool;

    if (!PyArg_ParseTuple(args, "s|bb", &name, &destroy_wf, &instant_error))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL)
        return NULL;

    RUN_SVN_WITH_POOL(temp_pool,
                      svn_wc_remove_from_revision_control(admobj->adm, name,
                                                          destroy_wf?TRUE:FALSE, instant_error?TRUE:FALSE, py_cancel_check, NULL, temp_pool));

    apr_pool_destroy(temp_pool);

    Py_RETURN_NONE;
}

static PyObject *relocate(PyObject *self, PyObject *args)
{
    const char *path;
    char *from, *to;
    AdmObject *admobj = (AdmObject *)self;
    apr_pool_t *temp_pool;
    bool recurse = true;
    PyObject *py_validator = Py_None, *py_path;

    if (!PyArg_ParseTuple(args, "Oss|bO:relocate", &py_path, &from, &to, &recurse,
                          &py_validator))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

#if ONLY_SINCE_SVN(1, 6)
    RUN_SVN_WITH_POOL(temp_pool, svn_wc_relocate3(path, admobj->adm, from, to, recurse?TRUE:FALSE, wc_validator3, py_validator, temp_pool));
#else
    RUN_SVN_WITH_POOL(temp_pool, svn_wc_relocate2(path, admobj->adm, from, to, recurse?TRUE:FALSE, wc_validator2, py_validator, temp_pool));
#endif

    apr_pool_destroy(temp_pool);

    Py_RETURN_NONE;
}

static PyObject *crop_tree(PyObject *self, PyObject *args)
{
    char *target;
    svn_depth_t depth;
    PyObject *notify;
    apr_pool_t *temp_pool;
    AdmObject *admobj = (AdmObject *)self;

    if (!PyArg_ParseTuple(args, "si|O", &target, &depth, &notify))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

#if ONLY_SINCE_SVN(1, 6)
    temp_pool = Pool(NULL);
    if (temp_pool == NULL)
        return NULL;

    RUN_SVN_WITH_POOL(temp_pool, svn_wc_crop_tree(admobj->adm,
                                                  target, depth, py_wc_notify_func, notify,
                                                  py_cancel_check, NULL, temp_pool));

    apr_pool_destroy(temp_pool);

    Py_RETURN_NONE;
#else
    PyErr_SetString(PyExc_NotImplementedError,
                    "crop_tree only available on subversion < 1.6");
    return NULL;
#endif
}

static PyObject *translated_stream(PyObject *self, PyObject *args)
{
    char *path, *versioned_file;
    StreamObject *ret;
    svn_stream_t *stream;
    AdmObject *admobj = (AdmObject *)self;
    apr_pool_t *stream_pool;
    int flags;

    if (!PyArg_ParseTuple(args, "ssi", &path, &versioned_file, &flags))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

#if ONLY_SINCE_SVN(1, 5)
    stream_pool = Pool(NULL);
    if (stream_pool == NULL)
        return NULL;

    RUN_SVN_WITH_POOL(stream_pool,
                      svn_wc_translated_stream(&stream, path, versioned_file, admobj->adm,
                                               flags, stream_pool));

    ret = PyObject_New(StreamObject, &Stream_Type);
    if (ret == NULL)
        return NULL;

    ret->pool = stream_pool;
    ret->closed = FALSE;
    ret->stream = stream;

    return (PyObject *)ret;
#else
    PyErr_SetString(PyExc_NotImplementedError,
                    "translated_stream() is only available on Subversion >= 1.5");
    return NULL;
#endif
}

static PyObject *adm_text_modified(PyObject *self, PyObject *args)
{
    const char *path;
    bool force_comparison = false;
    apr_pool_t *temp_pool;
    svn_boolean_t ret;
    AdmObject *admobj = (AdmObject *)self;
    PyObject *py_path;

    if (!PyArg_ParseTuple(args, "O|b", &py_path, &force_comparison))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(temp_pool,
                      svn_wc_text_modified_p(&ret, path, force_comparison?TRUE:FALSE, admobj->adm,
                                             temp_pool));

    apr_pool_destroy(temp_pool);

    return PyBool_FromLong(ret);
}

static PyObject *adm_props_modified(PyObject *self, PyObject *args)
{
    const char *path;
    apr_pool_t *temp_pool;
    svn_boolean_t ret;
    AdmObject *admobj = (AdmObject *)self;
    PyObject *py_path;

    if (!PyArg_ParseTuple(args, "O", &py_path))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(temp_pool,
                      svn_wc_props_modified_p(&ret, path, admobj->adm, temp_pool));

    apr_pool_destroy(temp_pool);

    return PyBool_FromLong(ret);
}

static PyObject *adm_process_committed_queue(PyObject *self, PyObject *args)
{
    apr_pool_t *temp_pool;
    AdmObject *admobj = (AdmObject *)self;
    svn_revnum_t revnum;
    char *date, *author;
    PyObject *py_queue;

    if (!PyArg_ParseTuple(args, "O!lss", &CommittedQueue_Type, &py_queue,
                          &revnum, &date, &author))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL)
        return NULL;

    svn_wc_committed_queue_t *committed_queue = PyObject_GetCommittedQueue(py_queue);

#if ONLY_SINCE_SVN(1, 5)
    RUN_SVN_WITH_POOL(temp_pool, svn_wc_process_committed_queue(committed_queue, admobj->adm, revnum, date, author, temp_pool));
#else
    {
        int i;
        for (i = 0; i < py_queue->queue->queue->nelts; i++) {
            committed_queue_item_t *cqi = APR_ARRAY_IDX(committed_queue->queue, i,
                                                        committed_queue_item_t *);

            RUN_SVN_WITH_POOL(temp_pool, svn_wc_process_committed3(cqi->path, admobj->adm,
                                                                   cqi->recurse, revnum, date, author, cqi->wcprop_changes,
                                                                   cqi->remove_lock, cqi->digest, temp_pool));
        }
    }
#endif
    apr_pool_destroy(temp_pool);

    Py_RETURN_NONE;
}


static PyObject *is_wc_root(PyObject *self, PyObject *args)
{
    const char *path;
    svn_boolean_t wc_root;
    apr_pool_t *temp_pool;
    AdmObject *admobj = (AdmObject *)self;
    PyObject *py_path;

    if (!PyArg_ParseTuple(args, "O", &py_path))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(temp_pool,
                      svn_wc_is_wc_root(&wc_root, path, admobj->adm, temp_pool));

    apr_pool_destroy(temp_pool);

    return PyBool_FromLong(wc_root);
}

static PyObject *transmit_text_deltas(PyObject *self, PyObject *args)
{
    const char *path;
    const char *tempfile;
    bool fulltext;
    PyObject *editor_obj, *py_digest, *py_path;
    unsigned char digest[APR_MD5_DIGESTSIZE];
    apr_pool_t *temp_pool;
    AdmObject *admobj = (AdmObject *)self;
    PyObject *ret;

    if (!PyArg_ParseTuple(args, "ObO", &py_path, &fulltext, &editor_obj))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

    Py_INCREF(editor_obj);

    RUN_SVN_WITH_POOL(temp_pool,
                      svn_wc_transmit_text_deltas2(&tempfile, digest,
                                                   path, admobj->adm, fulltext?TRUE:FALSE,
                                                   &py_editor, editor_obj, temp_pool));

    py_digest = PyBytes_FromStringAndSize((char *)digest, APR_MD5_DIGESTSIZE);
    if (py_digest == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

    ret = Py_BuildValue("sN", tempfile, py_digest);
    if (ret == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

    apr_pool_destroy(temp_pool);

    return ret;
}

static PyObject *transmit_prop_deltas(PyObject *self, PyObject *args)
{
    const char *path;
    PyObject *editor_obj;
    apr_pool_t *temp_pool;
    AdmObject *admobj = (AdmObject *)self;
    PyObject *py_path;
    EntryObject *py_entry;

    if (!PyArg_ParseTuple(args, "OO!O", &py_path, &Entry_Type, &py_entry, &editor_obj))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

    Py_INCREF(editor_obj);

    RUN_SVN_WITH_POOL(temp_pool,
                      svn_wc_transmit_prop_deltas(path,
                                                  admobj->adm, &(py_entry->entry), &py_editor, editor_obj, NULL, temp_pool));

    apr_pool_destroy(temp_pool);

    Py_RETURN_NONE;
}

static PyObject *retrieve(PyObject *self, PyObject *args)
{
    const char *path;
    svn_wc_adm_access_t *result;
    PyObject *py_path;
    AdmObject *admobj = (AdmObject *)self, *ret;
    apr_pool_t *pool;

    if (!PyArg_ParseTuple(args, "O", &py_path))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    pool = Pool(NULL);
    if (pool == NULL)
        return NULL;

    path = py_object_to_svn_dirent(py_path, pool);
    if (path == NULL) {
        apr_pool_destroy(pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(pool, svn_wc_adm_retrieve(&result, admobj->adm,
                                                path, pool));

    ret = PyObject_New(AdmObject, &Adm_Type);
    if (ret == NULL)
        return NULL;

    ret->pool = pool;
    ret->adm = result;

    return (PyObject *)ret;
}

static PyObject *probe_retrieve(PyObject *self, PyObject *args)
{
    const char *path;
    svn_wc_adm_access_t *result;
    AdmObject *admobj = (AdmObject *)self, *ret;
    apr_pool_t *pool;
    PyObject *py_path;

    if (!PyArg_ParseTuple(args, "O", &py_path))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    pool = Pool(NULL);
    if (pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, pool);
    if (path == NULL) {
        apr_pool_destroy(pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(pool, svn_wc_adm_probe_retrieve(&result, admobj->adm,
                                                      path, pool));

    ret = PyObject_New(AdmObject, &Adm_Type);
    if (ret == NULL)
        return NULL;

    ret->pool = pool;
    ret->adm = result;

    return (PyObject *)ret;
}

static PyObject *probe_try(PyObject *self, PyObject *args)
{
    const char *path;
    svn_wc_adm_access_t *result = NULL;
    AdmObject *admobj = (AdmObject *)self, *ret;
    apr_pool_t *pool;
    int levels_to_lock = -1;
    bool writelock = false;
    PyObject *py_path;

    if (!PyArg_ParseTuple(args, "O|bi", &py_path, &writelock, &levels_to_lock))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    pool = Pool(NULL);
    if (pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, pool);
    if (path == NULL) {
        apr_pool_destroy(pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(pool, svn_wc_adm_probe_try3(&result, admobj->adm,
                                                  path, writelock, levels_to_lock,
                                                  py_cancel_check, NULL, pool));

    if (result == NULL) {
        apr_pool_destroy(pool);
        Py_RETURN_NONE;
    }

    ret = PyObject_New(AdmObject, &Adm_Type);
    if (ret == NULL)
        return NULL;

    ret->pool = pool;
    ret->adm = result;

    return (PyObject *)ret;
}

static PyObject *resolved_conflict(PyObject *self, PyObject *args)
{
    AdmObject *admobj = (AdmObject *)self;
    apr_pool_t *temp_pool;
    bool resolve_props, resolve_tree, resolve_text;
    int depth;
#if ONLY_SINCE_SVN(1, 5)
    svn_wc_conflict_choice_t conflict_choice;
#else
    int conflict_choice;
#endif
    PyObject *notify_func = Py_None;
    const char *path;
    PyObject *py_path;

    if (!PyArg_ParseTuple(args, "Obbbii|O", &py_path, &resolve_text,
                          &resolve_props, &resolve_tree, &depth,
                          &conflict_choice, &notify_func))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

#if ONLY_SINCE_SVN(1, 6)
    RUN_SVN_WITH_POOL(temp_pool,
                      svn_wc_resolved_conflict4(path, admobj->adm, resolve_text?TRUE:FALSE,
                                                resolve_props?TRUE:FALSE, resolve_tree?TRUE:FALSE, depth,
                                                conflict_choice, py_wc_notify_func,
                                                (void *)notify_func, py_cancel_check,
                                                NULL, temp_pool));
#elif ONLY_SINCE_SVN(1, 5)
    if (resolve_tree) {
        PyErr_SetString(PyExc_NotImplementedError,
                        "resolve_tree not supported with svn < 1.6");
        apr_pool_destroy(temp_pool);
        return NULL;
    } else {
        RUN_SVN_WITH_POOL(temp_pool,
                          svn_wc_resolved_conflict3(path, admobj->adm, resolve_text?TRUE:FALSE,
                                                    resolve_props?TRUE:FALSE, depth,
                                                    conflict_choice, py_wc_notify_func,
                                                    (void *)notify_func, py_cancel_check,
                                                    NULL, temp_pool));
    }
#else
    if (resolve_tree) {
        PyErr_SetString(PyExc_NotImplementedError,
                        "resolve_tree not supported with svn < 1.6");
        apr_pool_destroy(temp_pool);
        return NULL;
    } else if (depth != svn_depth_infinity && depth != svn_depth_files) {
        PyErr_SetString(PyExc_NotImplementedError,
                        "only infinity and files values for depth are supported");
        apr_pool_destroy(temp_pool);
        return NULL;
    } else if (conflict_choice != 0) {
        PyErr_SetString(PyExc_NotImplementedError,
                        "conflict choice not supported with svn < 1.5");
        apr_pool_destroy(temp_pool);
        return NULL;
    } else {
        RUN_SVN_WITH_POOL(temp_pool,
                          svn_wc_resolved_conflict2(path, admobj->adm, resolve_text?TRUE:FALSE,
                                                    resolve_props?TRUE:FALSE,
                                                    (depth == svn_depth_infinity),
                                                    py_wc_notify_func,
                                                    (void *)notify_func, py_cancel_check,
                                                    NULL,
                                                    temp_pool));
    }
#endif

    apr_pool_destroy(temp_pool);

    Py_RETURN_NONE;
}

static PyObject *conflicted(PyObject *self, PyObject *args)
{
    const char *path;
    apr_pool_t *temp_pool;
    PyObject *ret;
    AdmObject *admobj = (AdmObject *)self;
    svn_boolean_t text_conflicted, prop_conflicted, tree_conflicted;
    PyObject *py_path;

    if (!PyArg_ParseTuple(args, "O", &py_path))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

#if ONLY_SINCE_SVN(1, 6)
    RUN_SVN_WITH_POOL(temp_pool, svn_wc_conflicted_p2(&text_conflicted,
                                                      &prop_conflicted, &tree_conflicted, path, admobj->adm, temp_pool));

    ret = Py_BuildValue("(bbb)", text_conflicted, prop_conflicted, tree_conflicted);
#else
    RUN_SVN_WITH_POOL(temp_pool, svn_wc_conflicted_p(&text_conflicted,
                                                     &prop_conflicted, path, admobj->adm, temp_pool));

    ret = Py_BuildValue("(bbO)", text_conflicted, prop_conflicted, Py_None);
#endif

    apr_pool_destroy(temp_pool);

    return ret;
}

/**
 * Determine the status of a file in the specified working copy.
 *
 * :return: A status object.
 */
static PyObject *wc_status(PyObject *self, PyObject *args)
{
    const char *path;
    svn_wc_status2_t *st;
    apr_pool_t *temp_pool;
    PyObject *ret;
    AdmObject *admobj = (AdmObject *)self;
    PyObject *py_path;

    if (!PyArg_ParseTuple(args, "O", &py_path))
        return NULL;

    ADM_CHECK_CLOSED(admobj);

    temp_pool = Pool(NULL);
    if (temp_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_dirent(py_path, temp_pool);
    if (path == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(temp_pool,
                      svn_wc_status2(&st, path, admobj->adm, temp_pool));

    ret = py_wc_status2(st);

    apr_pool_destroy(temp_pool);

    return (PyObject*)ret;
}

static PyMethodDef adm_methods[] = {
    { "prop_set", adm_prop_set, METH_VARARGS, "S.prop_set(name, value, path, skip_checks=False)" },
    { "access_path", (PyCFunction)adm_access_path, METH_NOARGS,
        "S.access_path() -> path\n"
            "Returns the base path for this working copy handle." },
    { "prop_get", adm_prop_get, METH_VARARGS, "S.prop_get(name, path) -> value" },
    { "entries_read", adm_entries_read, METH_VARARGS, "S.entries_read(include_hidden=False) -> dict" },
    { "walk_entries", adm_walk_entries, METH_VARARGS,
        "S.walk_entries(path, callback, show_hidden=False)\n"
            "callback should be a function that takes a path and a wc entry" },
    { "locked", (PyCFunction)adm_locked, METH_NOARGS,
        "S.locked() -> bool" },
    { "get_prop_diffs", adm_get_prop_diffs, METH_VARARGS,
        "S.get_prop_diffs(path) -> (propchanges, originalprops)" },
    { "add", (PyCFunction)adm_add, METH_VARARGS|METH_KEYWORDS, "S.add(path, copyfrom_url=None, copyfrom_rev=-1, notify_func=None)" },
    { "copy", adm_copy, METH_VARARGS, "S.copy(src_path, dest_path, notify_func=None)" },
    { "delete", (PyCFunction)adm_delete, METH_VARARGS|METH_KEYWORDS, "S.delete(path, notify_func=None, keep_local=False)" },
    { "crawl_revisions", (PyCFunction)adm_crawl_revisions, METH_VARARGS|METH_KEYWORDS,
        "S.crawl_revisions(path, reporter, restore_files=True, recurse=True, use_commit_times=True, notify_func=None) -> None" },
    { "get_update_editor", adm_get_update_editor, METH_VARARGS, NULL },
    { "close", (PyCFunction)adm_close, METH_NOARGS,
        "S.close()" },
    { "entry", (PyCFunction)adm_entry, METH_VARARGS,
        "s.entry(path, show_hidden=False) -> entry" },
    { "process_committed", (PyCFunction)adm_process_committed, METH_VARARGS|METH_KEYWORDS, "S.process_committed(path, recurse, new_revnum, rev_date, rev_author, wcprop_changes=None, remove_lock=False, digest=None)" },
    { "process_committed_queue", (PyCFunction)adm_process_committed_queue, METH_VARARGS, "S.process_committed_queue(queue, new_revnum, rev_date, rev_author)" },
    { "remove_lock", (PyCFunction)adm_remove_lock, METH_VARARGS, "S.remove_lock(path)" },
    { "has_binary_prop", (PyCFunction)adm_has_binary_prop, METH_VARARGS, "S.has_binary_prop(path) -> bool" },
    { "text_modified", (PyCFunction)adm_text_modified, METH_VARARGS, "S.text_modified(filename, force_comparison=False) -> bool" },
    { "props_modified", (PyCFunction)adm_props_modified, METH_VARARGS, "S.props_modified(filename) -> bool" },
    { "get_ancestry", (PyCFunction)get_ancestry, METH_VARARGS,
        "S.get_ancestry(path) -> (url, rev)" },
    { "maybe_set_repos_root", (PyCFunction)maybe_set_repos_root, METH_VARARGS, "S.maybe_set_repos_root(path, repos)" },
    { "add_repos_file", (PyCFunction)add_repos_file, METH_KEYWORDS,
        "S.add_repos_file(dst_path, new_base_contents, new_contents, new_base_props, new_props, copyfrom_url=None, copyfrom_rev=-1, notify_func=None)" },
    { "mark_missing_deleted", (PyCFunction)mark_missing_deleted, METH_VARARGS,
        "S.mark_missing_deleted(path)" },
    { "remove_from_revision_control", (PyCFunction)remove_from_revision_control, METH_VARARGS,
        "S.remove_from_revision_control(name, destroy_wf=False, instant_error=False)" },
    { "relocate", (PyCFunction)relocate, METH_VARARGS,
        "S.relocate(path, from, to, recurse=TRUE, validator=None)" },
    { "crop_tree", (PyCFunction)crop_tree, METH_VARARGS,
        "S.crop_tree(target, depth, notify_func=None, cancel=None)" },
    { "translated_stream", (PyCFunction)translated_stream, METH_VARARGS,
        "S.translated_stream(path, versioned_file, flags) -> stream" },
    { "is_wc_root", (PyCFunction)is_wc_root, METH_VARARGS,
        "S.is_wc_root(path) -> wc_root" },
    { "transmit_text_deltas", (PyCFunction)transmit_text_deltas, METH_VARARGS,
        "S.transmit_text_deltas(fulltext, editor) -> (tempfile, digest)" },
    { "transmit_prop_deltas", (PyCFunction)transmit_prop_deltas, METH_VARARGS,
        "S.transmit_prop_deltas(path, entry, editor)" },
    { "probe_retrieve", (PyCFunction)probe_retrieve, METH_VARARGS,
        "S.probe_retrieve(path) -> WorkingCopy" },
    { "retrieve", (PyCFunction)retrieve, METH_VARARGS,
        "S.retrieve(path) -> WorkingCopy" },
    { "probe_try", (PyCFunction)probe_try, METH_VARARGS,
        "S.probe_try(path, write_lock=False, levels_to_lock=-1)" },
    { "conflicted", (PyCFunction)conflicted, METH_VARARGS,
        "S.conflicted(path) -> (text_conflicted, prop_conflicted, tree_conflicted)" },
    { "resolved_conflict", (PyCFunction)resolved_conflict, METH_VARARGS,
        "S.resolved_conflict(path, resolve_text, resolve_props, resolve_tree, depth, conflict_choice, notify_func=None, cancel=None)" },
    { "status", (PyCFunction)wc_status, METH_VARARGS, "status(wc_path) -> Status" },
    { NULL, }
};

PyTypeObject Adm_Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
        "wc.WorkingCopy", /*	const char *tp_name;  For printing, in format "<module>.<name>" */
    sizeof(AdmObject),
    0,/*	Py_ssize_t tp_basicsize, tp_itemsize;  For allocation */

    /* Methods to implement standard operations */

    adm_dealloc, /*	destructor tp_dealloc;	*/
    NULL, /*	printfunc tp_print;	*/
    NULL, /*	getattrfunc tp_getattr;	*/
    NULL, /*	setattrfunc tp_setattr;	*/
    NULL, /*	cmpfunc tp_compare;	*/
    adm_repr, /*	reprfunc tp_repr;	*/

    /* Method suites for standard classes */

    NULL, /*	PyNumberMethods *tp_as_number;	*/
    NULL, /*	PySequenceMethods *tp_as_sequence;	*/
    NULL, /*	PyMappingMethods *tp_as_mapping;	*/

    /* More standard operations (here for binary compatibility) */

    NULL, /*	hashfunc tp_hash;	*/
    NULL, /*	ternaryfunc tp_call;	*/
    adm_repr, /*	reprfunc tp_repr;	*/
    NULL, /*	getattrofunc tp_getattro;	*/
    NULL, /*	setattrofunc tp_setattro;	*/

    /* Functions to access object as input/output buffer */
    NULL, /*	PyBufferProcs *tp_as_buffer;	*/

    /* Flags to define presence of optional/expanded features */
    0, /*	long tp_flags;	*/

    "Local working copy", /*	const char *tp_doc;  Documentation string */

    /* Assigned meaning in release 2.0 */
    /* call function for all accessible objects */
    NULL, /*	traverseproc tp_traverse;	*/

    /* delete references to contained objects */
    NULL, /*	inquiry tp_clear;	*/

    /* Assigned meaning in release 2.1 */
    /* rich comparisons */
    NULL, /*	richcmpfunc tp_richcompare;	*/

    /* weak reference enabler */
    0, /*	Py_ssize_t tp_weaklistoffset;	*/

    /* Added in release 2.2 */
    /* Iterators */
    NULL, /*	getiterfunc tp_iter;	*/
    NULL, /*	iternextfunc tp_iternext;	*/

    /* Attribute descriptor and subclassing stuff */
    adm_methods, /*	struct PyMethodDef *tp_methods;	*/
    NULL, /*	struct PyMemberDef *tp_members;	*/
    NULL, /*	struct PyGetSetDef *tp_getset;	*/
    NULL, /*	struct _typeobject *tp_base;	*/
    NULL, /*	PyObject *tp_dict;	*/
    NULL, /*	descrgetfunc tp_descr_get;	*/
    NULL, /*	descrsetfunc tp_descr_set;	*/
    0, /*	Py_ssize_t tp_dictoffset;	*/
    NULL, /*	initproc tp_init;	*/
    NULL, /*	allocfunc tp_alloc;	*/
    adm_init, /*	newfunc tp_new;	*/
};

static void entry_dealloc(PyObject *self)
{
	apr_pool_destroy(((EntryObject *)self)->pool);
	PyObject_Del(self);
}

static PyMemberDef entry_members[] = {
	{ "name", T_STRING, offsetof(EntryObject, entry.name), READONLY,
		"Name of the file"},
	{ "copyfrom_url", T_STRING, offsetof(EntryObject, entry.copyfrom_url), READONLY,
		"Copyfrom location" },
	{ "copyfrom_rev", T_LONG, offsetof(EntryObject, entry.copyfrom_rev), READONLY,
		"Copyfrom revision" },
	{ "uuid", T_STRING, offsetof(EntryObject, entry.uuid), READONLY,
		"UUID of repository" },
	{ "url", T_STRING, offsetof(EntryObject, entry.url), READONLY,
		"URL in repository" },
	{ "repos", T_STRING, offsetof(EntryObject, entry.repos), READONLY,
		"Canonical repository URL" },
	{ "schedule", T_INT, offsetof(EntryObject, entry.schedule), READONLY,
		"Scheduling (add, replace, delete, etc)" },
	{ "kind", T_INT, offsetof(EntryObject, entry.kind), READONLY,
		"Kind of file (file, dir, etc)" },
	{ "revision", T_LONG, offsetof(EntryObject, entry.revision), READONLY,
		"Base revision", },
	{ "cmt_rev", T_LONG, offsetof(EntryObject, entry.cmt_rev), READONLY,
		"Last revision this was changed" },
	{ "checksum", T_STRING, offsetof(EntryObject, entry.checksum), READONLY,
		"Hex MD5 checksum for the untranslated text base file" },
	{ "cmt_date", T_LONG, offsetof(EntryObject, entry.cmt_date), READONLY,
		"Last date this was changed" },
	{ "cmt_author", T_STRING, offsetof(EntryObject, entry.cmt_author), READONLY,
		"Last commit author of this item" },
	{ NULL, }
};

PyTypeObject Entry_Type = {
	PyVarObject_HEAD_INIT(NULL, 0)
	"wc.Entry", /*	const char *tp_name;  For printing, in format "<module>.<name>" */
	sizeof(EntryObject),
	0,/*	Py_ssize_t tp_basicsize, tp_itemsize;  For allocation */

	/* Methods to implement standard operations */

	entry_dealloc, /*	destructor tp_dealloc;	*/
	NULL, /*	printfunc tp_print;	*/
	NULL, /*	getattrfunc tp_getattr;	*/
	NULL, /*	setattrfunc tp_setattr;	*/
	NULL, /*	cmpfunc tp_compare;	*/
	NULL, /*	reprfunc tp_repr;	*/

	/* Method suites for standard classes */

	NULL, /*	PyNumberMethods *tp_as_number;	*/
	NULL, /*	PySequenceMethods *tp_as_sequence;	*/
	NULL, /*	PyMappingMethods *tp_as_mapping;	*/

	/* More standard operations (here for binary compatibility) */

	NULL, /*	hashfunc tp_hash;	*/
	NULL, /*	ternaryfunc tp_call;	*/
	NULL, /*	reprfunc tp_str;	*/
	NULL, /*	getattrofunc tp_getattro;	*/
	NULL, /*	setattrofunc tp_setattro;	*/

	/* Functions to access object as input/output buffer */
	NULL, /*	PyBufferProcs *tp_as_buffer;	*/

	/* Flags to define presence of optional/expanded features */
	0, /*	long tp_flags;	*/

	NULL, /*	const char *tp_doc;  Documentation string */

	/* Assigned meaning in release 2.0 */
	/* call function for all accessible objects */
	NULL, /*	traverseproc tp_traverse;	*/

	/* delete references to contained objects */
	NULL, /*	inquiry tp_clear;	*/

	/* Assigned meaning in release 2.1 */
	/* rich comparisons */
	NULL, /*	richcmpfunc tp_richcompare;	*/

	/* weak reference enabler */
	0, /*	Py_ssize_t tp_weaklistoffset;	*/

	/* Added in release 2.2 */
	/* Iterators */
	NULL, /*	getiterfunc tp_iter;	*/
	NULL, /*	iternextfunc tp_iternext;	*/

	/* Attribute descriptor and subclassing stuff */
	NULL, /*	struct PyMethodDef *tp_methods;	*/
	entry_members, /*	struct PyMemberDef *tp_members;	*/

};

static PyObject *py_entry(const svn_wc_entry_t *entry)
{
	EntryObject *ret;

	ret = PyObject_New(EntryObject, &Entry_Type);
	if (ret == NULL)
		return NULL;

	ret->pool = Pool(NULL);
	if (ret->pool == NULL)
		return NULL;
	ret->entry = *svn_wc_entry_dup(entry, ret->pool);
	return (PyObject *)ret;
}

typedef struct {
	PyObject_VAR_HEAD
	apr_pool_t *pool;
	svn_wc_status2_t status;
	PyObject *entry;
} StatusObject;

static void status_dealloc(PyObject *self)
{
	apr_pool_destroy(((StatusObject *)self)->pool);
	Py_XDECREF(((StatusObject *)self)->entry);
	PyObject_Del(self);
}

static PyMemberDef status_members[] = {
	{ "entry", T_OBJECT, offsetof(StatusObject, entry), READONLY,
		"Can be NULL if not under version control." },
	{ "locked", T_BOOL, offsetof(StatusObject, status.locked), READONLY,
		"a directory can be 'locked' if a working copy update was interrupted." },
	{ "copied", T_BOOL, offsetof(StatusObject, status.copied), READONLY,
		"a file or directory can be 'copied' if it's scheduled for addition-with-history (or part of a subtree that is scheduled as such.)." },
	{ "switched", T_BOOL, offsetof(StatusObject, status.switched), READONLY,
		"a file or directory can be 'switched' if the switch command has been used." },
	{ "url", T_STRING, offsetof(StatusObject, status.url), READONLY,
		"URL (actual or expected) in repository" },
	{ "revision", T_LONG, offsetof(StatusObject, status.ood_last_cmt_rev), READONLY,
		"Set to the youngest committed revision, or SVN_INVALID_REVNUM if not out of date.", },
	{ "kind", T_INT, offsetof(StatusObject, status.ood_kind), READONLY,
		"Set to the node kind of the youngest commit, or svn_node_none if not out of date.", },
	{ "status", T_INT, offsetof(StatusObject, status.text_status), READONLY,
		"The status of the entry.", },
	{ NULL, }
};

PyTypeObject Status_Type = {
	PyVarObject_HEAD_INIT(NULL, 0)
	"wc.Status", /*	const char *tp_name;  For printing, in format "<module>.<name>" */
	sizeof(StatusObject),
	0,/*	Py_ssize_t tp_basicsize, tp_itemsize;  For allocation */

	/* Methods to implement standard operations */

	status_dealloc, /*	destructor tp_dealloc;	*/
	NULL, /*	printfunc tp_print;	*/
	NULL, /*	getattrfunc tp_getattr;	*/
	NULL, /*	setattrfunc tp_setattr;	*/
	NULL, /*	cmpfunc tp_compare;	*/
	NULL, /*	reprfunc tp_repr;	*/

	/* Method suites for standard classes */

	NULL, /*	PyNumberMethods *tp_as_number;	*/
	NULL, /*	PySequenceMethods *tp_as_sequence;	*/
	NULL, /*	PyMappingMethods *tp_as_mapping;	*/

	/* More standard operations (here for binary compatibility) */

	NULL, /*	hashfunc tp_hash;	*/
	NULL, /*	ternaryfunc tp_call;	*/
	NULL, /*	reprfunc tp_str;	*/
	NULL, /*	getattrofunc tp_getattro;	*/
	NULL, /*	setattrofunc tp_setattro;	*/

	/* Functions to access object as input/output buffer */
	NULL, /*	PyBufferProcs *tp_as_buffer;	*/

	/* Flags to define presence of optional/expanded features */
	0, /*	long tp_flags;	*/

	"Working copy status object", /*	const char *tp_doc;  Documentation string */

	/* Assigned meaning in release 2.0 */
	/* call function for all accessible objects */
	NULL, /*	traverseproc tp_traverse;	*/

	/* delete references to contained objects */
	NULL, /*	inquiry tp_clear;	*/

	/* Assigned meaning in release 2.1 */
	/* rich comparisons */
	NULL, /*	richcmpfunc tp_richcompare;	*/

	/* weak reference enabler */
	0, /*	Py_ssize_t tp_weaklistoffset;	*/

	/* Added in release 2.2 */
	/* Iterators */
	NULL, /*	getiterfunc tp_iter;	*/
	NULL, /*	iternextfunc tp_iternext;	*/

	/* Attribute descriptor and subclassing stuff */
	NULL, /*	struct PyMethodDef *tp_methods;	*/
	status_members, /*	struct PyMemberDef *tp_members;	*/

};

PyObject *py_wc_status2(const svn_wc_status2_t *status)
{
	StatusObject *ret;
	svn_wc_status2_t *dup_status;

	ret = PyObject_New(StatusObject, &Status_Type);
	if (ret == NULL)
		return NULL;

	ret->pool = Pool(NULL);
	if (ret->pool == NULL) {
		PyObject_Del(ret);
		return NULL;
	}

	dup_status = svn_wc_dup_status2(status, ret->pool);
	if (dup_status == NULL)
	{
		PyErr_NoMemory();
		return NULL;
	}
	ret->status = *dup_status;

	ret->entry = py_entry(ret->status.entry);
	return (PyObject *)ret;
}

static svn_error_t *py_wc_found_entry(const char *path, const svn_wc_entry_t *entry, void *walk_baton, apr_pool_t *pool)
{
	PyObject *fn, *ret;
	PyObject *callbacks = (PyObject *)walk_baton;
	PyGILState_STATE state = PyGILState_Ensure();
	if (PyTuple_Check(callbacks)) {
		fn = PyTuple_GET_ITEM(callbacks, 0);
	} else {
		fn = (PyObject *)walk_baton;
	}
	ret = PyObject_CallFunction(fn, "sO", path, py_entry(entry));
	CB_CHECK_PYRETVAL(ret);
	Py_DECREF(ret);
	PyGILState_Release(state);
	return NULL;
}

#if ONLY_SINCE_SVN(1, 5)

svn_error_t *py_wc_handle_error(const char *path, svn_error_t *err, void *walk_baton, apr_pool_t *pool)
{
	PyObject *fn, *ret;
	PyObject *py_err;
	PyGILState_STATE state;
	PyObject *callbacks = (PyObject *)walk_baton;
	if (PyTuple_Check(callbacks)) {
		fn = PyTuple_GET_ITEM(callbacks, 1);
	} else {
		return err;
	}
	state = PyGILState_Ensure();
	py_err = PyErr_NewSubversionException(err);
	ret = PyObject_CallFunction(fn, "sO", path, py_err);
	CB_CHECK_PYRETVAL(ret);
	Py_DECREF(ret);
	PyGILState_Release(state);
	Py_DECREF(py_err);
	return NULL;
}

static svn_wc_entry_callbacks2_t py_wc_entry_callbacks2 = {
	py_wc_found_entry,
	py_wc_handle_error,
};
#else
static svn_wc_entry_callbacks_t py_wc_entry_callbacks = {
	py_wc_found_entry
};
#endif

#pragma GCC diagnostic pop
