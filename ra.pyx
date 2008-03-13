# Copyright (C) 2008 Jelmer Vernooij <jelmer@samba.org>

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

cdef extern from "svn_version.h":
    ctypedef struct svn_version_t:
        int major
        int minor
        int patch
        char *tag

cdef extern from "svn_error.h":
    ctypedef struct svn_error_t

cdef extern from "svn_auth.h":
    ctypedef struct svn_auth_baton_t

cdef extern from "apr_errno.h":
    ctypedef int apr_status_t

cdef extern from "apr_general.h":
    apr_status_t apr_initialize()

cdef extern from "apr_file_io.h":
    ctypedef struct apr_file_t 

apr_initialize()

cdef extern from "apr_pools.h":
    ctypedef struct apr_pool_t
    void apr_pool_destroy(apr_pool_t *)
    apr_status_t apr_pool_create(apr_pool_t **newpool, apr_pool_t *parent)

cdef apr_pool_t *Pool(apr_pool_t *parent):
    cdef apr_status_t status
    cdef apr_pool_t *ret
    ret = NULL
    status = apr_pool_create(&ret, parent)
    if status != 0:
        # FIXME: Clearer error
        raise Exception("APR Error")
    return ret

cdef extern from "apr_tables.h":
    ctypedef struct apr_array_header_t
    apr_array_header_t *apr_array_make(apr_pool_t *p, int nelts, int elt_size)
    void *apr_array_push(apr_array_header_t *arr)
    void *apr_array_pop(apr_array_header_t *arr)

cdef extern from "apr_hash.h":
    ctypedef struct apr_hash_t
    ctypedef struct apr_hash_index_t
    apr_hash_t *apr_hash_make(apr_pool_t *pool)
    void apr_hash_set(apr_hash_t *ht, char *key, long klen, char *val)
    apr_hash_index_t *apr_hash_first(apr_pool_t *p, apr_hash_t *ht)
    apr_hash_index_t * apr_hash_next(apr_hash_index_t *hi)
    void apr_hash_this(apr_hash_index_t *hi, void **key, 
                                long *klen, void **val)

cdef extern from "svn_types.h":
    ctypedef svn_error_t *(*svn_log_message_receiver_t) (baton, apr_hash_t *changed_paths, long revision, char *author, char *date, char *message, apr_pool_t *pool)

cdef svn_error_t *py_svn_log_wrapper(baton, apr_hash_t *changed_paths, long revision, char *author, char *date, char *message, apr_pool_t *pool):
    cdef apr_hash_index_t *idx
    if changed_paths == NULL:
        py_changed_paths = None
    else:
        py_changed_paths = {}
        idx = apr_hash_first(pool, changed_paths)
        while idx:
            # FIXME: apr_hash_this(idx, key, val
            idx = apr_hash_next(idx)
    baton(py_changed_paths, revision, author, date, message)

cdef extern from "svn_ra.h":
    svn_version_t *svn_ra_version()

    ctypedef struct svn_ra_reporter2_t:
        svn_error_t *(*set_path)(void *report_baton,
                           char *path,
                           long revision,
                           int start_empty,
                           char *lock_token,
                           apr_pool_t *pool)

        svn_error_t *(*delete_path)(void *report_baton, 
                char *path, apr_pool_t *pool)

        svn_error_t *(*link_path)(void *report_baton,
                                char *path,
                                char *url,
                                long revision,
                                int start_empty,
                                char *lock_token,
                                apr_pool_t *pool)

        svn_error_t *(*finish_report)(void *report_baton, apr_pool_t *pool)

        svn_error_t *(*abort_report)(void *report_baton, apr_pool_t *pool)

    ctypedef struct svn_ra_callbacks2_t:
        svn_error_t *(*open_tmp_file)(apr_file_t **fp, 
                                      void *callback_baton, apr_pool_t *pool)
        svn_auth_baton_t *auth_baton

    svn_error_t *svn_ra_create_callbacks(svn_ra_callbacks2_t **callbacks,
                            apr_pool_t *pool)

    ctypedef struct svn_ra_session_t

    svn_error_t *svn_ra_open2(svn_ra_session_t **session_p,
                          char *repos_URL,
                          svn_ra_callbacks2_t *callbacks,
                          callback_baton,
                          apr_hash_t *config,
                          apr_pool_t *pool)

    svn_error_t *svn_ra_reparent(svn_ra_session_t *ra_session, char *url, 
            apr_pool_t *pool)

    svn_error_t *svn_ra_get_latest_revnum(svn_ra_session_t *session,
                                      long *latest_revnum,
                                      apr_pool_t *pool)

    svn_error_t *svn_ra_get_uuid(svn_ra_session_t *session,
                             char **uuid,
                             apr_pool_t *pool)

    svn_error_t *svn_ra_get_repos_root(svn_ra_session_t *session,
                             char **root,
                             apr_pool_t *pool)

    svn_error_t *svn_ra_get_log(svn_ra_session_t *session,
                                apr_array_header_t *paths,
                                long start,
                                long end,
                                int limit,
                                int discover_changed_paths,
                                int strict_node_history,
                                svn_log_message_receiver_t receiver,
                                receiver_baton,
                                apr_pool_t *pool)

def version():
    """Get libsvn_ra version information.

    :return: tuple with major, minor, patch version number and tag.
    """
    return (svn_ra_version().major, svn_ra_version().minor, 
            svn_ra_version().minor, svn_ra_version().tag)

cdef void _check_error(svn_error_t *error):
    if error:
        # FIXME
        raise Exception("SVN error")

cdef class RemoteAccess:
    cdef svn_ra_session_t *ra
    cdef apr_pool_t *pool
    cdef char *url
    def __init__(self, url, callbacks=object(), config={}):
        """Connect to a remote Subversion repository. 

        :param url: URL of the repository
        :param callbacks: Object to report progress and errors to.
        :param config: Optional configuration
        """
        cdef svn_error_t *error
        cdef svn_ra_callbacks2_t *callbacks2
        cdef apr_hash_t *config_hash
        self.url = url
        self.pool = Pool(NULL)
        assert self.pool != NULL
        _check_error(svn_ra_create_callbacks(&callbacks2, self.pool))
        config_hash = apr_hash_make(self.pool)
        for (key, val) in config.items():
            apr_hash_set(config_hash, key, len(key), val)
        _check_error(svn_ra_open2(&self.ra, url, callbacks2, None, config_hash, 
                     self.pool))

    def get_uuid(self):
        """Obtain the globally unique identifier for this repository."""
        cdef char *uuid
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        _check_error(svn_ra_get_uuid(self.ra, &uuid, temp_pool))
        apr_pool_destroy(temp_pool)
        return uuid

    def reparent(self, url):
        """Switch to a different url."""
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        _check_error(svn_ra_reparent(self.ra, url, temp_pool))
        apr_pool_destroy(temp_pool)

    def get_latest_revnum(self):
        """Obtain the number of the latest committed revision in the 
        connected repository.
        """
        cdef long latest_revnum
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        _check_error(svn_ra_get_latest_revnum(self.ra, &latest_revnum, 
                     temp_pool))
        apr_pool_destroy(temp_pool)
        return latest_revnum

    def get_log(self, paths, start, end, callback, limit=0, 
                discover_changed_paths=True, strict_node_history=True):
        cdef apr_array_header_t *paths_array
        cdef apr_pool_t *temp_pool
        _check_error(svn_ra_get_log(self.ra, paths_array, start, end, limit,
            discover_changed_paths, strict_node_history, py_svn_log_wrapper, 
            callback, temp_pool))
        apr_pool_destroy(temp_pool)

    def get_repos_root(self):
        """Obtain the URL of the root of this repository."""
        cdef char *root
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        _check_error(svn_ra_get_repos_root(self.ra, &root, 
                     temp_pool))
        apr_pool_destroy(temp_pool)
        return root

    def __dealloc__(self):
        if self.pool != NULL:
            apr_pool_destroy(self.pool)

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.url)
