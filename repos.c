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
#include <svn_fs.h>
#include <svn_repos.h>

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
    hash_config = NULL; /* FIXME */
    hash_fs_config = NULL; /* FIXME */
    RUN_SVN_WITH_POOL(pool, svn_repos_create(&repos, path, "", "", 
                hash_config, hash_fs_config, pool));

	ret = PyObject_New(RepositoryObject, &Repository_Type);
	if (ret == NULL)
		return NULL;

	ret->pool = pool;
	ret->repos = repos;

    return ret;
}

static void repos_dealloc(PyObject *self)
{
	RepositoryObject *repos = (RepositoryObject *)self;

	apr_pool_destroy(repos->pool);
}

static PyObject *repos_init(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
	char *path;
	char *kwnames[] = { "path", NULL };
	RepositoryObject *ret;

	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "s", kwnames, &path))
		return NULL;

	ret = PyObject_New(RepositoryObject, &Repository_Type);
	if (ret == NULL)
		return NULL;

	ret->pool = Pool(NULL);
    if (!check_error(svn_repos_open(&self.repos, path, self.pool))) {
		apr_pool_destroy(ret->pool);
		PyObject_Del(ret);
		return NULL;
	}
}

static PyObject *repos_load_fs(PyObject *self, PyObject *args, PyObject *kwargs)
{
	const char *parent_dir = "";
	PyObject *dumpstream, *feedback_stream, *cancel_func = Py_None;
	bool use_pre_commit_hook = false, use_post_commit_hook = false;
	char *kwnames[] = { "dumpstream", "feedback_stream", "uuid_action",
		                "parent_dir", "use_pre_commit_hook", 
						"use_post_commit_hook", "cancel_func", NULL };
	apr_pool_t *temp_pool;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OOi|sbbO", kwnames,
								&dumpstream, &feedback_stream, &uuid_action,
								&parent_dir, &use_pre_commit_hook, 
								&use_post_commit_hook,
								&cancel_func))
		return NULL;

	temp_pool = Pool(self.pool);
	RUN_SVN_WITH_POOL(temp_pool, svn_repos_load_fs2(self.repos, 
				new_py_stream(temp_pool, dumpstream), 
				new_py_stream(temp_pool, feedback_stream),
				uuid_action, parent_dir, use_pre_commit_hook, 
				use_post_commit_hook, py_cancel_func, (void *)cancel_func,
				self.pool));
	apr_pool_destroy(temp_pool);
	return Py_None;
}

static PyObject *repos_fs(PyObject *self)
{
	FileSystemObject *ret = PyObject_New(FileSystemObject, &FileSystem_Type);

	if (ret == NULL)
		return NULL;

	ret->fs = svn_repos_fs(self->repos);
    ret->pool = Pool(self->pool);
	return (PyObject *)ret;
}

typedef struct { 
	PyObject_HEAD
    svn_fs_root_t *root;
    apr_pool_t *pool;
} FileSystemRootObject;

static void fsroot_dealloc(PyObject *obj)
{
	FileSystemRootObject *fsroot = (FileSystemRootObject *)obj;
	apr_pool_destroy(fsroot->pool);
}

static PyObject *repos_check_path(PyObject *self, PyObject *args)
{
	char *path;
	svn_node_kind_t kind;
	apr_pool_t *pool;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	pool = Pool(NULL);
	RUN_SVN_WITH_POOL(pool, svn_fs_check_path(&kind, self.root, path, pool));
	apr_pool_destroy(pool)
	return kind;
}

static PyObject *repos_make_dir(PyObject *self, PyObject *args)
{
	char *path;
	apr_pool_t *pool;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	pool = Pool(self.pool);
	RUN_SVN_WITH_POOL(pool, svn_fs_make_dir(self.root, path, pool));
	apr_pool_destroy(pool);

	return Py_None;
}

static PyObject *repos_delete(PyObject *self, PyObject *args)
{
	char *path;
	apr_pool_t *pool

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

    pool = Pool(self.pool);
   	RUN_SVN_WITH_POOL(pool, svn_fs_delete(self.root, path, pool));
	apr_pool_destroy(pool);

	return Py_None;
}

static PyObject *repos_copy(PyObject *self, PyObject *args)
{
	char *from_path;
	PyObject *to_root; 
	char *to_path;
    apr_pool_t *pool

	if (!PyArg_ParseTuple(args, "sOs", &from_path, &to_root, &to_path))
		return NULL;

    pool = Pool(self.pool)
    RUN_SVN_WITH_POOL(pool, 
		svn_fs_copy(self.root, from_path, to_root.root, to_path, pool));
	apr_pool_destroy(pool);
	
	return Py_None;
}

static PyObject *repos_file_length(PyObject *self, PyObject *args)
{
	char *path;
    apr_pool_t *pool;
	svn_filesize_t length;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	pool = Pool(self.pool);
	RUN_SVN_WITH_POOL(pool, svn_fs_file_length(&length, self.root, path, pool));
	apr_pool_destroy(pool);
	return PyLong_FromLong(length);
}

static PyObject *repos_file_md5_checksum(PyObject *self, PyObject *args)
{
	char *path;
	char digest[64];
	apr_pool_t *pool;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	pool = Pool(NULL);
	RUN_SVN_WITH_POOL(pool, 
		svn_fs_file_md5_checksum((unsigned char*)digest, self.root, path, pool));
	ret = PyString_FromStringAndSize(digest, 64);
	apr_pool_destroy(pool);
	return ret;
}

static PyObject *repos_file_contents(PyObject *self, PyObject *args)
{
    apr_pool_t *pool;
    svn_stream_t *stream;
	char *path;

	if (!PyArg_ParseTuple(args, "s", &path))
		return NULL;

	pool = Pool(self.pool);
	RUN_SVN_WITH_POOL(pool, svn_fs_file_contents(&stream, self.root, path, pool));
    apr_pool_destroy(pool);
	return Py_None; /* FIXME */
}

static PyObject *repos_is_txn_root(PyObject *self)
{
	return PyBool_FromLong(svn_fs_is_txn_root(self.root));
}

static PyObject *repos_is_revision_root(PyObject *self)
{
	return PyBool_FromLong(svn_fs_is_revision_root(self.root));
}

static PyObject *repos_close(PyObject *self)
{
	return svn_fs_close_root(self.root);
}

typedef struct {
	PyObject_HEAD
    svn_fs_t *fs;
    apr_pool_t *pool;
} FileSystemObject;


    def __dealloc__(self):
        apr_pool_destroy(self.pool)

    def get_uuid(self):
        cdef char *uuid
        check_error(svn_fs_get_uuid(self.fs, &uuid, self.pool))
        return uuid

    def youngest_revision(self):
        cdef apr_pool_t *pool
        cdef svn_revnum_t youngest
        pool = Pool(NULL)
        check_error(svn_fs_youngest_rev(&youngest, self.fs, pool))
        apr_pool_destroy(pool)
        return youngest

    def revision_root(self, svn_revnum_t rev):
        cdef FileSystemRoot ret
        ret = FileSystemRoot()
        ret.pool = Pool(NULL)
        check_error(svn_fs_revision_root(&ret.root, self.fs, rev, ret.pool))
        return ret

void initrepos(void)
{
	apr_initialize();

	mod = Py_InitModule3("repos", NULL, "Local repository management");
	if (mod == NULL)
		return;

	PyModule_AddObject(mod, "LOAD_UUID_DEFAULT", PyLong_FromLong(0));
	PyModule_AddObject(mod, "LOAD_UUID_IGNORE", PyLong_FromLong(1));
	PyModule_AddObject(mod, "LOAD_UUID_FORCE", PyLong_FromLong(2));
}
