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
from types cimport svn_error_t, svn_boolean_t, svn_cancel_func_t, svn_stream_t, svn_node_kind_t, svn_revnum_t, svn_filesize_t

from core cimport Pool, check_error, new_py_stream, py_cancel_func

cdef extern from "svn_fs.h":
    ctypedef struct svn_fs_t
    ctypedef struct svn_fs_root_t
    svn_error_t *svn_fs_get_uuid(svn_fs_t *fs, char **uuid, apr_pool_t *pool)
    svn_error_t *svn_fs_check_path(svn_node_kind_t *kind_p, svn_fs_root_t *root, char *path, apr_pool_t *pool)
    svn_boolean_t svn_fs_is_txn_root(svn_fs_root_t *root)
    svn_boolean_t svn_fs_is_revision_root(svn_fs_root_t *root)
    svn_error_t *svn_fs_youngest_rev(svn_revnum_t *youngest_p, svn_fs_t *fs, apr_pool_t *pool)
    svn_error_t *svn_fs_revision_root(svn_fs_root_t **root_p, svn_fs_t *fs, svn_revnum_t rev, apr_pool_t *pool)
    svn_error_t *svn_fs_make_dir(svn_fs_root_t *root, char *path, apr_pool_t *pool)
    svn_error_t *svn_fs_delete(svn_fs_root_t *root, char *path, apr_pool_t *pool)
    svn_error_t *svn_fs_copy(svn_fs_root_t *from_root, char *from_path, svn_fs_root_t *to_root, char *to_path, apr_pool_t *pool)
    svn_error_t *svn_fs_file_length(svn_filesize_t *length_p, svn_fs_root_t *root, char *path, apr_pool_t *pool)
    svn_error_t *svn_fs_file_md5_checksum(unsigned char digest[], svn_fs_root_t *root, char *path, apr_pool_t *pool)
    svn_error_t *svn_fs_file_contents(svn_stream_t **contents, svn_fs_root_t *root, char *path, apr_pool_t *pool)
    void svn_fs_close_root(svn_fs_root_t *root)


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

cdef class FileSystemRoot:
    cdef svn_fs_root_t *root
    cdef apr_pool_t *pool

    def __dealloc__(self):
        if self.pool != NULL:
            apr_pool_destroy(self.pool)

    def check_path(self, char *path):
        cdef svn_node_kind_t kind
        cdef apr_pool_t *pool
        pool = Pool(NULL)
        check_error(svn_fs_check_path(&kind, self.root, path, pool))
        apr_pool_destroy(pool)
        return kind

    def make_dir(self, char *path):
        cdef apr_pool_t *pool
        pool = Pool(self.pool)
        check_error(svn_fs_make_dir(self.root, path, pool))
        apr_pool_destroy(pool)

    def delete(self, char *path):
        cdef apr_pool_t *pool
        pool = Pool(self.pool)
        check_error(svn_fs_delete(self.root, path, pool))
        apr_pool_destroy(pool)

    def copy(self, char *from_path, FileSystemRoot to_root, char *to_path):
        cdef apr_pool_t *pool
        pool = Pool(self.pool)
        check_error(svn_fs_copy(self.root, from_path, to_root.root, to_path, pool))
        apr_pool_destroy(pool)

    def file_length(self, char *path):
        cdef apr_pool_t *pool
        cdef svn_filesize_t length
        pool = Pool(self.pool)
        check_error(svn_fs_file_length(&length, self.root, path, pool))
        apr_pool_destroy(pool)
        return length

    def file_md5_checksum(self, char *path):
        cdef char digest[64]
        cdef apr_pool_t *pool
        pool = Pool(NULL)
        check_error(svn_fs_file_md5_checksum(<unsigned char*>digest, self.root, path, pool))
        ret = digest
        apr_pool_destroy(pool)
        return ret

    def file_contents(self, char *path):
        cdef apr_pool_t *pool
        cdef svn_stream_t *stream
        pool = Pool(self.pool)
        check_error(svn_fs_file_contents(&stream, self.root, path, pool))
        apr_pool_destroy(pool)
        return None # FIXME

    def is_txn_root(self):
        return svn_fs_is_txn_root(self.root)

    def is_revision_root(self):
        return svn_fs_is_revision_root(self.root)

    def close(self):
        svn_fs_close_root(self.root)


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


LOAD_UUID_DEFAULT = 0
LOAD_UUID_IGNORE = 1
LOAD_UUID_FORCE = 2
