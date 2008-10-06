# Copyright (C) 2006 Jelmer Vernooij <jelmer@samba.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import copy
import os
import time

from subvertpy import NODE_NONE, NODE_FILE, NODE_DIR
from subvertpy.marshall import marshall, unmarshall, literal, MarshallError


class ServerBackend:

    def open_repository(self, location):
        raise NotImplementedError(self.open_repository)


class ServerRepositoryBackend:
    
    def get_uuid(self):
        raise NotImplementedError(self.get_uuid)

    def get_latest_revnum(self):
        raise NotImplementedError(self.get_latest_revnum)

    def log(self, send_revision, target_path, start_rev, end_rev, changed_paths,
            strict_node, limit):
        raise NotImplementedError(self.log)


SVN_MAJOR_VERSION = 1
SVN_MINOR_VERSION = 2

class SVNServer:
    def __init__(self, backend, recv_fn, send_fn, logf=None):
        self.backend = backend
        self.recv_fn = recv_fn
        self.send_fn = send_fn
        self.inbuffer = ""
        self._stop = False
        self._logf = logf

    def send_greeting(self):
        self.send_success(
            SVN_MAJOR_VERSION, SVN_MINOR_VERSION, [literal("ANONYMOUS")], [])

    def send_mechs(self):
        self.send_success([literal("ANONYMOUS")], "")

    def send_failure(self, *contents):
        self.send_msg([literal("failure"), list(contents)])

    def send_success(self, *contents):
        self.send_msg([literal("success"), list(contents)])

    def send_unknown(self, cmd):
        self.send_failure([210001, "Unknown command '%s'" % cmd, __file__, \
                          52])

    def get_latest_rev(self):
        self.send_success([], "")
        self.send_success(self.repo_backend.get_latest_revnum())

    def check_path(self, path, revnum):
        return NODE_DIR

    def log(self, target_path, start_rev, end_rev, changed_paths, 
            strict_node, limit=None):
        def send_revision(revno, author, date, message):
            self.send_msg([[], revno, [author], [date], [message]])
        self.send_success([], "")
        self.repo_backend.log(send_revision, target_path, start_rev[0], 
                              end_rev[0],
                              changed_paths, strict_node, limit)
        self.send_msg(literal("done"))
        self.send_success()

    def reparent(self, parent):
        self.send_success([], "")
        self.send_success()

    def stat(self, path, revnum):
        self.send_success([], "")
        self.send_success()

    def update(self, rev, target, recurse):
        self.send_success([], "")
        while True:
            msg = self.recv_msg()
            assert msg[0] in ["set-path", "finish-report"]
            if msg[0] == "finish-report":
                break

        self.send_success([], "")
        self.send_msg(["target-rev", rev])
        tree = self.branch.repository.revision_tree(
                self.branch.get_rev_id(rev[0]))
        path2id = {}
        id2path = {}
        self.send_msg(["open-root", [rev, tree.inventory.root.file_id]])
        def send_children(self, id):
            for child in tree.inventory[id].children:
                if tree.inventory[child].kind in ('symlink', 'file'):
                    self.send_msg(["add-file", [tree.inventory.id2path(child),
                                                id, child]])
                    # FIXME
                    self.send_msg(["close-file", [child]])
                else:
                    self.send_msg(["add-dir", [tree.inventory.id2path(child),
                                                id, child]])
                    send_children(child)
                    self.send_msg(["close-dir", [child]])
        #send_children(tree.inventory.root.file_id)
        self.send_msg(["close-dir", [tree.inventory.root.file_id]])
        self.send_msg(["close-edit", []])
        #msg = self.recv_msg()
        #self.send_msg(msg)


    commands = {
            "get-latest-rev": get_latest_rev,
            "log": log,
            "update": update,
            "check-path": check_path,
            "reparent": reparent,
            "stat": stat,
            # FIXME: get-dated-rev
            # FIXME: rev-proplist
            # FIXME: rev-prop
            # FIXME: get-file
            # FIXME: get-dir
            # FIXME: check-path
            # FIXME: switch
            # FIXME: status
            # FIXME: diff
            # FIXME: get-locations
            # FIXME: get-file-revs
            # FIXME: replay
    }

    def send_auth_request(self):
        pass

    def serve(self):
        self.send_greeting()
        (version, capabilities, url) = self.recv_msg()
        self.capabilities = capabilities
        self.version = version
        self.url = url
        self.mutter("client supports:")
        self.mutter("  version %r" % version)
        self.mutter("  capabilities %r " % capabilities)
        self.send_mechs()

        (mech, args) = self.recv_msg()
        # TODO: Proper authentication
        self.send_success()

        import urllib
        (rooturl, location) = urllib.splithost(url)

        self.repo_backend, self.relpath = self.backend.open_repository(location)
        self.send_success(self.repo_backend.get_uuid(), url)

        # Expect:
        while not self._stop:
            ( cmd, args ) = self.recv_msg()
            if not self.commands.has_key(cmd):
                self.send_unknown(cmd)
                return
            else:
                self.commands[cmd](self, *args)

    def close(self):
        self._stop = True

    def recv_msg(self):
        # FIXME: Blocking read?
        while True:
            try:
                self.inbuffer += self.recv_fn()
                (self.inbuffer, ret) = unmarshall(self.inbuffer)
                self.mutter('in: %r' % ret)
                return ret
            except MarshallError, e:
                self.mutter('ERROR: %r' % e)

    def send_msg(self, data):
        self.mutter('out: %r' % data)
        self.send_fn(marshall(data))

    def mutter(self, text):
        if self._logf is not None:
            self._logf.write(text)
