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
#include <stdbool.h>
#include <Python.h>
#include <apr_general.h>
#include <svn_fs.h>
#include <svn_path.h>
#include <svn_repos.h>
#include <apr_md5.h>

#include "util.h"

extern PyTypeObject FileSystemRoot_Type;
extern PyTypeObject Repository_Type;
extern PyTypeObject FileSystem_Type;
extern PyTypeObject Stream_Type;

typedef struct { 
	PyObject_HEAD
    apr_pool_t *pool;
    svn_repos_t *repos;
} RepositoryObject;

static PyObject *repos_create(PyObject *self, PyObject *args)
{
	char *path;
	PyObject *config=Py_None, *fs_config=Py_None;
	svn_repos_t *repos = NULL;
	apr_pool_t *pool;
	apr_hash_t *hash_config, *hash_fs_config;
	RepositoryObject *ret;

	if (!PyArg_ParseTuple(args, "s|OO:create", &path, &config, &fs_config))
		return NULL;

    pool = Pool(NULL);
	if (pool == NULL)
		return NULL;
    hash_config = config_hash_from_object(config, pool);
	if (hash_config == NULL) {
		apr_pool_destroy(pool);
		return NULL;
	}
	hash_fs_config = apr_hash_make(pool); /* FIXME */
	if (hash_fs_config == NULL) {
		PyErr_SetString(PyExc_RuntimeError, "Unable to create fs config hash");
		return NULL;
	}
	RUN_SVN_WITH_POOL(pool, svn_repos_create(&repos,
				svn_dirent_internal_style(path, pool), NULL, NULL,
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
	if (ret->pool == NULL) {
		PyObject_DEL(ret);
		return NULL;
	}
	Py_BEGIN_ALLOW_THREADS
	err = svn_repos_open(&ret->repos, svn_dirent_internal_style(path, ret->pool),
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

typedef struct {
	PyObject_HEAD
	apr_pool_t *pool;
	svn_fs_root_t *root;
} FileSystemRootObject;

typedef struct {
	PyObject_HEAD
	RepositoryObject *repos;
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
	ret = PyText_FromString(uuid);
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
	PyObject_DEL(fsobj);
}

PyTypeObject FileSystem_Type = {
	PyVarObject_HEAD_INIT(NULL, 0)
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
	const char *parent_dir = NULL;
	PyObject *dumpstream, *feedback_stream;
	unsigned char use_pre_commit_hook = 0, use_post_commit_hook = 0;
	char *kwnames[] = { "dumpstream", "feedback_stream", "uuid_action",
		                "parent_dir", "use_pre_commit_hook", 
						"use_post_commit_hook", NULL };
	int uuid_action;
	apr_pool_t *temp_pool;
	RepositoryObject *reposobj = (RepositoryObject *)self;

	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OOi|zbb", kwnames,
								&dumpstream, &feedback_stream, &uuid_action,
								&parent_dir, &use_pre_commit_hook,
								&use_post_commit_hook))
		return NULL;

	if (uuid_action != svn_repos_load_uuid_default &&
		uuid_action != svn_repos_load_uuid_ignore &&
		uuid_action != svn_repos_load_uuid_force) {
		PyErr_SetString(PyExc_RuntimeError, "Invalid UUID action");
		return NULL;
	}

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(temp_pool, svn_repos_load_fs2(reposobj->repos, 
				new_py_stream(temp_pool, dumpstream), 
				new_py_stream(temp_pool, feedback_stream),
				uuid_action, parent_dir, use_pre_commit_hook, 
				use_post_commit_hook, py_cancel_check, NULL,
				temp_pool));
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

	RUN_SVN_WITH_POOL(temp_pool,
		svn_repos_hotcopy(src_path, dest_path, clean_logs, temp_pool));

	apr_pool_destroy(temp_pool);

	Py_RETURN_NONE;
}

/**
 * Get runtime libsvn_wc version information.
 *
 * :return: tuple with major, minor, patch version number and tag.
 */
static PyObject *version(PyObject *self)
{
	const svn_version_t *ver = svn_repos_version();
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

static PyMethodDef repos_module_methods[] = {
	{ "create", (PyCFunction)repos_create, METH_VARARGS, 
		"create(path, config=None, fs_config=None)\n\n"
		"Create a new repository." },
	{ "delete", (PyCFunction)repos_delete, METH_VARARGS, 
		"delete(path)\n\n"
		"Delete a repository." },
	{ "hotcopy", (PyCFunction)repos_hotcopy, METH_VARARGS, 
		"hotcopy(src_path, dest_path, clean_logs=False)\n\n"
		"Make a hot copy of a repository." },
	{ "api_version", (PyCFunction)api_version, METH_NOARGS,
		"api_version() -> (major, minor, patch, tag)\n\n"
		"Version of libsvn_client Subvertpy was compiled against."
	},
	{ "version", (PyCFunction)version, METH_NOARGS,
		"version() -> (major, minor, patch, tag)\n\n"
		"Version of libsvn_wc currently used."
	},

	{ NULL, }
};

static PyObject *repos_has_capability(RepositoryObject *self, PyObject *args)
{
#if ONLY_SINCE_SVN(1, 5)
	char *name;
	svn_boolean_t has;
	apr_pool_t *temp_pool;
	if (!PyArg_ParseTuple(args, "s", &name))
		return NULL;
	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(temp_pool,
		svn_repos_has_capability(self->repos, &has, name, temp_pool));
	apr_pool_destroy(temp_pool);
	return PyBool_FromLong(has);
#else
	PyErr_SetString(PyExc_NotImplementedError, "has_capability is only supported in Subversion >= 1.5");
	return NULL;
#endif
}

static PyObject *repos_verify(RepositoryObject *self, PyObject *args)
{
	apr_pool_t *temp_pool;
	PyObject *py_feedback_stream;
	svn_revnum_t start_rev, end_rev;
	if (!PyArg_ParseTuple(args, "Oll", &py_feedback_stream, &start_rev, &end_rev))
		return NULL;
	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(temp_pool,
		svn_repos_verify_fs(self->repos,
			new_py_stream(temp_pool, py_feedback_stream), start_rev, end_rev,
			py_cancel_check, NULL, temp_pool));
	apr_pool_destroy(temp_pool);

	Py_RETURN_NONE;
}

static svn_error_t *py_pack_notify(void *baton, apr_int64_t shard, svn_fs_pack_notify_action_t action, apr_pool_t *pool)
{
	PyObject *ret;
	if (baton == Py_None)
		return NULL;
	ret = PyObject_CallFunction((PyObject *)baton, "li", shard, action);
	if (ret == NULL)
		return py_svn_error();
	Py_DECREF(ret);
	return NULL;
}

static PyObject *repos_pack(RepositoryObject *self, PyObject *args)
{
	apr_pool_t *temp_pool;
	PyObject *notify_func = Py_None;
	if (!PyArg_ParseTuple(args, "|O", &notify_func))
		return NULL;
	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(temp_pool,
		svn_repos_fs_pack(self->repos, py_pack_notify, notify_func,
			py_cancel_check, NULL, temp_pool));
	apr_pool_destroy(temp_pool);

	Py_RETURN_NONE;
}

static PyMethodDef repos_methods[] = {
	{ "load_fs", (PyCFunction)repos_load_fs, METH_VARARGS|METH_KEYWORDS, NULL },
	{ "fs", (PyCFunction)repos_fs, METH_NOARGS, NULL },
	{ "has_capability", (PyCFunction)repos_has_capability, METH_VARARGS, NULL },
	{ "verify_fs", (PyCFunction)repos_verify, METH_VARARGS,
		"S.verify_repos(feedback_stream, start_revnum, end_revnum)" },
	{ "pack_fs", (PyCFunction)repos_pack, METH_VARARGS, NULL },
	{ NULL, }
};

PyTypeObject Repository_Type = {
	PyVarObject_HEAD_INIT(NULL, 0)
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
	
	"Local repository", /*	const char *tp_doc;  Documentation string */
	
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
	svn_string_t *str;
	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	str = svn_fs_unparse_id(id, temp_pool);
	if (str == NULL) {
		apr_pool_destroy(temp_pool);
		return NULL;
	}
	return PyBytes_FromStringAndSize(str->data, str->len);
}

#if ONLY_BEFORE_SVN(1, 6)
static PyObject *py_fs_path_change(svn_fs_path_change_t *val)
{
	PyObject *ret, *py_node_id;

	py_node_id = py_string_from_svn_node_id(val->node_rev_id);
	if (py_node_id == NULL) {
		return NULL;
	}
	ret = Py_BuildValue("(Oibb)", py_node_id,
						   val->change_kind, val->text_mod, val->prop_mod);
	Py_DECREF(py_node_id);
	if (ret == NULL) {
		return NULL;
	}

	return ret;
}

#else

static PyObject *py_fs_path_change2(svn_fs_path_change2_t *val)
{
	PyObject *ret, *py_node_id;

	py_node_id = py_string_from_svn_node_id(val->node_rev_id);
	if (py_node_id == NULL) {
		return NULL;
	}
	ret = Py_BuildValue("(Oibb)", py_node_id,
						   val->change_kind, val->text_mod, val->prop_mod);
	Py_DECREF(py_node_id);
	if (ret == NULL) {
		return NULL;
	}

	/* FIXME: copyfrom information */

	return ret;
}
#endif

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
#if ONLY_SINCE_SVN(1, 6)
	RUN_SVN_WITH_POOL(temp_pool, 
					  svn_fs_paths_changed2(&changed_paths, self->root, temp_pool));
#else
	RUN_SVN_WITH_POOL(temp_pool, 
					  svn_fs_paths_changed(&changed_paths, self->root, temp_pool));
#endif
	ret = PyDict_New();
	if (ret == NULL) {
		apr_pool_destroy(temp_pool);
		return NULL;
	}

	for (idx = apr_hash_first(temp_pool, changed_paths); idx != NULL;
		 idx = apr_hash_next(idx)) {
		PyObject *py_val;
#if ONLY_SINCE_SVN(1, 6)
		svn_fs_path_change2_t *val;
#else
		svn_fs_path_change_t *val;
#endif
		apr_hash_this(idx, (const void **)&key, &klen, (void **)&val);
#if ONLY_SINCE_SVN(1, 6)
		py_val = py_fs_path_change2(val);
#else
		py_val = py_fs_path_change(val);
#endif
		if (py_val == NULL) {
			apr_pool_destroy(temp_pool);
			PyObject_Del(ret);
			return NULL;
		}
		if (PyDict_SetItemString(ret, key, py_val) != 0) {
			apr_pool_destroy(temp_pool);
			PyObject_Del(ret);
			Py_DECREF(py_val);
			return NULL;
		}

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

static PyObject *fs_node_file_proplist(FileSystemRootObject *self, PyObject *args)
{
	apr_pool_t *temp_pool;
	PyObject *ret;
	char *path;
	apr_hash_t *proplist;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
	RUN_SVN_WITH_POOL(temp_pool, svn_fs_node_proplist(&proplist, self->root, 
											   path, temp_pool));
	ret = prop_hash_to_dict(proplist);
	apr_pool_destroy(temp_pool);
	return ret;
}

static PyObject *fs_root_file_checksum(FileSystemRootObject *self, PyObject *args)
{
	apr_pool_t *temp_pool;
	svn_boolean_t force = FALSE;
	char *path;
#if ONLY_SINCE_SVN(1, 6)
	svn_checksum_kind_t kind;
	const char *cstr;
	svn_checksum_t *checksum;
#else
	int kind;
	unsigned char checksum[APR_MD5_DIGESTSIZE];
#endif
	PyObject *ret;

	if (!PyArg_ParseTuple(args, "s|ib", &path, &kind, &force))
		return NULL;

	temp_pool = Pool(NULL);
	if (temp_pool == NULL)
		return NULL;
#if ONLY_SINCE_SVN(1, 6)
	RUN_SVN_WITH_POOL(temp_pool, svn_fs_file_checksum(&checksum, kind, 
													  self->root, 
											   path, force, temp_pool));
	cstr = svn_checksum_to_cstring(checksum, temp_pool);
	if (cstr == NULL) {
		ret = Py_None;
		Py_INCREF(ret);
	} else {
		ret = PyBytes_FromString(cstr);
	}
#else
	if (kind > 0)  {
		PyErr_SetString(PyExc_ValueError, "Only MD5 checksums allowed with subversion < 1.6");
		return NULL;
	}

	RUN_SVN_WITH_POOL(temp_pool, svn_fs_file_md5_checksum(checksum, 
													  self->root, 
											   path, temp_pool));
	ret = PyBytes_FromStringAndSize((char *)checksum, APR_MD5_DIGESTSIZE);
#endif
	apr_pool_destroy(temp_pool);
	return ret;
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
	ret->closed = FALSE;
	ret->stream = stream;

    return (PyObject *)ret;
}

static PyMethodDef fs_root_methods[] = {
	{ "paths_changed", (PyCFunction)fs_root_paths_changed, METH_NOARGS, NULL },
	{ "is_dir", (PyCFunction)fs_root_is_dir, METH_VARARGS, NULL },
	{ "is_file", (PyCFunction)fs_root_is_file, METH_VARARGS, NULL },
	{ "file_length", (PyCFunction)fs_root_file_length, METH_VARARGS, NULL },
	{ "file_content", (PyCFunction)fs_root_file_contents, METH_VARARGS, NULL },
	{ "file_checksum", (PyCFunction)fs_root_file_checksum, METH_VARARGS, NULL },
	{ "proplist", (PyCFunction)fs_node_file_proplist, METH_VARARGS, NULL },
	{ NULL, }
};

PyTypeObject FileSystemRoot_Type = {
	PyVarObject_HEAD_INIT(NULL, 0)
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


PyModule_Init_DEFINE(repos)
{
	static apr_pool_t *pool;
	PyObject *mod = NULL;

	if (PyType_Ready(&Repository_Type) < 0)
		PyModule_RETURN(mod);

	if (PyType_Ready(&FileSystem_Type) < 0)
		PyModule_RETURN(mod);

	if (PyType_Ready(&FileSystemRoot_Type) < 0)
		PyModule_RETURN(mod);

	if (PyType_Ready(&Stream_Type) < 0)
		PyModule_RETURN(mod);

	apr_initialize();
	pool = Pool(NULL);
	if (pool == NULL)
		PyModule_RETURN(mod);

	svn_fs_initialize(pool);

	PyModule_DEFINE(mod, "repos", "Local repository management", repos_module_methods)
	if (mod == NULL)
		PyModule_RETURN(mod);

	PyModule_AddObject(mod, "LOAD_UUID_DEFAULT", PyLong_FromLong(svn_repos_load_uuid_default));
	PyModule_AddObject(mod, "LOAD_UUID_IGNORE", PyLong_FromLong(svn_repos_load_uuid_ignore));
	PyModule_AddObject(mod, "LOAD_UUID_FORCE", PyLong_FromLong(svn_repos_load_uuid_force));

	PyModule_AddObject(mod, "PATH_CHANGE_MODIFY", PyInt_FromLong(svn_fs_path_change_modify));
	PyModule_AddObject(mod, "PATH_CHANGE_ADD", PyInt_FromLong(svn_fs_path_change_add));
	PyModule_AddObject(mod, "PATH_CHANGE_DELETE", PyInt_FromLong(svn_fs_path_change_delete));
	PyModule_AddObject(mod, "PATH_CHANGE_REPLACE", PyInt_FromLong(svn_fs_path_change_replace));

#if ONLY_SINCE_SVN(1, 6)
	PyModule_AddObject(mod, "CHECKSUM_MD5", PyInt_FromLong(svn_checksum_md5));
	PyModule_AddObject(mod, "CHECKSUM_SHA1", PyInt_FromLong(svn_checksum_sha1));
#else
	PyModule_AddObject(mod, "CHECKSUM_MD5", PyInt_FromLong(0));
#endif

	PyModule_AddObject(mod, "Repository", (PyObject *)&Repository_Type);
	Py_INCREF(&Repository_Type);

	PyModule_AddObject(mod, "Stream", (PyObject *)&Stream_Type);
	Py_INCREF(&Stream_Type);
	PyModule_RETURN(mod);
}
