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
#include <stdbool.h>
#include <Python.h>
#include <apr_general.h>
#include <svn_opt.h>
#include <svn_client.h>

#include "util.h"

static bool to_opt_revision(PyObject *arg, svn_opt_revision_t *ret)
{
    if (PyInt_Check(arg)) {
        ret->kind = svn_opt_revision_number;
        ret->value.number = PyLong_AsLong(arg);
        return true;
    } else if (arg == Py_None) {
        ret->kind = svn_opt_revision_unspecified;
        return true;
    } else if (PyString_Check(arg)) {
        char *text = PyString_AsString(arg);
        if (!strcmp(text, "HEAD")) {
            ret->kind = svn_opt_revision_head;
            return true;
        } else if (!strcmp(text, "WORKING")) {
            ret->kind = svn_opt_revision_working;
            return true;
        } else if (!strcmp(text, "BASE")) {
            ret->kind = svn_opt_revision_base;
            return true;
        } 
    } 

    PyErr_SetString(PyExc_ValueError, "Unable to parse revision");
    return false;
}
     
svn_error_t *py_log_msg_func2(const char **log_msg, const char **tmp_file, const apr_array_header_t *commit_items, void *baton, apr_pool_t *pool)
{
    PyObject *py_commit_items, *ret, *py_log_msg, *py_tmp_file;
    if (baton == Py_None)
        return NULL;
    py_commit_items = PyList_New(commit_items->nelts);
    ret = PyObject_CallFunction(baton, "O", py_commit_items);
	if (ret == NULL)
		return py_svn_error();
    if (PyTuple_Check(ret)) {
        py_log_msg = PyTuple_GetItem(ret, 0);
        py_tmp_file = PyTuple_GetItem(ret, 1);
    } else {
        py_tmp_file = Py_None;
        py_log_msg = ret;
    }
    if (py_log_msg != Py_None) {
        *log_msg = PyString_AsString(py_log_msg);
    }
    if (py_tmp_file != Py_None) {
        *tmp_file = PyString_AsString(py_tmp_file);
    }
    return NULL;
}

static PyObject *py_commit_info_tuple(svn_commit_info_t *ci)
{
    if (ci == NULL)
        return Py_None;
    return Py_BuildValue("(izz)", ci->revision, ci->date, ci->author);
}

PyAPI_DATA(PyTypeObject) Client_Type;

typedef struct {
    PyObject_HEAD
    svn_client_ctx_t *client;
    apr_pool_t *pool;
    PyObject *callbacks;
} ClientObject;

static PyObject *client_new(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
    ClientObject *ret;
    char *kwnames[] = { NULL };
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "", kwnames))
        return NULL;

    ret = PyObject_New(ClientObject, &Client_Type);
    if (ret == NULL)
        return NULL;

    ret->pool = Pool(NULL);
    if (!check_error(svn_client_create_context(&ret->client, ret->pool)))
        return NULL;
    return (PyObject *)ret;
}

static void client_dealloc(PyObject *self)
{
    ClientObject *client = (ClientObject *)self;
    apr_pool_destroy(client->pool);
    client->pool = NULL;
}

static PyObject *client_set_log_msg_func(PyObject *self, PyObject *args)
{
    PyObject *func;
    ClientObject *client = (ClientObject *)self;
    if (!PyArg_ParseTuple(args, "O", &func))
        return NULL;

    client->client->log_msg_func2 = py_log_msg_func2;
    client->client->log_msg_baton2 = (void *)func;
    Py_INCREF(func);
    return Py_None;
}

static PyObject *client_add(PyObject *self, PyObject *args, PyObject *kwargs)
{
    char *path; 
    ClientObject *client = (ClientObject *)self;
    bool recursive=true, force=false, no_ignore=false;
    char *kwnames[] = { "path", "recursive", "force", "no_ignore", NULL };

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "s|bbb", kwnames, 
                          &path, &recursive, &force, &no_ignore))
        return NULL;
    if (!check_error(svn_client_add3(path, recursive, force, no_ignore, 
                client->client, client->pool)))
        return NULL;
    return Py_None;
}

static PyObject *client_checkout(PyObject *self, PyObject *args, PyObject *kwargs)
{
    ClientObject *client = (ClientObject *)self;
    char *kwnames[] = { "url", "path", "peg_rev", "rev", "recurse", "ignore_externals", NULL };
    svn_revnum_t result_rev;
    svn_opt_revision_t c_peg_rev, c_rev;
    char *url, *path; 
    PyObject *peg_rev=Py_None, *rev=Py_None;
    bool recurse=true, ignore_externals=false;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "ss|OObb", kwnames, &url, &path, &peg_rev, &rev, &recurse, &ignore_externals))
        return NULL;

    if (!to_opt_revision(peg_rev, &c_peg_rev))
        return NULL;
    if (!to_opt_revision(rev, &c_rev))
        return NULL;
    if (!check_error(svn_client_checkout2(&result_rev, url, path, 
        &c_peg_rev, &c_rev, recurse, 
        ignore_externals, client->client, client->pool)))
        return NULL;
    return PyLong_FromLong(result_rev);
}

static PyObject *client_commit(PyObject *self, PyObject *args, PyObject *kwargs)
{
    PyObject *targets; 
    ClientObject *client = (ClientObject *)self;
    bool recurse=true, keep_locks=true;
    svn_commit_info_t *commit_info = NULL;
    char *kwnames[] = { "targets", "recurse", "keep_locks", NULL };
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|bb", kwnames, &targets, &recurse, &keep_locks))
        return NULL;
    if (!check_error(svn_client_commit3(&commit_info, 
               string_list_to_apr_array(client->pool, targets),
               recurse, keep_locks, client->client, client->pool)))
        return NULL;
    return py_commit_info_tuple(commit_info);
}

static PyObject *client_mkdir(PyObject *self, PyObject *args)
{
    PyObject *paths;
    svn_commit_info_t *commit_info = NULL;
    ClientObject *client = (ClientObject *)self;
    if (!PyArg_ParseTuple(args, "O", &paths))
        return NULL;
    if (!check_error(svn_client_mkdir2(&commit_info, 
                string_list_to_apr_array(client->pool, paths), 
                client->client, client->pool)))
        return NULL;
    return py_commit_info_tuple(commit_info);
}

static PyObject *client_delete(PyObject *self, PyObject *args)
{
    PyObject *paths; 
    bool force=false;
    svn_commit_info_t *commit_info = NULL;
    ClientObject *client = (ClientObject *)self;

    if (!PyArg_ParseTuple(args, "O|b", &paths, &force))
        return NULL;

    if (!check_error(svn_client_delete2(&commit_info, 
                string_list_to_apr_array(client->pool, paths),
                force, client->client, client->pool)))
        return NULL;

    return py_commit_info_tuple(commit_info);
}

static PyObject *client_copy(PyObject *self, PyObject *args)
{
    char *src_path, *dst_path;
    PyObject *src_rev=Py_None;
    svn_commit_info_t *commit_info = NULL;
    svn_opt_revision_t c_src_rev;
    ClientObject *client = (ClientObject *)self;
    if (!PyArg_ParseTuple(args, "ss|O", &src_path, &dst_path, &src_rev))
        return NULL;
    if (!to_opt_revision(src_rev, &c_src_rev))
        return NULL;
    if (!check_error(svn_client_copy3(&commit_info, src_path, 
                &c_src_rev, dst_path, client->client, client->pool)))
        return NULL;
    return py_commit_info_tuple(commit_info);
}

static PyObject *client_propset(PyObject *self, PyObject *args)
{
    char *propname;
    svn_string_t c_propval;
    int recurse = true;
    int skip_checks = false;
    ClientObject *client = (ClientObject *)self;
    char *target;

    if (!PyArg_ParseTuple(args, "sz#s|bb", &propname, &c_propval.data, &c_propval.len, &target, &recurse, &skip_checks))
        return NULL;
    if (!check_error(svn_client_propset2(propname, &c_propval,
                target, recurse, skip_checks, client->client, client->pool)))
        return NULL;
    return Py_None;
}
    
static PyObject *client_propget(PyObject *self, PyObject *args)
{
    svn_opt_revision_t c_peg_rev;
    svn_opt_revision_t c_rev;
    apr_hash_t *hash_props;
    bool recurse = false;
    char *propname;
    char *target;
    PyObject *peg_revision;
    PyObject *revision;
    ClientObject *client = (ClientObject *)self;

    if (!PyArg_ParseTuple(args, "ssOO|b", &propname, &target, &peg_revision, 
                          &revision, &recurse))
        return NULL;
    if (!to_opt_revision(peg_revision, &c_peg_rev))
        return NULL;
    if (!to_opt_revision(revision, &c_rev))
        return NULL;
    if (!check_error(svn_client_propget2(&hash_props, propname, target,
                &c_peg_rev, &c_rev, recurse, client->client, client->pool)))
        return NULL;
    return prop_hash_to_dict(hash_props);
}

static PyObject *client_update(PyObject *self, PyObject *args)
{
    bool recurse = true;
    bool ignore_externals = false;
    PyObject *rev = Py_None, *paths;
    apr_array_header_t *result_revs;
    svn_opt_revision_t c_rev;
    svn_revnum_t *ret_rev;
    PyObject *ret;
    int i = 0;
    ClientObject *client = (ClientObject *)self;

    if (!PyArg_ParseTuple(args, "O|Obb", &paths, &rev, &recurse, &ignore_externals))
        return NULL;

    if (!to_opt_revision(rev, &c_rev))
        return NULL;
    if (!check_error(svn_client_update2(&result_revs, 
            string_list_to_apr_array(client->pool, paths), &c_rev, 
            recurse, ignore_externals, client->client, client->pool)))
        return NULL;
    ret = PyList_New(result_revs->nelts);
    ret_rev = (svn_revnum_t *)apr_array_pop(result_revs);
    while (ret_rev != NULL) {
        PyList_SetItem(ret, i, PyLong_FromLong(*ret_rev));
        i++;
        ret_rev = (svn_revnum_t *)apr_array_pop(result_revs);
    }
    return ret;
}

static PyObject *client_revprop_get(PyObject *self, PyObject *args)
{
    PyObject *rev = Py_None;
    char *propname, *propval, *url;
    svn_revnum_t set_rev;
    svn_opt_revision_t c_rev;
    svn_string_t *c_val;
    ClientObject *client = (ClientObject *)self;
    if (!PyArg_ParseTuple(args, "sssO", &propname, &propval, &url, &rev))
        return NULL;
    if (!to_opt_revision(rev, &c_rev))
        return NULL;
    if (!check_error(svn_client_revprop_get(propname, &c_val, url, 
                &c_rev, &set_rev, client->client, client->pool)))
        return NULL;
    return Py_BuildValue("(z#i)", c_val->data, c_val->len, set_rev);
}

static PyObject *client_revprop_set(PyObject *self, PyObject *args)
{
    PyObject *rev = Py_None;
    bool force = false;
    ClientObject *client = (ClientObject *)self;
    char *propname, *url;
    svn_revnum_t set_rev;
    svn_opt_revision_t c_rev;
    svn_string_t c_val;
    if (!PyArg_ParseTuple(args, "sz#s|Ob", &propname, &c_val.data, &c_val.len, &url, &rev, &force))
        return NULL;
    if (!to_opt_revision(rev, &c_rev))
        return NULL;
    if (!check_error(svn_client_revprop_set(propname, &c_val, url, 
                &c_rev, &set_rev, force, client->client, client->pool)))
        return NULL;
    return PyLong_FromLong(set_rev);
}

static PyObject *client_log(PyObject *self, PyObject *args, PyObject *kwargs)
{
    char *kwnames[] = { "targets", "callback", "peg_revision", "start", "end", "limit", "discover_changed_paths", "strict_node_history", NULL };
    PyObject *targets, *callback, *peg_revision=Py_None, *start=Py_None, 
             *end=Py_None;
    ClientObject *client = (ClientObject *)self;
    int limit=0; 
    bool discover_changed_paths=true, strict_node_history=true;
    svn_opt_revision_t c_peg_rev, c_start_rev, c_end_rev;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO|OOOlbb", 
                                     kwnames, &targets, &callback, 
                                     &peg_revision, &start, &end, 
                                     &limit, &discover_changed_paths, 
                                     &strict_node_history))
        return NULL;

    if (!to_opt_revision(peg_revision, &c_peg_rev))
        return NULL;
    if (!to_opt_revision(start, &c_start_rev))
        return NULL;
    if (!to_opt_revision(end, &c_end_rev))
        return NULL;
    if (!check_error(svn_client_log3(string_list_to_apr_array(client->pool, targets),
                &c_peg_rev, &c_start_rev, &c_end_rev, limit, discover_changed_paths, strict_node_history, py_svn_log_wrapper, callback, client->client, client->pool)))
        return NULL;
    return Py_None;
}

static PyMethodDef client_methods[] = {
    { "set_log_msg_func", client_set_log_msg_func, METH_VARARGS, NULL },
    { "add", (PyCFunction)client_add, METH_VARARGS|METH_KEYWORDS, NULL },
    { "checkout", (PyCFunction)client_checkout, METH_VARARGS|METH_KEYWORDS, NULL },
    { "commit", (PyCFunction)client_commit, METH_VARARGS|METH_KEYWORDS, NULL },
    { "mkdir", client_mkdir, METH_VARARGS, NULL },
    { "delete", client_delete, METH_VARARGS, NULL },
    { "copy", client_copy, METH_VARARGS, NULL },
    { "propset", client_propset, METH_VARARGS, NULL },
    { "propget", client_propget, METH_VARARGS, NULL },
    { "update", client_update, METH_VARARGS, NULL },
    { "revprop_get", client_revprop_get, METH_VARARGS, NULL },
    { "revprop_set", client_revprop_set, METH_VARARGS, NULL },
    { "log", (PyCFunction)client_log, METH_KEYWORDS|METH_VARARGS, NULL },
    { NULL }
};

PyTypeObject Client_Type = {
    PyObject_HEAD_INIT(NULL) 0,
    .tp_name = "client.Client",
    .tp_basicsize = sizeof(ClientObject),
    .tp_methods = client_methods,
    .tp_dealloc = client_dealloc,
    .tp_new = client_new,
};

void initclient(void)
{
    PyObject *mod;

    if (PyType_Check(&Client_Type) < 0)
        return;

	/* Make sure APR is initialized */
	apr_initialize();

    mod = Py_InitModule3("client", NULL, "Client methods");
    if (mod == NULL)
        return;

    PyModule_AddObject(mod, "Client", (PyObject *)&Client_Type);
    Py_INCREF(&Client_Type);
}
