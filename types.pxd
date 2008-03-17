# Copyright (C) 2008 Jelmer Vernooij <jelmer@samba.org>
# vim: ft=pyrex

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from apr cimport apr_status_t, apr_pool_t, apr_time_t, apr_array_header_t, apr_hash_t, apr_size_t, apr_uint32_t

cdef extern from "svn_version.h":
    ctypedef struct svn_version_t:
        int major
        int minor
        int patch
        char *tag


cdef extern from "svn_error.h":
    ctypedef struct svn_error_t:
        apr_status_t apr_err
        svn_error_t *child
        char *message
        char *file
        char *line
    cdef svn_error_t *svn_error_create(apr_status_t apr_err, 
                                       svn_error_t *child, char *message)

cdef extern from "svn_types.h":
    ctypedef int svn_boolean_t
    ctypedef unsigned long long svn_filesize_t
    ctypedef svn_error_t *(*svn_cancel_func_t)(cancel_baton)
    ctypedef long svn_revnum_t
    ctypedef struct svn_lock_t:
        char *path
        char *token
        char *owner
        char *comment
        svn_boolean_t is_dav_comment
        apr_time_t creation_date
        apr_time_t expiration_date
    ctypedef enum svn_node_kind_t:
        svn_node_none
        svn_node_file
        svn_node_dir
        svn_node_unknown
    ctypedef struct svn_commit_info_t:
        long revision
        char *date
        char *author
        char *post_commit_err
    ctypedef struct svn_dirent_t:
        svn_node_kind_t kind
        svn_filesize_t size
        svn_boolean_t has_props
        svn_revnum_t created_rev
        apr_time_t time
        char *last_author
    ctypedef struct svn_log_changed_path_t:
        char action
        char *copyfrom_path
        svn_revnum_t copyfrom_rev
    ctypedef svn_error_t *(*svn_log_message_receiver_t) (baton, apr_hash_t *changed_paths, long revision, char *author, char *date, char *message, apr_pool_t *pool) except *

cdef extern from "svn_string.h":
    ctypedef struct svn_string_t:
        char *data
        long len
    ctypedef struct svn_stringbuf_t:
        apr_pool_t *pool
        char *data
        apr_size_t len
        apr_size_t blocksize
    svn_string_t *svn_string_ncreate(char *bytes, long size, apr_pool_t *pool)
    svn_stringbuf_t *svn_stringbuf_ncreate(char *bytes, apr_size_t size, apr_pool_t *pool)


cdef extern from "svn_io.h":
    ctypedef struct svn_stream_t
    ctypedef svn_error_t *(*svn_read_fn_t)(void *baton, char *buffer, apr_size_t *len) 
    ctypedef svn_error_t *(*svn_write_fn_t)(void *baton, char *data, apr_size_t *len)
    ctypedef svn_error_t *(*svn_close_fn_t)(void *baton) 
    void svn_stream_set_read(svn_stream_t *stream, svn_read_fn_t read_fn)
    void svn_stream_set_write(svn_stream_t *stream, svn_write_fn_t write_fn)
    void svn_stream_set_close(svn_stream_t *stream, svn_close_fn_t close_fn)
    svn_stream_t *svn_stream_from_stringbuf(svn_stringbuf_t *str, apr_pool_t *pool)
    svn_stream_t *svn_stream_create(void *baton, apr_pool_t *pool)

cdef extern from "svn_props.h":
    ctypedef struct svn_prop_t:
        char *name
        svn_string_t *value

cdef extern from "svn_auth.h":
    ctypedef struct svn_auth_baton_t
    void svn_auth_open(svn_auth_baton_t **auth_baton,
                       apr_array_header_t *providers,
                       apr_pool_t *pool)
    void svn_auth_set_parameter(svn_auth_baton_t *auth_baton, 
                                char *name, void *value)
    void *svn_auth_get_parameter(svn_auth_baton_t *auth_baton,
                                  char *name)
    ctypedef struct svn_auth_provider_t:
        char *cred_kind
        svn_error_t * (*first_credentials)(void **credentials,
                                            void **iter_baton,
                                             void *provider_baton,
                                             apr_hash_t *parameters,
                                             char *realmstring,
                                             apr_pool_t *pool)
        svn_error_t * (*next_credentials)(void **credentials,
                                            void *iter_baton,
                                            void *provider_baton,
                                            apr_hash_t *parameters,
                                            char *realmstring,
                                            apr_pool_t *pool)
         
        svn_error_t * (*save_credentials)(int *saved,
                                    void *credentials,
                                    void *provider_baton,
                                    apr_hash_t *parameters,
                                    char *realmstring,
                                    apr_pool_t *pool)

    ctypedef struct svn_auth_provider_object_t:
        svn_auth_provider_t *vtable
        void *provider_baton

    ctypedef struct svn_auth_cred_simple_t:
        char *username
        char *password
        int may_save

    ctypedef struct svn_auth_cred_username_t:
        char *username
        svn_boolean_t may_save

    ctypedef svn_error_t *(*svn_auth_simple_prompt_func_t) (svn_auth_cred_simple_t **cred, void *baton, char *realm, char *username, int may_save, apr_pool_t *pool)

    void svn_auth_get_simple_prompt_provider(
            svn_auth_provider_object_t **provider, svn_auth_simple_prompt_func_t prompt_func, void *prompt_baton, int retry_limit, apr_pool_t *pool)

    ctypedef svn_error_t *(*svn_auth_username_prompt_func_t) (svn_auth_cred_username_t **cred, void *baton, char *realm, svn_boolean_t may_save, apr_pool_t *pool)

    void svn_auth_get_username_prompt_provider (svn_auth_provider_object_t **provider, svn_auth_username_prompt_func_t prompt_func, void *prompt_baton, int retry_limit, apr_pool_t *pool)

    ctypedef struct svn_auth_ssl_server_cert_info_t:
        char *hostname
        char *fingerprint
        char *valid_from
        char *valid_until
        char *issuer_dname
        char *ascii_cert

    ctypedef struct svn_auth_cred_ssl_server_trust_t:
        svn_boolean_t may_save
        apr_uint32_t accepted_failures

    ctypedef svn_error_t *(*svn_auth_ssl_server_trust_prompt_func_t) (svn_auth_cred_ssl_server_trust_t **cred, void *baton, char *realm, apr_uint32_t failures, svn_auth_ssl_server_cert_info_t *cert_info, svn_boolean_t may_save, apr_pool_t *pool)

    void svn_auth_get_ssl_server_trust_prompt_provider(svn_auth_provider_object_t **provider, svn_auth_ssl_server_trust_prompt_func_t prompt_func, void *prompt_baton, apr_pool_t *pool)

    ctypedef struct svn_auth_cred_ssl_client_cert_pw_t:
        char *password
        svn_boolean_t may_save

    ctypedef svn_error_t *(*svn_auth_ssl_client_cert_pw_prompt_func_t) (svn_auth_cred_ssl_client_cert_pw_t **cred, void *baton, char *realm, svn_boolean_t may_save, apr_pool_t *pool)

    void svn_auth_get_ssl_client_cert_pw_prompt_provider(svn_auth_provider_object_t **provider, svn_auth_ssl_client_cert_pw_prompt_func_t prompt_func, void *prompt_baton, int retry_limit, apr_pool_t *pool)

    void svn_auth_get_simple_provider(svn_auth_provider_object_t **provider, apr_pool_t *pool)
    void svn_auth_get_username_provider(svn_auth_provider_object_t **provider, apr_pool_t *pool)
    void svn_auth_get_ssl_server_trust_file_provider(svn_auth_provider_object_t **provider, apr_pool_t *pool)
    void svn_auth_get_ssl_client_cert_file_provider(svn_auth_provider_object_t **provider, apr_pool_t *pool)
    void svn_auth_get_ssl_client_cert_pw_file_provider (svn_auth_provider_object_t **provider, apr_pool_t *pool)
