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
#include <svn_opt.h>
#include <svn_client.h>
#include <svn_config.h>

#include "util.h"
#include "ra.h"
#include "wc.h"

extern PyTypeObject Client_Type;
extern PyTypeObject Config_Type;
extern PyTypeObject ConfigItem_Type;

typedef struct {
    PyObject_HEAD
    apr_hash_t *config;
    apr_pool_t *pool;
} ConfigObject;

typedef struct {
    PyObject_HEAD
    svn_config_t *item;
    PyObject *parent;
} ConfigItemObject;

static int client_set_auth(PyObject *self, PyObject *auth, void *closure);
static int client_set_config(PyObject *self, PyObject *auth, void *closure);

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

static PyObject *wrap_py_commit_items(const apr_array_header_t *commit_items)
{
    PyObject *ret;
    int i;

    ret = PyList_New(commit_items->nelts);
    if (ret == NULL)
        return NULL;

    assert(commit_items->elt_size == sizeof(svn_client_commit_item2_t *));

    for (i = 0; i < commit_items->nelts; i++) {
        svn_client_commit_item2_t *commit_item = 
            APR_ARRAY_IDX(commit_items, i, svn_client_commit_item2_t *);
        PyObject *item, *copyfrom;

        if (commit_item->copyfrom_url != NULL) {
            copyfrom = Py_BuildValue("(sl)", commit_item->copyfrom_url, 
                                     commit_item->copyfrom_rev);
            if (copyfrom == NULL) {
                Py_DECREF(ret);
                return NULL;
            }
        } else {
            copyfrom = Py_None;
            Py_INCREF(copyfrom);
        }

        item = Py_BuildValue("(szlNi)", 
                             /* commit_item->path */ "foo",
                             commit_item->url, commit_item->revision, 
                             copyfrom,
                             commit_item->state_flags);
        if (item == NULL) {
            Py_DECREF(ret);
            return NULL;
        }

        if (PyList_SetItem(ret, i, item) != 0)
            return NULL;
    }

    return ret;
}

#if SVN_VER_MAJOR >= 1 && SVN_VER_MINOR >= 5
static svn_error_t *proplist_receiver(void *prop_list, const char *path,
                                      apr_hash_t *prop_hash, apr_pool_t *pool)
{
    PyGILState_STATE state = PyGILState_Ensure();
    PyObject *prop_dict;
    PyObject *value;

    prop_dict = prop_hash_to_dict(prop_hash);

    if (prop_dict == NULL) {
        PyGILState_Release(state);
        return py_svn_error();
    }

    value = Py_BuildValue("(sO)", path, prop_dict);
    if (value == NULL) {
        PyGILState_Release(state);
        return py_svn_error();
    }

    PyList_Append(prop_list, value);

    PyGILState_Release(state);

    return NULL;
}
#endif

static svn_error_t *list_receiver(void *dict, const char *path,
                                  const svn_dirent_t *dirent,
                                  const svn_lock_t *lock, const char *abs_path,
                                  apr_pool_t *pool)
{
    PyGILState_STATE state = PyGILState_Ensure();
    PyObject *value;

    value = py_dirent(dirent, SVN_DIRENT_ALL);
    if (value == NULL) {
        PyGILState_Release(state);
        return py_svn_error();
    }

    PyDict_SetItemString(dict, path, value);

    PyGILState_Release(state);

    return NULL;
}

static svn_error_t *py_log_msg_func2(const char **log_msg, const char **tmp_file, const apr_array_header_t *commit_items, void *baton, apr_pool_t *pool)
{
    PyObject *py_commit_items, *ret, *py_log_msg, *py_tmp_file;
    PyGILState_STATE state;

    if (baton == Py_None)
        return NULL;

    state = PyGILState_Ensure();
    py_commit_items = wrap_py_commit_items(commit_items);
    CB_CHECK_PYRETVAL(py_commit_items);

    ret = PyObject_CallFunction(baton, "O", py_commit_items);
    Py_DECREF(py_commit_items);
    CB_CHECK_PYRETVAL(ret);
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
    Py_DECREF(ret);
    PyGILState_Release(state);
    return NULL;
}

static PyObject *py_commit_info_tuple(svn_commit_info_t *ci)
{
    if (ci == NULL)
        Py_RETURN_NONE;
    if (ci->revision == SVN_INVALID_REVNUM)
        Py_RETURN_NONE;
    return Py_BuildValue("(lzz)", ci->revision, ci->date, ci->author);
}

typedef struct {
    PyObject_HEAD
    svn_client_ctx_t *client;
    apr_pool_t *pool;
    PyObject *callbacks;
    PyObject *py_auth;
    PyObject *py_config;
} ClientObject;

static PyObject *client_new(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
    ClientObject *ret;
    PyObject *config = Py_None, *auth = Py_None;
    char *kwnames[] = { "config", "auth", NULL };
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|OO", kwnames, &config, &auth))
        return NULL;

    ret = PyObject_New(ClientObject, &Client_Type);
    if (ret == NULL)
        return NULL;

    ret->pool = Pool(NULL);
    if (ret->pool == NULL) {
        Py_DECREF(ret);
        return NULL;
    }

    if (!check_error(svn_client_create_context(&ret->client, ret->pool))) {
        Py_DECREF(ret);
        return NULL;
    }

    ret->py_auth = NULL;
    ret->py_config = NULL;
    ret->client->notify_func2 = NULL;
    ret->client->notify_baton2 = NULL;
    client_set_config((PyObject *)ret, config, NULL);
    client_set_auth((PyObject *)ret, auth, NULL);
    return (PyObject *)ret;
}

static void client_dealloc(PyObject *self)
{
    ClientObject *client = (ClientObject *)self;
    Py_XDECREF((PyObject *)client->client->notify_baton2);
    Py_XDECREF((PyObject *)client->client->log_msg_baton2);
    Py_XDECREF(client->py_auth);
    Py_XDECREF(client->py_config);
    if (client->pool != NULL)
        apr_pool_destroy(client->pool);
    PyObject_Del(self);
}

static PyObject *client_get_log_msg_func(PyObject *self, void *closure)
{
    ClientObject *client = (ClientObject *)self;
    if (client->client->log_msg_func2 == NULL)
        Py_RETURN_NONE;
    return client->client->log_msg_baton2;
}

static int client_set_log_msg_func(PyObject *self, PyObject *func, void *closure)
{
    ClientObject *client = (ClientObject *)self;

    if (client->client->log_msg_baton2 != NULL) {
        Py_DECREF((PyObject *)client->client->log_msg_baton2);
    }
    if (func == Py_None) {
        client->client->log_msg_func2 = NULL;
        client->client->log_msg_baton2 = Py_None;
    } else {
        client->client->log_msg_func2 = py_log_msg_func2;
        client->client->log_msg_baton2 = (void *)func;
    }
    Py_INCREF(func);
    return 0;
}

static PyObject *client_get_notify_func(PyObject *self, void *closure)
{
    ClientObject *client = (ClientObject *)self;
    if (client->client->notify_func2 == NULL)
        Py_RETURN_NONE;
    return client->client->notify_baton2;
}

static int client_set_notify_func(PyObject *self, PyObject *func, void *closure)
{
    ClientObject *client = (ClientObject *)self;

    if (client->client->notify_baton2 != NULL) {
        Py_DECREF((PyObject *)client->client->notify_baton2);
    }
    if (func == Py_None) {
        client->client->notify_func2 = NULL;
        client->client->notify_baton2 = Py_None;
    } else {
        client->client->notify_func2 = py_wc_notify_func;
        client->client->notify_baton2 = (void *)func;
    }
    Py_INCREF(func);
    return 0;
}

static int client_set_auth(PyObject *self, PyObject *auth, void *closure)
{
    ClientObject *client = (ClientObject *)self;
    apr_array_header_t *auth_providers;

    Py_XDECREF(client->py_auth);


    if (auth == Py_None) {
        auth_providers = apr_array_make(client->pool, 0, sizeof(svn_auth_provider_object_t *));
        if (auth_providers == NULL) {
            PyErr_NoMemory();
            return 1;
        }
        Py_BEGIN_ALLOW_THREADS
        svn_auth_open(&client->client->auth_baton, auth_providers, client->pool);
        Py_END_ALLOW_THREADS
    } else {
        client->client->auth_baton = ((AuthObject *)auth)->auth_baton;
    }

    client->py_auth = auth;
    Py_INCREF(auth);

    return 0;
}

static int client_set_config(PyObject *self, PyObject *config, void *closure)
{
    ClientObject *client = (ClientObject *)self;

    Py_XDECREF(client->py_config);

    client->client->config = config_hash_from_object(config, client->pool);

    client->py_config = config;
    Py_INCREF(config);

    return 0;
}


static PyObject *client_add(PyObject *self, PyObject *args, PyObject *kwargs)
{
    char *path; 
    ClientObject *client = (ClientObject *)self;
    bool recursive=true, force=false, no_ignore=false;
    bool add_parents = false;
    apr_pool_t *temp_pool;
    char *kwnames[] = { "path", "recursive", "force", "no_ignore", 
                        "add_parents", NULL };

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "s|bbbb", kwnames, 
                          &path, &recursive, &force, &no_ignore, &add_parents))
        return NULL;

#if SVN_VER_MAJOR <= 1 && SVN_VER_MINOR < 4
    if (add_parents == false) {
        PyErr_SetString(PyExc_NotImplementedError, 
            "Subversion < 1.4 does not support add_parents=false");
        return NULL;
    }
#endif
    
    temp_pool = Pool(NULL);
    if (temp_pool == NULL)
        return NULL;

#if SVN_VER_MAJOR == 1 && SVN_VER_MINOR >= 5
    RUN_SVN_WITH_POOL(temp_pool, 
        svn_client_add4(path, recursive?svn_depth_infinity:svn_depth_empty, 
                        force, no_ignore, add_parents, 
                        client->client, temp_pool)
        );
#else
    RUN_SVN_WITH_POOL(temp_pool, 
        svn_client_add3(path, recursive, force, no_ignore, client->client, 
                        temp_pool)
        );
#endif
    apr_pool_destroy(temp_pool);
    Py_RETURN_NONE;
}

static PyObject *client_checkout(PyObject *self, PyObject *args, PyObject *kwargs)
{
    ClientObject *client = (ClientObject *)self;
    char *kwnames[] = { "url", "path", "rev", "peg_rev", "recurse", "ignore_externals", "allow_unver_obstructions", NULL };
    svn_revnum_t result_rev;
    svn_opt_revision_t c_peg_rev, c_rev;
    char *url, *path; 
    apr_pool_t *temp_pool;
    PyObject *peg_rev=Py_None, *rev=Py_None;
    bool recurse=true, ignore_externals=false, allow_unver_obstructions=false;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "ss|OObbb", kwnames, &url, &path, &rev, &peg_rev, &recurse, &ignore_externals, &allow_unver_obstructions))
        return NULL;

    if (!to_opt_revision(peg_rev, &c_peg_rev))
        return NULL;
    if (!to_opt_revision(rev, &c_rev))
        return NULL;

    temp_pool = Pool(NULL);
    if (temp_pool == NULL)
        return NULL;
#if SVN_VER_MAJOR >= 1 && SVN_VER_MINOR >= 5
    RUN_SVN_WITH_POOL(temp_pool, svn_client_checkout3(&result_rev, url, path, 
        &c_peg_rev, &c_rev, recurse?svn_depth_infinity:svn_depth_files, 
        ignore_externals, allow_unver_obstructions, client->client, temp_pool));
#else
    if (allow_unver_obstructions) {
        PyErr_SetString(PyExc_NotImplementedError, 
            "allow_unver_obstructions not supported when built against svn<1.5");
        apr_pool_destroy(temp_pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(temp_pool, svn_client_checkout2(&result_rev, url, path, 
        &c_peg_rev, &c_rev, recurse, 
        ignore_externals, client->client, temp_pool));
#endif
    apr_pool_destroy(temp_pool);
    return PyLong_FromLong(result_rev);
}

static PyObject *client_commit(PyObject *self, PyObject *args, PyObject *kwargs)
{
    PyObject *targets; 
    ClientObject *client = (ClientObject *)self;
    bool recurse=true, keep_locks=true;
    apr_pool_t *temp_pool;
    svn_commit_info_t *commit_info = NULL;
    PyObject *ret;
    apr_array_header_t *apr_targets;
    PyObject *revprops = Py_None;
    char *kwnames[] = { "targets", "recurse", "keep_locks", "revprops", NULL };
#if SVN_VER_MAJOR == 1 && SVN_VER_MINOR >= 5
    apr_hash_t *hash_revprops;
#endif
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|bbO", kwnames, &targets, &recurse, &keep_locks, &revprops))
        return NULL;
    temp_pool = Pool(NULL);
    if (temp_pool == NULL)
        return NULL;
    if (!path_list_to_apr_array(temp_pool, targets, &apr_targets)) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

    if (revprops != Py_None && !PyDict_Check(revprops)) {
        apr_pool_destroy(temp_pool);
        PyErr_SetString(PyExc_TypeError, "Expected dictionary with revision properties");
        return NULL;
    }


#if SVN_VER_MAJOR >= 1 && SVN_VER_MINOR >= 5
    if (revprops != Py_None) {
        hash_revprops = prop_dict_to_hash(temp_pool, revprops);
        if (hash_revprops == NULL) {
            apr_pool_destroy(temp_pool);
            return NULL;
        }
    } else {
        hash_revprops = NULL;
    }

    /* FIXME: Support keep_changelist and changelists */
    RUN_SVN_WITH_POOL(temp_pool, svn_client_commit4(&commit_info, 
                apr_targets, recurse?svn_depth_infinity:svn_depth_files,
               keep_locks, false, NULL, hash_revprops,
               client->client, temp_pool));
#else
    if (revprops != Py_None && PyDict_Size(revprops) > 0) {
        PyErr_SetString(PyExc_NotImplementedError, 
                "Setting revision properties only supported on svn > 1.5");
        apr_pool_destroy(temp_pool);
        return NULL;
    }
    RUN_SVN_WITH_POOL(temp_pool, svn_client_commit3(&commit_info, 
                apr_targets,
               recurse, keep_locks, client->client, temp_pool));
#endif
    ret = py_commit_info_tuple(commit_info);
    apr_pool_destroy(temp_pool);

    return ret;
}

static PyObject *client_delete(PyObject *self, PyObject *args)
{
    PyObject *paths; 
    bool force=false, keep_local=false;
    apr_pool_t *temp_pool;
    svn_commit_info_t *commit_info = NULL;
    PyObject *ret;
    apr_array_header_t *apr_paths;
    ClientObject *client = (ClientObject *)self;

    if (!PyArg_ParseTuple(args, "O|bb", &paths, &force, &keep_local))
        return NULL;

    temp_pool = Pool(NULL);
    if (temp_pool == NULL)
        return NULL;
    if (!path_list_to_apr_array(temp_pool, paths, &apr_paths)) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

#if SVN_VER_MAJOR >= 1 && SVN_VER_MINOR >= 5
    RUN_SVN_WITH_POOL(temp_pool, svn_client_delete3(&commit_info, 
                                                    apr_paths,
                force, keep_local, NULL, client->client, temp_pool));
#else
    if (keep_local) {
        PyErr_SetString(PyExc_ValueError, 
                        "keep_local not supported against svn 1.4");
        apr_pool_destroy(temp_pool);
        return NULL;
    }
    RUN_SVN_WITH_POOL(temp_pool, svn_client_delete2(&commit_info, 
                                                    apr_paths,
                force, client->client, temp_pool));
#endif

    ret = py_commit_info_tuple(commit_info);

    apr_pool_destroy(temp_pool);

    return ret;
}

static PyObject *client_copy(PyObject *self, PyObject *args, PyObject *kwargs)
{
    char *src_path, *dst_path;
    PyObject *src_rev = Py_None;
    svn_commit_info_t *commit_info = NULL;
    apr_pool_t *temp_pool;
    svn_opt_revision_t c_src_rev;
    bool copy_as_child = true, make_parents = false;
    PyObject *ret;
    apr_hash_t *revprops;
    bool ignore_externals = false;
    ClientObject *client = (ClientObject *)self;
    char *kwnames[] = { "src_path", "dst_path", "src_rev", "copy_as_child",
        "make_parents", "ignore_externals", "revprpos", NULL };

#if SVN_VER_MAJOR == 1 && SVN_VER_MINOR >= 4
    PyObject *py_revprops = Py_None;
#endif
#if SVN_VER_MAJOR == 1 && SVN_VER_MINOR >= 5
    apr_array_header_t *src_paths;
    svn_client_copy_source_t src;
#endif

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "ss|ObbbO", kwnames,
             &src_path, &dst_path, &src_rev, &copy_as_child, &make_parents,
             &ignore_externals, &py_revprops))
        return NULL;
    if (!to_opt_revision(src_rev, &c_src_rev))
        return NULL;
    temp_pool = Pool(NULL);
    if (temp_pool == NULL)
        return NULL;

    if (py_revprops != Py_None) {
        revprops = prop_dict_to_hash(temp_pool, py_revprops);
        if (revprops == NULL) {
            apr_pool_destroy(temp_pool);
            return NULL;
        }
    } else {
        revprops = NULL;
    }

#if SVN_VER_MAJOR >= 1 && SVN_VER_MINOR < 4
    if (copy_as_child) {
        PyErr_SetString(PyExc_NotImplementedError, 
                        "copy_as_child not supported in svn <= 1.4");
        apr_pool_destroy(temp_pool);
        return NULL;
    }
    if (make_parents) {
        PyErr_SetString(PyExc_NotImplementedError, 
                        "make_parents not supported in svn <= 1.4");
        apr_pool_destroy(temp_pool);
        return NULL;
    }
    if (revprops) {
        PyErr_SetString(PyExc_NotImplementedError, 
                        "revprops not supported in svn <= 1.4");
        apr_pool_destroy(temp_pool);
        return NULL;
    }
#endif
#if SVN_VER_MAJOR >= 1 && SVN_VER_MINOR < 5
    if (ignore_externals) {
        PyErr_SetString(PyExc_NotImplementedError, 
                        "ignore_externals not supported in svn <= 1.5");
        apr_pool_destroy(temp_pool);
        return NULL;
    }
#endif
#if SVN_VER_MAJOR == 1 && SVN_VER_MINOR >= 5
    src.path = src_path;
    src.revision = src.peg_revision = &c_src_rev;
    src_paths = apr_array_make(temp_pool, 1, sizeof(svn_client_copy_source_t *));
    if (src_paths == NULL) {
        PyErr_NoMemory();
        apr_pool_destroy(temp_pool);
        return NULL;
    }
    APR_ARRAY_IDX(src_paths, 0, svn_client_copy_source_t *) = &src;
#endif
#if SVN_VER_MAJOR >= 1 && SVN_VER_MINOR > 5
    RUN_SVN_WITH_POOL(temp_pool, svn_client_copy5(&commit_info, src_paths, 
                dst_path, copy_as_child, make_parents, 
                ignore_externals, revprops, client->client, temp_pool));
#elif SVN_VER_MAJOR >= 1 && SVN_VER_MINOR == 5
    RUN_SVN_WITH_POOL(temp_pool, svn_client_copy4(&commit_info, src_paths, 
                dst_path, copy_as_child, make_parents, 
                revprops, client->client, temp_pool));
#else
    RUN_SVN_WITH_POOL(temp_pool, svn_client_copy2(&commit_info, src_path, 
                &c_src_rev, dst_path, client->client, temp_pool));
#endif
    ret = py_commit_info_tuple(commit_info);
    apr_pool_destroy(temp_pool);
    return ret;
}

static PyObject *client_propset(PyObject *self, PyObject *args)
{
    char *propname;
    svn_string_t c_propval;
    int recurse = true;
    int skip_checks = false;
    ClientObject *client = (ClientObject *)self;
    apr_pool_t *temp_pool;
    char *target;
#if SVN_VER_MAJOR >= 1 && SVN_VER_MINOR >= 5
    svn_commit_info_t *commit_info = NULL;
#endif
    PyObject *ret, *py_revprops = Py_None;
    svn_revnum_t base_revision_for_url = SVN_INVALID_REVNUM;
    apr_hash_t *revprops;

    if (!PyArg_ParseTuple(args, "sz#s|bblO", &propname, &c_propval.data,
                          &c_propval.len, &target, &recurse, &skip_checks,
                          &base_revision_for_url, &py_revprops))
        return NULL;

    temp_pool = Pool(NULL);
    if (temp_pool == NULL)
        return NULL;

    if (py_revprops != Py_None) {
        revprops = prop_dict_to_hash(temp_pool, py_revprops);
        if (revprops == NULL) {
            apr_pool_destroy(temp_pool);
            return NULL;
        }
    } else {
        revprops = NULL;
    }

#if SVN_VER_MAJOR >= 1 && SVN_VER_MINOR >= 5
    /* FIXME: Support changelists */
    /* FIXME: Support depth */
    RUN_SVN_WITH_POOL(temp_pool, svn_client_propset3(&commit_info, propname,
                &c_propval, target, recurse?svn_depth_infinity:svn_depth_files,
                skip_checks, base_revision_for_url, 
                NULL, revprops, client->client, temp_pool));
    ret = py_commit_info_tuple(commit_info);
#else
    if (revprops) {
        PyErr_SetString(PyExc_NotImplementedError, 
                        "revprops not supported with svn < 1.5");
        apr_pool_destroy(temp_pool);
        return NULL;
    }
    RUN_SVN_WITH_POOL(temp_pool, svn_client_propset2(propname, &c_propval,
                target, recurse, skip_checks, client->client, temp_pool));
    ret = Py_None;
    Py_INCREF(ret);
#endif
    apr_pool_destroy(temp_pool);
    return ret;
}

static PyObject *client_propget(PyObject *self, PyObject *args)
{
    svn_opt_revision_t c_peg_rev;
    svn_opt_revision_t c_rev;
    apr_hash_t *hash_props;
    bool recurse = false;
    char *propname;
    apr_pool_t *temp_pool;
    char *target;
    PyObject *peg_revision = Py_None;
    PyObject *revision;
    ClientObject *client = (ClientObject *)self;
    PyObject *ret;

    if (!PyArg_ParseTuple(args, "ssO|Ob", &propname, &target, &peg_revision, 
                          &revision, &recurse))
        return NULL;
    if (!to_opt_revision(peg_revision, &c_peg_rev))
        return NULL;
    if (!to_opt_revision(revision, &c_rev))
        return NULL;
    temp_pool = Pool(NULL);
    if (temp_pool == NULL)
        return NULL;
#if SVN_VER_MAJOR >= 1 && SVN_VER_MINOR >= 5
    /* FIXME: Support changelists */
    /* FIXME: Support actual_revnum */
    /* FIXME: Support depth properly */
    RUN_SVN_WITH_POOL(temp_pool, 
                      svn_client_propget3(&hash_props, propname, target,
                &c_peg_rev, &c_rev, NULL, recurse?svn_depth_infinity:svn_depth_files,
                NULL, client->client, temp_pool));
#else
    RUN_SVN_WITH_POOL(temp_pool, 
                      svn_client_propget2(&hash_props, propname, target,
                &c_peg_rev, &c_rev, recurse, client->client, temp_pool));
#endif
    ret = prop_hash_to_dict(hash_props);
    apr_pool_destroy(temp_pool);
    return ret;
}

static PyObject *client_proplist(PyObject *self, PyObject *args,
                                 PyObject *kwargs)
{
    char *kwnames[] = { "target", "peg_revision", "depth", "revision", NULL };
    svn_opt_revision_t c_peg_rev;
    svn_opt_revision_t c_rev;
    int depth;
    apr_pool_t *temp_pool;
    char *target;
    PyObject *peg_revision = Py_None, *revision = Py_None;
    ClientObject *client = (ClientObject *)self;
    PyObject *prop_list;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "sOi|O", kwnames,
                                     &target, &peg_revision, &depth, &revision))
        return NULL;
    if (!to_opt_revision(peg_revision, &c_peg_rev))
        return NULL;
    if (!to_opt_revision(revision, &c_rev))
        return NULL;
    temp_pool = Pool(NULL);
    if (temp_pool == NULL)
        return NULL;

    prop_list = PyList_New(0);
    if (prop_list == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

#if SVN_VER_MAJOR >= 1 && SVN_VER_MINOR >= 5
    RUN_SVN_WITH_POOL(temp_pool,
                      svn_client_proplist3(target, &c_peg_rev, &c_rev,
                                           depth, NULL,
                                           proplist_receiver, prop_list,
                                           client->client, temp_pool));

    apr_pool_destroy(temp_pool);
#else
    {
        apr_array_header_t *props;
        int i;
        
    
    if (depth != svn_depth_infinity && depth != svn_depth_empty) {
        PyErr_SetString(PyExc_NotImplementedError, 
                        "depth can only be infinity or empty when built against svn < 1.5");
        apr_pool_destroy(temp_pool);
        return NULL;
    }


    RUN_SVN_WITH_POOL(temp_pool,
                      svn_client_proplist2(&props, target, &c_peg_rev, &c_rev,
                                           (depth == svn_depth_infinity), 
                                           client->client, temp_pool));

    for (i = 0; i < props->nelts; i++) {
        svn_client_proplist_item_t *item;
        PyObject *prop_dict, *value;

        item = APR_ARRAY_IDX(props, i, svn_client_proplist_item_t *);

        prop_dict = prop_hash_to_dict(item->prop_hash);
        if (prop_dict == NULL) {
            apr_pool_destroy(temp_pool);
            Py_DECREF(prop_list);
            return NULL;
        }

        value = Py_BuildValue("(sO)", item->node_name, prop_dict);
        if (value == NULL) {
            apr_pool_destroy(temp_pool);
            Py_DECREF(prop_list);
            Py_DECREF(prop_dict);
            return NULL;
        }
        PyList_Append(prop_list, value);
    }

    apr_pool_destroy(temp_pool);

    }
#endif

    return prop_list;
}

static PyObject *client_resolve(PyObject *self, PyObject *args)
{
#if SVN_VER_MAJOR >= 1 && SVN_VER_MINOR >= 5
    svn_depth_t depth;
    svn_wc_conflict_choice_t choice;
    ClientObject *client = (ClientObject *)self;
    apr_pool_t *temp_pool;
    char *path;
    
    if (!PyArg_ParseTuple(args, "sii", &path, &depth, &choice))
        return NULL;

    temp_pool = Pool(NULL);
    if (temp_pool == NULL)
        return NULL;
    RUN_SVN_WITH_POOL(temp_pool, svn_client_resolve(path, depth, choice,
            client->client, temp_pool));

    apr_pool_destroy(temp_pool);

    Py_RETURN_NONE;
#else
    PyErr_SetString(PyExc_NotImplementedError, 
        "svn_client_resolve not available with Subversion < 1.5");
    return NULL;
#endif
}

static PyObject *client_update(PyObject *self, PyObject *args)
{
    bool recurse = true;
    bool ignore_externals = false;
    apr_pool_t *temp_pool;
    PyObject *rev = Py_None, *paths;
    apr_array_header_t *result_revs, *apr_paths;
    svn_opt_revision_t c_rev;
    svn_revnum_t ret_rev;
    PyObject *ret;
    int i = 0;
    ClientObject *client = (ClientObject *)self;
    svn_boolean_t allow_unver_obstructions = FALSE,
                  depth_is_sticky = FALSE;

    if (!PyArg_ParseTuple(args, "O|Obbbb", &paths, &rev, &recurse, &ignore_externals,
                          &depth_is_sticky, &allow_unver_obstructions))
        return NULL;

    if (!to_opt_revision(rev, &c_rev))
        return NULL;
    temp_pool = Pool(NULL);
    if (temp_pool == NULL)
        return NULL;
    if (!path_list_to_apr_array(temp_pool, paths, &apr_paths)) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }
#if SVN_VER_MAJOR >= 1 && SVN_VER_MINOR >= 5
    RUN_SVN_WITH_POOL(temp_pool, svn_client_update3(&result_revs, 
            apr_paths, &c_rev, 
            recurse?svn_depth_infinity:svn_depth_files, depth_is_sticky, 
            ignore_externals, allow_unver_obstructions, client->client, temp_pool));
#else
    RUN_SVN_WITH_POOL(temp_pool, svn_client_update2(&result_revs, 
            apr_paths, &c_rev, 
            recurse, ignore_externals, client->client, temp_pool));
#endif
    ret = PyList_New(result_revs->nelts);
    if (ret == NULL)
        return NULL;
    for (i = 0; i < result_revs->nelts; i++) {
        ret_rev = APR_ARRAY_IDX(result_revs, i, svn_revnum_t);
        if (PyList_SetItem(ret, i, PyLong_FromLong(ret_rev)) != 0)
            return NULL;
    }
    apr_pool_destroy(temp_pool);
    return ret;
}

static PyObject *client_list(PyObject *self, PyObject *args, PyObject *kwargs)
{
    char *kwnames[] =
        { "path", "peg_revision", "depth", "dirents", "revision", NULL };
    svn_opt_revision_t c_peg_rev;
    svn_opt_revision_t c_rev;
    int depth;
    int dirents = SVN_DIRENT_ALL;
    apr_pool_t *temp_pool;
    char *path;
    PyObject *peg_revision = Py_None, *revision = Py_None;
    ClientObject *client = (ClientObject *)self;
    PyObject *entry_dict;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "sOi|iO", kwnames,
                                     &path, &peg_revision, &depth, &dirents,
                                     &revision))
        return NULL;

    if (!to_opt_revision(peg_revision, &c_peg_rev))
        return NULL;
    if (!to_opt_revision(revision, &c_rev))
        return NULL;
    temp_pool = Pool(NULL);
    if (temp_pool == NULL)
        return NULL;
    entry_dict = PyDict_New();
    if (entry_dict == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

#if SVN_VER_MAJOR >= 1 && SVN_VER_MINOR >= 5
    RUN_SVN_WITH_POOL(temp_pool,
                      svn_client_list2(path, &c_peg_rev, &c_rev,
                                       depth, dirents, false,
                                       list_receiver, entry_dict,
                                       client->client, temp_pool));
#else
    if (depth != svn_depth_infinity && depth != svn_depth_empty) {
        PyErr_SetString(PyExc_NotImplementedError, 
                        "depth can only be infinity or empty when built against svn < 1.5");
        apr_pool_destroy(temp_pool);
        return NULL;
    }

    RUN_SVN_WITH_POOL(temp_pool,
                      svn_client_list(path, &c_peg_rev, &c_rev,
                                       (depth == svn_depth_infinity)?TRUE:FALSE,
                                       dirents, false,
                                       list_receiver, entry_dict,
                                       client->client, temp_pool));
#endif

    return entry_dict;
}

static PyObject *client_diff(PyObject *self, PyObject *args, PyObject *kwargs)
{
#if SVN_VER_MAJOR >= 1 && SVN_VER_MINOR >= 5
    char *kwnames[] = {
        "rev1", "rev2", "path1", "path2",
        "relative_to_dir", "diffopts", "encoding",
        "ignore_ancestry", "no_diff_deleted", "ignore_content_type",
        NULL,
    };
    apr_pool_t *temp_pool;
    ClientObject *client = (ClientObject *)self;

    svn_opt_revision_t c_rev1, c_rev2;
    svn_depth_t depth = svn_depth_infinity;
    char *path1 = NULL, *path2 = NULL, *relative_to_dir = NULL;
    char *encoding = "utf-8";
    PyObject *rev1 = Py_None, *rev2 = Py_None;
    int ignore_ancestry = true, no_diff_deleted = true,
        ignore_content_type = false;
    PyObject *diffopts = Py_None;
    apr_array_header_t *c_diffopts;
    PyObject *outfile, *errfile;
    apr_file_t *c_outfile, *c_errfile;
    apr_off_t offset;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO|zzzOsbbb:diff", kwnames,
                                     &rev1, &rev2, &path1, &path2,
                                     &relative_to_dir, &diffopts, &encoding,
                                     &ignore_ancestry, &no_diff_deleted,
                                     &ignore_content_type))
        return NULL;

    if (!to_opt_revision(rev1, &c_rev1) || !to_opt_revision(rev2, &c_rev2))
        return NULL;

    temp_pool = Pool(NULL);
    if (temp_pool == NULL)
        return NULL;

    if (diffopts == Py_None)
        diffopts = PyList_New(0);
    else
        Py_INCREF(diffopts);

    if (diffopts == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }

    if (!string_list_to_apr_array(temp_pool, diffopts, &c_diffopts)) {
        apr_pool_destroy(temp_pool);
        Py_DECREF(diffopts);
        return NULL;
    }
    Py_DECREF(diffopts);

    outfile = PyOS_tmpfile();
    if (outfile == NULL) {
        apr_pool_destroy(temp_pool);
        return NULL;
    }
    errfile = PyOS_tmpfile();
    if (errfile == NULL) {
        apr_pool_destroy(temp_pool);
        Py_DECREF(outfile);
        return NULL;
    }

    c_outfile = apr_file_from_object(outfile, temp_pool);
    if (c_outfile == NULL) {
        apr_pool_destroy(temp_pool);
        Py_DECREF(outfile);
        Py_DECREF(errfile);
        return NULL;
    }

    c_errfile = apr_file_from_object(errfile, temp_pool);
    if (c_errfile == NULL) {
        apr_pool_destroy(temp_pool);
        Py_DECREF(outfile);
        Py_DECREF(errfile);
        return NULL;
    }

    RUN_SVN_WITH_POOL(temp_pool,
                      svn_client_diff4(c_diffopts,
                                       path1, &c_rev1, path2, &c_rev2,
                                       relative_to_dir, depth,
                                       ignore_ancestry, no_diff_deleted,
                                       ignore_content_type, encoding,
                                       c_outfile, c_errfile, NULL,
                                       client->client, temp_pool));
    
    offset = 0;
    apr_file_seek(c_outfile, APR_SET, &offset);
    offset = 0;
    apr_file_seek(c_errfile, APR_SET, &offset);

    apr_pool_destroy(temp_pool);
    
    return Py_BuildValue("(NN)", outfile, errfile);
#else
    PyErr_SetString(PyExc_NotImplementedError,
                    "svn_client_diff4 not available with Subversion < 1.5");
    return NULL;
#endif
}

static PyMethodDef client_methods[] = {
    { "add", (PyCFunction)client_add, METH_VARARGS|METH_KEYWORDS, 
        "S.add(path, recursive=True, force=False, no_ignore=False)" },
    { "checkout", (PyCFunction)client_checkout, METH_VARARGS|METH_KEYWORDS, 
        "S.checkout(url, path, rev=None, peg_rev=None, recurse=True, ignore_externals=False, allow_unver_obstructions=False)" },
    { "commit", (PyCFunction)client_commit, METH_VARARGS|METH_KEYWORDS, "S.commit(targets, recurse=True, keep_locks=True, revprops=None) -> (revnum, date, author)" },
    { "delete", client_delete, METH_VARARGS, "S.delete(paths, force=False)" },
    { "copy", (PyCFunction)client_copy, METH_VARARGS|METH_KEYWORDS, "S.copy(src_path, dest_path, srv_rev=None)" },
    { "propset", client_propset, METH_VARARGS, "S.propset(name, value, target, recurse=True, skip_checks=False)" },
    { "propget", client_propget, METH_VARARGS, "S.propget(name, target, peg_revision, revision=None, recurse=False) -> value" },
    { "proplist", (PyCFunction)client_proplist, METH_VARARGS|METH_KEYWORDS, "S.proplist(path, peg_revision, depth, revision=None)" },
    { "resolve", client_resolve, METH_VARARGS, "S.resolve(path, depth, choice)" },
    { "update", client_update, METH_VARARGS, "S.update(path, rev=None, recurse=True, ignore_externals=False) -> list of revnums" },
    { "list", (PyCFunction)client_list, METH_VARARGS|METH_KEYWORDS, "S.update(path, peg_revision, depth, dirents=ra.DIRENT_ALL, revision=None) -> list of directory entries" },
    { "diff", (PyCFunction)client_diff, METH_VARARGS|METH_KEYWORDS, "S.diff(rev1, rev2, path1=None, path2=None, relative_to_dir=None, diffopts=[], encoding=\"utf-8\", ignore_ancestry=True, no_diff_deleted=True, ignore_content_type=False) -> unified diff as a string" },
    { NULL, }
};

static PyGetSetDef client_getset[] = {
    { "log_msg_func", client_get_log_msg_func, client_set_log_msg_func, NULL },
    { "notify_func", client_get_notify_func, client_set_notify_func, NULL },
    { "auth", NULL, client_set_auth, NULL },
    { "config", NULL, client_set_config, NULL },
    { NULL, }
};

static PyObject *get_default_ignores(PyObject *self)
{
    apr_array_header_t *patterns;
    apr_pool_t *pool;
    int i = 0;
    ConfigObject *configobj = (ConfigObject *)self;
    PyObject *ret;

    pool = Pool(NULL);
    if (pool == NULL)
        return NULL;
    RUN_SVN_WITH_POOL(pool, svn_wc_get_default_ignores(&patterns, configobj->config, pool));
    ret = PyList_New(patterns->nelts);
    for (i = 0; i < patterns->nelts; i++) {
        PyList_SetItem(ret, i, PyString_FromString(APR_ARRAY_IDX(patterns, i, char *)));
    }
    apr_pool_destroy(pool);
    return ret;
}

static PyObject *config_get_dict(PyObject *self, void *closure)
{
    ConfigObject *config = (ConfigObject *)self;
    apr_pool_t *pool;
    PyObject *ret;
    apr_hash_index_t *idx;
    const char *key;
    svn_config_t *val;
    apr_ssize_t klen;

    pool = Pool(NULL);
    if (pool == NULL)
        return NULL;

    ret = PyDict_New();
    for (idx = apr_hash_first(pool, config->config); idx != NULL; 
         idx = apr_hash_next(idx)) {
        ConfigItemObject *data;
        apr_hash_this(idx, (const void **)&key, &klen, (void **)&val);
        data = PyObject_New(ConfigItemObject, &ConfigItem_Type);
        data->item = val;
        data->parent = NULL;
        PyDict_SetItemString(ret, key, (PyObject *)data);
        Py_DECREF(data);
    }

    return ret;
}

static PyGetSetDef config_getset[] = {
    { "__dict__", config_get_dict, NULL, NULL },
    { NULL }
};

static PyMethodDef config_methods[] = {
    { "get_default_ignores", (PyCFunction)get_default_ignores, METH_NOARGS, NULL },
    { NULL }
};


static void config_dealloc(PyObject *obj)
{
    apr_pool_t *pool = ((ConfigObject *)obj)->pool;
    if (pool != NULL)
        apr_pool_destroy(pool);
    PyObject_Del(obj);
}

PyTypeObject Config_Type = {
    PyObject_HEAD_INIT(NULL) 0,
    "client.Config", /*    const char *tp_name;  For printing, in format "<module>.<name>" */
    sizeof(ConfigObject),  /*  tp_basicsize    */
    0,  /*    tp_itemsize;  For allocation */
    
    /* Methods to implement standard operations */
    
    (destructor)config_dealloc, /*    destructor tp_dealloc;    */
    NULL, /*    printfunc tp_print;    */
    NULL, /*    getattrfunc tp_getattr;    */
    NULL, /*    setattrfunc tp_setattr;    */
    NULL, /*    cmpfunc tp_compare;    */
    NULL, /*    reprfunc tp_repr;    */
    
    /* Method suites for standard classes */
    
    NULL, /*    PyNumberMethods *tp_as_number;    */
    NULL, /*    PySequenceMethods *tp_as_sequence;    */
    NULL, /*    PyMappingMethods *tp_as_mapping;    */
    
    /* More standard operations (here for binary compatibility) */
    
    NULL, /*    hashfunc tp_hash;    */
    NULL, /*    ternaryfunc tp_call;    */
    NULL, /*    reprfunc tp_str;    */
    NULL, /*    getattrofunc tp_getattro;    */
    NULL, /*    setattrofunc tp_setattro;    */
    
    /* Functions to access object as input/output buffer */
    NULL, /*    PyBufferProcs *tp_as_buffer;    */
    
    /* Flags to define presence of optional/expanded features */
    0, /*    long tp_flags;    */
    
    NULL, /*    const char *tp_doc;  Documentation string */
    
    /* Assigned meaning in release 2.0 */
    /* call function for all accessible objects */
    NULL, /*    traverseproc tp_traverse;    */
    
    /* delete references to contained objects */
    NULL, /*    inquiry tp_clear;    */
    
    /* Assigned meaning in release 2.1 */
    /* rich comparisons */
    NULL, /*    richcmpfunc tp_richcompare;    */
    
    /* weak reference enabler */
    0, /*    Py_ssize_t tp_weaklistoffset;    */
    
    /* Added in release 2.2 */
    /* Iterators */
    NULL, /*    getiterfunc tp_iter;    */
    NULL, /*    iternextfunc tp_iternext;    */
    
    /* Attribute descriptor and subclassing stuff */
    config_methods, /*    struct PyMethodDef *tp_methods;    */
    NULL, /*    struct PyMemberDef *tp_members;    */
    config_getset, /*    struct PyGetSetDef *tp_getset;    */
};

static void configitem_dealloc(PyObject *self)
{
    ConfigItemObject *item = (ConfigItemObject *)self;

    Py_XDECREF(item->parent);
    PyObject_Del(item);
}

PyTypeObject ConfigItem_Type = {
    PyObject_HEAD_INIT(NULL) 0,
    "client.ConfigItem", /*    const char *tp_name;  For printing, in format "<module>.<name>" */
    sizeof(ConfigItemObject), 
    0,/*    Py_ssize_t tp_basicsize, tp_itemsize;  For allocation */
    
    /* Methods to implement standard operations */
    
    (destructor)configitem_dealloc, /*    destructor tp_dealloc;    */
};


PyTypeObject Client_Type = {
    PyObject_HEAD_INIT(NULL) 0,
    /*    PyObject_VAR_HEAD    */
    "client.Client", /*    const char *tp_name;  For printing, in format "<module>.<name>" */
    sizeof(ClientObject),
    0,/*    Py_ssize_t tp_basicsize, tp_itemsize;  For allocation */
    
    /* Methods to implement standard operations */
    
    client_dealloc, /*    destructor tp_dealloc;    */
    NULL, /*    printfunc tp_print;    */
    NULL, /*    getattrfunc tp_getattr;    */
    NULL, /*    setattrfunc tp_setattr;    */
    NULL, /*    cmpfunc tp_compare;    */
    NULL, /*    reprfunc tp_repr;    */
    
    /* Method suites for standard classes */
    
    NULL, /*    PyNumberMethods *tp_as_number;    */
    NULL, /*    PySequenceMethods *tp_as_sequence;    */
    NULL, /*    PyMappingMethods *tp_as_mapping;    */
    
    /* More standard operations (here for binary compatibility) */
    
    NULL, /*    hashfunc tp_hash;    */
    NULL, /*    ternaryfunc tp_call;    */
    NULL, /*    reprfunc tp_str;    */
    NULL, /*    getattrofunc tp_getattro;    */
    NULL, /*    setattrofunc tp_setattro;    */
    
    /* Functions to access object as input/output buffer */
    NULL, /*    PyBufferProcs *tp_as_buffer;    */
    
    /* Flags to define presence of optional/expanded features */
    0, /*    long tp_flags;    */
    
    NULL, /*    const char *tp_doc;  Documentation string */
    
    /* Assigned meaning in release 2.0 */
    /* call function for all accessible objects */
    NULL, /*    traverseproc tp_traverse;    */
    
    /* delete references to contained objects */
    NULL, /*    inquiry tp_clear;    */
    
    /* Assigned meaning in release 2.1 */
    /* rich comparisons */
    NULL, /*    richcmpfunc tp_richcompare;    */
    
    /* weak reference enabler */
    0, /*    Py_ssize_t tp_weaklistoffset;    */
    
    /* Added in release 2.2 */
    /* Iterators */
    NULL, /*    getiterfunc tp_iter;    */
    NULL, /*    iternextfunc tp_iternext;    */
    
    /* Attribute descriptor and subclassing stuff */
    client_methods, /*    struct PyMethodDef *tp_methods;    */
    NULL, /*    struct PyMemberDef *tp_members;    */
    client_getset, /*    struct PyGetSetDef *tp_getset;    */
    NULL, /*    struct _typeobject *tp_base;    */
    NULL, /*    PyObject *tp_dict;    */
    NULL, /*    descrgetfunc tp_descr_get;    */
    NULL, /*    descrsetfunc tp_descr_set;    */
    0, /*    Py_ssize_t tp_dictoffset;    */
    NULL, /*    initproc tp_init;    */
    NULL, /*    allocfunc tp_alloc;    */
    client_new, /*    newfunc tp_new;    */

};

static PyObject *get_config(PyObject *self, PyObject *args)
{
    char *config_dir = NULL;
    ConfigObject *data;

    if (!PyArg_ParseTuple(args, "|z", &config_dir))
        return NULL;

    data = PyObject_New(ConfigObject, &Config_Type);
    if (data == NULL)
        return NULL;

    data->pool = Pool(NULL);
    if (data->pool == NULL)
        return NULL;

    RUN_SVN_WITH_POOL(data->pool, 
                      svn_config_get_config(&data->config, config_dir, data->pool));

    return (PyObject *)data;
}

static PyMethodDef client_mod_methods[] = {
    { "get_config", get_config, METH_VARARGS, "get_config(config_dir=None) -> config" },
    { NULL }
};

void initclient(void)
{
    PyObject *mod;

    if (PyType_Ready(&Client_Type) < 0)
        return;

    if (PyType_Ready(&Config_Type) < 0)
        return;

    if (PyType_Ready(&ConfigItem_Type) < 0)
        return;

    /* Make sure APR is initialized */
    apr_initialize();

    mod = Py_InitModule3("client", client_mod_methods, "Client methods");
    if (mod == NULL)
        return;

    Py_INCREF(&Client_Type);
    PyModule_AddObject(mod, "Client", (PyObject *)&Client_Type);

    PyModule_AddObject(mod, "depth_empty",
                       (PyObject *)PyLong_FromLong(svn_depth_empty));
    PyModule_AddObject(mod, "depth_files",
                       (PyObject *)PyLong_FromLong(svn_depth_files));
    PyModule_AddObject(mod, "depth_immediates",
                       (PyObject *)PyLong_FromLong(svn_depth_immediates));
    PyModule_AddObject(mod, "depth_infinity",
                       (PyObject *)PyLong_FromLong(svn_depth_infinity));
}
