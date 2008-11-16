# Copyright (C) 2006-2008 Jelmer Vernooij <jelmer@samba.org>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""Python bindings for Subversion."""

__author__ = "Jelmer Vernooij <jelmer@samba.org>"

import socket
import urllib

SVN_PORT = 3690

class RemoteAccess(object):

    def __init__(self, url, progress_cb=None, auth=None, config=None, 
                 client_string_func=None, open_tmp_file_func=None):
        self.url = url
        (type, opaque) = urllib.splittype(url)
        assert type == "svn"
        (host, path) = urllib.splithost(opaque)
        (self.host, self.port) = urllib.split(host, SVN_PORT)
        self._progress_cb = progress_cb
        self._auth = auth
        self._config = config
        self._client_string_func = client_string_func
        # open_tmp_file_func is ignored, as it is not needed for svn://

    def get_file_revs(self, path, start, end, file_rev_handler):
        raise NotImplementedError(self.get_file_revs)

    def get_locations(self, path, peg_revision, location_revisions):
        raise NotImplementedError(self.get_locations)

    def get_locks(self, path):
        raise NotImplementedError(self.get_locks)

    def lock(self, path_revs, comment, steal_lock, lock_func):
        raise NotImplementedError(self.lock)

    def unlock(self, path_tokens, break_lock, lock_func):
        raise NotImplementedError(self.unlock)

    def mergeinfo(self, paths, revision=-1, inherit=None, include_descendants=False):
        raise NotImplementedError(self.mergeinfo)

    def get_location_segments(self, path, peg_revision, start_revision,
                              end_revision, py_rcvr):
        raise NotImplementedError(self.get_location_segments)

    def has_capability(self, capability):
        raise NotImplementedError(self.has_capability)

    def check_path(self, path, revision):
        raise NotImplementedError(self.check_path)

    def get_lock(self, path):
        raise NotImplementedError(self.get_lock)

    def get_dir(self, path, revision=-1, dirent_fields=0):
        raise NotImplementedError(self.get_dir)

    def get_file(self, path, stream, revision=-1):
        raise NotImplementedError(self.get_file)

    def change_rev_prop(self, rev, name, value):
        raise NotImplementedError(self.change_rev_prop)

    def get_commit_editor(self, revprops, callback=None, lock_tokens=None, 
                          keep_locks=False):
        raise NotImplementedError(self.get_commit_editor)

    def rev_proplist(self, revision):
        raise NotImplementedError(self.rev_proplist)

    def replay(self, revision, low_water_mark, update_editor, send_deltas=True):
        raise NotImplementedError(self.replay)

    def replay_range(self, start_revision, end_revision, low_water_mark, cbs, 
                     send_deltas=True):
        raise NotImplementedError(self.replay_range)

    def do_switch(self, revision_to_update_to, update_target, recurse, 
                  switch_url, update_editor):
        raise NotImplementedError(self.do_switch)

    def do_update(self, revision_to_update_to, update_target, recurse, 
                  update_editor):
        raise NotImplementedError(self.do_update)

    def do_diff(self, revision_to_update, diff_target, versus_url, diff_editor,
                recurse=True, ignore_ancestry=False, text_deltas=False):
        raise NotImplementedError(self.do_diff)

    def get_repos_root(self):
        raise NotImplementedError(self.get_repos_root)

    def get_latest_revnum(self):
        raise NotImplementedError(self.get_latest_revnum)

    def reparent(self, url):
        raise NotImplementedError(self.reparent)

    def get_uuid(self, uuid):
        raise NotImplementedError(self.uuid)

    def get_log(self, callback, paths, start, end, limit, 
                discover_changed_paths, strict_node_history, 
                include_merged_revisions, revprops):
        raise NotImplementedError(self.get_log)
    
