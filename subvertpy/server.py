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

from subvertpy import SVN_NODE_NONE, SVN_NODE_FILE, SVN_NODE_DIR
from subvertpy.marshall import marshall, unmarshall, literal, MarshallError

SVN_MAJOR_VERSION = 1
SVN_MINOR_VERSION = 2

class SVNServer:
    def __init__(self, rootdir, recv_fn, send_fn):
        self.rootdir = rootdir
        self.recv_fn = recv_fn
        self.send_fn = send_fn
        self.inbuffer = ""
        self._stop = False

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
        self.send_success(self.branch.revno())

    def check_path(self, path, revnum):
        return SVN_NODE_DIR

    def log(self, target_path, start_rev, end_rev, changed_paths, 
            strict_node, limit=None):
        def send_revision(revno, rev):
            self.send_msg([[], revno, [rev.committer], 
              [time.strftime("%Y-%m-%dT%H:%M:%S.00000Z", time.gmtime(rev.timestamp))],
                          [rev.message]])
        self.send_success([], "")
        revno = start_rev[0]
        i = 0
        self.branch.repository.lock_read()
        try:
            # FIXME: check whether start_rev and end_rev actually exist
            while revno != end_rev[0]:
                #TODO: Honor target_path, strict_node, changed_paths
                if end_rev[0] > revno:
                    revno+=1
                else:
                    revno-=1
                if limit != 0 and i == limit:
                    break
                if revno != 0:
                    send_revision(revno, self.branch.repository.get_revision(self.branch.get_rev_id(revno)))
        finally:
            self.branch.repository.unlock()

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

    def get_branch_uuid(self):
        config = self.branch.get_config()
        uuid = config.get_user_option('svn_uuid')
        if uuid is None:
            import uuid
            uuid = uuid.uuid4()
            config.set_user_option('svn_uuid', uuid)
        return str(uuid)

    def send_auth_request(self):
        pass

    def serve(self):
        self.send_greeting()
        (version, capabilities, url) = self.recv_msg()
        self.capabilities = capabilities
        self.version = version
        self.url = url
        mutter("client supports:")
        mutter("  version %r" % version)
        mutter("  capabilities %r " % capabilities)
        self.send_mechs()

        (mech, args) = self.recv_msg()
        # TODO: Proper authentication
        self.send_success()

        import bzrlib.urlutils as urlutils
        (rooturl, location) = urlutils.split(url)

        self.branch, branch_path = Branch.open_containing(os.path.join(self.rootdir, location))
        self.send_success(self.get_branch_uuid(), url)

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
                mutter('in: %r' % ret)
                return ret
            except MarshallError, e:
                mutter('ERROR: %r' % e)

    def send_msg(self, data):
        mutter('out: %r' % data)
        self.send_fn(marshall(data))
