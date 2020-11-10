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
 * but WITHOUT ANY WARWCNTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA
 */

#ifndef _BZR_SVN_WC_H_
#define _BZR_SVN_WC_H_

#ifdef __GNUC__
#pragma GCC visibility push(hidden)
#endif

bool py_dict_to_wcprop_changes(PyObject *dict, apr_pool_t *pool, apr_array_header_t **ret);
void py_wc_notify_func(void *baton, const svn_wc_notify_t *notify, apr_pool_t *pool);
PyObject *py_wc_status2(svn_wc_status2_t *status);
extern const svn_ra_reporter3_t py_ra_reporter3;
extern const svn_ra_reporter2_t py_ra_reporter2;

svn_error_t *wc_validator3(void *baton, const char *uuid, const char *url, const char *root_url, apr_pool_t *pool);
svn_error_t *wc_validator2(void *baton, const char *uuid, const char *url, svn_boolean_t root, apr_pool_t *pool);
svn_wc_committed_queue_t *PyObject_GetCommittedQueue(PyObject *obj);
extern PyTypeObject CommittedQueue_Type;
svn_lock_t *py_object_to_svn_lock(PyObject *py_lock, apr_pool_t *pool);

#ifdef __GNUC__
#pragma GCC visibility pop
#endif

#endif /* _BZR_SVN_WC_H_ */
