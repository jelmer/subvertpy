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

from subvertpy import ERR_RA_SVN_UNKNOWN_CMD, NODE_DIR, NODE_FILE, NODE_UNKNOWN, NODE_NONE, ERR_UNSUPPORTED_FEATURE
from subvertpy.delta import pack_svndiff0_window, SVNDIFF0_HEADER
from subvertpy.marshall import marshall, unmarshall, literal, MarshallError, NeedMoreData


class ServerBackend:

    def open_repository(self, location):
        raise NotImplementedError(self.open_repository)


def generate_random_id():
    import uuid
    return str(uuid.uuid4())


class ServerRepositoryBackend:
    
    def get_uuid(self):
        raise NotImplementedError(self.get_uuid)

    def get_latest_revnum(self):
        raise NotImplementedError(self.get_latest_revnum)

    def log(self, send_revision, target_path, start_rev, end_rev, changed_paths,
            strict_node, limit):
        raise NotImplementedError(self.log)

    def update(self, editor, revnum, target_path, recurse=True):
        raise NotImplementedError(self.update)

    def check_path(self, path, revnum):
        raise NotImplementedError(self.check_path)

    def stat(self, path, revnum):
        """Stat a path.

        Should return a dictionary with the following keys: name, kind, size, has-props, 
        created-rev, created-date, last-author.
        """
        raise NotImplementedError(self.stat)

    def rev_proplist(self, revnum):
        raise NotImplementedError(self.rev_proplist)

    def get_locations(self, path, peg_revnum, revnums):
        raise NotImplementedError(self.get_locations)


MAJOR_VERSION = 1
MINOR_VERSION = 2
CAPABILITIES = ["edit-pipeline"]
MECHANISMS = ["ANONYMOUS"]

class Editor:

    def __init__(self, conn):
        self.conn = conn

    def set_target_revision(self, revnum):
        self.conn.send_msg([literal("target-rev"), [revnum]])

    def open_root(self, base_revision=None):
        id = generate_random_id()
        if base_revision is None:
            baserev = []
        else:
            baserev = [base_revision]
        self.conn.send_msg([literal("open-root"), [baserev, id]])
        self.conn._open_ids = []
        return DirectoryEditor(self.conn, id)

    def close(self):
        self.conn.send_msg([literal("close-edit"), []])

    def abort(self):
        self.conn.send_msg([literal("abort-edit"), []])

class DirectoryEditor:

    def __init__(self, conn, id):
        self.conn = conn
        self.id = id
        self.conn._open_ids.append(id)

    def add_file(self, path, copyfrom_path=None, copyfrom_rev=-1):
        self._is_last_open()
        child = generate_random_id()
        if copyfrom_path is not None:
            copyfrom_data = [copyfrom_path, copyfrom_rev]
        else:
            copyfrom_data = []
        self.conn.send_msg([literal("add-file"), [path, self.id, child, copyfrom_data]])
        return FileEditor(self.conn, child)

    def open_file(self, path, base_revnum):
        self._is_last_open()
        child = generate_random_id()
        self.conn.send_msg([literal("open-file"), [path, self.id, child, base_revnum]])
        return FileEditor(self.conn, child)

    def delete_entry(self, path, base_revnum):
        self._is_last_open()
        self.conn.send_msg([literal("delete-entry"), [path, base_revnum, self.id]])

    def add_directory(self, path, copyfrom_path=None, copyfrom_rev=-1):
        self._is_last_open()
        child = generate_random_id()
        if copyfrom_path is not None:
            copyfrom_data = [copyfrom_path, copyfrom_rev]
        else:
            copyfrom_data = []
        self.conn.send_msg([literal("add-dir"), [path, self.id, child, copyfrom_data]])
        return DirectoryEditor(self.conn, child)

    def open_directory(self, path, base_revnum):
        self._is_last_open()
        child = generate_random_id()
        self.conn.send_msg([literal("open-dir"), [path, self.id, child, base_revnum]])
        return DirectoryEditor(self.conn, child)

    def change_prop(self, name, value):
        self._is_last_open()
        if value is None:
            value = []
        else:
            value = [value]
        self.conn.send_msg([literal("change-dir-prop"), [self.id, name, value]])

    def _is_last_open(self):
        assert self.conn._open_ids[-1] == self.id

    def close(self):
        self._is_last_open()
        self.conn._open_ids.pop()
        self.conn.send_msg([literal("close-dir"), [self.id]])

class FileEditor:

    def __init__(self, conn, id):
        self.conn = conn
        self.id = id
        self.conn._open_ids.append(id)

    def _is_last_open(self):
        assert self.conn._open_ids[-1] == self.id

    def close(self, checksum=None):
        self._is_last_open()
        self.conn._open_ids.pop()
        if checksum is None:
            checksum = []
        else:
            checksum = [checksum]
        self.conn.send_msg([literal("close-file"), [self.id, checksum]])

    def apply_textdelta(self, base_checksum=None):
        self._is_last_open()
        if base_checksum is None:
            base_check = []
        else:
            base_check = [base_checksum]
        self.conn.send_msg([literal("apply-textdelta"), [self.id, base_check]])
        self.conn.send_msg([literal("textdelta-chunk"), [self.id, SVNDIFF0_HEADER]])
        def send_textdelta(delta):
            if delta is None:
                self.conn.send_msg([literal("textdelta-end"), [self.id]])
            else:
                self.conn.send_msg([literal("textdelta-chunk"), [self.id, pack_svndiff0_window(delta)]])
        return send_textdelta

    def change_prop(self, name, value):
        self._is_last_open()
        if value is None:
            value = []
        else:
            value = [value]
        self.conn.send_msg([literal("change-file-prop"), [self.id, name, value]])


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
            MAJOR_VERSION, MINOR_VERSION, [literal(x) for x in MECHANISMS], 
            [literal(x) for x in CAPABILITIES])

    def send_mechs(self):
        self.send_success([literal(x) for x in MECHANISMS], "")

    def send_failure(self, *contents):
        self.send_msg([literal("failure"), list(contents)])

    def send_success(self, *contents):
        self.send_msg([literal("success"), list(contents)])

    def send_ack(self):
        self.send_success([], "")

    def send_unknown(self, cmd):
        self.send_failure([ERR_RA_SVN_UNKNOWN_CMD, 
            "Unknown command '%s'" % cmd, __file__, 52])

    def get_latest_rev(self):
        self.send_ack()
        self.send_success(self.repo_backend.get_latest_revnum())

    def check_path(self, path, rev):
        if len(rev) == 0:
            revnum = None
        else:
            revnum = rev[0]
        kind = self.repo_backend.check_path(path, revnum)
        self.send_ack()
        self.send_success(literal({NODE_NONE: "none", 
                           NODE_DIR: "dir",
                           NODE_FILE: "file",
                           NODE_UNKNOWN: "unknown"}[kind]))

    def log(self, target_path, start_rev, end_rev, changed_paths, 
            strict_node, limit=None, include_merged_revisions=False, 
            all_revprops=None, revprops=None):
        def send_revision(revno, author, date, message, changed_paths=None):
            changes = []
            if changed_paths is not None:
                for p, (action, cf, cr) in changed_paths.items():
                    if cf is not None:
                        changes.append((p, literal(action), (cf, cr)))
                    else:
                        changes.append((p, literal(action), ()))
            self.send_msg([changes, revno, [author], [date], [message]])
        self.send_ack()
        if len(start_rev) == 0:
            start_revnum = None
        else:
            start_revnum = start_rev[0]
        if len(end_rev) == 0:
            end_revnum = None
        else:
            end_revnum = end_rev[0]
        self.repo_backend.log(send_revision, target_path, start_revnum, 
                              end_revnum, changed_paths, strict_node, limit)
        self.send_msg(literal("done"))
        self.send_success()

    def open_backend(self, url):
        import urllib
        (rooturl, location) = urllib.splithost(url)
        self.repo_backend, self.relpath = self.backend.open_repository(location)

    def reparent(self, parent):
        self.open_backend(parent)
        self.send_ack()
        self.send_success()

    def stat(self, path, rev):
        if len(rev) == 0:
            revnum = None
        else:
            revnum = rev[0]
        self.send_ack()
        dirent = self.repo_backend.stat(path, revnum)
        if dirent is None:
            self.send_success([])
        else:
            self.send_success([dirent["name"], dirent["kind"], dirent["size"],
                          dirent["has-props"], dirent["created-rev"],
                          dirent["created-date"], dirent["last-author"]])

    def commit(self, logmsg, locks, keep_locks=False, rev_props=None):
        self.send_failure([ERR_UNSUPPORTED_FEATURE, 
            "commit not yet supported", __file__, 42])

    def rev_proplist(self, revnum):
        self.send_ack()
        revprops = self.repo_backend.rev_proplist(revnum)
        self.send_success(revprops.items())

    def rev_prop(self, revnum, name):
        self.send_ack()
        revprops = self.repo_backend.rev_proplist(revnum)
        if name in revprops:
            self.send_success([revprops[name]])
        else:
            self.send_success()

    def get_locations(self, path, peg_revnum, revnums):
        self.send_ack()
        locations = self.repo_backend.get_locations(path, peg_revnum, revnums)
        for rev, path in locations.items():
            self.send_msg([rev, path])
        self.send_msg(literal("done"))
        self.send_success()

    def update(self, rev, target, recurse, depth=None, send_copyfrom_param=True):
        self.send_ack()
        while True:
            msg = self.recv_msg()
            assert msg[0] in ["set-path", "finish-report"]
            if msg[0] == "finish-report":
                break

        self.send_ack()

        if len(rev) == 0:
            revnum = None
        else:
            revnum = rev[0]
        self.repo_backend.update(Editor(self), revnum, target, recurse)
        self.send_success()
        client_result = self.recv_msg()
        if client_result[0] == "success":
            return
        else:
            self.mutter("Client reported error during update: %r" % client_result)
            # Needs to be sent back to the client to display
            self.send_failure(client_result[1][0])

    commands = {
            "get-latest-rev": get_latest_rev,
            "log": log,
            "update": update,
            "check-path": check_path,
            "reparent": reparent,
            "stat": stat,
            "commit": commit,
            "rev-proplist": rev_proplist,
            "rev-prop": rev_prop,
            "get-locations": get_locations,
            # FIXME: get-dated-rev
            # FIXME: get-file
            # FIXME: get-dir
            # FIXME: check-path
            # FIXME: switch
            # FIXME: status
            # FIXME: diff
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

        self.open_backend(url)
        self.send_success(self.repo_backend.get_uuid(), url)

        # Expect:
        while not self._stop:
            ( cmd, args ) = self.recv_msg()
            if not self.commands.has_key(cmd):
                self.mutter("client used unknown command %r" % cmd)
                self.send_unknown(cmd)
                return
            else:
                self.commands[cmd](self, *args)

    def close(self):
        self._stop = True

    def recv_msg(self):
        while True:
            try:
                (self.inbuffer, ret) = unmarshall(self.inbuffer)
                return ret
            except NeedMoreData:
                newdata = self.recv_fn(512)
                if newdata != "":
                    #self.mutter("IN: %r" % newdata)
                    self.inbuffer += newdata
            except MarshallError, e:
                self.mutter('ERROR: %r' % e)
                raise

    def send_msg(self, data):
        marshalled_data = marshall(data)
        # self.mutter("OUT: %r" % marshalled_data)
        self.send_fn(marshalled_data)

    def mutter(self, text):
        if self._logf is not None:
            self._logf.write("%s\n" % text)


from subvertpy.ra_svn import SVN_PORT


class TCPSVNServer(object):

    def __init__(self, backend, port=None, logf=None):
        if port is None:
            self._port = SVN_PORT
        else:
            self._port = int(port)
        self._backend = backend
        self._logf = logf

    def serve(self):
        import socket
        import threading
        server_sock = socket.socket()
        server_sock.bind(('0.0.0.0', self._port))
        server_sock.listen(5)
        def handle_new_client(sock):
            def handle_connection():
                try:
                    server.serve()
                finally:
                    sock.close()
            self._logf.write("New client connection from %s:%d\n" % sock.getsockname())
            sock.setblocking(True)
            server = SVNServer(self._backend, sock.recv, sock.send, self._logf)
            server_thread = threading.Thread(None, handle_connection, name='svn-smart-server')
            server_thread.setDaemon(True)
            server_thread.start()
            
        while True:
            sock, _ = server_sock.accept()
            handle_new_client(sock)


