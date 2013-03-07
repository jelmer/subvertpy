/*
 * Copyright © 2012 Yonggang Luo <luoyonggang@gmail.org>
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

#ifndef _SUBVERTPY_PY_FIXUP_H_
#define _SUBVERTPY_PY_FIXUP_H_

/*Macros and functions to ease compatibility with Python 2 and Python 3.*/

#if PY_VERSION_HEX >= 0x03000000 && PY_VERSION_HEX < 0x03010000
#error Python 3.0 is not supported.  Please use 3.1 and higher.
#endif

/* There's no Py_ssize_t and T_PYSSIZET in 2.4, apparently */
#if PY_VERSION_HEX < 0x2050000
typedef int Py_ssize_t;
#define T_PYSSIZET 19
#endif


/*Macros introduced in 2.6, backported for 2.4 and 2.5.*/
#ifndef PyVarObject_HEAD_INIT
#define PyVarObject_HEAD_INIT(type, size) PyObject_HEAD_INIT(type) size,
#endif
#ifndef Py_TYPE
#define Py_TYPE(ob) (((PyObject*)(ob))->ob_type)
#endif

/*Fixup for MSVC inline.*/
#ifdef _MSC_VER
#define inline __inline
#endif

/*Used for items that are ANSI in Python 2 and Unicode in Python 3 or in int 2 and long in 3.*/

#if PY_MAJOR_VERSION >= 3
  #define staticforward static
  #define PyModule_DEFINE(ob, name, doc, methods) \
      {static struct PyModuleDef module_##ob = { \
          PyModuleDef_HEAD_INIT, name, doc, -1, methods, }; \
      ob = PyModule_Create(&module_##ob);}

  #define PyModule_Init_DEFINE(module_name) PyMODINIT_FUNC PyInit_##module_name(void)
  #define PyModule_RETURN(v) return (v)

  #define PyInt_FromLong PyLong_FromLong
  #define PyInt_AsLong PyLong_AsLong
  #define PyInt_AS_LONG PyLong_AS_LONG
  #define PyInt_Check PyLong_Check
  #define PyInt_Type PyLong_Type
  #define Py_TPFLAGS_HAVE_ITER 0

  #define PyText_Check PyUnicode_Check
  #define PyText_FromFormat PyUnicode_FromFormat
  #define PyText_FromString PyUnicode_FromString
  #define PyText_FromStringAndSize(data, len) PyUnicode_DecodeUTF8(data, len, NULL)
  #define PyText_AsString PyUnicode_AsString
  #define PyText_AsStringAndSize PyUnicode_AsStringAndSize

#else /* PY_MAJOR_VERSION */
  #include <stringobject.h>
  #include <intobject.h>
  #include <bufferobject.h>

  #define PyModule_DEFINE(ob, name, doc, methods) \
      ob = Py_InitModule3(name, methods, doc);

  #define PyModule_Init_DEFINE(module_name) void init##module_name(void)
  #define PyModule_RETURN(v)

  #define PyBytes_Check PyString_Check
  #define PyBytes_FromString PyString_FromString
  #define PyBytes_FromStringAndSize PyString_FromStringAndSize
  #define PyBytes_AsString PyString_AsString
  #define PyBytes_AsStringAndSize PyString_AsStringAndSize
  #define PyBytes_GET_SIZE PyString_GET_SIZE

  #define PyText_Check PyString_Check
  #define PyText_FromFormat PyString_FromFormat
  #define PyText_FromString PyString_FromString
  #define PyText_FromStringAndSize PyString_FromStringAndSize
  #define PyText_AsString PyString_AsString
  #define PyText_AsStringAndSize PyString_AsStringAndSize

#endif /* PY_MAJOR_VERSION */


static inline bool PyInteger_Check(PyObject *o)
{
#if PY_MAJOR_VERSION < 3
    if (o && PyInt_Check(o))
        return true;
#endif
    return o && PyLong_Check(o);
}


static inline long PyInteger_AsLong(PyObject *o)
{
#if PY_MAJOR_VERSION < 3
    if (o && PyInt_Check(o))
        return PyInt_AsLong(o);
#endif
    return PyLong_AsLong(o);
}


static inline char* PyUnicode_AsString(PyObject *o)
{
    o = PyUnicode_AsEncodedString(o, "utf-8", "Error");
    return PyBytes_AsString(o);
}


static inline int PyUnicode_AsStringAndSize(PyObject *o, char **buffer, Py_ssize_t *length)
{
    o = PyUnicode_AsEncodedString(o, "utf-8", "Error");
    return PyBytes_AsStringAndSize(o, buffer, length);
}


static inline PyObject* PyText_New(Py_ssize_t length)
{
    /*Returns a new, uninitialized String (Python 2) or Unicode object (Python 3) object.*/
#if PY_MAJOR_VERSION < 3
    return PyString_FromStringAndSize(0, length);
#else
    return PyUnicode_FromUnicode(0, length);
#endif
}


static inline bool PyText_CheckAll(PyObject* o)
{
    /*Check Text is Bytes or Unicode*/
    if (o && PyBytes_Check(o))
        return true;
    if (o && PyUnicode_Check(o))
        return true;
    return false;
}


static inline char* PyText_AsStringAll(PyObject* o)
{
    if (o && PyBytes_Check(o))
        return PyBytes_AsString(o);
    return PyUnicode_AsString(o);
}


static inline Py_ssize_t PyText_Size(PyObject* o)
{
#if PY_MAJOR_VERSION < 3
    if (o && PyBytes_Check(o))
        return PyBytes_GET_SIZE(o);
#else
    if (o && PyUnicode_Check(o))
        return PyUnicode_GET_SIZE(o);
#endif
    return 0;
}


static inline Py_ssize_t PyText_SizeAll(PyObject* o)
{
    if (o && PyBytes_Check(o))
        return PyBytes_GET_SIZE(o);
    if (o && PyUnicode_Check(o))
        return PyUnicode_GET_SIZE(o);
    return 0;
}

#endif /* _SUBVERTPY_PY_FIXUP_H_ */
