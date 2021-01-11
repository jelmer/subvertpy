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
#include <stdbool.h>
#include <Python.h>
#include <apr_general.h>
#include <apr_file_io.h>
#include <apr_portable.h>
#include <svn_error.h>
#include <svn_io.h>
#include <apr_errno.h>
#include <svn_error_codes.h>
#include <svn_config.h>
#include <svn_path.h>
#include <svn_props.h>

#include "util.h"

#define BZR_SVN_APR_ERROR_OFFSET (APR_OS_START_USERERR + \
								  (50 * SVN_ERR_CATEGORY_SIZE))

void PyErr_SetAprStatus(apr_status_t status)
{
	char errmsg[1024];

	PyErr_SetString(PyExc_Exception,
		apr_strerror(status, errmsg, sizeof(errmsg)));
}

const char *py_object_to_svn_path_or_url(PyObject *obj, apr_pool_t *pool)
{
    const char *ret;

    if (PyUnicode_Check(obj)) {
        obj = PyUnicode_AsUTF8String(obj);
        if (obj == NULL) {
            return NULL;
        }
    } else {
        Py_INCREF(obj);
    }

    if (!PyBytes_Check(obj)) {
        PyErr_SetString(PyExc_TypeError,
                        "URIs need to be UTF-8 bytestrings or unicode strings");
        Py_DECREF(obj);
        return NULL;
    }

    ret = PyBytes_AsString(obj);
    if (svn_path_is_url(ret)) {
        ret = svn_uri_canonicalize(ret, pool);
    } else {
        ret = svn_dirent_canonicalize(ret, pool);
    }

    Py_DECREF(obj);
    return ret;
}

const char *py_object_to_svn_abspath(PyObject *obj, apr_pool_t *pool)
{
    const char *ret;

    if (PyUnicode_Check(obj)) {
        obj = PyUnicode_AsUTF8String(obj);
        if (obj == NULL) {
            return NULL;
        }
    } else {
        Py_INCREF(obj);
    }

    if (!PyBytes_Check(obj)) {
        PyErr_SetString(PyExc_TypeError,
                        "URIs need to be UTF-8 bytestrings or unicode strings");
        Py_DECREF(obj);
        return NULL;
    }

    ret = PyBytes_AsString(obj);
    ret = apr_pstrdup(pool, ret);
    Py_DECREF(obj);
    if (ret == NULL) {
        return NULL;
    }
    if (svn_dirent_is_absolute(ret)) {
        return svn_dirent_canonicalize(ret, pool);
    } else {
        const char *absolute;
        RUN_SVN(svn_dirent_get_absolute(&absolute, ret, pool))
        return svn_dirent_canonicalize(absolute, pool);
    }
}

const char *py_object_to_svn_dirent(PyObject *obj, apr_pool_t *pool)
{
    const char *ret;

    if (PyUnicode_Check(obj)) {
        obj = PyUnicode_AsUTF8String(obj);
        if (obj == NULL) {
            return NULL;
        }
    } else {
        Py_INCREF(obj);
    }

    if (PyBytes_Check(obj)) {
        ret = svn_dirent_canonicalize(PyBytes_AsString(obj), pool);
        Py_DECREF(obj);
        return ret;
    } else {
        PyErr_SetString(PyExc_TypeError,
                        "URIs need to be UTF-8 bytestrings or unicode strings");
        Py_DECREF(obj);
        return NULL;
    }
}

char *py_object_to_svn_string(PyObject *obj, apr_pool_t *pool)
{
    char *ret;

    if (PyUnicode_Check(obj)) {
        obj = PyUnicode_AsUTF8String(obj);
        if (obj == NULL) {
            return NULL;
        }
    } else {
        Py_INCREF(obj);
    }

    if (PyBytes_Check(obj)) {
        ret = apr_pstrdup(pool, PyBytes_AsString(obj));
        Py_DECREF(obj);
        return ret;
    } else {
        PyErr_SetString(PyExc_TypeError,
                        "URIs need to be UTF-8 bytestrings or unicode strings");
        Py_DECREF(obj);
        return NULL;
    }
}

const char *py_object_to_svn_uri(PyObject *obj, apr_pool_t *pool)
{
	const char *ret;

	if (PyUnicode_Check(obj)) {
		obj = PyUnicode_AsUTF8String(obj);
		if (obj == NULL) {
			return NULL;
		}
	} else {
        Py_INCREF(obj);
    }

	if (PyBytes_Check(obj)) {
		ret = svn_uri_canonicalize(PyBytes_AsString(obj), pool);
		Py_DECREF(obj);
		return ret;
	} else {
		PyErr_SetString(PyExc_TypeError,
						"URIs need to be UTF-8 bytestrings or unicode strings");
		Py_DECREF(obj);
		return NULL;
	}
}

const char *py_object_to_svn_relpath(PyObject *obj, apr_pool_t *pool)
{
    const char *ret;

    if (PyUnicode_Check(obj)) {
        obj = PyUnicode_AsUTF8String(obj);
        if (obj == NULL) {
            return NULL;
        }
    } else {
        Py_INCREF(obj);
    }

    if (PyBytes_Check(obj)) {
        ret = svn_relpath_canonicalize(PyBytes_AsString(obj), pool);
        Py_DECREF(obj);
        return ret;
    } else {
        PyErr_SetString(PyExc_TypeError,
                        "relative paths need to be UTF-8 bytestrings or unicode strings");
        Py_DECREF(obj);
        return NULL;
    }
}

apr_pool_t *Pool(apr_pool_t *parent)
{
    apr_status_t status;
    apr_pool_t *ret;
    ret = NULL;
    status = apr_pool_create(&ret, parent);
    if (status != 0) {
        PyErr_SetAprStatus(status);
        return NULL;
    }
    return ret;
}

PyTypeObject *PyErr_GetSubversionExceptionTypeObject(void)
{
    PyObject *coremod, *excobj;
    coremod = PyImport_ImportModule("subvertpy");

    if (coremod == NULL) {
        return NULL;
    }

    excobj = PyObject_GetAttrString(coremod, "SubversionException");
    Py_DECREF(coremod);

    if (excobj == NULL) {
        PyErr_BadInternalCall();
        return NULL;
    }

    return (PyTypeObject *)excobj;
}

PyTypeObject *PyErr_GetGaiExceptionTypeObject(void)
{
    PyObject *socketmod, *excobj;
    socketmod = PyImport_ImportModule("socket");

    if (socketmod == NULL) {
        return NULL;
    }

    excobj = PyObject_GetAttrString(socketmod, "gaierror");
    Py_DECREF(socketmod);

    if (excobj == NULL) {
        PyErr_BadInternalCall();
        return NULL;
    }

    return (PyTypeObject *)excobj;
}

PyObject *PyErr_NewSubversionException(svn_error_t *error)
{
	PyObject *loc, *child;
	const char *message;
	char buf[1024];

	if (error->file != NULL) {
		loc = Py_BuildValue("(si)", error->file, error->line);
	} else {
		loc = Py_None;
		Py_INCREF(loc);
	}

	if (error->child != NULL) {
		PyTypeObject *cls = PyErr_GetSubversionExceptionTypeObject();
		PyObject *args = PyErr_NewSubversionException(error->child);
		child = PyObject_CallObject((PyObject *)cls, args);
		Py_DECREF(cls);
		Py_DECREF(args);
	} else {
		child = Py_None;
		Py_INCREF(child);
	}

	message = svn_err_best_message(error, buf, sizeof(buf)-1);

	return Py_BuildValue("(siNN)", message, error->apr_err, child, loc);
}

void PyErr_SetSubversionException(svn_error_t *error)
{
	PyObject *excval, *excobj;

	if (error->apr_err < 1000) {
		PyObject *excval = Py_BuildValue("(iz)", error->apr_err, error->message);
		PyErr_SetObject(PyExc_OSError, excval);
		Py_DECREF(excval);
		return;
	}

	if (error->apr_err >= APR_OS_START_SYSERR &&
		error->apr_err < APR_OS_START_SYSERR + APR_OS_ERRSPACE_SIZE) {
		PyObject *excval = Py_BuildValue("(iz)", error->apr_err - APR_OS_START_SYSERR, error->message);
		PyErr_SetObject(PyExc_OSError, excval);
		Py_DECREF(excval);
		return;
	}

	if (error->apr_err >= APR_OS_START_EAIERR &&
		error->apr_err < APR_OS_START_EAIERR + APR_OS_ERRSPACE_SIZE) {
		excobj = (PyObject *)PyErr_GetGaiExceptionTypeObject();
		if (excobj == NULL)
			return;

		excval = Py_BuildValue("(is)", error->apr_err - APR_OS_START_EAIERR,
							   error->message);
		if (excval == NULL)
			return;

		PyErr_SetObject(excobj, excval);
		Py_DECREF(excval);
		Py_DECREF(excobj);
		return;
	}

	excobj = (PyObject *)PyErr_GetSubversionExceptionTypeObject();
	if (excobj == NULL)
		return;

	excval = PyErr_NewSubversionException(error);
	PyErr_SetObject(excobj, excval);
	Py_DECREF(excval);
	Py_DECREF(excobj);
}

PyObject *PyOS_tmpfile(void)
{
	PyObject *tempfile, *tmpfile_fn, *ret;

	tempfile = PyImport_ImportModule("tempfile");
	if (tempfile == NULL)
		return NULL;

	tmpfile_fn = PyObject_GetAttrString(tempfile, "TemporaryFile");
	Py_DECREF(tempfile);

	if (tmpfile_fn == NULL)
		return NULL;

	ret = PyObject_CallObject(tmpfile_fn, NULL);
	Py_DECREF(tmpfile_fn);
	return ret;
}

void handle_svn_error(svn_error_t *error)
{
	if (error->apr_err == BZR_SVN_APR_ERROR_OFFSET)
		return; /* Just let Python deal with it */

	if (error->apr_err == SVN_ERR_CANCELLED &&
		error->child != NULL && error->child->apr_err == BZR_SVN_APR_ERROR_OFFSET)
		return; /* Cancelled because of a Python exception, let Python deal with it. */

	if (error->apr_err == SVN_ERR_RA_SVN_UNKNOWN_CMD) {
		/* svnserve doesn't handle the 'failure' command sent back
		 * by the client if one of the editor commands failed.
		 * Rather than bouncing the error sent by the client
		 * (BZR_SVN_APR_ERROR_OFFSET for example), it will send
		 * SVN_ERR_RA_SVN_UNKNOWN_CMD. */
		if (PyErr_Occurred() != NULL)
			return;
	}

	if (error->apr_err == SVN_ERR_RA_NOT_IMPLEMENTED) {
		PyErr_SetString(PyExc_NotImplementedError, error->message);
		return;
	}

	PyErr_SetSubversionException(error);
}

bool string_list_to_apr_array(apr_pool_t *pool, PyObject *l, apr_array_header_t **ret)
{
	int i;
	if (l == Py_None) {
		*ret = NULL;
		return true;
	}
	if (!PyList_Check(l)) {
		PyErr_Format(PyExc_TypeError, "Expected list of strings, got: %s",
					 l->ob_type->tp_name);
		return false;
	}
	*ret = apr_array_make(pool, PyList_Size(l), sizeof(char *));
	if (*ret == NULL) {
		PyErr_NoMemory();
		return false;
	}
	for (i = 0; i < PyList_GET_SIZE(l); i++) {
		PyObject *item = PyList_GET_ITEM(l, i);
		if (!PyUnicode_Check(item) && !PyBytes_Check(item)) {
			PyErr_Format(PyExc_TypeError, "Expected list of strings, item was %s", item->ob_type->tp_name);
			return false;
		}
		APR_ARRAY_PUSH(*ret, char *) = py_object_to_svn_string(item, pool);
	}
	return true;
}

bool relpath_list_to_apr_array(apr_pool_t *pool, PyObject *l, apr_array_header_t **ret)
{
	int i;
	const char *relpath;
	if (l == Py_None) {
		*ret = NULL;
		return true;
	}
	if (PyUnicode_Check(l) || PyBytes_Check(l)) {
		*ret = apr_array_make(pool, 1, sizeof(char *));
		relpath = py_object_to_svn_relpath(l, pool);
		if (relpath == NULL) {
			return false;
		}
		APR_ARRAY_PUSH(*ret, const char *) = relpath;
	} else if (PyList_Check(l)) {
		*ret = apr_array_make(pool, PyList_Size(l), sizeof(char *));
		for (i = 0; i < PyList_GET_SIZE(l); i++) {
			PyObject *item = PyList_GET_ITEM(l, i);
			relpath = py_object_to_svn_relpath(item, pool);
			if (relpath == NULL) {
				return false;
			}
			APR_ARRAY_PUSH(*ret, const char *) = relpath;
		}
	} else {
		PyErr_Format(PyExc_TypeError, "Expected list of strings, got: %s",
					 l->ob_type->tp_name);
		return false;
	}
	return true;
}

PyObject *prop_hash_to_dict(apr_hash_t *props)
{
	const char *key;
	apr_hash_index_t *idx;
	apr_ssize_t klen;
	svn_string_t *val;
	apr_pool_t *pool;
	PyObject *py_props;
	if (props == NULL) {
		return PyDict_New();
	}
	pool = Pool(NULL);
	if (pool == NULL)
		goto fail_pool;
	py_props = PyDict_New();
	if (py_props == NULL) {
		goto fail_props;
	}
	for (idx = apr_hash_first(pool, props); idx != NULL;
		 idx = apr_hash_next(idx)) {
		PyObject *py_key, *py_val;
		apr_hash_this(idx, (const void **)&key, &klen, (void **)&val);
		if (val == NULL || val->data == NULL) {
			py_val = Py_None;
			Py_INCREF(py_val);
		} else {
			py_val = PyBytes_FromStringAndSize(val->data, val->len);
		}
		if (py_val == NULL) {
			goto fail_item;
		}
		if (key == NULL) {
			py_key = Py_None;
			Py_INCREF(py_key);
		} else {
			py_key = PyUnicode_FromStringAndSize(key, klen);
		}
		if (PyDict_SetItem(py_props, py_key, py_val) != 0) {
			Py_DECREF(py_key);
			Py_DECREF(py_val);
			goto fail_item;
		}
		Py_DECREF(py_key);
		Py_DECREF(py_val);
	}
	apr_pool_destroy(pool);
	return py_props;

fail_item:
	Py_DECREF(py_props);
fail_props:
	apr_pool_destroy(pool);
fail_pool:
	return NULL;
}

apr_hash_t *prop_dict_to_hash(apr_pool_t *pool, PyObject *py_props)
{
	Py_ssize_t idx = 0;
	PyObject *k, *v;
	apr_hash_t *hash_props;
	svn_string_t *val_string;

	if (!PyDict_Check(py_props)) {
		PyErr_SetString(PyExc_TypeError, "props should be dictionary");
		return NULL;
	}

	hash_props = apr_hash_make(pool);
	if (hash_props == NULL) {
		PyErr_NoMemory();
		return NULL;
	}

	while (PyDict_Next(py_props, &idx, &k, &v)) {
		char *key, *val;
		Py_ssize_t val_size;

		key = py_object_to_svn_string(k, pool);
		if (key == NULL) {
			return NULL;
		}

		if (PyUnicode_Check(v)) {
			v = PyUnicode_AsUTF8String(v);
		} else {
			Py_INCREF(v);
		}

		if (PyBytes_AsStringAndSize(v, &val, &val_size) == -1) {
			return NULL;
		}

		val_string = svn_string_ncreate(val, val_size, pool);

		Py_DECREF(v);

		apr_hash_set(hash_props, key, strlen(key), val_string);
	}

	return hash_props;
}

#if PY_MAJOR_VERSION >= 3
#define SOURCEPATH_FORMAT3 "(CNl)"
#define SOURCEPATH_FORMAT4 "(CNli)"
#else
#define SOURCEPATH_FORMAT3 "(cNl)"
#define SOURCEPATH_FORMAT4 "(cNli)"
#endif

PyObject *pyify_changed_paths(apr_hash_t *changed_paths, bool node_kind, apr_pool_t *pool)
{
	PyObject *py_changed_paths, *pyval;
	apr_hash_index_t *idx;
	const char *key;
	apr_ssize_t klen;
	svn_log_changed_path_t *val;

	if (changed_paths == NULL) {
		py_changed_paths = Py_None;
		Py_INCREF(py_changed_paths);
	} else {
		py_changed_paths = PyDict_New();
		if (py_changed_paths == NULL) {
			return NULL;
		}
		for (idx = apr_hash_first(pool, changed_paths); idx != NULL;
			 idx = apr_hash_next(idx)) {
			PyObject *py_copyfrom_path, *py_key;

			apr_hash_this(idx, (const void **)&key, &klen, (void **)&val);
			if (val->copyfrom_path == NULL) {
				py_copyfrom_path = Py_None;
				Py_INCREF(Py_None);
			} else {
				py_copyfrom_path = PyUnicode_FromString(val->copyfrom_path);
			}
			if (node_kind) {
				pyval = Py_BuildValue(SOURCEPATH_FORMAT4, val->action, py_copyfrom_path,
											 val->copyfrom_rev,
											 svn_node_unknown);
			} else {
				pyval = Py_BuildValue(SOURCEPATH_FORMAT3, val->action, py_copyfrom_path,
											 val->copyfrom_rev);
			}
			if (pyval == NULL) {
				Py_DECREF(py_changed_paths);
				return NULL;
			}
			if (key == NULL) {
				PyErr_SetString(PyExc_RuntimeError, "path can not be NULL");
				Py_DECREF(pyval);
				Py_DECREF(py_changed_paths);
				return NULL;
			}

			py_key = PyUnicode_FromString(key);
			if (py_key == NULL) {
				Py_DECREF(pyval);
				Py_DECREF(py_changed_paths);
				return NULL;
			}

			if (PyDict_SetItem(py_changed_paths, py_key, pyval) != 0) {
				Py_DECREF(py_changed_paths);
				Py_DECREF(py_key);
				Py_DECREF(pyval);
				return NULL;
			}
			Py_DECREF(py_key);
			Py_DECREF(pyval);
		}
	}

	return py_changed_paths;
}

PyObject *pyify_changed_paths2(apr_hash_t *changed_paths, apr_pool_t *pool)
{
	PyObject *py_changed_paths, *pyval;
	apr_hash_index_t *idx;
	const char *key;
	apr_ssize_t klen;
	svn_log_changed_path2_t *val;

	if (changed_paths == NULL) {
		py_changed_paths = Py_None;
		Py_INCREF(py_changed_paths);
	} else {
		py_changed_paths = PyDict_New();
		if (py_changed_paths == NULL) {
			return NULL;
		}
		for (idx = apr_hash_first(pool, changed_paths); idx != NULL;
			 idx = apr_hash_next(idx)) {
			PyObject *py_key, *py_copyfrom_path;
			apr_hash_this(idx, (const void **)&key, &klen, (void **)&val);
			if (val->copyfrom_path == NULL) {
				py_copyfrom_path = Py_None;
				Py_INCREF(Py_None);
			} else {
				py_copyfrom_path = PyUnicode_FromString(val->copyfrom_path);
			}
			pyval = Py_BuildValue(SOURCEPATH_FORMAT4, val->action, py_copyfrom_path,
										 val->copyfrom_rev, val->node_kind);
			if (pyval == NULL) {
				Py_DECREF(py_changed_paths);
				return NULL;
			}
			if (key == NULL) {
				PyErr_SetString(PyExc_RuntimeError, "path can not be NULL");
				Py_DECREF(py_changed_paths);
				Py_DECREF(pyval);
				return NULL;
			}
			py_key = PyUnicode_FromString(key);
			if (py_key == NULL) {
				Py_DECREF(py_changed_paths);
				Py_DECREF(pyval);
				return NULL;
			}

			if (PyDict_SetItem(py_changed_paths, py_key, pyval) != 0) {
				Py_DECREF(pyval);
				Py_DECREF(py_key);
				Py_DECREF(py_changed_paths);
				return NULL;
			}
			Py_DECREF(py_key);
			Py_DECREF(pyval);
		}
	}

	return py_changed_paths;
}

bool pyify_log_message(apr_hash_t *changed_paths, const char *author,
const char *date, const char *message, bool node_kind, apr_pool_t *pool,
PyObject **py_changed_paths, PyObject **revprops)
{
	PyObject *obj;

	*py_changed_paths = pyify_changed_paths(changed_paths, node_kind,
		pool);
	if (*py_changed_paths == NULL) {
		goto fail;
	}

	*revprops = PyDict_New();
	if (*revprops == NULL) {
		goto fail_dict;
	}
	if (message != NULL) {
		obj = PyBytes_FromString(message);
		PyDict_SetItemString(*revprops, SVN_PROP_REVISION_LOG, obj);
		Py_DECREF(obj);
	}
	if (author != NULL) {
		obj = PyBytes_FromString(author);
		PyDict_SetItemString(*revprops, SVN_PROP_REVISION_AUTHOR, obj);
		Py_DECREF(obj);
	}
	if (date != NULL) {
		obj = PyBytes_FromString(date);
		PyDict_SetItemString(*revprops, SVN_PROP_REVISION_DATE, obj);
		Py_DECREF(obj);
	}
	return true;

fail_dict:
	Py_DECREF(*py_changed_paths);
fail:
	return false;
}

svn_error_t *py_svn_log_entry_receiver(void *baton, svn_log_entry_t *log_entry, apr_pool_t *pool)
{
	PyObject *revprops, *py_changed_paths, *ret;
	PyGILState_STATE state = PyGILState_Ensure();

	/* FIXME: Support include node_kind */
	py_changed_paths = pyify_changed_paths(log_entry->changed_paths, false, pool);
	CB_CHECK_PYRETVAL(py_changed_paths);

	revprops = prop_hash_to_dict(log_entry->revprops);
	CB_CHECK_PYRETVAL(revprops);

	ret = PyObject_CallFunction((PyObject *)baton, "OlOb", py_changed_paths,
								 log_entry->revision, revprops, log_entry->has_children);
	Py_DECREF(py_changed_paths);
	Py_DECREF(revprops);
	CB_CHECK_PYRETVAL(ret);
	Py_DECREF(ret);

	PyGILState_Release(state);
	return NULL;
}

svn_error_t *py_svn_log_wrapper(void *baton, apr_hash_t *changed_paths, svn_revnum_t revision, const char *author, const char *date, const char *message, apr_pool_t *pool)
{
	PyObject *revprops, *py_changed_paths, *ret;
	PyGILState_STATE state = PyGILState_Ensure();

	/*  FIXME: Support including node kind */
	if (!pyify_log_message(changed_paths, author, date, message, false,
	pool, &py_changed_paths, &revprops)) {
		PyGILState_Release(state);
		return py_svn_error();
	}
	ret = PyObject_CallFunction((PyObject *)baton, "OlO", py_changed_paths,
								 revision, revprops);
	Py_DECREF(py_changed_paths);
	Py_DECREF(revprops);
	CB_CHECK_PYRETVAL(ret);
	Py_DECREF(ret);

	PyGILState_Release(state);
	return NULL;
}

svn_error_t *py_svn_error()
{
	return svn_error_create(BZR_SVN_APR_ERROR_OFFSET, NULL, "Error occured in python bindings");
}

PyObject *wrap_lock(svn_lock_t *lock)
{
	return Py_BuildValue("(zzzbzz)", lock->path, lock->token, lock->owner,
						 lock->comment, lock->is_dav_comment,
						 lock->creation_date, lock->expiration_date);
}

apr_array_header_t *revnum_list_to_apr_array(apr_pool_t *pool, PyObject *l)
{
	int i;
	apr_array_header_t *ret;
	if (l == Py_None) {
		return NULL;
	}
	if (!PyList_Check(l)) {
		PyErr_SetString(PyExc_TypeError, "expected list with revision numbers");
		return NULL;
	}
	ret = apr_array_make(pool, PyList_Size(l), sizeof(svn_revnum_t));
	if (ret == NULL) {
		PyErr_NoMemory();
		return NULL;
	}
	for (i = 0; i < PyList_Size(l); i++) {
		PyObject *item = PyList_GetItem(l, i);
		long rev = py_to_svn_revnum(item);
		if (rev == -1 && PyErr_Occurred()) {
			return NULL;
		}
		APR_ARRAY_PUSH(ret, svn_revnum_t) = rev;
	}
	return ret;
}


static svn_error_t *py_stream_read(void *baton, char *buffer, apr_size_t *length)
{
	PyObject *self = (PyObject *)baton, *ret;
	PyGILState_STATE state = PyGILState_Ensure();

	ret = PyObject_CallMethod(self, "read", "i", *length);
	CB_CHECK_PYRETVAL(ret);

	if (!PyBytes_Check(ret)) {
		PyErr_SetString(PyExc_TypeError, "Expected stream read function to return bytes");
		PyGILState_Release(state);
		return py_svn_error();
	}
	*length = PyBytes_Size(ret);
	memcpy(buffer, PyBytes_AsString(ret), *length);
	Py_DECREF(ret);
	PyGILState_Release(state);
	return NULL;
}

static svn_error_t *py_stream_write(void *baton, const char *data, apr_size_t *len)
{
	PyObject *self = (PyObject *)baton, *ret, *py_data;
	PyGILState_STATE state = PyGILState_Ensure();

	py_data = PyBytes_FromStringAndSize(data, *len);
	CB_CHECK_PYRETVAL(py_data);

	ret = PyObject_CallMethod(self, "write", "O", py_data);
	CB_CHECK_PYRETVAL(ret);
	Py_DECREF(ret);
	PyGILState_Release(state);
	return NULL;
}

static svn_error_t *py_stream_close(void *baton)
{
	PyObject *self = (PyObject *)baton, *ret;
	PyGILState_STATE state = PyGILState_Ensure();
	ret = PyObject_CallMethod(self, "close", "");
	Py_DECREF(self);
	CB_CHECK_PYRETVAL(ret);
	Py_DECREF(ret);
	PyGILState_Release(state);
	return NULL;
}

svn_stream_t *new_py_stream(apr_pool_t *pool, PyObject *py)
{
	svn_stream_t *stream;
	stream = svn_stream_create((void *)py, pool);
	if (stream == NULL) {
		PyErr_SetString(PyExc_RuntimeError,
						"Unable to create a Subversion stream");
		return NULL;
	}
	Py_INCREF(py);
	svn_stream_set_read(stream, py_stream_read);
	svn_stream_set_write(stream, py_stream_write);
	svn_stream_set_close(stream, py_stream_close);
	return stream;
}

svn_error_t *py_cancel_check(void *cancel_baton)
{
	PyGILState_STATE state = PyGILState_Ensure();

	if (PyErr_Occurred()) {
		PyGILState_Release(state);
		return svn_error_create(SVN_ERR_CANCELLED, py_svn_error(),
			"Python exception raised");
	}
	PyGILState_Release(state);

	return NULL;
}

static apr_hash_t *get_default_config(void)
{
	static bool initialised = false;
	static apr_pool_t *pool = NULL;
	static apr_hash_t *default_config = NULL;

	if (!initialised) {
		pool = Pool(NULL);
		RUN_SVN_WITH_POOL(pool,
					  svn_config_get_config(&default_config, NULL, pool));
		/* TODO(jelmer): Deal with pool */
		initialised = true;
	}

	return default_config;
}

apr_hash_t *config_hash_from_object(PyObject *config, apr_pool_t *pool)
{
	if (config == Py_None) {
		return get_default_config();
	} else {
        return ((ConfigObject *)config)->config;
    }
}

PyObject *py_dirent(const svn_dirent_t *dirent, int dirent_fields)
{
	PyObject *ret, *obj;
	ret = PyDict_New();
	if (ret == NULL)
		return NULL;
	if (dirent_fields & SVN_DIRENT_KIND) {
#if PY_MAJOR_VERSION < 3
		obj = PyInt_FromLong(dirent->kind);
#else
		obj = PyLong_FromLong(dirent->kind);
#endif
		PyDict_SetItemString(ret, "kind", obj);
		Py_DECREF(obj);
	}
	if (dirent_fields & SVN_DIRENT_SIZE) {
		obj = PyLong_FromLongLong(dirent->size);
		PyDict_SetItemString(ret, "size", obj);
		Py_DECREF(obj);
	}
	if (dirent_fields & SVN_DIRENT_HAS_PROPS) {
		obj = PyBool_FromLong(dirent->has_props);
		PyDict_SetItemString(ret, "has_props", obj);
		Py_DECREF(obj);
	}
	if (dirent_fields & SVN_DIRENT_CREATED_REV) {
		obj = PyLong_FromLong(dirent->created_rev);
		PyDict_SetItemString(ret, "created_rev", obj);
		Py_DECREF(obj);
	}
	if (dirent_fields & SVN_DIRENT_TIME) {
		obj = PyLong_FromLongLong(dirent->time);
		PyDict_SetItemString(ret, "time", obj);
		Py_DECREF(obj);
	}
	if (dirent_fields & SVN_DIRENT_LAST_AUTHOR) {
		if (dirent->last_author != NULL) {
			obj = PyBytes_FromString(dirent->last_author);
		} else {
			obj = Py_None;
			Py_INCREF(obj);
		}
		PyDict_SetItemString(ret, "last_author", obj);
		Py_DECREF(obj);
	}
	return ret;
}

apr_file_t *apr_file_from_object(PyObject *object, apr_pool_t *pool)
{
	apr_status_t status;
	int fd = -1;
	apr_file_t *fp = NULL;
	apr_os_file_t osfile;
	if ((fd = PyObject_AsFileDescriptor(object)) >= 0)
	{
#ifdef WIN32
		osfile = (apr_os_file_t)_get_osfhandle(fd);
#else
		osfile = (apr_os_file_t)fd;
#endif
	}
	else
	{
		PyErr_SetString(PyExc_TypeError, "Unknown type for file variable");
		return NULL;
	}

	status = apr_os_file_put(&fp, &osfile,
			APR_FOPEN_WRITE | APR_FOPEN_CREATE, pool);
	if (status != 0) {
		PyErr_SetAprStatus(status);
		return NULL;
	}

	return fp;
}

static void stream_dealloc(PyObject *self)
{
	StreamObject *streamself = (StreamObject *)self;

	apr_pool_destroy(streamself->pool);

	PyObject_Del(self);
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
	ret->closed = false;

	return (PyObject *)ret;
}

static PyObject *stream_close(StreamObject *self)
{
	if (!self->closed) {
		svn_stream_close(self->stream);
		self->closed = true;
	}
	Py_RETURN_NONE;
}

static PyObject *stream_write(StreamObject *self, PyObject *args)
{
	char *buffer;
	Py_ssize_t len;
	size_t length;
	if (!PyArg_ParseTuple(args, "s#", &buffer, &len))
		return NULL;

	if (self->closed) {
		PyErr_SetString(PyExc_RuntimeError, "unable to write: stream already closed");
		return NULL;
	}

	length = len;

	RUN_SVN(svn_stream_write(self->stream, buffer, &length));

	return PyLong_FromLong(length);
}

static PyObject *stream_read_full(StreamObject *self, PyObject *args)
{
	/* TODO(jelmer): Implemented stream_read2 */
	PyObject *ret;
	apr_pool_t *temp_pool;
	long len = -1;
	if (!PyArg_ParseTuple(args, "|l", &len))
		return NULL;

	if (self->closed) {
		return PyBytes_FromString("");
	}

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
		RUN_SVN_WITH_POOL(temp_pool, svn_stream_read_full(self->stream, buffer, &size));
		ret = PyBytes_FromStringAndSize(buffer, size);
		apr_pool_destroy(temp_pool);
		return ret;
	} else {
		svn_string_t *result;
		RUN_SVN_WITH_POOL(temp_pool, svn_string_from_stream(&result,
							   self->stream,
							   temp_pool,
							   temp_pool));
		self->closed = true;
		ret = PyBytes_FromStringAndSize(result->data, result->len);
		apr_pool_destroy(temp_pool);
		return ret;
	}
}

static PyMethodDef stream_methods[] = {
	{ "read_full", (PyCFunction)stream_read_full, METH_VARARGS, NULL },
	{ "read", (PyCFunction)stream_read_full, METH_VARARGS, NULL },
	{ "write", (PyCFunction)stream_write, METH_VARARGS, NULL },
	{ "close", (PyCFunction)stream_close, METH_NOARGS, NULL },
	{ NULL, }
};

PyTypeObject Stream_Type = {
	PyVarObject_HEAD_INIT(NULL, 0)
	"repos.Stream", /*	const char *tp_name;  For printing, in format "<module>.<name>" */
	sizeof(StreamObject),
	0,/*	Py_ssize_t tp_basicsize, tp_itemsize;  For allocation */

	/* Methods to implement standard operations */

	.tp_dealloc = stream_dealloc, /*	destructor tp_dealloc;	*/

	.tp_doc = "Byte stream", /*	const char *tp_doc;  Documentation string */

	.tp_methods = stream_methods, /*	struct PyMethodDef *tp_methods;	*/

	.tp_new = stream_init, /* tp_new tp_new */
};

PyObject *dirent_hash_to_dict(apr_hash_t *dirents, unsigned int dirent_fields, apr_pool_t *temp_pool)
{
	svn_dirent_t *dirent;
	apr_ssize_t klen;
	const char *key;
	apr_hash_index_t *idx;
	PyObject *py_dirents = PyDict_New();

	if (py_dirents == NULL) {
		return NULL;
	}
	idx = apr_hash_first(temp_pool, dirents);
	while (idx != NULL) {
		PyObject *item, *pykey;
		apr_hash_this(idx, (const void **)&key, &klen, (void **)&dirent);
		item = py_dirent(dirent, dirent_fields);
		if (item == NULL) {
			Py_DECREF(py_dirents);
			return NULL;
		}
		if (key == NULL) {
			pykey = Py_None;
			Py_INCREF(pykey);
		} else {
			pykey = PyUnicode_FromStringAndSize(key, klen);
		}
		if (PyDict_SetItem(py_dirents, pykey, item) != 0) {
			Py_DECREF(item);
			Py_DECREF(pykey);
			Py_DECREF(py_dirents);
			return NULL;
		}
		Py_DECREF(pykey);
		Py_DECREF(item);
		idx = apr_hash_next(idx);
	}
	return py_dirents;
}

PyObject *propchanges_to_list(const apr_array_header_t *propchanges)
{
    int i;
    svn_prop_t el;
    PyObject *py_propchanges = PyList_New(propchanges->nelts);
    PyObject *pyval;
    if (py_propchanges == NULL) {
        return NULL;
    }
    for (i = 0; i < propchanges->nelts; i++) {
        el = APR_ARRAY_IDX(propchanges, i, svn_prop_t);
        if (el.value != NULL)
            pyval = Py_BuildValue("(sz#)", el.name, el.value->data, el.value->len);
        else
            pyval = Py_BuildValue("(sO)", el.name, Py_None);
        if (pyval == NULL) {
            Py_DECREF(py_propchanges);
            return NULL;
        }
        if (PyList_SetItem(py_propchanges, i, pyval) != 0) {
            Py_DECREF(py_propchanges);
            return NULL;
        }
    }

    return py_propchanges;
}
