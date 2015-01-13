/*
 * Copyright © 2008 Jelmer Vernooij <jelmer@samba.org>
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

#include "util.h"
#include "editor.h"
#include "wc.h"

#ifndef T_BOOL
#define T_BOOL T_BYTE
#endif

#if ONLY_SINCE_SVN(1, 5)
#define REPORTER_T svn_ra_reporter3_t
#else
#define REPORTER_T svn_ra_reporter2_t
#endif

staticforward PyTypeObject Entry_Type;
staticforward PyTypeObject Status_Type;
staticforward PyTypeObject Adm_Type;

static PyObject *py_entry(const svn_wc_entry_t *entry);
static PyObject *py_status(const svn_wc_status2_t *status);

#if ONLY_BEFORE_SVN(1, 5)
struct svn_wc_committed_queue_t
{
	apr_pool_t *pool;
	apr_array_header_t *queue;
	svn_boolean_t have_recursive;
};

#if SVN_VER_MINOR < 5
typedef struct svn_wc_committed_queue_t svn_wc_committed_queue_t;
#endif

typedef struct
{
	const char *path;
	svn_wc_adm_access_t *adm_access;
	svn_boolean_t recurse;
	svn_boolean_t remove_lock;
	apr_array_header_t *wcprop_changes;
	unsigned char *digest;
} committed_queue_item_t;

#if SVN_VER_MINOR < 5
static
#endif
svn_wc_committed_queue_t *svn_wc_committed_queue_create(apr_pool_t *pool)
{
	svn_wc_committed_queue_t *q;

	q = apr_palloc(pool, sizeof(*q));
	q->pool = pool;
	q->queue = apr_array_make(pool, 1, sizeof(committed_queue_item_t *));
	q->have_recursive = FALSE;

	return q;
}

#if SVN_VER_MINOR < 5
static
#endif
svn_error_t *svn_wc_queue_committed(svn_wc_committed_queue_t **queue,
                        const char *path,
                        svn_wc_adm_access_t *adm_access,
                        svn_boolean_t recurse,
                        apr_array_header_t *wcprop_changes,
                        svn_boolean_t remove_lock,
                        svn_boolean_t remove_changelist,
                        const unsigned char *digest,
                        apr_pool_t *scratch_pool)
{
  committed_queue_item_t *cqi;

  (*queue)->have_recursive |= recurse;

  /* Use the same pool as the one QUEUE was allocated in,
     to prevent lifetime issues.  Intermediate operations
     should use SCRATCH_POOL. */

  /* Add to the array with paths and options */
  cqi = apr_palloc((*queue)->pool, sizeof(*cqi));
  cqi->path = path;
  cqi->adm_access = adm_access;
  cqi->recurse = recurse;
  cqi->remove_lock = remove_lock;
  cqi->wcprop_changes = wcprop_changes;
  cqi->digest = digest;

  APR_ARRAY_PUSH((*queue)->queue, committed_queue_item_t *) = cqi;

  return SVN_NO_ERROR;
}

#endif

typedef struct {
	PyObject_HEAD
	apr_pool_t *pool;
	svn_wc_committed_queue_t *queue;
} CommittedQueueObject;
staticforward PyTypeObject CommittedQueue_Type;

#if ONLY_SINCE_SVN(1, 5)
static svn_error_t *py_ra_report_set_path(void *baton, const char *path, svn_revnum_t revision, svn_depth_t depth, int start_empty, const char *lock_token, apr_pool_t *pool)
{
	PyObject *self = (PyObject *)baton, *py_lock_token, *ret;
	PyGILState_STATE state = PyGILState_Ensure();
	if (lock_token == NULL) {
		py_lock_token = Py_None;
		Py_INCREF(py_lock_token);
	} else {
		py_lock_token = PyString_FromString(lock_token);
	}
	ret = PyObject_CallMethod(self, "set_path", "slbOi", path, revision, start_empty, py_lock_token, depth);
	Py_DECREF(py_lock_token);
	CB_CHECK_PYRETVAL(ret);
	Py_DECREF(ret);
	PyGILState_Release(state);
	return NULL;
}

static svn_error_t *py_ra_report_link_path(void *report_baton, const char *path, const char *url, svn_revnum_t revision, svn_depth_t depth, int start_empty, const char *lock_token, apr_pool_t *pool)
{
	PyObject *self = (PyObject *)report_baton, *ret, *py_lock_token;
	PyGILState_STATE state = PyGILState_Ensure();
	if (lock_token == NULL) {
		py_lock_token = Py_None;
		Py_INCREF(py_lock_token);
	} else { 
		py_lock_token = PyString_FromString(lock_token);
	}
	ret = PyObject_CallMethod(self, "link_path", "sslbOi", path, url, revision, start_empty, py_lock_token, depth);
	Py_DECREF(py_lock_token);
	CB_CHECK_PYRETVAL(ret);
	Py_DECREF(ret);
	PyGILState_Release(state);
	return NULL;
}


#else
static svn_error_t *py_ra_report_set_path(void *baton, const char *path, svn_revnum_t revision, int start_empty, const char *lock_token, apr_pool_t *pool)
{
	PyObject *self = (PyObject *)baton, *py_lock_token, *ret;
	PyGILState_STATE state = PyGILState_Ensure();
	if (lock_token == NULL) {
		py_lock_token = Py_None;
		Py_INCREF(py_lock_token);
	} else {
		py_lock_token = PyString_FromString(lock_token);
	}
	ret = PyObject_CallMethod(self, "set_path", "slbOi", path, revision, start_empty, py_lock_token, svn_depth_infinity);
	CB_CHECK_PYRETVAL(ret);
	Py_DECREF(ret);
	PyGILState_Release(state);
	return NULL;
}

static svn_error_t *py_ra_report_link_path(void *report_baton, const char *path, const char *url, svn_revnum_t revision, int start_empty, const char *lock_token, apr_pool_t *pool)
{
	PyObject *self = (PyObject *)report_baton, *ret, *py_lock_token;
	PyGILState_STATE state = PyGILState_Ensure();
	if (lock_token == NULL) {
		py_lock_token = Py_None;
		Py_INCREF(py_lock_token);
	} else { 
		py_lock_token = PyString_FromString(lock_token);
	}
	ret = PyObject_CallMethod(self, "link_path", "sslbOi", path, url, revision, start_empty, py_lock_token, svn_depth_infinity);
	CB_CHECK_PYRETVAL(ret);
	Py_DECREF(ret);
	PyGILState_Release(state);
	return NULL;
}


#endif

static svn_error_t *py_ra_report_delete_path(void *baton, const char *path, apr_pool_t *pool)
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

static const REPORTER_T py_ra_reporter = {
	py_ra_report_set_path,
	py_ra_report_delete_path,
	py_ra_report_link_path,
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


void py_wc_notify_func(void *baton, const svn_wc_notify_t *notify, apr_pool_t *pool)
{
	PyObject *func = baton, *ret;
	if (func == Py_None)
		return;

	if (notify->err != NULL) {
		PyObject *excval = PyErr_NewSubversionException(notify->err);
		ret = PyObject_CallFunction(func, "O", excval);
		Py_DECREF(excval);
		Py_XDECREF(ret);
		/* If ret was NULL, the cancel func should abort the operation. */
	}
}

typedef struct {
	PyObject_HEAD
	apr_pool_t *pool;
	svn_wc_entry_t entry;
} EntryObject;

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

static PyTypeObject Entry_Type = {
	PyObject_HEAD_INIT(NULL) 0,
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
	PyObject_HEAD
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

static PyTypeObject Status_Type = {
	PyObject_HEAD_INIT(NULL) 0,
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

static PyObject *py_status(const svn_wc_status2_t *status)
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

typedef struct {
	PyObject_HEAD
	svn_wc_adm_access_t *adm;
	apr_pool_t *pool;
} AdmObject;

#define ADM_CHECK_CLOSED(adm_obj) \
	if (adm_obj->adm == NULL) { \
		PyErr_SetString(PyExc_RuntimeError, "WorkingCopy instance already closed"); \
		return NULL; \
	}

static PyObject *adm_init(PyTypeObject *self, PyObject *args, PyObject *kwargs)
{
	PyObject *associated;
	char *path;
	bool write_lock=false;
	int depth=0;
	svn_wc_adm_access_t *parent_wc;
	svn_error_t *err;
	AdmObject *ret;
	char *kwnames[] = { "associated", "path", "write_lock", "depth", NULL };

	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "Os|bi", kwnames,
			&associated, &path, &write_lock, &depth))
		return NULL;

	ret = PyObject_New(AdmObject, &Adm_Type);
	if (ret == NULL)
		return NULL;

	ret->pool = Pool(NULL);
	if (ret->pool == NULL)
		return NULL;
	if (associated == Py_None) {
		parent_wc = NULL;
	} else {
		parent_wc = ((AdmObject *)associated)->adm;
	}
	Py_BEGIN_ALLOW_THREADS
	err = svn_wc_adm_open3(&ret->adm, parent_wc, 
						   svn_path_canonicalize(path, ret->pool),
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
	return PyString_FromString(svn_wc_adm_access_path(admobj->adm));
}

static PyObject *adm_locked(PyObject *self)
{
	AdmObject *admobj = (AdmObject *)self;
	ADM_CHECK_CLOSED(admobj);
	return PyBool_FromLong(svn_wc_adm_locked(admobj->adm));
}

static PyObject *adm_prop_get(PyObject *self, PyObject *args)
{
	char *name, *path;
	AdmObject *admobj = (AdmObject *)self;
	const svn_string_t *value;
	apr_pool_t *temp_pool;
	PyObject *ret;

	if (!PyArg_ParseTuple(args, "ss", &name, &path))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(temp_pool, svn_wc_prop_get(&value, name, path, admobj->adm, temp_pool));
	if (value == NULL || value->data == NULL) {
		ret = Py_None;
		Py_INCREF(ret);
	} else {
		ret = PyString_FromStringAndSize(value->data, value->len);
	}
	apr_pool_destroy(temp_pool);
	return ret;
}

static PyObject *adm_prop_set(PyObject *self, PyObject *args)
{
	char *name, *value, *path; 
	AdmObject *admobj = (AdmObject *)self;
	bool skip_checks=false;
	apr_pool_t *temp_pool;
	int vallen;
	svn_string_t *cvalue;
	PyObject *notify_func = Py_None;

	if (!PyArg_ParseTuple(args, "sz#s|bO", &name, &value, &vallen, &path, &skip_checks,
						  &notify_func))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
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
	char *path;
	PyObject *callbacks; 
	bool show_hidden=false;
	apr_pool_t *temp_pool;
	AdmObject *admobj = (AdmObject *)self;
	svn_depth_t depth = svn_depth_infinity;

	if (!PyArg_ParseTuple(args, "sO|bi", &path, &callbacks, &show_hidden, &depth))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
#if ONLY_SINCE_SVN(1, 5)
	RUN_SVN_WITH_POOL(temp_pool, svn_wc_walk_entries3(
			  svn_path_canonicalize(path, temp_pool), admobj->adm, 
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
			  svn_path_canonicalize(path, temp_pool), admobj->adm, 
				&py_wc_entry_callbacks, (void *)callbacks,
				show_hidden, py_cancel_check, NULL,
				temp_pool));
#endif
	apr_pool_destroy(temp_pool);

	Py_RETURN_NONE;
}

static PyObject *adm_entry(PyObject *self, PyObject *args)
{
	char *path;
	bool show_hidden=false;
	apr_pool_t *temp_pool;
	AdmObject *admobj = (AdmObject *)self;
	const svn_wc_entry_t *entry;
	PyObject *ret;

	if (!PyArg_ParseTuple(args, "s|b", &path, &show_hidden))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(temp_pool, svn_wc_entry(&entry, svn_path_canonicalize(path, temp_pool), admobj->adm, show_hidden, temp_pool));

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
	char *path;
	apr_pool_t *temp_pool;
	apr_array_header_t *propchanges;
	apr_hash_t *original_props;
	AdmObject *admobj = (AdmObject *)self;
	svn_prop_t el;
	int i;
	PyObject *py_propchanges, *py_orig_props, *pyval;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(temp_pool, svn_wc_get_prop_diffs(&propchanges, &original_props,
				svn_path_canonicalize(path, temp_pool), admobj->adm, temp_pool));
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
	char *path, *copyfrom_url=NULL;
	svn_revnum_t copyfrom_rev=-1; 
	char *kwnames[] = { "path", "copyfrom_url", "copyfrom_rev", "notify_func", "depth", NULL };
	PyObject *notify_func=Py_None;
	AdmObject *admobj = (AdmObject *)self;
	apr_pool_t *temp_pool;
	svn_depth_t depth = svn_depth_infinity;

	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "s|zlOi", kwnames, &path,
			&copyfrom_url, &copyfrom_rev, &notify_func, &depth))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;

#if ONLY_SINCE_SVN(1, 6)
	RUN_SVN_WITH_POOL(temp_pool, svn_wc_add3(
						   svn_path_canonicalize(path, temp_pool), admobj->adm, depth, copyfrom_url, 
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
						   svn_path_canonicalize(path, temp_pool), admobj->adm, copyfrom_url, 
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
	char *path;
	PyObject *notify_func=Py_None;
	bool keep_local = false;

	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "s|Ob:delete", kwnames, 
			&path, &notify_func, &keep_local))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;

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
	char *path;
	PyObject *reporter;
	bool restore_files=true, recurse=true, use_commit_times=true;
	PyObject *notify_func=Py_None;
	apr_pool_t *temp_pool;
	AdmObject *admobj = (AdmObject *)self;
	svn_wc_traversal_info_t *traversal_info;
	svn_boolean_t depth_compatibility_trick = FALSE;
	svn_boolean_t honor_depth_exclude = FALSE;
	char *kwnames[] = { "path", "reporter", "restore_files", "recurse", "use_commit_times", "notify_func", "depth_compatibility_trick", "honor_depth_exclude,", NULL };

	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "sO|bbbObb", kwnames, &path,
			&reporter, &restore_files, &recurse, &use_commit_times,
			&notify_func, &depth_compatibility_trick, &honor_depth_exclude))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	traversal_info = svn_wc_init_traversal_info(temp_pool);
#if ONLY_SINCE_SVN(1, 6)
	RUN_SVN_WITH_POOL(temp_pool, svn_wc_crawl_revisions4(svn_path_canonicalize(path, temp_pool), admobj->adm, 
				&py_ra_reporter, (void *)reporter, 
				restore_files, recurse?svn_depth_infinity:svn_depth_files,
				honor_depth_exclude,
				depth_compatibility_trick, use_commit_times, 
				py_wc_notify_func, (void *)notify_func,
				traversal_info, temp_pool));
#elif ONLY_SINCE_SVN(1, 5)
	RUN_SVN_WITH_POOL(temp_pool, svn_wc_crawl_revisions3(svn_path_canonicalize(path, temp_pool), admobj->adm, 
				&py_ra_reporter, (void *)reporter, 
				restore_files, recurse?svn_depth_infinity:svn_depth_files, 
				depth_compatibility_trick, use_commit_times, 
				py_wc_notify_func, (void *)notify_func,
				traversal_info, temp_pool));
#else
	RUN_SVN_WITH_POOL(temp_pool, svn_wc_crawl_revisions2(svn_path_canonicalize(path, temp_pool), admobj->adm, 
				&py_ra_reporter, (void *)reporter, 
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
	svn_boolean_t allow_unver_obstructions = FALSE;
	svn_boolean_t depth_is_sticky = FALSE;

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
				depth_is_sticky, allow_unver_obstructions, 
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

static bool py_dict_to_wcprop_changes(PyObject *dict, apr_pool_t *pool, apr_array_header_t **ret)
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
		   prop->name = PyString_AsString(key);
		   if (val == Py_None) {
			   prop->value = NULL;
		   } else {
			   prop->value = svn_string_ncreate(PyString_AsString(val), PyString_Size(val), pool);
		   }
		   APR_ARRAY_PUSH(*ret, svn_prop_t *) = prop;
	}

	return true;
}

static PyObject *adm_has_binary_prop(PyObject *self, PyObject *args)
{
	char *path;
	svn_boolean_t binary;
	AdmObject *admobj = (AdmObject *)self;
	apr_pool_t *temp_pool;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;

	RUN_SVN_WITH_POOL(temp_pool, svn_wc_has_binary_prop(&binary, path, admobj->adm, temp_pool));

	apr_pool_destroy(temp_pool);

	return PyBool_FromLong(binary);
}

static PyObject *adm_process_committed(PyObject *self, PyObject *args, PyObject *kwargs)
{
	char *path, *rev_date = NULL, *rev_author = NULL;
	bool recurse, remove_lock = false;
	unsigned char *digest = NULL;
	svn_revnum_t new_revnum;
	PyObject *py_wcprop_changes = Py_None;
	apr_array_header_t *wcprop_changes = NULL;
	AdmObject *admobj = (AdmObject *)self;
	apr_pool_t *temp_pool;
	int digest_len;
	svn_boolean_t remove_changelist = FALSE;
	char *kwnames[] = { "path", "recurse", "new_revnum", "rev_date", "rev_author", 
						"wcprop_changes", "remove_lock", "digest", "remove_changelist", NULL };

	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "sblzz|Obz#b", kwnames, 
									 &path, &recurse, &new_revnum, &rev_date,
									 &rev_author, &py_wcprop_changes, 
									 &remove_lock, &digest, &digest_len, &remove_changelist))
		return NULL;

#if PY_VERSION_HEX < 0x02050000
	PyErr_Warn(PyExc_DeprecationWarning, "process_committed is deprecated. Use process_committed_queue instead.");
#else
	PyErr_WarnEx(PyExc_DeprecationWarning, "process_committed is deprecated. Use process_committed_queue instead.", 2);
#endif


	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;

	if (!py_dict_to_wcprop_changes(py_wcprop_changes, temp_pool, &wcprop_changes)) {
		apr_pool_destroy(temp_pool);
		return NULL;
	}

#if ONLY_SINCE_SVN(1, 6)
	RUN_SVN_WITH_POOL(temp_pool, svn_wc_process_committed4(
		svn_path_canonicalize(path, temp_pool), admobj->adm, recurse, new_revnum, 
			rev_date, rev_author, wcprop_changes, 
			remove_lock, remove_changelist, digest, temp_pool));
#else
	if (remove_changelist) {
		PyErr_SetString(PyExc_NotImplementedError, "remove_changelist only supported in svn < 1.6");
		apr_pool_destroy(temp_pool);
		return NULL;
	}
	RUN_SVN_WITH_POOL(temp_pool, svn_wc_process_committed3(svn_path_canonicalize(path, temp_pool), admobj->adm, recurse, new_revnum, 
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
		return PyString_FromFormat("<wc.WorkingCopy (closed) at 0x%p>", admobj);
	} else {
		return PyString_FromFormat("<wc.WorkingCopy at '%s'>", 
								   svn_wc_adm_access_path(admobj->adm));
	}
}

static PyObject *adm_remove_lock(PyObject *self, PyObject *args)
{
	char *path;
	AdmObject *admobj = (AdmObject *)self;
	apr_pool_t *temp_pool;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;

	RUN_SVN_WITH_POOL(temp_pool, svn_wc_remove_lock(path, admobj->adm, temp_pool))

	apr_pool_destroy(temp_pool);

	Py_RETURN_NONE;
}

static PyObject *get_ancestry(PyObject *self, PyObject *args)
{
	char *path;
	char *url;
	svn_revnum_t rev;
	apr_pool_t *temp_pool;
	AdmObject *admobj = (AdmObject *)self;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;

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
	char *dst_path, *copyfrom_url = NULL;
	svn_revnum_t copyfrom_rev = -1;
	PyObject *py_new_base_contents, *py_new_contents, *py_new_base_props,
			 *py_new_props, *notify = Py_None;
	svn_stream_t *new_contents, *new_base_contents;
	apr_hash_t *new_props, *new_base_props;

	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "sOOOO|zlO", kwnames,
			&dst_path, &py_new_base_contents, &py_new_contents, &py_new_base_props, 
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
	char *path;
	AdmObject *admobj = (AdmObject *)self;
	apr_pool_t *temp_pool;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;

	RUN_SVN_WITH_POOL(temp_pool, svn_wc_mark_missing_deleted(path, admobj->adm, temp_pool));

	apr_pool_destroy(temp_pool);

	Py_RETURN_NONE;
}

static PyObject *remove_from_revision_control(PyObject *self, PyObject *args)
{
	char *name;
	svn_boolean_t destroy_wf = FALSE, instant_error = FALSE;
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
			destroy_wf, instant_error, py_cancel_check, NULL, temp_pool));

	apr_pool_destroy(temp_pool);

	Py_RETURN_NONE;
}

#if ONLY_SINCE_SVN(1, 6)
static svn_error_t *wc_validator3(void *baton, const char *uuid, const char *url, const char *root_url, apr_pool_t *pool)
{
	PyObject *py_validator = baton, *ret;

	if (py_validator == Py_None) {
		return NULL;
	}

	ret = PyObject_CallFunction(py_validator, "sss", uuid, url, root_url);
	if (ret == NULL) {
		return py_svn_error();
	}

	Py_DECREF(ret);

	return NULL;
}

#else

static svn_error_t *wc_validator2(void *baton, const char *uuid, const char *url, svn_boolean_t root, apr_pool_t *pool)
{
	PyObject *py_validator = baton, *ret;

	if (py_validator == Py_None) {
		return NULL;
	}

	ret = PyObject_CallFunction(py_validator, "ssO", uuid, url, Py_None);
	if (ret == NULL) {
		return py_svn_error();
	}

	Py_DECREF(ret);

	return NULL;
}

#endif

static PyObject *relocate(PyObject *self, PyObject *args)
{
	char *path, *from, *to;
	AdmObject *admobj = (AdmObject *)self;
	apr_pool_t *temp_pool;
	svn_boolean_t recurse = TRUE;
	PyObject *py_validator = Py_None;

	if (!PyArg_ParseTuple(args, "sss|bO:relocate", &path, &from, &to, &recurse,
			&py_validator))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;

#if ONLY_SINCE_SVN(1, 6)
	RUN_SVN_WITH_POOL(temp_pool, svn_wc_relocate3(path, admobj->adm, from, to, recurse, wc_validator3, py_validator, temp_pool));
#else
	RUN_SVN_WITH_POOL(temp_pool, svn_wc_relocate2(path, admobj->adm, from, to, recurse, wc_validator2, py_validator, temp_pool));
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
	char *path;
	svn_boolean_t force_comparison = FALSE;
	apr_pool_t *temp_pool;
	svn_boolean_t ret;
	AdmObject *admobj = (AdmObject *)self;

	if (!PyArg_ParseTuple(args, "s|b", &path, &force_comparison))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;

	RUN_SVN_WITH_POOL(temp_pool,
		  svn_wc_text_modified_p(&ret, path, force_comparison, admobj->adm, 
			temp_pool));

	apr_pool_destroy(temp_pool);

	return PyBool_FromLong(ret);
}

static PyObject *adm_props_modified(PyObject *self, PyObject *args)
{
	char *path;
	apr_pool_t *temp_pool;
	svn_boolean_t ret;
	AdmObject *admobj = (AdmObject *)self;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;

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
	CommittedQueueObject *py_queue;

	if (!PyArg_ParseTuple(args, "O!lss", &CommittedQueue_Type, &py_queue,
			&revnum, &date, &author))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;

#if ONLY_SINCE_SVN(1, 5)
	RUN_SVN_WITH_POOL(temp_pool, svn_wc_process_committed_queue(py_queue->queue, admobj->adm, revnum, date, author, temp_pool));
#else
	{
		int i;
		for (i = 0; i < py_queue->queue->queue->nelts; i++) {
			committed_queue_item_t *cqi = APR_ARRAY_IDX(py_queue->queue->queue, i,
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

static PyObject *get_actual_target(PyObject *self, PyObject *args)
{
	char *path;
	const char *anchor = NULL, *target = NULL;
	apr_pool_t *temp_pool;
	PyObject *ret;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;

	RUN_SVN_WITH_POOL(temp_pool,
		  svn_wc_get_actual_target(svn_path_canonicalize(path, temp_pool),
								   &anchor, &target, temp_pool));

	ret = Py_BuildValue("(ss)", anchor, target);

	apr_pool_destroy(temp_pool);

	return ret;
}

static PyObject *is_wc_root(PyObject *self, PyObject *args)
{
	char *path;
	svn_boolean_t wc_root;
	apr_pool_t *temp_pool;
	AdmObject *admobj = (AdmObject *)self;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;

	RUN_SVN_WITH_POOL(temp_pool,
		  svn_wc_is_wc_root(&wc_root, path, admobj->adm, temp_pool));

	apr_pool_destroy(temp_pool);

	return PyBool_FromLong(wc_root);
}

static PyObject *transmit_text_deltas(PyObject *self, PyObject *args)
{
	char *path;
	const char *tempfile;
	svn_boolean_t fulltext;
	PyObject *editor_obj, *py_digest;
	unsigned char digest[APR_MD5_DIGESTSIZE];
	apr_pool_t *temp_pool;
	AdmObject *admobj = (AdmObject *)self;
	PyObject *ret;

	if (!PyArg_ParseTuple(args, "sbO", &path, &fulltext, &editor_obj))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;

	Py_INCREF(editor_obj);

	RUN_SVN_WITH_POOL(temp_pool,
		svn_wc_transmit_text_deltas2(&tempfile, digest,
			svn_path_canonicalize(path, temp_pool), admobj->adm, fulltext,
			&py_editor, editor_obj, temp_pool));

	py_digest = PyString_FromStringAndSize((char *)digest, APR_MD5_DIGESTSIZE);
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
	char *path;
	PyObject *editor_obj;
	apr_pool_t *temp_pool;
	AdmObject *admobj = (AdmObject *)self;
	EntryObject *py_entry;

	if (!PyArg_ParseTuple(args, "sO!O", &path, &Entry_Type, &py_entry, &editor_obj))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;

	Py_INCREF(editor_obj);

	RUN_SVN_WITH_POOL(temp_pool,
		svn_wc_transmit_prop_deltas(svn_path_canonicalize(path, temp_pool),
			admobj->adm, &(py_entry->entry), &py_editor, editor_obj, NULL, temp_pool));

	apr_pool_destroy(temp_pool);

	Py_RETURN_NONE;
}

static PyObject *retrieve(PyObject *self, PyObject *args)
{
	char *path;
	svn_wc_adm_access_t *result;
	AdmObject *admobj = (AdmObject *)self, *ret;
	apr_pool_t *pool;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	pool = Pool(NULL);
	if (pool == NULL)
		return NULL;

	RUN_SVN_WITH_POOL(pool, svn_wc_adm_retrieve(&result, admobj->adm, 
		svn_path_canonicalize(path, pool), pool));

	ret = PyObject_New(AdmObject, &Adm_Type);
	if (ret == NULL)
		return NULL;

	ret->pool = pool;
	ret->adm = result;

	return (PyObject *)ret;
}

static PyObject *probe_retrieve(PyObject *self, PyObject *args)
{
	char *path;
	svn_wc_adm_access_t *result;
	AdmObject *admobj = (AdmObject *)self, *ret;
	apr_pool_t *pool;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	pool = Pool(NULL);
	if (pool == NULL)
		return NULL;

	RUN_SVN_WITH_POOL(pool, svn_wc_adm_probe_retrieve(&result, admobj->adm, 
		svn_path_canonicalize(path, pool), pool));

	ret = PyObject_New(AdmObject, &Adm_Type);
	if (ret == NULL)
		return NULL;

	ret->pool = pool;
	ret->adm = result;

	return (PyObject *)ret;
}

static PyObject *probe_try(PyObject *self, PyObject *args)
{
	char *path;
	svn_wc_adm_access_t *result = NULL;
	AdmObject *admobj = (AdmObject *)self, *ret;
	apr_pool_t *pool;
	int levels_to_lock = -1;
	svn_boolean_t writelock = FALSE;

	if (!PyArg_ParseTuple(args, "s|bi", &path, &writelock, &levels_to_lock))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	pool = Pool(NULL);
	if (pool == NULL)
		return NULL;

	RUN_SVN_WITH_POOL(pool, svn_wc_adm_probe_try3(&result, admobj->adm, 
		svn_path_canonicalize(path, pool), writelock, levels_to_lock,
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
	svn_boolean_t resolve_props, resolve_tree, resolve_text;
	int depth;
#if ONLY_SINCE_SVN(1, 5)
	svn_wc_conflict_choice_t conflict_choice;
#else
	int conflict_choice;
#endif
	PyObject *notify_func = Py_None;
	char *path;

	if (!PyArg_ParseTuple(args, "sbbbii|O", &path, &resolve_text,
						  &resolve_props, &resolve_tree, &depth,
						  &conflict_choice, &notify_func))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;

#if ONLY_SINCE_SVN(1, 6)
	RUN_SVN_WITH_POOL(temp_pool,
		  svn_wc_resolved_conflict4(path, admobj->adm, resolve_text, 
										resolve_props, resolve_tree, depth,
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
			  svn_wc_resolved_conflict3(path, admobj->adm, resolve_text, 
											resolve_props, depth,
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
			  svn_wc_resolved_conflict2(path, admobj->adm, resolve_text,
											resolve_props,
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
	char *path;
	apr_pool_t *temp_pool;
	PyObject *ret;
	AdmObject *admobj = (AdmObject *)self;
	svn_boolean_t text_conflicted, prop_conflicted, tree_conflicted;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;

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
static PyObject *ra_status(PyObject *self, PyObject *args)
{
	char *path;
	svn_wc_status2_t *st;
	apr_pool_t *temp_pool;
	PyObject *ret;
	AdmObject *admobj = (AdmObject *)self;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	ADM_CHECK_CLOSED(admobj);

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;

	RUN_SVN_WITH_POOL(temp_pool, 
			svn_wc_status2(
				&st,
				svn_path_canonicalize(svn_path_join(svn_wc_adm_access_path(admobj->adm), path, temp_pool), temp_pool),
				admobj->adm,
				temp_pool));

	ret = py_status(st);

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
	{ "status", (PyCFunction)ra_status, METH_VARARGS, "status(wc_path) -> Status" },
	{ NULL, }
};

static PyTypeObject Adm_Type = {
	PyObject_HEAD_INIT(NULL) 0,
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

static void committed_queue_dealloc(PyObject *self)
{
	apr_pool_destroy(((CommittedQueueObject *)self)->pool);
	PyObject_Del(self);
}

static PyObject *committed_queue_repr(PyObject *self)
{
	CommittedQueueObject *cqobj = (CommittedQueueObject *)self;

	return PyString_FromFormat("<wc.CommittedQueue at 0x%p>", cqobj->queue);
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

static PyObject *committed_queue_queue(CommittedQueueObject *self, PyObject *args)
{
	char *path;
	AdmObject *admobj;
	PyObject *py_wcprop_changes = Py_None;
	svn_boolean_t remove_lock = FALSE, remove_changelist = FALSE;
	char *digest = NULL;
	svn_boolean_t recurse = FALSE;
	apr_pool_t *temp_pool;
	apr_array_header_t *wcprop_changes = NULL;
	int digest_len = 0;

	if (!PyArg_ParseTuple(args, "sO!|bObbz#", &path, &Adm_Type, &admobj,
						  &recurse, &py_wcprop_changes, &remove_lock,
						  &remove_changelist, &digest, &digest_len))
		return NULL;

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;

	if (!py_dict_to_wcprop_changes(py_wcprop_changes, self->pool, &wcprop_changes)) {
		apr_pool_destroy(temp_pool);
		return NULL;
	}

	path = apr_pstrdup(self->pool, path);
	if (path == NULL) {
		PyErr_NoMemory();
		return NULL;
	}

	if (digest != NULL) {
		if (digest_len != APR_MD5_DIGESTSIZE) {
			PyErr_SetString(PyExc_ValueError, "Invalid size for md5 digest");
			apr_pool_destroy(temp_pool);
			return NULL;
		}
		digest = apr_pstrdup(self->pool, digest);
		if (digest == NULL) {
			PyErr_NoMemory();
			return NULL;
		}
	}

	RUN_SVN_WITH_POOL(temp_pool, 
		svn_wc_queue_committed(&self->queue, path, admobj->adm, recurse,
							   wcprop_changes, remove_lock, remove_changelist,
							   (unsigned char *)digest, temp_pool));

	apr_pool_destroy(temp_pool);

	Py_RETURN_NONE;
}

static PyMethodDef committed_queue_methods[] = {
	{ "queue", (PyCFunction)committed_queue_queue, METH_VARARGS,
		"S.queue(path, adm, recurse, wcprop_changes, remove_lock, remove_changelist, digest)" },
	{ NULL }
};

static PyTypeObject CommittedQueue_Type = {
	PyObject_HEAD_INIT(NULL) 0,
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

/** 
 * Determine the revision status of a specified working copy.
 *
 * :return: Tuple with minimum and maximum revnums found, whether the 
 * working copy was switched and whether it was modified.
 */
static PyObject *revision_status(PyObject *self, PyObject *args, PyObject *kwargs)
{
	char *kwnames[] = { "wc_path", "trail_url", "committed",  NULL };
	char *wc_path, *trail_url=NULL;
	bool committed=false;
	PyObject *ret;
	 svn_wc_revision_status_t *revstatus;
	apr_pool_t *temp_pool;

	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "s|zb", kwnames, &wc_path,
									 &trail_url, &committed))
		return NULL;

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(temp_pool, 
			svn_wc_revision_status(
				&revstatus, 
				svn_path_canonicalize(wc_path, temp_pool),
				trail_url,
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
	char *name;
	apr_pool_t *pool;
	svn_boolean_t ret;

	if (!PyArg_ParseTuple(args, "s", &name))
		return NULL;

	pool = Pool(NULL);
	if (pool == NULL)
		return NULL;

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
	ret = PyString_FromString(dir);
	apr_pool_destroy(pool);
	return ret;
}

static PyObject *set_adm_dir(PyObject *self, PyObject *args)
{
	apr_pool_t *temp_pool;
	char *name;

	if (!PyArg_ParseTuple(args, "s", &name))
		return NULL;

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(temp_pool, svn_wc_set_adm_dir(name, temp_pool));
	apr_pool_destroy(temp_pool);
	Py_RETURN_NONE;
}

static PyObject *get_pristine_copy_path(PyObject *self, PyObject *args)
{
	apr_pool_t *pool;
	const char *pristine_path;
	char *path;
	PyObject *ret;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	pool = Pool(NULL);
	if (pool == NULL)
		return NULL;
#if PY_VERSION_HEX < 0x02050000
	PyErr_Warn(PyExc_DeprecationWarning, "get_pristine_copy_path is deprecated. Use get_pristine_contents instead.");
#else
	PyErr_WarnEx(PyExc_DeprecationWarning, "get_pristine_copy_path is deprecated. Use get_pristine_contents instead.", 2);
#endif
	RUN_SVN_WITH_POOL(pool,
		  svn_wc_get_pristine_copy_path(svn_path_canonicalize(path, pool),
										&pristine_path, pool));
	ret = PyString_FromString(pristine_path);
	apr_pool_destroy(pool);
	return ret;
}

static PyObject *get_pristine_contents(PyObject *self, PyObject *args)
{
	char *path;
	apr_pool_t *temp_pool;
#if ONLY_SINCE_SVN(1, 6)
	apr_pool_t *stream_pool;
	StreamObject *ret;
	svn_stream_t *stream;
#else
	PyObject *ret;
	const char *pristine_path;
#endif

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

#if ONLY_SINCE_SVN(1, 6)
	stream_pool = Pool(NULL);
	if (stream_pool == NULL)
		return NULL;

	temp_pool = Pool(stream_pool);
	if (temp_pool == NULL) {
		apr_pool_destroy(stream_pool);
		return NULL;
	}

	RUN_SVN_WITH_POOL(stream_pool, svn_wc_get_pristine_contents(&stream, svn_path_canonicalize(path, temp_pool), stream_pool, temp_pool));
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
#else
	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(temp_pool, svn_wc_get_pristine_copy_path(svn_path_canonicalize(path, temp_pool), &pristine_path, temp_pool));
	ret = PyFile_FromString((char *)pristine_path, "rb");
	apr_pool_destroy(temp_pool);
	return ret;
#endif
}

static PyObject *ensure_adm(PyObject *self, PyObject *args, PyObject *kwargs)
{
	char *path, *uuid, *url;
	char *repos=NULL; 
	svn_revnum_t rev=-1;
	apr_pool_t *pool;
	char *kwnames[] = { "path", "uuid", "url", "repos", "rev", "depth", NULL };
	svn_depth_t depth = svn_depth_infinity;

	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "sss|sli", kwnames, 
									 &path, &uuid, &url, &repos, &rev, &depth))
		return NULL;

	pool = Pool(NULL);
	if (pool == NULL)
		return NULL;
#if ONLY_SINCE_SVN(1, 5)
	RUN_SVN_WITH_POOL(pool, 
					  svn_wc_ensure_adm3(svn_path_canonicalize(path, pool),
										 uuid, url, repos, rev, depth, pool));
#else
	if (depth != svn_depth_infinity) {
		PyErr_SetString(PyExc_NotImplementedError, 
						"depth != infinity not supported with svn < 1.5");
		apr_pool_destroy(pool);
		return NULL;
	}
	RUN_SVN_WITH_POOL(pool, 
					  svn_wc_ensure_adm2(svn_path_canonicalize(path, pool),
										 uuid, url, repos, rev, pool));
#endif
	apr_pool_destroy(pool);
	Py_RETURN_NONE;
}

static PyObject *check_wc(PyObject *self, PyObject *args)
{
	char *path;
	apr_pool_t *pool;
	int wc_format;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	pool = Pool(NULL);
	if (pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(pool, svn_wc_check_wc(svn_path_canonicalize(path, pool), &wc_format, pool));
	apr_pool_destroy(pool);
	return PyLong_FromLong(wc_format);
}

static PyObject *cleanup_wc(PyObject *self, PyObject *args, PyObject *kwargs)
{
	char *path;
	char *diff3_cmd = NULL;
	char *kwnames[] = { "path", "diff3_cmd", NULL };
	apr_pool_t *temp_pool;

	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "s|z", kwnames, 
									 &path, &diff3_cmd)) 
		return NULL;

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(temp_pool, 
				svn_wc_cleanup2(path, diff3_cmd, py_cancel_check, NULL,
								temp_pool));
	apr_pool_destroy(temp_pool);

	Py_RETURN_NONE;
}

static PyObject *match_ignore_list(PyObject *self, PyObject *args)
{
#if ONLY_SINCE_SVN(1, 5)
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
#else
	PyErr_SetNone(PyExc_NotImplementedError);
	return NULL;
#endif
}

static PyMethodDef wc_methods[] = {
	{ "check_wc", check_wc, METH_VARARGS, "check_wc(path) -> version\n"
		"Check whether path contains a Subversion working copy\n"
		"return the workdir version"},
	{ "cleanup", (PyCFunction)cleanup_wc, METH_VARARGS|METH_KEYWORDS, "cleanup(path, diff3_cmd=None)\n" },
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
	{ "revision_status", (PyCFunction)revision_status, METH_KEYWORDS|METH_VARARGS, "revision_status(wc_path, trail_url=None, committed=False) -> (min_rev, max_rev, switched, modified)" },
	{ "version", (PyCFunction)version, METH_NOARGS,
		"version() -> (major, minor, patch, tag)\n\n"
		"Version of libsvn_wc currently used."
	},
	{ "api_version", (PyCFunction)api_version, METH_NOARGS,
		"api_version() -> (major, minor, patch, tag)\n\n"
		"Version of libsvn_wc Subvertpy was compiled against."
	},
	{ "match_ignore_list", (PyCFunction)match_ignore_list, METH_VARARGS,
		"match_ignore_list(str, patterns) -> bool" },
	{ "get_actual_target", (PyCFunction)get_actual_target, METH_VARARGS,
		"get_actual_target(path) -> (anchor, target)" },
	{ NULL, }
};

void initwc(void)
{
	PyObject *mod;

	if (PyType_Ready(&Entry_Type) < 0)
		return;

	if (PyType_Ready(&Status_Type) < 0)
		return;

	if (PyType_Ready(&Adm_Type) < 0)
		return;

	if (PyType_Ready(&Editor_Type) < 0)
		return;

	if (PyType_Ready(&FileEditor_Type) < 0)
		return;

	if (PyType_Ready(&DirectoryEditor_Type) < 0)
		return;

	if (PyType_Ready(&TxDeltaWindowHandler_Type) < 0)
		return;

	if (PyType_Ready(&Stream_Type) < 0)
		return;

	if (PyType_Ready(&CommittedQueue_Type) < 0)
		return;

	apr_initialize();

	mod = Py_InitModule3("wc", wc_methods, "Working Copies");
	if (mod == NULL)
		return;

	PyModule_AddIntConstant(mod, "SCHEDULE_NORMAL", 0);
	PyModule_AddIntConstant(mod, "SCHEDULE_ADD", 1);
	PyModule_AddIntConstant(mod, "SCHEDULE_DELETE", 2);
	PyModule_AddIntConstant(mod, "SCHEDULE_REPLACE", 3);

#if ONLY_SINCE_SVN(1, 5)
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
#endif

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

#if ONLY_SINCE_SVN(1, 5)
	PyModule_AddIntConstant(mod, "CONFLICT_CHOOSE_POSTPONE", svn_wc_conflict_choose_postpone);
	PyModule_AddIntConstant(mod, "CONFLICT_CHOOSE_BASE", svn_wc_conflict_choose_base);
	PyModule_AddIntConstant(mod, "CONFLICT_CHOOSE_THEIRS_FULL", svn_wc_conflict_choose_theirs_full);
	PyModule_AddIntConstant(mod, "CONFLICT_CHOOSE_MINE_FULL", svn_wc_conflict_choose_mine_full);
	PyModule_AddIntConstant(mod, "CONFLICT_CHOOSE_THEIRS_CONFLICT", svn_wc_conflict_choose_theirs_conflict);
	PyModule_AddIntConstant(mod, "CONFLICT_CHOOSE_MINE_CONFLICT", svn_wc_conflict_choose_mine_conflict);
	PyModule_AddIntConstant(mod, "CONFLICT_CHOOSE_MERGED", svn_wc_conflict_choose_merged);
#endif

	PyModule_AddObject(mod, "WorkingCopy", (PyObject *)&Adm_Type);
	Py_INCREF(&Adm_Type);

	PyModule_AddObject(mod, "CommittedQueue", (PyObject *)&CommittedQueue_Type);
	Py_INCREF(&CommittedQueue_Type);
}

