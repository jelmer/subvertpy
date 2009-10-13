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
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 */
#include <stdbool.h>
#include <Python.h>
#include <apr_general.h>
#include <svn_fs.h>
#include <svn_repos.h>

#include "util.h"

extern PyTypeObject FileSystemRoot_Type;
extern PyTypeObject Repository_Type;
extern PyTypeObject FileSystem_Type;
extern PyTypeObject Stream_Type;

typedef struct {
	PyObject_HEAD
	svn_stream_t *stream;
	apr_pool_t *pool;
} StreamObject;

typedef struct { 
	PyObject_HEAD
    apr_pool_t *pool;
    svn_repos_t *repos;
} RepositoryObject;

static PyObject *repos_create(PyObject *self, PyObject *args)
{
	char *path;
	PyObject *config=Py_None, *fs_config=Py_None;
    svn_repos_t *repos;
    apr_pool_t *pool;
    apr_hash_t *hash_config, *hash_fs_config;
	RepositoryObject *ret;

	if (!PyArg_ParseTuple(args, "s|OO", &path, &config, &fs_config))
		return NULL;

    pool = Pool(NULL);
	if (pool == NULL)
		return NULL;
    hash_config = config_hash_from_object(config, pool);
	if (hash_config == NULL)
		return NULL;
    hash_fs_config = apr_hash_make(pool); /* FIXME */
	if (hash_fs_config == NULL) {
		PyErr_SetString(PyExc_RuntimeError, "Unable to create fs config hash");
		return NULL;
	}
    RUN_SVN_WITH_POOL(pool, svn_repos_create(&repos, path, NULL, NULL, 
                hash_config, hash_fs_config, pool));

	ret = PyObject_New(RepositoryObject, &Repository_Type);
	if (ret == NULL)
		return NULL;

	ret->pool = pool;
	ret->repos = repos;

    return (PyObject *)ret;
}

static void repos_dealloc(PyObject *self)
{
	RepositoryObject *repos = (RepositoryObject *)self;

	apr_pool_destroy(repos->pool);
	PyObject_Del(repos);
}

static PyObject *repos_init(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
	char *path;
	char *kwnames[] = { "path", NULL };
	svn_error_t *err;
	RepositoryObject *ret;

	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "s", kwnames, &path))
		return NULL;

	ret = PyObject_New(RepositoryObject, &Repository_Type);
	if (ret == NULL)
		return NULL;

	ret->pool = Pool(NULL);
	if (ret->pool == NULL)
		return NULL;
	Py_BEGIN_ALLOW_THREADS
	err = svn_repos_open(&ret->repos, path, ret->pool);
	Py_END_ALLOW_THREADS
    if (!check_error(err)) {
		Py_DECREF(ret);
		return NULL;
	}

	return (PyObject *)ret;
}

typedef struct {
	PyObject_HEAD
	apr_pool_t *pool;
	svn_fs_root_t *root;
} FileSystemRootObject;

typedef struct {
	PyObject_HEAD
	RepositoryObject *repos;
	apr_pool_t *pool;
	svn_fs_t *fs;
} FileSystemObject;

static PyObject *repos_fs(PyObject *self)
{
	RepositoryObject *reposobj = (RepositoryObject *)self;
	FileSystemObject *ret;
	svn_fs_t *fs;

	fs = svn_repos_fs(reposobj->repos);

	if (fs == NULL) {
		PyErr_SetString(PyExc_RuntimeError, "Unable to obtain fs handle");
		return NULL;
	}

	ret = PyObject_New(FileSystemObject, &FileSystem_Type);
	if (ret == NULL)
		return NULL;

	ret->fs = fs;
	ret->repos = reposobj;
	ret->pool = reposobj->pool;
	Py_INCREF(reposobj);

	return (PyObject *)ret;
}

static PyObject *fs_get_uuid(PyObject *self)
{
	FileSystemObject *fsobj = (FileSystemObject *)self;
	const char *uuid;
	PyObject *ret;
	apr_pool_t *temp_pool;

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(temp_pool, svn_fs_get_uuid(fsobj->fs, &uuid, temp_pool));
	ret = PyString_FromString(uuid);
	apr_pool_destroy(temp_pool);

	return ret;
}

static PyObject *fs_get_youngest_revision(FileSystemObject *self)
{
	svn_revnum_t rev;
	apr_pool_t *temp_pool;
	PyObject *ret;

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(temp_pool, svn_fs_youngest_rev(&rev, self->fs, temp_pool));
	ret = PyInt_FromLong(rev);
	apr_pool_destroy(temp_pool);

	return ret;
}

static PyObject *fs_get_revision_root(FileSystemObject *self, PyObject *args)
{
	svn_revnum_t rev;
	FileSystemRootObject *ret;
	apr_pool_t *pool;
	svn_fs_root_t *root;

	if (!PyArg_ParseTuple(args, "l", &rev))
		return NULL;

	pool = Pool(NULL);
	if (pool == NULL)
		return NULL;

	RUN_SVN_WITH_POOL(pool, svn_fs_revision_root(&root, self->fs, rev, pool));

	ret = PyObject_New(FileSystemRootObject, &FileSystemRoot_Type);
	if (ret == NULL)
		return NULL;

	ret->root = root;
	ret->pool = pool;

	return (PyObject *)ret;
}

static PyObject *fs_get_revision_proplist(FileSystemObject *self, PyObject *args)
{
	svn_revnum_t rev;
	PyObject *ret;
	apr_pool_t *temp_pool;
	apr_hash_t *props;

	if (!PyArg_ParseTuple(args, "l", &rev))
		return NULL;

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;

	RUN_SVN_WITH_POOL(temp_pool, svn_fs_revision_proplist(&props, self->fs, rev, temp_pool));

	ret = prop_hash_to_dict(props);

	apr_pool_destroy(temp_pool);

	return (PyObject *)ret;
}

static PyMethodDef fs_methods[] = {
	{ "get_uuid", (PyCFunction)fs_get_uuid, METH_NOARGS, NULL },
	{ "youngest_revision", (PyCFunction)fs_get_youngest_revision, METH_NOARGS, NULL },
	{ "revision_root", (PyCFunction)fs_get_revision_root, METH_VARARGS, NULL },
	{ "revision_proplist", (PyCFunction)fs_get_revision_proplist, METH_VARARGS, NULL },
	{ NULL, }
};

static void fs_dealloc(PyObject *self)
{
	FileSystemObject *fsobj = (FileSystemObject *)self;

	Py_DECREF(fsobj->repos);
	apr_pool_destroy(fsobj->pool);
}

PyTypeObject FileSystem_Type = {
	PyObject_HEAD_INIT(NULL) 0,
	"repos.FileSystem", /*	const char *tp_name;  For printing, in format "<module>.<name>" */
	sizeof(FileSystemObject), 
	0,/*	Py_ssize_t tp_basicsize, tp_itemsize;  For allocation */
	
	/* Methods to implement standard operations */
	
	fs_dealloc, /*	destructor tp_dealloc;	*/
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
	fs_methods, /*	struct PyMethodDef *tp_methods;	*/

};

static PyObject *repos_load_fs(PyObject *self, PyObject *args, PyObject *kwargs)
{
	const char *parent_dir = "";
	PyObject *dumpstream, *feedback_stream, *cancel_func = Py_None;
	bool use_pre_commit_hook = false, use_post_commit_hook = false;
	char *kwnames[] = { "dumpstream", "feedback_stream", "uuid_action",
		                "parent_dir", "use_pre_commit_hook", 
						"use_post_commit_hook", "cancel_func", NULL };
	int uuid_action;
	apr_pool_t *temp_pool;
	RepositoryObject *reposobj = (RepositoryObject *)self;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OOi|sbbO", kwnames,
								&dumpstream, &feedback_stream, &uuid_action,
								&parent_dir, &use_pre_commit_hook, 
								&use_post_commit_hook,
								&cancel_func))
		return NULL;

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(temp_pool, svn_repos_load_fs2(reposobj->repos, 
				new_py_stream(temp_pool, dumpstream), 
				new_py_stream(temp_pool, feedback_stream),
				uuid_action, parent_dir, use_pre_commit_hook, 
				use_post_commit_hook, py_cancel_func, (void *)cancel_func,
				reposobj->pool));
	apr_pool_destroy(temp_pool);
	Py_RETURN_NONE;
}

static PyObject *repos_delete(PyObject *self, PyObject *args)
{
	char *path;
	apr_pool_t *temp_pool;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(temp_pool, svn_repos_delete(path, temp_pool));

	apr_pool_destroy(temp_pool);

	Py_RETURN_NONE;
}

static PyObject *repos_hotcopy(RepositoryObject *self, PyObject *args)
{
	char *src_path, *dest_path;
	svn_boolean_t clean_logs = FALSE;
	apr_pool_t *temp_pool;

	if (!PyArg_ParseTuple(args, "ss|b", &src_path, &dest_path, &clean_logs))
		return NULL;

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;

	RUN_SVN_WITH_POOL(temp_pool, svn_repos_hotcopy(src_path, dest_path, clean_logs, temp_pool));

	apr_pool_destroy(temp_pool);

	Py_RETURN_NONE;
}

static PyMethodDef repos_module_methods[] = {
	{ "create", repos_create, METH_VARARGS, NULL },
	{ "delete", repos_delete, METH_VARARGS, NULL },
	{ "hotcopy", repos_hotcopy, METH_VARARGS, NULL },
	{ NULL, }
};

#if SVN_VER_MAJOR >= 1 && SVN_VER_MINOR >= 5
static PyObject *repos_has_capability(RepositoryObject *self, PyObject *args)
{
	char *name;
	svn_boolean_t has;
	apr_pool_t *temp_pool;
	if (!PyArg_ParseTuple(args, "s", &name))
		return NULL;
	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(temp_pool, svn_repos_has_capability(self->repos, &has, name, temp_pool));
	apr_pool_destroy(temp_pool);
	return PyBool_FromLong(has);
}
#endif

static PyMethodDef repos_methods[] = {
	{ "load_fs", (PyCFunction)repos_load_fs, METH_VARARGS|METH_KEYWORDS, NULL },
	{ "fs", (PyCFunction)repos_fs, METH_NOARGS, NULL },
#if SVN_VER_MAJOR >= 1 && SVN_VER_MINOR >= 5
	{ "has_capability", (PyCFunction)repos_has_capability, METH_VARARGS, NULL },
#endif
	{ NULL, }
};

PyTypeObject Repository_Type = {
	PyObject_HEAD_INIT(NULL) 0,
	"repos.Repository", /*	const char *tp_name;  For printing, in format "<module>.<name>" */
	sizeof(RepositoryObject), 
	0,/*	Py_ssize_t tp_basicsize, tp_itemsize;  For allocation */
	
	/* Methods to implement standard operations */
	
	repos_dealloc, /*	destructor tp_dealloc;	*/
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
	repos_methods, /*	struct PyMethodDef *tp_methods;	*/
	NULL, /*	struct PyMemberDef *tp_members;	*/
	NULL, /*	struct PyGetSetDef *tp_getset;	*/
	NULL, /*	struct _typeobject *tp_base;	*/
	NULL, /*	PyObject *tp_dict;	*/
	NULL, /*	descrgetfunc tp_descr_get;	*/
	NULL, /*	descrsetfunc tp_descr_set;	*/
	0, /*	Py_ssize_t tp_dictoffset;	*/
	NULL, /*	initproc tp_init;	*/
	NULL, /*	allocfunc tp_alloc;	*/
	repos_init, /*	newfunc tp_new;	*/

};

static void fs_root_dealloc(PyObject *self)
{
	FileSystemRootObject *fsobj = (FileSystemRootObject *)self;

	apr_pool_destroy(fsobj->pool);
	PyObject_DEL(fsobj);
}

static PyObject *py_string_from_svn_node_id(const svn_fs_id_t *id)
{
	apr_pool_t *temp_pool;
	temp_pool = Pool(NULL);
	svn_string_t *str;
	if (temp_pool == NULL)
		return NULL;
	str = svn_fs_unparse_id(id, temp_pool);
	if (str == NULL) {
		apr_pool_destroy(temp_pool);
		return NULL;
	}
	return PyString_FromStringAndSize(str->data, str->len);
}

static PyObject *fs_root_paths_changed(FileSystemRootObject *self)
{
	apr_pool_t *temp_pool;
	apr_hash_t *changed_paths;
	const char *key;
	apr_ssize_t klen;
	apr_hash_index_t *idx;
	PyObject *ret;
	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(temp_pool, 
					  svn_fs_paths_changed(&changed_paths, self->root, temp_pool));
	ret = PyDict_New();
	for (idx = apr_hash_first(temp_pool, changed_paths); idx != NULL;
		 idx = apr_hash_next(idx)) {
		PyObject *py_val, *py_node_id;
		svn_fs_path_change_t *val;
		apr_hash_this(idx, (const void **)&key, &klen, (void **)&val);
		py_node_id = py_string_from_svn_node_id(val->node_rev_id);
		if (py_node_id == NULL) {
			apr_pool_destroy(temp_pool);
			PyObject_Del(ret);
			return NULL;
		}
		py_val = Py_BuildValue("(sibb)", py_node_id,
							   val->change_kind, val->text_mod, val->prop_mod);
		if (py_val == NULL) {
			apr_pool_destroy(temp_pool);
			PyObject_Del(ret);
			return NULL;
		}
		PyDict_SetItemString(ret, key, py_val);
		Py_DECREF(py_val);
	}
	apr_pool_destroy(temp_pool);
	return ret;
}

static PyObject *fs_root_is_dir(FileSystemRootObject *self, PyObject *args)
{
	svn_boolean_t is_dir;
	apr_pool_t *temp_pool;
	char *path;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(temp_pool, svn_fs_is_dir(&is_dir, self->root, 
											   path, temp_pool));
	apr_pool_destroy(temp_pool);
	return PyBool_FromLong(is_dir);
}

static PyObject *fs_root_is_file(FileSystemRootObject *self, PyObject *args)
{
	svn_boolean_t is_file;
	apr_pool_t *temp_pool;
	char *path;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(temp_pool, svn_fs_is_file(&is_file, self->root, 
											   path, temp_pool));
	apr_pool_destroy(temp_pool);
	return PyBool_FromLong(is_file);
}

static PyObject *fs_root_file_length(FileSystemRootObject *self, PyObject *args)
{
	svn_filesize_t filesize;
	apr_pool_t *temp_pool;
	char *path;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(temp_pool, svn_fs_file_length(&filesize, self->root, 
											   path, temp_pool));
	apr_pool_destroy(temp_pool);
	return PyInt_FromLong(filesize);
}

static PyObject *fs_root_file_contents(FileSystemRootObject *self, PyObject *args)
{
	svn_stream_t *stream;
	apr_pool_t *pool;
	StreamObject *ret;
	char *path;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	pool = Pool(NULL);
	if (pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(pool, svn_fs_file_contents(&stream, self->root, 
											   path, pool));

	ret = PyObject_New(StreamObject, &Stream_Type);
	if (ret == NULL)
		return NULL;

	ret->pool = pool;
	ret->stream = stream;

    return (PyObject *)ret;
}

static PyMethodDef fs_root_methods[] = {
	{ "paths_changed", (PyCFunction)fs_root_paths_changed, METH_NOARGS, NULL },
	{ "is_dir", (PyCFunction)fs_root_is_dir, METH_VARARGS, NULL },
	{ "is_file", (PyCFunction)fs_root_is_file, METH_VARARGS, NULL },
	{ "file_length", (PyCFunction)fs_root_file_length, METH_VARARGS, NULL },
	{ "file_content", (PyCFunction)fs_root_file_contents, METH_VARARGS, NULL },
	{ NULL, }
};

PyTypeObject FileSystemRoot_Type = {
	PyObject_HEAD_INIT(NULL) 0,
	"repos.FileSystemRoot", /*	const char *tp_name;  For printing, in format "<module>.<name>" */
	sizeof(FileSystemRootObject), 
	0,/*	Py_ssize_t tp_basicsize, tp_itemsize;  For allocation */
	
	/* Methods to implement standard operations */
	
	fs_root_dealloc, /*	destructor tp_dealloc;	*/
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
	fs_root_methods, /*	struct PyMethodDef *tp_methods;	*/
};


static void stream_dealloc(PyObject *self)
{
	StreamObject *streamself = (StreamObject *)self;

	apr_pool_destroy(streamself->pool);
}

static PyObject *stream_init(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
	char *kwnames[] = { NULL };
	StreamObject *ret;

	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "", kwnames))
		return NULL;

	ret = PyObject_New(StreamObject, &Stream_Type);
	if (ret == NULL)
		return NULL;

	ret->pool = Pool(NULL);
	if (ret->pool == NULL)
		return NULL;
	ret->stream = svn_stream_empty(ret->pool);

	return (PyObject *)ret;
}

static PyObject *stream_close(StreamObject *self)
{
	svn_stream_close(self->stream);
	Py_RETURN_NONE;
}

static PyObject *stream_write(StreamObject *self, PyObject *args)
{
	char *buffer;
	size_t len;
	if (!PyArg_ParseTuple(args, "s#", &buffer, &len))
		return NULL;

	RUN_SVN(svn_stream_write(self->stream, buffer, &len));

	return PyInt_FromLong(len);
}

static PyObject *stream_read(StreamObject *self, PyObject *args)
{
	PyObject *ret;
	apr_pool_t *temp_pool;
	long len = -1;
	if (!PyArg_ParseTuple(args, "|l", &len))
		return NULL;

	temp_pool = Pool(NULL);
	if (temp_pool == NULL) 
		return NULL;
	if (len != -1) {
		char *buffer;
		apr_size_t size = len;
		buffer = apr_palloc(temp_pool, len);
		if (buffer == NULL) {
			PyErr_NoMemory();
			apr_pool_destroy(temp_pool);
			return NULL;
		}
		RUN_SVN_WITH_POOL(temp_pool, svn_stream_read(self->stream, buffer, &size));
		ret = PyString_FromStringAndSize(buffer, size);
		apr_pool_destroy(temp_pool);
		return ret;
	} else {
		svn_string_t *result;
		RUN_SVN_WITH_POOL(temp_pool, svn_string_from_stream(&result, 
							   self->stream,
							   temp_pool,
							   temp_pool));
		ret = PyString_FromStringAndSize(result->data, result->len);
		apr_pool_destroy(temp_pool);
		return ret;
	}
}

static PyMethodDef stream_methods[] = {
	{ "read", (PyCFunction)stream_read, METH_VARARGS, NULL },
	{ "write", (PyCFunction)stream_write, METH_VARARGS, NULL },
	{ "close", (PyCFunction)stream_close, METH_NOARGS, NULL },
	{ NULL, }
};

PyTypeObject Stream_Type = {
	PyObject_HEAD_INIT(NULL) 0,
	"repos.Stream", /*	const char *tp_name;  For printing, in format "<module>.<name>" */
	sizeof(StreamObject), 
	0,/*	Py_ssize_t tp_basicsize, tp_itemsize;  For allocation */
	
	/* Methods to implement standard operations */
	
	stream_dealloc, /*	destructor tp_dealloc;	*/
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
	stream_methods, /*	struct PyMethodDef *tp_methods;	*/
	NULL, /*	struct PyMemberDef *tp_members;	*/
	NULL, /*	struct PyGetSetDef *tp_getset;	*/
	NULL, /*	struct _typeobject *tp_base;	*/
	NULL, /*	PyObject *tp_dict;	*/
	NULL, /*	descrgetfunc tp_descr_get;	*/
	NULL, /*	descrsetfunc tp_descr_set;	*/
	0, /*	Py_ssize_t tp_dictoffset;	*/
	NULL, /*	initproc tp_init;	*/
	NULL, /*	allocfunc tp_alloc;	*/
	stream_init, /* tp_new tp_new */
};

void initrepos(void)
{
	static apr_pool_t *pool;
	PyObject *mod;

	if (PyType_Ready(&Repository_Type) < 0)
		return;

	if (PyType_Ready(&FileSystem_Type) < 0)
		return;

	if (PyType_Ready(&FileSystemRoot_Type) < 0)
		return;

	if (PyType_Ready(&Stream_Type) < 0)
		return;

	apr_initialize();
	pool = Pool(NULL);
	if (pool == NULL)
		return;

	svn_fs_initialize(pool);

	mod = Py_InitModule3("repos", repos_module_methods, "Local repository management");
	if (mod == NULL)
		return;

	PyModule_AddObject(mod, "LOAD_UUID_DEFAULT", PyLong_FromLong(svn_repos_load_uuid_default));
	PyModule_AddObject(mod, "LOAD_UUID_IGNORE", PyLong_FromLong(svn_repos_load_uuid_ignore));
	PyModule_AddObject(mod, "LOAD_UUID_FORCE", PyLong_FromLong(svn_repos_load_uuid_force));

	PyModule_AddObject(mod, "PATH_CHANGE_MODIFY", PyInt_FromLong(svn_fs_path_change_modify));
	PyModule_AddObject(mod, "PATH_CHANGE_ADD", PyInt_FromLong(svn_fs_path_change_add));
	PyModule_AddObject(mod, "PATH_CHANGE_DELETE", PyInt_FromLong(svn_fs_path_change_delete));
	PyModule_AddObject(mod, "PATH_CHANGE_REPLACE", PyInt_FromLong(svn_fs_path_change_replace));

	PyModule_AddObject(mod, "Repository", (PyObject *)&Repository_Type);
	Py_INCREF(&Repository_Type);

	PyModule_AddObject(mod, "Stream", (PyObject *)&Stream_Type);
	Py_INCREF(&Stream_Type);
}
