/*
 * Copyright © 2017 Jelmer Vernooij <jelmer@jelmer.uk>
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
#include <svn_path.h>
#include <stdbool.h>
#include <apr_md5.h>
#include <apr_sha1.h>

#include "util.h"

static PyObject *py_uri_canonicalize(PyObject *self, PyObject *args)
{
    const char *uri;
    PyObject *py_uri, *ret;
    apr_pool_t *pool;

    if (!PyArg_ParseTuple(args, "O", &py_uri))
        return NULL;

    pool = Pool(NULL);
    uri = py_object_to_svn_uri(py_uri, pool);
    ret = PyUnicode_FromString(uri);
    apr_pool_destroy(pool);

    return ret;
}

static PyObject *py_dirent_canonicalize(PyObject *self, PyObject *args)
{
    const char *dirent;
    PyObject *py_dirent, *ret;
    apr_pool_t *pool;

    if (!PyArg_ParseTuple(args, "O", &py_dirent))
        return NULL;

    pool = Pool(NULL);
    dirent = py_object_to_svn_dirent(py_dirent, pool);
    ret = PyUnicode_FromString(dirent);
    apr_pool_destroy(pool);

    return ret;
}

static PyObject *py_abspath(PyObject *self, PyObject *args)
{
    const char *path;
    PyObject *py_path, *ret;
    apr_pool_t *pool;

    if (!PyArg_ParseTuple(args, "O", &py_path))
        return NULL;

    pool = Pool(NULL);
    path = py_object_to_svn_abspath(py_path, pool);
    ret = PyUnicode_FromString(path);
    apr_pool_destroy(pool);

    return ret;
}

static PyMethodDef subr_methods[] = {
    { "uri_canonicalize", py_uri_canonicalize, METH_VARARGS, "uri_canonicalize(uri) -> uri\n"
        "Canonicalize a URI."},
    { "dirent_canonicalize", py_dirent_canonicalize, METH_VARARGS, "dirent_canonicalize(dirent) -> dirent\n"
        "Canonicalize a dirent path."},
    { "abspath", py_abspath, METH_VARARGS, "abspath(path) -> path\n"
        "Return the absolute version of a path."},
    { NULL }
};

static PyObject *
moduleinit(void)
{
    PyObject *mod;

    apr_initialize();

#if PY_MAJOR_VERSION >= 3
    static struct PyModuleDef moduledef = {
      PyModuleDef_HEAD_INIT,
      "subr",         /* m_name */
      "subr", /* m_doc */
      -1,              /* m_size */
      subr_methods, /* m_methods */
      NULL,            /* m_reload */
      NULL,            /* m_traverse */
      NULL,            /* m_clear*/
      NULL,            /* m_free */
    };
    mod = PyModule_Create(&moduledef);
#else
    mod = Py_InitModule3("subr", subr_methods, "Subversion subr");
#endif
    if (mod == NULL)
        return NULL;

    return mod;
}

#if PY_MAJOR_VERSION >= 3
PyMODINIT_FUNC
PyInit_subr(void)
{
    return moduleinit();
}
#else
PyMODINIT_FUNC
initsubr(void)
{
    moduleinit();
}
#endif
