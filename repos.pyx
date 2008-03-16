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

from apr cimport apr_pool_t, apr_hash_t, apr_pool_destroy
from types cimport svn_error_t, svn_boolean_t, svn_cancel_func_t, svn_stream_t

from core cimport Pool, check_error, new_py_stream, py_cancel_func

cdef extern from "svn_fs.h":
    ctypedef struct svn_fs_t
    svn_error_t *svn_fs_get_uuid(svn_fs_t *fs, char **uuid, apr_pool_t *pool)

cdef extern from "svn_repos.h":
    ctypedef struct svn_repos_t
    enum svn_repos_load_uuid:
        svn_repos_load_uuid_default,
        svn_repos_load_uuid_ignore,
        svn_repos_load_uuid_force
    svn_error_t *svn_repos_create(svn_repos_t **repos_p, 
                              char *path,
                              char *unused_1,
                              char *unused_2,
                              apr_hash_t *config,
                              apr_hash_t *fs_config,
                              apr_pool_t *pool)
    svn_error_t *svn_repos_open(svn_repos_t **repos_p,
                            char *path,
                            apr_pool_t *pool)
    svn_error_t *svn_repos_load_fs2(svn_repos_t *repos,
                                svn_stream_t *dumpstream,
                                svn_stream_t *feedback_stream,
                                svn_repos_load_uuid uuid_action,
                                char *parent_dir,
                                svn_boolean_t use_pre_commit_hook,
                                svn_boolean_t use_post_commit_hook,
                                svn_cancel_func_t cancel_func,
                                void *cancel_baton,
                                apr_pool_t *pool)
    svn_fs_t *svn_repos_fs(svn_repos_t *repos)

def create(path, config=None, fs_config=None):
    cdef svn_repos_t *repos
    cdef apr_pool_t *pool
    cdef apr_hash_t *hash_config, *hash_fs_config
    pool = Pool(NULL)
    hash_config = NULL # FIXME
    hash_fs_config = NULL # FIXME
    check_error(svn_repos_create(&repos, path, "", "", 
                hash_config, hash_fs_config, pool))
    apr_pool_destroy(pool)
    return Repository(path)

cdef class Repository:
    cdef apr_pool_t *pool
    cdef svn_repos_t *repos
    def __init__(self, path):
        self.pool = Pool(NULL)
        check_error(svn_repos_open(&self.repos, path, self.pool))

    def __dealloc__(self):
        apr_pool_destroy(self.pool)

    def load_fs(self, dumpstream, feedback_stream, uuid_action,
                parent_dir="", use_pre_commit_hook=False, 
                use_post_commit_hook=False,
                cancel_func=None):
        cdef apr_pool_t *temp_pool
        temp_pool = Pool(self.pool)
        check_error(svn_repos_load_fs2(self.repos, 
                    new_py_stream(temp_pool, dumpstream), 
                    new_py_stream(temp_pool, feedback_stream),
                    uuid_action, parent_dir, use_pre_commit_hook, 
                    use_post_commit_hook, py_cancel_func, <void *>cancel_func,
                    self.pool))
        apr_pool_destroy(temp_pool)

    def fs(self):
        return FileSystem(self)

cdef class FileSystem:
    cdef svn_fs_t *fs
    cdef apr_pool_t *pool
    def __init__(self, Repository repos):
        self.fs = svn_repos_fs(repos.repos)
        self.pool = Pool(repos.pool)

    def __dealloc__(self):
        apr_pool_destroy(self.pool)

    def get_uuid(self):
        cdef char *uuid
        check_error(svn_fs_get_uuid(self.fs, &uuid, self.pool))
        return uuid

LOAD_UUID_DEFAULT = 0
LOAD_UUID_IGNORE = 1
LOAD_UUID_FORCE = 2
