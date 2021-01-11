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
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <apr_general.h>
#include <svn_wc.h>
#include <svn_path.h>
#include <svn_props.h>
#include <structmember.h>
#include <stdbool.h>
#include <apr_md5.h>
#include <apr_sha1.h>
#include <fcntl.h>

#include "util.h"
#include "editor.h"
#include "wc.h"

#ifndef T_BOOL
#define T_BOOL T_BYTE
#endif

typedef struct {
    PyObject_HEAD
    svn_lock_t lock;
    apr_pool_t *pool;
} LockObject;

typedef struct {
    PyObject_VAR_HEAD
    apr_pool_t *pool;
    svn_wc_context_t *context;
} ContextObject;
static PyTypeObject Context_Type;

typedef struct {
    PyObject_VAR_HEAD
    apr_pool_t *pool;
    svn_wc_committed_queue_t *queue;
} CommittedQueueObject;

extern PyTypeObject Lock_Type;

svn_wc_committed_queue_t *PyObject_GetCommittedQueue(PyObject *obj)
{
    return ((CommittedQueueObject *)obj)->queue;
}

static svn_error_t *py_ra_report3_set_path(void *baton, const char *path,
                                           svn_revnum_t revision,
                                           svn_depth_t depth, int start_empty,
                                           const char *lock_token, apr_pool_t *pool)
{
    PyObject *self = (PyObject *)baton, *py_lock_token, *ret;
    PyGILState_STATE state = PyGILState_Ensure();
    if (lock_token == NULL) {
        py_lock_token = Py_None;
        Py_INCREF(py_lock_token);
    } else {
        py_lock_token = PyBytes_FromString(lock_token);
    }
    ret = PyObject_CallMethod(self, "set_path", "slbOi", path, revision,
                              start_empty, py_lock_token, depth);
    Py_DECREF(py_lock_token);
    CB_CHECK_PYRETVAL(ret);
    Py_DECREF(ret);
    PyGILState_Release(state);
    return NULL;
}

static svn_error_t *py_ra_report3_link_path(void *report_baton,
                                            const char *path, const char *url,
                                            svn_revnum_t revision,
                                            svn_depth_t depth, int start_empty,
                                            const char *lock_token, apr_pool_t *pool)
{
    PyObject *self = (PyObject *)report_baton, *ret, *py_lock_token;
    PyGILState_STATE state = PyGILState_Ensure();
    if (lock_token == NULL) {
        py_lock_token = Py_None;
        Py_INCREF(py_lock_token);
    } else {
        py_lock_token = PyBytes_FromString(lock_token);
    }
    ret = PyObject_CallMethod(self, "link_path", "sslbOi", path, url, revision,
                              start_empty, py_lock_token, depth);
    Py_DECREF(py_lock_token);
    CB_CHECK_PYRETVAL(ret);
    Py_DECREF(ret);
    PyGILState_Release(state);
    return NULL;
}

static svn_error_t *py_ra_report2_set_path(void *baton, const char *path,
                                           svn_revnum_t revision,
                                           int start_empty, const char *lock_token,
                                           apr_pool_t *pool)
{
    PyObject *self = (PyObject *)baton, *py_lock_token, *ret;
    PyGILState_STATE state = PyGILState_Ensure();
    if (lock_token == NULL) {
        py_lock_token = Py_None;
        Py_INCREF(py_lock_token);
    } else {
        py_lock_token = PyBytes_FromString(lock_token);
    }
    ret = PyObject_CallMethod(self, "set_path", "slbOi", path, revision,
                              start_empty, py_lock_token, svn_depth_infinity);
    CB_CHECK_PYRETVAL(ret);
    Py_DECREF(ret);
    PyGILState_Release(state);
    return NULL;
}

static svn_error_t *py_ra_report2_link_path(void *report_baton,
                                            const char *path, const char *url,
                                            svn_revnum_t revision,
                                            int start_empty,
                                            const char *lock_token,
                                            apr_pool_t *pool)
{
    PyObject *self = (PyObject *)report_baton, *ret, *py_lock_token;
    PyGILState_STATE state = PyGILState_Ensure();
    if (lock_token == NULL) {
        py_lock_token = Py_None;
        Py_INCREF(py_lock_token);
    } else {
        py_lock_token = PyBytes_FromString(lock_token);
    }
    ret = PyObject_CallMethod(self, "link_path", "sslbOi", path, url, revision,
                              start_empty, py_lock_token, svn_depth_infinity);
    CB_CHECK_PYRETVAL(ret);
    Py_DECREF(ret);
    PyGILState_Release(state);
    return NULL;
}

static svn_error_t *py_ra_report_delete_path(void *baton, const char *path,
                                             apr_pool_t *pool)
{
    PyObject *self = (PyObject *)baton, *ret;
    PyGILState_STATE state = PyGILState_Ensure();
    ret = PyObject_CallMethod(self, "delete_path", "s", path);
    CB_CHECK_PYRETVAL(ret);
    Py_DECREF(ret);
    PyGILState_Release(state);
    return NULL;
}

static svn_error_t *py_ra_report_finish(void *baton, apr_pool_t *pool)
{
    PyObject *self = (PyObject *)baton, *ret;
    PyGILState_STATE state = PyGILState_Ensure();
    ret = PyObject_CallMethod(self, "finish", "");
    CB_CHECK_PYRETVAL(ret);
    Py_DECREF(ret);
    PyGILState_Release(state);
    return NULL;
}

static svn_error_t *py_ra_report_abort(void *baton, apr_pool_t *pool)
{
    PyObject *self = (PyObject *)baton, *ret;
    PyGILState_STATE state = PyGILState_Ensure();
    ret = PyObject_CallMethod(self, "abort", "");
    CB_CHECK_PYRETVAL(ret);
    Py_DECREF(ret);
    PyGILState_Release(state);
    return NULL;
}

const svn_ra_reporter3_t py_ra_reporter3 = {
    py_ra_report3_set_path,
    py_ra_report_delete_path,
    py_ra_report3_link_path,
    py_ra_report_finish,
    py_ra_report_abort,
};

const svn_ra_reporter2_t py_ra_reporter2 = {
    py_ra_report2_set_path,
    py_ra_report_delete_path,
    py_ra_report2_link_path,
    py_ra_report_finish,
    py_ra_report_abort,
};


/**
 * Get runtime libsvn_wc version information.
 *
 * :return: tuple with major, minor, patch version number and tag.
 */
static PyObject *version(PyObject *self)
{
	const svn_version_t *ver = svn_wc_version();
	return Py_BuildValue("(iiis)", ver->major, ver->minor,
						 ver->patch, ver->tag);
}

SVN_VERSION_DEFINE(svn_api_version);

/**
 * Get compile-time libsvn_wc version information.
 *
 * :return: tuple with major, minor, patch version number and tag.
 */
static PyObject *api_version(PyObject *self)
{
	const svn_version_t *ver = &svn_api_version;
	return Py_BuildValue("(iiis)", ver->major, ver->minor,
						 ver->patch, ver->tag);
}


void py_wc_notify_func(void *baton, const svn_wc_notify_t *notify, apr_pool_t *pool)
{
	PyObject *func = baton, *ret;
	if (func == Py_None)
		return;

	if (notify->err != NULL) {
        PyGILState_STATE state = PyGILState_Ensure();
		PyObject *excval = PyErr_NewSubversionException(notify->err);
		ret = PyObject_CallFunction(func, "O", excval);
		Py_DECREF(excval);
		Py_XDECREF(ret);
		/* If ret was NULL, the cancel func should abort the operation. */
        PyGILState_Release(state);
	}
}
bool py_dict_to_wcprop_changes(PyObject *dict, apr_pool_t *pool, apr_array_header_t **ret)
{
	PyObject *key, *val;
	Py_ssize_t idx;

	if (dict == Py_None) {
		*ret = NULL;
		return true;
	}

	if (!PyDict_Check(dict)) {
		PyErr_SetString(PyExc_TypeError, "Expected dictionary with property changes");
		return false;
	}

	*ret = apr_array_make(pool, PyDict_Size(dict), sizeof(char *));

	while (PyDict_Next(dict, &idx, &key, &val)) {
		svn_prop_t *prop = apr_palloc(pool, sizeof(svn_prop_t));
		prop->name = py_object_to_svn_string(key, pool);
		if (prop->name == NULL) {
			return false;
		}
		if (val == Py_None) {
			prop->value = NULL;
		} else {
			if (!PyBytes_Check(val)) {
				PyErr_SetString(PyExc_TypeError, "property values should be bytes");
				return false;
			}
			prop->value = svn_string_ncreate(PyBytes_AsString(val), PyBytes_Size(val), pool);
		}
		APR_ARRAY_PUSH(*ret, svn_prop_t *) = prop;
	}

	return true;
}

svn_error_t *wc_validator3(void *baton, const char *uuid, const char *url, const char *root_url, apr_pool_t *pool)
{
	PyObject *py_validator = baton, *ret;
    PyGILState_STATE state;

	if (py_validator == Py_None) {
		return NULL;
	}
    state = PyGILState_Ensure();
	ret = PyObject_CallFunction(py_validator, "sss", uuid, url, root_url);
	if (ret == NULL) {
        PyGILState_Release(state);
		return py_svn_error();
	}

	Py_DECREF(ret);

    PyGILState_Release(state);
	return NULL;
}

svn_error_t *wc_validator2(void *baton, const char *uuid, const char *url, svn_boolean_t root, apr_pool_t *pool)
{
	PyObject *py_validator = baton, *ret;
    PyGILState_STATE state;

	if (py_validator == Py_None) {
		return NULL;
	}

    state = PyGILState_Ensure();
	ret = PyObject_CallFunction(py_validator, "ssO", uuid, url, Py_None);
	if (ret == NULL) {
        PyGILState_Release(state);
		return py_svn_error();
	}

	Py_DECREF(ret);
    PyGILState_Release(state);

	return NULL;
}

static PyObject *get_actual_target(PyObject *self, PyObject *args)
{
	const char *path;
	const char *anchor = NULL, *target = NULL;
	apr_pool_t *temp_pool;
	PyObject *ret, *py_path;

	if (!PyArg_ParseTuple(args, "O", &py_path))
		return NULL;

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
		  svn_wc_get_actual_target(path,
								   &anchor, &target, temp_pool));

	ret = Py_BuildValue("(ss)", anchor, target);

	apr_pool_destroy(temp_pool);

	return ret;
}

/**
 * Determine the revision status of a specified working copy.
 *
 * :return: Tuple with minimum and maximum revnums found, whether the
 * working copy was switched and whether it was modified.
 */
static PyObject *revision_status(PyObject *self, PyObject *args, PyObject *kwargs)
{
	char *kwnames[] = { "wc_path", "trail_url", "committed",  NULL };
	const char *wc_path;
	char *trail_url=NULL;
	bool committed=false;
	PyObject *ret, *py_wc_path;
	svn_wc_revision_status_t *revstatus;
	apr_pool_t *temp_pool;

	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|zb", kwnames, &py_wc_path,
									 &trail_url, &committed))
		return NULL;

	temp_pool = Pool(NULL);
	if (temp_pool == NULL) {
		return NULL;
	}

	wc_path = py_object_to_svn_dirent(py_wc_path, temp_pool);
	if (wc_path == NULL) {
		apr_pool_destroy(temp_pool);
		return NULL;
	}
	RUN_SVN_WITH_POOL(temp_pool,
			svn_wc_revision_status(
				&revstatus, wc_path, trail_url,
				 committed, py_cancel_check, NULL, temp_pool));
	ret = Py_BuildValue("(llbb)", revstatus->min_rev, revstatus->max_rev,
			revstatus->switched, revstatus->modified);
	apr_pool_destroy(temp_pool);
	return ret;
}

static PyObject *is_normal_prop(PyObject *self, PyObject *args)
{
	char *name;

	if (!PyArg_ParseTuple(args, "s", &name))
		return NULL;

	return PyBool_FromLong(svn_wc_is_normal_prop(name));
}

static PyObject *is_adm_dir(PyObject *self, PyObject *args)
{
	const char *name;
    PyObject *py_name;
	apr_pool_t *pool;
	svn_boolean_t ret;

	if (!PyArg_ParseTuple(args, "O", &py_name))
		return NULL;

	pool = Pool(NULL);
	if (pool == NULL)
		return NULL;

    name = py_object_to_svn_string(py_name, pool);
    if (name == NULL) {
        return NULL;
    }

	ret = svn_wc_is_adm_dir(name, pool);

	apr_pool_destroy(pool);

	return PyBool_FromLong(ret);
}

static PyObject *is_wc_prop(PyObject *self, PyObject *args)
{
	char *name;

	if (!PyArg_ParseTuple(args, "s", &name))
		return NULL;

	return PyBool_FromLong(svn_wc_is_wc_prop(name));
}

static PyObject *is_entry_prop(PyObject *self, PyObject *args)
{
	char *name;

	if (!PyArg_ParseTuple(args, "s", &name))
		return NULL;

	return PyBool_FromLong(svn_wc_is_entry_prop(name));
}

static PyObject *get_adm_dir(PyObject *self)
{
	apr_pool_t *pool;
	PyObject *ret;
	const char *dir;
	pool = Pool(NULL);
	if (pool == NULL)
		return NULL;
	dir = svn_wc_get_adm_dir(pool);
	ret = py_object_from_svn_abspath(dir);
	apr_pool_destroy(pool);
	return ret;
}

static PyObject *set_adm_dir(PyObject *self, PyObject *args)
{
	apr_pool_t *temp_pool;
	char *name;
	PyObject *py_name;

	if (!PyArg_ParseTuple(args, "O", &py_name))
		return NULL;

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	name = py_object_to_svn_string(py_name, temp_pool);
	if (name == NULL) {
		apr_pool_destroy(temp_pool);
		return NULL;
	}
	RUN_SVN_WITH_POOL(temp_pool, svn_wc_set_adm_dir(name, temp_pool));
	apr_pool_destroy(temp_pool);
	Py_RETURN_NONE;
}

static PyObject *get_pristine_copy_path(PyObject *self, PyObject *args)
{
	apr_pool_t *pool;
	const char *pristine_path;
	const char *path;
	PyObject *py_path;
	PyObject *ret;

	if (!PyArg_ParseTuple(args, "O", &py_path))
		return NULL;

	pool = Pool(NULL);
	if (pool == NULL)
		return NULL;

	path = py_object_to_svn_abspath(py_path, pool);
	if (path == NULL) {
		apr_pool_destroy(pool);
		return NULL;
	}

	PyErr_WarnEx(PyExc_DeprecationWarning, "get_pristine_copy_path is deprecated. Use get_pristine_contents instead.", 2);
	RUN_SVN_WITH_POOL(pool,
		  svn_wc_get_pristine_copy_path(path,
										&pristine_path, pool));
	ret = py_object_from_svn_abspath(pristine_path);
	apr_pool_destroy(pool);
	return ret;
}

static PyObject *get_pristine_contents(PyObject *self, PyObject *args)
{
	const char *path;
	apr_pool_t *temp_pool;
	PyObject *py_path;
	StreamObject *ret;
	apr_pool_t *stream_pool;
	svn_stream_t *stream;

	if (!PyArg_ParseTuple(args, "O", &py_path))
		return NULL;

	stream_pool = Pool(NULL);
	if (stream_pool == NULL)
		return NULL;

	temp_pool = Pool(stream_pool);
	if (temp_pool == NULL) {
		apr_pool_destroy(stream_pool);
		return NULL;
	}

	path = py_object_to_svn_abspath(py_path, temp_pool);
	if (path == NULL) {
		apr_pool_destroy(temp_pool);
		return NULL;
	}

	RUN_SVN_WITH_POOL(stream_pool, svn_wc_get_pristine_contents(&stream, path, stream_pool, temp_pool));
	apr_pool_destroy(temp_pool);

	if (stream == NULL) {
		apr_pool_destroy(stream_pool);
		Py_RETURN_NONE;
	}

	ret = PyObject_New(StreamObject, &Stream_Type);
	if (ret == NULL)
		return NULL;

	ret->pool = stream_pool;
	ret->closed = FALSE;
	ret->stream = stream;

	return (PyObject *)ret;
}

static PyObject *ensure_adm(PyObject *self, PyObject *args, PyObject *kwargs)
{
	const char *path;
	char *uuid, *url = NULL;
	PyObject *py_path;
	char *repos = NULL;
	long rev = -1;
	apr_pool_t *pool;
	char *kwnames[] = { "path", "uuid", "url", "repos", "rev", "depth", NULL };
	int depth = svn_depth_infinity;

	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "Oss|sli", kwnames,
									 &py_path, &uuid, &url, &repos, &rev, &depth))
		return NULL;

	pool = Pool(NULL);
	if (pool == NULL) {
		return NULL;
	}

	path = py_object_to_svn_dirent(py_path, pool);
	if (path == NULL) {
		apr_pool_destroy(pool);
		return NULL;
	}

	RUN_SVN_WITH_POOL(pool,
					  svn_wc_ensure_adm3(path,
										 uuid, url, repos, rev, depth, pool));
	apr_pool_destroy(pool);
	Py_RETURN_NONE;
}

static PyObject *check_wc(PyObject *self, PyObject *args)
{
	const char *path;
	apr_pool_t *pool;
	int wc_format;
	PyObject *py_path;

	if (!PyArg_ParseTuple(args, "O", &py_path))
		return NULL;

	pool = Pool(NULL);
	if (pool == NULL) {
		return NULL;
	}

	path = py_object_to_svn_dirent(py_path, pool);
	if (path == NULL) {
		apr_pool_destroy(pool);
		return NULL;
	}

	RUN_SVN_WITH_POOL(pool, svn_wc_check_wc(path, &wc_format, pool));
	apr_pool_destroy(pool);
	return PyLong_FromLong(wc_format);
}

static PyObject *cleanup_wc(PyObject *self, PyObject *args, PyObject *kwargs)
{
	const char *path;
	char *diff3_cmd = NULL;
	char *kwnames[] = { "path", "diff3_cmd", NULL };
	apr_pool_t *temp_pool;
	PyObject *py_path;

	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|z", kwnames,
									 &py_path, &diff3_cmd))
		return NULL;

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
				svn_wc_cleanup2(path, diff3_cmd, py_cancel_check, NULL,
								temp_pool));

	apr_pool_destroy(temp_pool);

	Py_RETURN_NONE;
}

static PyObject *match_ignore_list(PyObject *self, PyObject *args)
{
	char *str;
	PyObject *py_list;
	apr_array_header_t *list;
	apr_pool_t *temp_pool;
	svn_boolean_t ret;

	if (!PyArg_ParseTuple(args, "sO", &str, &py_list))
		return NULL;

	temp_pool = Pool(NULL);

	if (!string_list_to_apr_array(temp_pool, py_list, &list)) {
		apr_pool_destroy(temp_pool);
		return NULL;
	}

	ret = svn_wc_match_ignore_list(str, list, temp_pool);

	apr_pool_destroy(temp_pool);

	return PyBool_FromLong(ret);
}

static PyMethodDef wc_methods[] = {
    { "check_wc", check_wc, METH_VARARGS, "check_wc(path) -> version\n"
        "Check whether path contains a Subversion working copy\n"
            "return the workdir version"},
    { "cleanup", (PyCFunction)cleanup_wc,
        METH_VARARGS|METH_KEYWORDS, "cleanup(path, diff3_cmd=None)\n" },
    { "ensure_adm", (PyCFunction)ensure_adm, METH_KEYWORDS|METH_VARARGS,
        "ensure_adm(path, uuid, url, repos=None, rev=None)" },
    { "get_adm_dir", (PyCFunction)get_adm_dir, METH_NOARGS,
        "get_adm_dir() -> name" },
    { "set_adm_dir", (PyCFunction)set_adm_dir, METH_VARARGS,
        "set_adm_dir(name)" },
    { "get_pristine_copy_path", get_pristine_copy_path, METH_VARARGS,
        "get_pristine_copy_path(path) -> path" },
    { "get_pristine_contents", get_pristine_contents, METH_VARARGS,
        "get_pristine_contents(path) -> stream" },
    { "is_adm_dir", is_adm_dir, METH_VARARGS,
        "is_adm_dir(name) -> bool" },
    { "is_normal_prop", is_normal_prop, METH_VARARGS,
        "is_normal_prop(name) -> bool" },
    { "is_entry_prop", is_entry_prop, METH_VARARGS,
        "is_entry_prop(name) -> bool" },
    { "is_wc_prop", is_wc_prop, METH_VARARGS,
        "is_wc_prop(name) -> bool" },
    { "revision_status", (PyCFunction)revision_status,
        METH_KEYWORDS|METH_VARARGS,
        "revision_status(wc_path, trail_url=None, committed=False)"
            "-> (min_rev, max_rev, switched, modified)" },
    { "version", (PyCFunction)version, METH_NOARGS,
        "version() -> (major, minor, patch, tag)\n\n"
            "Version of libsvn_wc currently used."
    },
    { "api_version", (PyCFunction)api_version, METH_NOARGS,
        "api_version() -> (major, minor, patch, tag)\n\n"
            "Version of libsvn_wc Subvertpy was compiled against." },
    { "match_ignore_list", (PyCFunction)match_ignore_list, METH_VARARGS,
        "match_ignore_list(str, patterns) -> bool" },
    { "get_actual_target", (PyCFunction)get_actual_target, METH_VARARGS,
        "get_actual_target(path) -> (anchor, target)" },
    { NULL, }
};

static void committed_queue_dealloc(PyObject *self)
{
	apr_pool_destroy(((CommittedQueueObject *)self)->pool);
	PyObject_Del(self);
}

static PyObject *committed_queue_repr(PyObject *self)
{
	CommittedQueueObject *cqobj = (CommittedQueueObject *)self;

	return PyRepr_FromFormat("<wc.CommittedQueue at 0x%p>", cqobj->queue);
}

static PyObject *committed_queue_init(PyTypeObject *self, PyObject *args, PyObject *kwargs)
{
	CommittedQueueObject *ret;
	char *kwnames[] = { NULL };

	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "", kwnames))
		return NULL;

	ret = PyObject_New(CommittedQueueObject, &CommittedQueue_Type);
	if (ret == NULL)
		return NULL;

	ret->pool = Pool(NULL);
	if (ret->pool == NULL)
		return NULL;
	ret->queue = svn_wc_committed_queue_create(ret->pool);
	if (ret->queue == NULL) {
		PyObject_Del(ret);
		PyErr_NoMemory();
		return NULL;
	}

	return (PyObject *)ret;
}

static PyObject *committed_queue_queue(CommittedQueueObject *self, PyObject *args, PyObject *kwargs)
{
	const char *path;
	PyObject *admobj;
	PyObject *py_wcprop_changes = Py_None, *py_path;
    svn_wc_adm_access_t *adm = NULL;
	bool remove_lock = false, remove_changelist = false;
	char *md5_digest = NULL, *sha1_digest = NULL;
	bool recurse = false;
	apr_array_header_t *wcprop_changes;
	Py_ssize_t md5_digest_len, sha1_digest_len;
	svn_wc_context_t *context = NULL;
	char *kwnames[] = { "path", "adm", "recurse", "wcprop_changes", "remove_lock", "remove_changelist", "md5_digest", "sha1_digest", NULL };

	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO|bObbz#z#", kwnames,
									 &py_path, &admobj,
						  &recurse, &py_wcprop_changes, &remove_lock,
						  &remove_changelist, &md5_digest, &md5_digest_len,
						  &sha1_digest, &sha1_digest_len))
		return NULL;

	if (!py_dict_to_wcprop_changes(py_wcprop_changes, self->pool, &wcprop_changes)) {
		return NULL;
	}

	path = py_object_to_svn_abspath(py_path, self->pool);
	if (path == NULL) {
		return NULL;
	}

	if (md5_digest != NULL) {
		if (md5_digest_len != APR_MD5_DIGESTSIZE) {
			PyErr_SetString(PyExc_ValueError, "Invalid size for md5 digest");
			return NULL;
		}
	}

	if (sha1_digest != NULL) {
		if (sha1_digest_len != APR_SHA1_DIGESTSIZE) {
			PyErr_SetString(PyExc_ValueError, "Invalid size for sha1 digest");
			return NULL;
		}
	}

	if (PyObject_IsInstance(admobj, (PyObject *)&Context_Type)) {
		context = ((ContextObject*)admobj)->context;
	} else {
		PyErr_SetString(PyExc_TypeError, "Second arguments needs to be Context");
		return NULL;
	}

	if (adm != NULL) {
	{
	svn_checksum_t *svn_checksum_p;

	if (md5_digest != NULL) {
		svn_checksum_p  = apr_palloc(self->pool, sizeof(svn_checksum_t));
        svn_checksum_p->digest = apr_pmemdup(
            self->pool, (unsigned char *)md5_digest, APR_MD5_DIGESTSIZE);
		svn_checksum_p->kind = svn_checksum_md5;
	} else {
		svn_checksum_p = NULL;
	}
	RUN_SVN(
		svn_wc_queue_committed2(self->queue, path, adm, recurse?TRUE:FALSE,
							   wcprop_changes, remove_lock?TRUE:FALSE, remove_changelist?TRUE:FALSE,
							   svn_checksum_p, self->pool));
	}
	} else {
		svn_checksum_t *svn_checksum_p;

		if (sha1_digest != NULL) {
			svn_checksum_p  = apr_palloc(self->pool, sizeof(svn_checksum_t));
			svn_checksum_p->digest = apr_pmemdup(
				self->pool, (unsigned char *)sha1_digest, APR_SHA1_DIGESTSIZE);
			svn_checksum_p->kind = svn_checksum_sha1;
		} else {
			svn_checksum_p = NULL;
		}
		RUN_SVN(
			svn_wc_queue_committed3(self->queue, context, path, recurse?TRUE:FALSE,
								   wcprop_changes, remove_lock?TRUE:FALSE, remove_changelist?TRUE:FALSE,
								   svn_checksum_p, self->pool));
	}

	Py_RETURN_NONE;
}

static PyMethodDef committed_queue_methods[] = {
	{ "queue", (PyCFunction)committed_queue_queue, METH_VARARGS|METH_KEYWORDS,
		"S.queue(path, adm, recurse=False, wcprop_changes=[], remove_lock=False, remove_changelist=False, digest=None)" },
	{ NULL }
};

PyTypeObject CommittedQueue_Type = {
	PyVarObject_HEAD_INIT(NULL, 0)
	"wc.CommittedQueue", /*	const char *tp_name;  For printing, in format "<module>.<name>" */
	sizeof(CommittedQueueObject),
	0,/*	Py_ssize_t tp_basicsize, tp_itemsize;  For allocation */

	/* Methods to implement standard operations */

	committed_queue_dealloc, /*	destructor tp_dealloc;	*/
	NULL, /*	printfunc tp_print;	*/
	NULL, /*	getattrfunc tp_getattr;	*/
	NULL, /*	setattrfunc tp_setattr;	*/
	NULL, /*	cmpfunc tp_compare;	*/
	committed_queue_repr, /*	reprfunc tp_repr;	*/

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

	"Committed queue", /*	const char *tp_doc;  Documentation string */

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
	committed_queue_methods, /*	struct PyMethodDef *tp_methods;	*/
	NULL, /*	struct PyMemberDef *tp_members;	*/
	NULL, /*	struct PyGetSetDef *tp_getset;	*/
	NULL, /*	struct _typeobject *tp_base;	*/
	NULL, /*	PyObject *tp_dict;	*/
	NULL, /*	descrgetfunc tp_descr_get;	*/
	NULL, /*	descrsetfunc tp_descr_set;	*/
	0, /*	Py_ssize_t tp_dictoffset;	*/
	NULL, /*	initproc tp_init;	*/
	NULL, /*	allocfunc tp_alloc;	*/
	committed_queue_init, /*	newfunc tp_new;	*/
};

svn_lock_t *py_object_to_svn_lock(PyObject *py_lock, apr_pool_t *pool)
{
	LockObject* lockobj = (LockObject *)py_lock;
    if (!PyObject_IsInstance(py_lock, (PyObject *)&Lock_Type)) {
        PyErr_SetString(PyExc_TypeError, "Expected Lock object");
        return NULL;
    }
	return &lockobj->lock;
}

static PyTypeObject Context_Type;

static PyObject *py_wc_context_locked(PyObject *self, PyObject *args)
{
    PyObject* py_path;
    const char *path;
    apr_pool_t *pool;
    svn_wc_context_t *wc_context = ((ContextObject *)self)->context;
    svn_boolean_t locked_here, locked;

    if (!PyArg_ParseTuple(args, "O", &py_path))
        return NULL;

    pool = Pool(NULL);

    path = py_object_to_svn_abspath(py_path, pool);
    if (path == NULL) {
        apr_pool_destroy(pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(pool, svn_wc_locked2(&locked_here, &locked, wc_context, path, pool));

    apr_pool_destroy(pool);

    return Py_BuildValue("(bb)", locked_here?true:false, locked?true:false);
}

static PyObject *py_wc_context_check_wc(PyObject *self, PyObject *args)
{
    PyObject* py_path;
    const char *path;
    apr_pool_t *pool;
    svn_wc_context_t *wc_context = ((ContextObject *)self)->context;
    int wc_format;

    if (!PyArg_ParseTuple(args, "O", &py_path))
        return NULL;

    pool = Pool(NULL);

    path = py_object_to_svn_abspath(py_path, pool);
    if (path == NULL) {
        apr_pool_destroy(pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(pool, svn_wc_check_wc2(&wc_format, wc_context, path, pool));

    apr_pool_destroy(pool);

#if PY_MAJOR_VERSION >= 3
    return PyLong_FromLong(wc_format);
#else
    return PyInt_FromLong(wc_format);
#endif
}

static PyObject *py_wc_context_text_modified_p2(PyObject *self, PyObject *args)
{
    PyObject* py_path;
    const char *path;
    apr_pool_t *pool;
    svn_wc_context_t *wc_context = ((ContextObject *)self)->context;
    svn_boolean_t modified;

    if (!PyArg_ParseTuple(args, "O", &py_path))
        return NULL;

    pool = Pool(NULL);

    path = py_object_to_svn_abspath(py_path, pool);
    if (path == NULL) {
        apr_pool_destroy(pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(pool, svn_wc_text_modified_p2(&modified, wc_context,
                                                    path, FALSE, pool));

    apr_pool_destroy(pool);

    return PyBool_FromLong(modified);
}

static PyObject *py_wc_context_props_modified_p2(PyObject *self, PyObject *args)
{
    PyObject* py_path;
    const char *path;
    apr_pool_t *pool;
    svn_wc_context_t *wc_context = ((ContextObject *)self)->context;
    svn_boolean_t modified;

    if (!PyArg_ParseTuple(args, "O", &py_path))
        return NULL;

    pool = Pool(NULL);

    path = py_object_to_svn_abspath(py_path, pool);
    if (path == NULL) {
        apr_pool_destroy(pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(pool, svn_wc_props_modified_p2(&modified, wc_context,
                                                    path, pool));

    apr_pool_destroy(pool);

    return PyBool_FromLong(modified);
}

static PyObject *py_wc_context_conflicted(PyObject *self, PyObject *args)
{
    PyObject* py_path;
    const char *path;
    apr_pool_t *pool;
    svn_wc_context_t *wc_context = ((ContextObject *)self)->context;
    svn_boolean_t text_conflicted, props_conflicted, tree_conflicted;

    if (!PyArg_ParseTuple(args, "O", &py_path))
        return NULL;

    pool = Pool(NULL);

    path = py_object_to_svn_abspath(py_path, pool);
    if (path == NULL) {
        apr_pool_destroy(pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(pool, svn_wc_conflicted_p3(
         &text_conflicted, &props_conflicted, &tree_conflicted, wc_context,
         path, pool));

    apr_pool_destroy(pool);

    return Py_BuildValue("(bbb)", text_conflicted, props_conflicted, tree_conflicted);
}

static PyObject *py_wc_context_crawl_revisions(PyObject *self, PyObject *args, PyObject *kwargs)
{
    PyObject* py_path, *py_reporter;
    const char *path;
    apr_pool_t *pool;
    svn_wc_context_t *wc_context = ((ContextObject *)self)->context;
    char *kwnames[] = { "path", "reporter", "restore_files", "depth",
        "honor_depth_exclude", "depth_compatibility_trick", "use_commit_times",
        "cancel", "notify", NULL };
    bool restore_files = false;
    int depth = svn_depth_infinity;
    bool honor_depth_exclude = true;
    bool depth_compatibility_trick = false;
    bool use_commit_times = false;
    PyObject *notify = Py_None;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO|bibbbOO", kwnames,
                                     &py_path, &py_reporter, &restore_files,
                                     &depth, &honor_depth_exclude,
                                     &depth_compatibility_trick,
                                     &use_commit_times, &notify)) {
        return NULL;
    }

    pool = Pool(NULL);

    path = py_object_to_svn_abspath(py_path, pool);
    if (path == NULL) {
        apr_pool_destroy(pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(pool, svn_wc_crawl_revisions5(
         wc_context, path, &py_ra_reporter3, py_reporter, restore_files,
         depth, honor_depth_exclude, depth_compatibility_trick,
         use_commit_times, py_cancel_check, NULL, py_wc_notify_func, notify, pool));

    apr_pool_destroy(pool);

    Py_RETURN_NONE;
}

static void context_done_handler(void *self)
{
    PyObject *selfobj = (PyObject *)self;

    Py_DECREF(selfobj);
}

static PyObject *py_wc_context_get_update_editor(PyObject *self, PyObject *args, PyObject *kwargs)
{
    char *kwnames[] = {
        "anchor_abspath", "target_basename", "use_commit_times", "depth",
        "depth_is_sticky", "allow_unver_obstructions", "adds_as_modification",
        "server_performs_filtering", "clean_checkout", "diff3_cmd",
        "preserved_exts", "dirents_func", "conflict_func", "external_func",
        "notify_func", NULL };
    const svn_delta_editor_t *editor;
    void *edit_baton;
    const char *anchor_abspath;
    char *target_basename;
    char *diff3_cmd = NULL;
    svn_wc_context_t *wc_context = ((ContextObject *)self)->context;
    bool use_commit_times = false;
    int depth = svn_depth_infinity;
    bool depth_is_sticky = false;
    bool allow_unver_obstructions = true;
    bool adds_as_modification = false;
    bool server_performs_filtering = false;
    bool clean_checkout = false;
    apr_array_header_t *preserved_exts = NULL;
    PyObject *py_preserved_exts = Py_None;
    PyObject *dirents_func = Py_None;
    PyObject *conflict_func = Py_None;
    PyObject *external_func = Py_None;
    PyObject *notify_func = Py_None;
    PyObject *py_anchor_abspath;
    apr_pool_t *result_pool, *scratch_pool;
    svn_error_t *err;
    svn_revnum_t target_revision;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "Os|bibbbbbzOOOOO", kwnames,
                                     &py_anchor_abspath, &target_basename,
                                     &use_commit_times, &depth,
                                     &depth_is_sticky,
                                     &allow_unver_obstructions,
                                     &adds_as_modification,
                                     &server_performs_filtering,
                                     &clean_checkout, &py_preserved_exts,
                                     &dirents_func, &conflict_func,
                                     &external_func, &notify_func)) {
        return NULL;
    }

    if (conflict_func != Py_None) {
        // TODO
        PyErr_SetString(PyExc_NotImplementedError,
                        "conflict_func is not currently supported");
        return NULL;
    }

    if (external_func != Py_None) {
        // TODO
        PyErr_SetString(PyExc_NotImplementedError,
                        "external_func is not currently supported");
        return NULL;
    }

    if (dirents_func != Py_None) {
        // TODO
        PyErr_SetString(PyExc_NotImplementedError,
                        "dirents_func is not currently supported");
        return NULL;
    }

    scratch_pool = Pool(NULL);

    anchor_abspath = py_object_to_svn_abspath(py_anchor_abspath, scratch_pool);

    if (py_preserved_exts != Py_None) {
        if (!string_list_to_apr_array(scratch_pool, py_preserved_exts, &preserved_exts)) {
            apr_pool_destroy(scratch_pool);
            return NULL;
        }
    }

    result_pool = Pool(NULL);

    Py_BEGIN_ALLOW_THREADS
    err = svn_wc_get_update_editor4(
             &editor, &edit_baton, &target_revision, wc_context,
             anchor_abspath, target_basename, use_commit_times, depth,
             depth_is_sticky, allow_unver_obstructions, adds_as_modification,
             server_performs_filtering, clean_checkout, diff3_cmd,
             preserved_exts, NULL, dirents_func, NULL, conflict_func, NULL,
             external_func, py_cancel_check, NULL, py_wc_notify_func,
             notify_func, result_pool, scratch_pool);
    Py_END_ALLOW_THREADS

    apr_pool_destroy(scratch_pool);

    if (err != NULL) {
        handle_svn_error(err);
        svn_error_clear(err);
        apr_pool_destroy(result_pool);
        return NULL;
    }

    /* TODO: Also return target_revision ? */
    Py_INCREF(self);
    return new_editor_object(NULL, editor, edit_baton, result_pool, &Editor_Type,
                             context_done_handler, self, NULL);
}

static PyObject *py_wc_context_ensure_adm(PyObject *self, PyObject *args,
                                          PyObject *kwargs)
{
    ContextObject *context_obj = (ContextObject *)self;
    char *kwnames[] = {
        "local_abspath", "url", "repos_root_url", "repos_uuid",
        "revnum", "depth", NULL };
    char *local_abspath;
    char *url;
    char *repos_root_url;
    char *repos_uuid;
    int revnum;
    int depth = svn_depth_infinity;
    apr_pool_t *pool;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "ssssi|i", kwnames,
                                     &local_abspath, &url, &repos_root_url,
                                     &repos_uuid, &revnum, &depth)) {
        return NULL;
    }

    pool = Pool(NULL);

    RUN_SVN_WITH_POOL(pool, svn_wc_ensure_adm4(context_obj->context,
                                               local_abspath, url,
                                               repos_root_url, repos_uuid,
                                               revnum, depth, pool));

    apr_pool_destroy(pool);

    Py_RETURN_NONE;
}

typedef struct {
    PyObject_VAR_HEAD
    apr_pool_t *pool;
    svn_wc_status3_t status;
} Status3Object;

static void status_dealloc(PyObject *self)
{
    apr_pool_t *pool = ((Status3Object *)self)->pool;
    if (pool != NULL)
        apr_pool_destroy(pool);
    PyObject_Del(self);
}

static PyMemberDef status_members[] = {
    { "kind", T_INT, offsetof(Status3Object, status.kind), READONLY,
        "The kind of node as recorded in the working copy." },
    { "depth", T_INT, offsetof(Status3Object, status.depth), READONLY,
        "The depth of the node as recorded in the working copy." },
    { "filesize", T_LONG, offsetof(Status3Object, status.filesize), READONLY,
        "The actual size of the working file on disk, or SVN_INVALID_FILESIZE"
        "if unknown (or if the item isn't a file at all)" },
    { "versioned", T_BOOL, offsetof(Status3Object, status.versioned), READONLY,
        "If the path is under version control, versioned is TRUE, "
        "otherwise FALSE." },
    { "repos_uuid", T_STRING, offsetof(Status3Object, status.repos_uuid), READONLY,
        "UUID of repository" },
    { "repos_root_url", T_STRING, offsetof(Status3Object, status.repos_root_url), READONLY,
        "Repository root URL" },
    { "repos_relpath", T_STRING, offsetof(Status3Object, status.repos_relpath), READONLY,
        "Relative path in repository" },
    /* TODO */
    { NULL }
};

static PyTypeObject Status3_Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "wc.Status", /*   const char *tp_name;  For printing, in format "<module>.<name>" */
    sizeof(Status3Object),
    0,/*    Py_ssize_t tp_basicsize, tp_itemsize;  For allocation */

    /* Methods to implement standard operations */

    status_dealloc, /*    destructor tp_dealloc;  */
    NULL, /*    printfunc tp_print; */
    NULL, /*    getattrfunc tp_getattr; */
    NULL, /*    setattrfunc tp_setattr; */
    NULL, /*    cmpfunc tp_compare; */
    NULL, /*    reprfunc tp_repr;   */

    /* Method suites for standard classes */

    NULL, /*    PyNumberMethods *tp_as_number;  */
    NULL, /*    PySequenceMethods *tp_as_sequence;  */
    NULL, /*    PyMappingMethods *tp_as_mapping;    */

    /* More standard operations (here for binary compatibility) */

    NULL, /*    hashfunc tp_hash;   */
    NULL, /*    ternaryfunc tp_call;    */
    NULL, /*    reprfunc tp_str;    */
    NULL, /*    getattrofunc tp_getattro;   */
    NULL, /*    setattrofunc tp_setattro;   */

    /* Functions to access object as input/output buffer */
    NULL, /*    PyBufferProcs *tp_as_buffer;    */

    /* Flags to define presence of optional/expanded features */
    0, /*   long tp_flags;  */

    NULL, /*    const char *tp_doc;  Documentation string */

    /* Assigned meaning in release 2.0 */
    /* call function for all accessible objects */
    NULL, /*    traverseproc tp_traverse;   */

    /* delete references to contained objects */
    NULL, /*    inquiry tp_clear;   */

    /* Assigned meaning in release 2.1 */
    /* rich comparisons */
    NULL, /*    richcmpfunc tp_richcompare; */

    /* weak reference enabler */
    0, /*   Py_ssize_t tp_weaklistoffset;   */

    /* Added in release 2.2 */
    /* Iterators */
    NULL, /*    getiterfunc tp_iter;    */
    NULL, /*    iternextfunc tp_iternext;   */

    /* Attribute descriptor and subclassing stuff */
    NULL, /*    struct PyMethodDef *tp_methods; */
    status_members, /*    struct PyMemberDef *tp_members; */
    NULL, /* struct PyGetSetDef *tp_getsetters; */
};

static PyObject *py_wc_status(PyObject *self, PyObject *args, PyObject *kwargs)
{
    ContextObject *context_obj = (ContextObject *)self;
    char *kwnames[] = {"path", NULL};
    PyObject *py_path;
    Status3Object *ret;
    const char *path;
    apr_pool_t *scratch_pool, *result_pool;
    svn_wc_status3_t* status;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O", kwnames, &py_path)) {
        return NULL;
    }

    result_pool = Pool(NULL);
    if (result_pool == NULL) {
        return NULL;
    }
    scratch_pool = Pool(result_pool);
    if (scratch_pool == NULL) {
        apr_pool_destroy(result_pool);
        return NULL;
    }

    path = py_object_to_svn_abspath(py_path, scratch_pool);
    if (path == NULL) {
        apr_pool_destroy(result_pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(result_pool,
                      svn_wc_status3(&status, context_obj->context, path,
                                     result_pool, scratch_pool));

    apr_pool_destroy(scratch_pool);

    ret = PyObject_New(Status3Object, &Status3_Type);
    if (ret == NULL) {
        apr_pool_destroy(result_pool);
        return NULL;
    }
    ret->pool = result_pool;
    ret->status = *status;
    return (PyObject *)ret;
}

static svn_error_t *py_status_receiver(void *baton, const char *local_abspath,
                                       const svn_wc_status3_t *status,
                                       apr_pool_t *scratch_pool)
{
    Status3Object *py_status;
    PyObject *ret;
    PyGILState_STATE state;

    if (baton == Py_None)
        return NULL;

    state = PyGILState_Ensure();

    py_status = PyObject_New(Status3Object, &Status3_Type);
    if (py_status == NULL) {
        PyGILState_Release(state);
        return py_svn_error();
    }
    py_status->pool = Pool(NULL);
    py_status->status = *svn_wc_dup_status3(status, py_status->pool);

    ret = PyObject_CallFunction((PyObject *)baton, "sO", local_abspath, py_status);
    Py_DECREF(py_status);

    if (ret == NULL) {
        PyGILState_Release(state);
        return py_svn_error();
    }

    Py_DECREF(ret);
    PyGILState_Release(state);

    return NULL;
}

static PyObject *py_wc_walk_status(PyObject *self, PyObject *args, PyObject *kwargs)
{
    ContextObject *context_obj = (ContextObject *)self;
    char *kwnames[] = {"path", "receiver", "depth", "get_all", "no_ignore",
        "ignore_text_mode", "ignore_patterns", NULL};
    PyObject *py_path;
    const char *path;
    int depth = svn_depth_infinity;
    bool get_all = true;
    bool no_ignore = false;
    bool ignore_text_mode = false;
    PyObject *py_ignore_patterns = Py_None;
    PyObject *status_func;
    apr_array_header_t *ignore_patterns;
    apr_pool_t *pool;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO|ibbbOO", kwnames,
                                     &py_path, &status_func, &depth, &get_all, &no_ignore,
                                     &ignore_text_mode, &py_ignore_patterns)) {
        return NULL;
    }

    pool = Pool(NULL);

    path = py_object_to_svn_abspath(py_path, pool);
    if (path == NULL) {
        apr_pool_destroy(pool);
        return NULL;
    }

    if (py_ignore_patterns == Py_None) {
        ignore_patterns = NULL;
    } else {
        if (!string_list_to_apr_array(pool, py_ignore_patterns, &ignore_patterns)) {
            apr_pool_destroy(pool);
            return NULL;
        }
    }

    RUN_SVN_WITH_POOL(pool,
                      svn_wc_walk_status(context_obj->context, path, depth,
                                         get_all, no_ignore, ignore_text_mode,
                                         ignore_patterns, py_status_receiver,
                                         status_func, py_cancel_check, NULL,
                                         pool));

    apr_pool_destroy(pool);

    Py_RETURN_NONE;
}

static PyObject *py_wc_add_lock(PyObject *self, PyObject *args, PyObject *kwargs)
{
    ContextObject *context_obj = (ContextObject *)self;
    PyObject *py_path, *py_lock;
    svn_lock_t *lock;
    char *kwnames[] = { "path", "lock", NULL };
    const char *path;
    apr_pool_t *scratch_pool;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO!", kwnames, &py_path, &Lock_Type,
                                     &py_lock)) {
        return NULL;
    }

    scratch_pool = Pool(NULL);
    if (scratch_pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_abspath(py_path, scratch_pool);
    if (path == NULL) {
        apr_pool_destroy(scratch_pool);
        return NULL;
    }

    lock = py_object_to_svn_lock(py_lock, scratch_pool);
    if (lock == NULL) {
        apr_pool_destroy(scratch_pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(scratch_pool,
                      svn_wc_add_lock2(context_obj->context, path, lock, scratch_pool));

    apr_pool_destroy(scratch_pool);

    Py_RETURN_NONE;
}

static PyObject *py_wc_remove_lock(PyObject *self, PyObject *args, PyObject *kwargs)
{
    ContextObject *context_obj = (ContextObject *)self;
    char *kwnames[] = { "path", NULL };
    PyObject *py_path;
    const char *path;
    apr_pool_t *scratch_pool;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O", kwnames, &py_path)) {
        return NULL;
    }

    scratch_pool = Pool(NULL);

    path = py_object_to_svn_abspath(py_path, scratch_pool);
    if (path == NULL) {
        apr_pool_destroy(scratch_pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(scratch_pool,
                      svn_wc_remove_lock2(context_obj->context, path,
                                          scratch_pool));

    apr_pool_destroy(scratch_pool);
    Py_RETURN_NONE;
}

static PyObject *py_wc_add_from_disk(PyObject *self, PyObject *args, PyObject *kwargs)
{
    ContextObject *context_obj = (ContextObject *)self;
    char *kwnames[] = {"path", "props", "skip_checks", "notify", NULL };
    PyObject *py_path;
    const char *path;
    bool skip_checks = false;
    PyObject *py_props = Py_None;
    PyObject *notify_func = Py_None;
    apr_pool_t *pool;
    apr_hash_t *props;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|ObO", kwnames,
                                     &py_path, &py_props, &skip_checks, &notify_func)) {
        return NULL;
    }

    pool = Pool(NULL);
    if (pool == NULL) {
        return NULL;
    }

    path = py_object_to_svn_abspath(py_path, pool);
    if (path == NULL) {
        apr_pool_destroy(pool);
        return NULL;
    }

    if (py_props == Py_None) {
        props = NULL;
    } else {
        props = prop_dict_to_hash(pool, py_props);
        if (props == NULL) {
            apr_pool_destroy(pool);
            return NULL;
        }
    }

    RUN_SVN_WITH_POOL(
            pool, svn_wc_add_from_disk3(
                    context_obj->context, path, props, skip_checks,
                    notify_func == Py_None?NULL:py_wc_notify_func,
                    notify_func, pool));

    apr_pool_destroy(pool);

    Py_RETURN_NONE;
}

static PyObject *py_wc_get_prop_diffs(PyObject *self, PyObject *args, PyObject *kwargs)
{
    ContextObject *context_obj = (ContextObject *)self;
    PyObject *py_path, *py_orig_props, *py_propchanges;
    apr_pool_t *pool;
    char *kwnames[] = {"path", NULL};
    apr_hash_t *original_props;
    apr_array_header_t *propchanges;
    const char *path;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O", kwnames, &py_path)) {
        return NULL;
    }

    pool = Pool(NULL);

    path = py_object_to_svn_abspath(py_path, pool);
    if (path == NULL) {
        apr_pool_destroy(pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(pool, svn_wc_get_prop_diffs2(&propchanges,
                                                   &original_props,
                                                   context_obj->context,
                                                   path, pool, pool));

    py_orig_props = prop_hash_to_dict(original_props);
    if (py_orig_props == NULL) {
        apr_pool_destroy(pool);
        return NULL;
    }

    py_propchanges = propchanges_to_list(propchanges);
    if (py_propchanges == NULL) {
        apr_pool_destroy(pool);
        Py_DECREF(py_propchanges);
        return NULL;
    }

    apr_pool_destroy(pool);

    return Py_BuildValue("NN", py_orig_props, py_propchanges);
}

static PyObject *py_wc_context_process_committed_queue(PyObject *self, PyObject *args)
{
    apr_pool_t *temp_pool;
    ContextObject *contextobj = (ContextObject *)self;
    svn_revnum_t revnum;
    char *date, *author;
    PyObject *py_queue;

    if (!PyArg_ParseTuple(args, "O!lss", &CommittedQueue_Type, &py_queue,
                          &revnum, &date, &author))
        return NULL;

    temp_pool = Pool(NULL);
    if (temp_pool == NULL)
        return NULL;

    svn_wc_committed_queue_t *committed_queue = PyObject_GetCommittedQueue(py_queue);

    RUN_SVN_WITH_POOL(temp_pool,
                      svn_wc_process_committed_queue2(committed_queue,
                                                      contextobj->context,
                                                      revnum, date, author,
                                                      py_cancel_check, NULL,
                                                      temp_pool));

    apr_pool_destroy(temp_pool);

    Py_RETURN_NONE;
}



static PyMethodDef context_methods[] = {
    { "locked", py_wc_context_locked, METH_VARARGS,
        "locked(path) -> (locked_here, locked)\n"
        "Check whether a patch is locked."},
    { "check_wc", py_wc_context_check_wc, METH_VARARGS,
        "check_wc(path) -> wc_format\n"
        "Check format version of a working copy." },
    { "text_modified", py_wc_context_text_modified_p2, METH_VARARGS,
        "text_modified(path) -> bool\n"
        "Check whether text of a file is modified against base." },
    { "props_modified", py_wc_context_props_modified_p2, METH_VARARGS,
        "props_modified(path) -> bool\n"
        "Check whether props of a file are modified against base." },
    { "conflicted", py_wc_context_conflicted, METH_VARARGS,
        "conflicted(path) -> (text_conflicted, prop_conflicted, "
            "tree_conflicted)\n"
        "Check whether a path is conflicted." },
    { "crawl_revisions", (PyCFunction)py_wc_context_crawl_revisions,
        METH_VARARGS|METH_KEYWORDS,
        "crawl_revisions(path, reporter, restore_files, depth, "
            "honor_depth_exclude, depth_compatibility_trick, "
            "use_commit_time, notify)\n"
        "Do a depth-first crawl of the working copy." },
    { "get_update_editor",
        (PyCFunction)py_wc_context_get_update_editor,
        METH_VARARGS|METH_KEYWORDS,
        "get_update_editor(anchor_abspath, target_basename, use_commit_time, "
            "depth, depth_is_sticky, allow_unver_obstructions, "
            "adds_as_modification, server_performs_filtering, clean_checkout, "
            "diff3_cmd, dirent_func=None, conflict_func=None, "
            "external_func=None) -> target_revnum" },
    { "ensure_adm",
        (PyCFunction)py_wc_context_ensure_adm,
        METH_VARARGS|METH_KEYWORDS,
        "ensure_adm(local_abspath, url, repos_root_url, repos_uuid, revnum, depth)" },
    { "process_committed_queue",
        (PyCFunction)py_wc_context_process_committed_queue,
        METH_VARARGS|METH_KEYWORDS,
        "" },
    { "status",
        (PyCFunction)py_wc_status,
        METH_VARARGS|METH_KEYWORDS,
        "status(path) -> status" },
    { "walk_status",
        (PyCFunction)py_wc_walk_status,
        METH_VARARGS|METH_KEYWORDS,
        "walk_status(path, receiver, depth=DEPTH_INFINITY, get_all=True, "
            "no_ignore=False, ignore_text_mode=False, ignore_patterns=None)\n" },
    { "add_lock",
        (PyCFunction)py_wc_add_lock,
        METH_VARARGS|METH_KEYWORDS,
        "add_lock(path, lock)" },
    { "remove_lock",
        (PyCFunction)py_wc_remove_lock,
        METH_VARARGS|METH_KEYWORDS,
        "remove_lock(path)" },
    { "add_from_disk",
        (PyCFunction)py_wc_add_from_disk,
        METH_VARARGS|METH_KEYWORDS,
        "add_from_disk(local_abspath, props=None, skip_checks=False, notify=None)" },
    { "get_prop_diffs",
        (PyCFunction)py_wc_get_prop_diffs,
        METH_VARARGS|METH_KEYWORDS,
        "get_prop_diffs(path) -> (changes orig_props)" },
    { NULL }
};

static void context_dealloc(PyObject *self)
{
    ContextObject *context_obj = (ContextObject *)self;
    svn_wc_context_destroy(context_obj->context);
    apr_pool_destroy(context_obj->pool);
    PyObject_Del(self);
}

static PyObject *context_init(PyTypeObject *self, PyObject *args, PyObject *kwargs)
{
    ContextObject *ret;
    char *kwnames[] = { NULL };
    svn_config_t *config = NULL;

    // TODO(jelmer): Support passing in config
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "", kwnames))
        return NULL;

    ret = PyObject_New(ContextObject, &Context_Type);
    if (ret == NULL)
        return NULL;

    ret->pool = Pool(NULL);
    if (ret->pool == NULL)
        return NULL;
    RUN_SVN_WITH_POOL(ret->pool, svn_wc_context_create(&ret->context, config,
                                                       ret->pool, ret->pool));

    return (PyObject *)ret;
}

static PyTypeObject Context_Type = {
	PyVarObject_HEAD_INIT(NULL, 0)
	"wc.Context", /*	const char *tp_name;  For printing, in format "<module>.<name>" */
	sizeof(ContextObject),
	0,/*	Py_ssize_t tp_basicsize, tp_itemsize;  For allocation */

	/* Methods to implement standard operations */

	context_dealloc, /*	destructor tp_dealloc;	*/
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

	"Context", /*	const char *tp_doc;  Documentation string */

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
	context_methods, /*	struct PyMethodDef *tp_methods;	*/
	NULL, /*	struct PyMemberDef *tp_members;	*/
	NULL, /*	struct PyGetSetDef *tp_getset;	*/
	NULL, /*	struct _typeobject *tp_base;	*/
	NULL, /*	PyObject *tp_dict;	*/
	NULL, /*	descrgetfunc tp_descr_get;	*/
	NULL, /*	descrsetfunc tp_descr_set;	*/
	0, /*	Py_ssize_t tp_dictoffset;	*/
	NULL, /*	initproc tp_init;	*/
	NULL, /*	allocfunc tp_alloc;	*/
	context_init, /*	newfunc tp_new;	*/
};

static void lock_dealloc(PyObject *self)
{
	LockObject *lockself = (LockObject *)self;

	apr_pool_destroy(lockself->pool);

	PyObject_Del(self);
}

static PyObject *lock_init(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
	char *kwnames[] = { "token", NULL };
	LockObject *ret;
    char *token = NULL;

	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|z", kwnames, &token))
		return NULL;

	ret = PyObject_New(LockObject, &Lock_Type);
	if (ret == NULL)
		return NULL;

	ret->pool = Pool(NULL);
	if (ret->pool == NULL)
		return NULL;
	ret->lock = *svn_lock_create(ret->pool);
    if (token != NULL) {
        ret->lock.token = apr_pstrdup(ret->pool, token);
    }

	return (PyObject *)ret;
}

static PyObject *lock_get_path(PyObject *self, void *closure) {
    LockObject *lock_obj = (LockObject *)self;

    if (lock_obj->lock.path == NULL) {
        Py_RETURN_NONE;
    }

    return PyUnicode_FromString(lock_obj->lock.path);
}

static int lock_set_path(PyObject *self, PyObject *value, void *closure) {
    LockObject *lock_obj = (LockObject *)self;
    char *path;

    path = PyBytes_AsString(value);
    if (path == NULL) {
        return -1;
    }

    lock_obj->lock.path = py_object_to_svn_string(value, lock_obj->pool);
    return 0;
}

static PyObject *lock_get_token(PyObject *self, void *closure) {
    LockObject *lock_obj = (LockObject *)self;

    if (lock_obj->lock.token == NULL) {
        Py_RETURN_NONE;
    }

    return PyBytes_FromString(lock_obj->lock.token);
}

static int lock_set_token(PyObject *self, PyObject *value, void *closure) {
    LockObject *lock_obj = (LockObject *)self;
    char *token;

    token = PyBytes_AsString(value);
    if (token == NULL) {
        PyErr_SetNone(PyExc_TypeError);
        return -1;
    }

    lock_obj->lock.token = apr_pstrdup(lock_obj->pool, PyBytes_AsString(value));
    return 0;
}

static PyGetSetDef lock_getsetters[] = {
    { "path", lock_get_path, lock_set_path,
        "the path this lock applies to"},
    { "token", lock_get_token, lock_set_token,
        "unique URI representing lock"},
    { NULL },
};

PyTypeObject Lock_Type = {
	PyVarObject_HEAD_INIT(NULL, 0)
	"wc.Lock", /*	const char *tp_name;  For printing, in format "<module>.<name>" */
	sizeof(LockObject),
	0,/*	Py_ssize_t tp_basicsize, tp_itemsize;  For allocation */

	/* Methods to implement standard operations */

	.tp_dealloc = lock_dealloc, /*	destructor tp_dealloc;	*/

	.tp_doc = "Lock", /*	const char *tp_doc;  Documentation string */

	.tp_methods = NULL, /*	struct PyMethodDef *tp_methods;	*/

	.tp_new = lock_init, /* tp_new tp_new */

    .tp_getset = lock_getsetters,
};

static PyObject *
moduleinit(void)
{
	PyObject *mod;

	if (PyType_Ready(&Context_Type) < 0)
		return NULL;

	if (PyType_Ready(&Editor_Type) < 0)
		return NULL;

	if (PyType_Ready(&FileEditor_Type) < 0)
		return NULL;

	if (PyType_Ready(&DirectoryEditor_Type) < 0)
		return NULL;

	if (PyType_Ready(&TxDeltaWindowHandler_Type) < 0)
		return NULL;

	if (PyType_Ready(&Stream_Type) < 0)
		return NULL;

	if (PyType_Ready(&CommittedQueue_Type) < 0)
		return NULL;

	if (PyType_Ready(&Status3_Type) < 0)
		return NULL;

	if (PyType_Ready(&Lock_Type) < 0)
		return NULL;

	apr_initialize();

#if PY_MAJOR_VERSION >= 3
	static struct PyModuleDef moduledef = {
	  PyModuleDef_HEAD_INIT,
	  "wc",         /* m_name */
	  "Working Copies", /* m_doc */
	  -1,              /* m_size */
	  wc_methods, /* m_methods */
	  NULL,            /* m_reload */
	  NULL,            /* m_traverse */
	  NULL,            /* m_clear*/
	  NULL,            /* m_free */
	};
	mod = PyModule_Create(&moduledef);
#else
	mod = Py_InitModule3("wc", wc_methods, "Working Copies");
#endif
	if (mod == NULL)
		return NULL;

	PyModule_AddIntConstant(mod, "SCHEDULE_NORMAL", 0);
	PyModule_AddIntConstant(mod, "SCHEDULE_ADD", 1);
	PyModule_AddIntConstant(mod, "SCHEDULE_DELETE", 2);
	PyModule_AddIntConstant(mod, "SCHEDULE_REPLACE", 3);

	PyModule_AddIntConstant(mod, "CONFLICT_CHOOSE_POSTPONE",
							svn_wc_conflict_choose_postpone);
	PyModule_AddIntConstant(mod, "CONFLICT_CHOOSE_BASE",
							svn_wc_conflict_choose_base);
	PyModule_AddIntConstant(mod, "CONFLICT_CHOOSE_THEIRS_FULL",
							svn_wc_conflict_choose_theirs_full);
	PyModule_AddIntConstant(mod, "CONFLICT_CHOOSE_MINE_FULL",
							svn_wc_conflict_choose_mine_full);
	PyModule_AddIntConstant(mod, "CONFLICT_CHOOSE_THEIRS_CONFLICT",
							svn_wc_conflict_choose_theirs_conflict);
	PyModule_AddIntConstant(mod, "CONFLICT_CHOOSE_MINE_CONFLICT",
							svn_wc_conflict_choose_mine_conflict);
	PyModule_AddIntConstant(mod, "CONFLICT_CHOOSE_MERGED",
							svn_wc_conflict_choose_merged);

	PyModule_AddIntConstant(mod, "STATUS_NONE", svn_wc_status_none);
	PyModule_AddIntConstant(mod, "STATUS_UNVERSIONED", svn_wc_status_unversioned);
	PyModule_AddIntConstant(mod, "STATUS_NORMAL", svn_wc_status_normal);
	PyModule_AddIntConstant(mod, "STATUS_ADDED", svn_wc_status_added);
	PyModule_AddIntConstant(mod, "STATUS_MISSING", svn_wc_status_missing);
	PyModule_AddIntConstant(mod, "STATUS_DELETED", svn_wc_status_deleted);
	PyModule_AddIntConstant(mod, "STATUS_REPLACED", svn_wc_status_replaced);
	PyModule_AddIntConstant(mod, "STATUS_MODIFIED", svn_wc_status_modified);
	PyModule_AddIntConstant(mod, "STATUS_MERGED", svn_wc_status_merged);
	PyModule_AddIntConstant(mod, "STATUS_CONFLICTED", svn_wc_status_conflicted);
	PyModule_AddIntConstant(mod, "STATUS_IGNORED", svn_wc_status_ignored);
	PyModule_AddIntConstant(mod, "STATUS_OBSTRUCTED", svn_wc_status_obstructed);
	PyModule_AddIntConstant(mod, "STATUS_EXTERNAL", svn_wc_status_external);
	PyModule_AddIntConstant(mod, "STATUS_INCOMPLETE", svn_wc_status_incomplete);

	PyModule_AddIntConstant(mod, "TRANSLATE_FROM_NF", SVN_WC_TRANSLATE_FROM_NF);
	PyModule_AddIntConstant(mod, "TRANSLATE_TO_NF", SVN_WC_TRANSLATE_TO_NF);
	PyModule_AddIntConstant(mod, "TRANSLATE_FORCE_EOL_REPAIR", SVN_WC_TRANSLATE_FORCE_EOL_REPAIR);
	PyModule_AddIntConstant(mod, "TRANSLATE_NO_OUTPUT_CLEANUP", SVN_WC_TRANSLATE_NO_OUTPUT_CLEANUP);
	PyModule_AddIntConstant(mod, "TRANSLATE_FORCE_COPY", SVN_WC_TRANSLATE_FORCE_COPY);
	PyModule_AddIntConstant(mod, "TRANSLATE_USE_GLOBAL_TMP", SVN_WC_TRANSLATE_USE_GLOBAL_TMP);

	PyModule_AddIntConstant(mod, "CONFLICT_CHOOSE_POSTPONE", svn_wc_conflict_choose_postpone);
	PyModule_AddIntConstant(mod, "CONFLICT_CHOOSE_BASE", svn_wc_conflict_choose_base);
	PyModule_AddIntConstant(mod, "CONFLICT_CHOOSE_THEIRS_FULL", svn_wc_conflict_choose_theirs_full);
	PyModule_AddIntConstant(mod, "CONFLICT_CHOOSE_MINE_FULL", svn_wc_conflict_choose_mine_full);
	PyModule_AddIntConstant(mod, "CONFLICT_CHOOSE_THEIRS_CONFLICT", svn_wc_conflict_choose_theirs_conflict);
	PyModule_AddIntConstant(mod, "CONFLICT_CHOOSE_MINE_CONFLICT", svn_wc_conflict_choose_mine_conflict);
	PyModule_AddIntConstant(mod, "CONFLICT_CHOOSE_MERGED", svn_wc_conflict_choose_merged);

	PyModule_AddObject(mod, "Lock", (PyObject *)&Lock_Type);
	Py_INCREF(&Lock_Type);

	PyModule_AddObject(mod, "CommittedQueue", (PyObject *)&CommittedQueue_Type);
	Py_INCREF(&CommittedQueue_Type);

	PyModule_AddObject(mod, "Context", (PyObject *)&Context_Type);
	Py_INCREF(&Context_Type);

	return mod;
}

#if PY_MAJOR_VERSION >= 3
PyMODINIT_FUNC
PyInit_wc(void)
{
	return moduleinit();
}
#else
PyMODINIT_FUNC
initwc(void)
{
	moduleinit();
}
#endif
