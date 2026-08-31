# Copyright (C) 2006-2008 Jelmer Vernooij <jelmer@jelmer.uk>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA
"""Python bindings for Subversion."""

__author__ = "Jelmer Vernooij <jelmer@jelmer.uk>"

import base64
import os
import socket
import subprocess
import urllib.parse as urlparse
from collections.abc import Callable, Iterator
from errno import EPIPE
from socketserver import StreamRequestHandler, TCPServer
from types import TracebackType
from typing import IO, ClassVar, Literal, TypeVar, cast

from subvertpy import (
    ERR_RA_SVN_UNKNOWN_CMD,
    ERR_UNSUPPORTED_FEATURE,
    NODE_DIR,
    NODE_FILE,
    NODE_NONE,
    NODE_UNKNOWN,
    SubversionException,
    properties,
)
from subvertpy._ra import (
    DIRENT_CREATED_REV,
    DIRENT_HAS_PROPS,
    DIRENT_KIND,
    DIRENT_LAST_AUTHOR,
    DIRENT_SIZE,
    DIRENT_TIME,
)
from subvertpy._typing import (
    ClientStringFunc,
    CommitFinalizer,
    Dirent,
    FileRevHandler,
    MarshallValue,
    OpenTmpFileFunc,
    ProgressFunc,
    ReplayRevFinishCallback,
    ReplayRevStartCallback,
    ServerLogPathChange,
    TxDeltaHandler,
    UnmarshalledValue,
)
from subvertpy._typing import DirectoryEditor as _typing_DirectoryEditor
from subvertpy._typing import (
    Editor as EditorProto,
)
from subvertpy._typing import FileEditor as _typing_FileEditor
from subvertpy.delta import (
    SVNDIFF0_HEADER,
    TxDeltaWindow,
    pack_svndiff0_window,
    unpack_svndiff0,
)
from subvertpy.marshall import (
    MarshallError,
    NeedMoreData,
    literal,
    marshall,
    unmarshall,
)
from subvertpy.server import (
    ServerBackend,
    generate_random_id,
)


class SSHSubprocess:
    """A socket-like object that talks to an ssh subprocess via pipes."""

    __slots__ = "proc"

    def __init__(self, proc: subprocess.Popen) -> None:
        self.proc = proc

    def send(self, data: bytes) -> int:
        return os.write(self.proc.stdin.fileno(), data)  # type: ignore[union-attr]

    def recv(self, count: int) -> bytes:
        return os.read(self.proc.stdout.fileno(), count)  # type: ignore[union-attr]

    def close(self) -> None:
        self.proc.stdin.close()  # type: ignore[union-attr]
        self.proc.stdout.close()  # type: ignore[union-attr]
        self.proc.wait()

    def get_filelike_channels(
        self,
    ) -> tuple[IO[bytes] | None, IO[bytes] | None]:
        return (self.proc.stdout, self.proc.stdin)


class SSHVendor:
    def connect_ssh(
        self,
        username: str | None,
        password: str | None,
        host: str,
        port: int | None,
        command: list[str],
    ) -> SSHSubprocess:
        args = ["ssh", "-x"]
        if port is not None:
            args.extend(["-p", str(port)])
        if username is not None:
            host = f"{username}@{host}"
        args.append(host)
        proc = subprocess.Popen(
            args + command, stdin=subprocess.PIPE, stdout=subprocess.PIPE
        )
        return SSHSubprocess(proc)


# Can be overridden by users
get_ssh_vendor = SSHVendor


class SVNConnection:
    def __init__(
        self,
        recv_fn: Callable[[int], bytes],
        send_fn: Callable[[bytes], int],
    ) -> None:
        self.inbuffer: bytes = b""
        self.recv_fn = recv_fn
        self.send_fn = send_fn

    def recv_msg(self) -> UnmarshalledValue:
        while True:
            try:
                (self.inbuffer, ret) = unmarshall(self.inbuffer)
                return ret
            except NeedMoreData:
                newdata = self.recv_fn(1)
                if newdata != b"":
                    # self.mutter("IN: %r" % newdata)
                    self.inbuffer += newdata

    def send_msg(self, data: MarshallValue) -> None:
        marshalled_data = marshall(data)
        # self.mutter("OUT: %r" % marshalled_data)
        self.send_fn(marshalled_data)

    def send_success(self, *contents: MarshallValue) -> None:
        self.send_msg([literal("success"), list(contents)])


SVN_PORT = 3690


# --- Runtime narrowing helpers for wire-protocol values -----------------
#
# `recv_msg` returns a nested UnmarshalledValue. Each command has a
# well-defined shape, but Python-side dispatch has to descend into that
# shape one field at a time. These helpers assert the runtime type and
# return a narrowed value so the surrounding code type-checks without
# a scatter of `cast()` calls or `# type: ignore` markers.


def _as_list(value: UnmarshalledValue) -> list[UnmarshalledValue]:
    if not isinstance(value, list):
        raise MarshallError(f"Expected list, got {type(value).__name__}")
    return value


def _as_int(value: UnmarshalledValue) -> int:
    if not isinstance(value, int):
        raise MarshallError(f"Expected int, got {type(value).__name__}")
    return value


def _as_bytes(value: UnmarshalledValue) -> bytes:
    if not isinstance(value, bytes):
        raise MarshallError(f"Expected bytes, got {type(value).__name__}")
    return value


def _as_str(value: UnmarshalledValue) -> str:
    """Decode a wire string (literal or bytes) to str."""
    if isinstance(value, literal):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, str):
        return value
    raise MarshallError(f"Expected string-ish, got {type(value).__name__}")


def _dir(token: object) -> "_typing_DirectoryEditor":
    return cast("_typing_DirectoryEditor", token)


def _file(token: object) -> "_typing_FileEditor":
    return cast("_typing_FileEditor", token)


def _bytes_dict(value: UnmarshalledValue) -> dict[str, bytes]:
    """Convert a wire property-list ((name, value) pairs) to dict[str, bytes]."""
    items = _as_list(value)
    out: dict[str, bytes] = {}
    for item in items:
        pair = _as_list(item)
        out[_as_str(pair[0])] = _as_bytes(pair[1])
    return out


def feed_editor(conn: "SVNClient", editor: EditorProto) -> None:
    tokens: dict[object, _typing_DirectoryEditor | _typing_FileEditor] = {}
    diff: dict[object, bytes] = {}
    txdelta_handler: dict[object, TxDeltaHandler] = {}
    while True:
        msg = _as_list(conn.recv_msg())
        command_str = _as_str(msg[0])
        args = _as_list(msg[1])

        if command_str == "target-rev":
            editor.set_target_revision(_as_int(args[0]))
        elif command_str == "open-root":
            base_rev_list = _as_list(args[0])
            root = (
                editor.open_root()
                if len(base_rev_list) == 0
                else editor.open_root(_as_int(base_rev_list[0]))
            )
            tokens[args[1]] = root
        elif command_str == "delete-entry":
            _dir(tokens[args[2]]).delete_entry(_as_str(args[0]), _as_int(args[1]))
        elif command_str == "add-dir":
            parent = _dir(tokens[args[1]])
            copyfrom = _as_list(args[3])
            if len(copyfrom) == 0:
                tokens[args[2]] = parent.add_directory(_as_str(args[0]))
            else:
                tokens[args[2]] = parent.add_directory(
                    _as_str(args[0]),
                    _as_str(copyfrom[0]),
                    _as_int(_as_list(args[4])[0]),
                )
        elif command_str == "open-dir":
            tokens[args[2]] = _dir(tokens[args[1]]).open_directory(
                _as_str(args[0]), _as_int(args[3])
            )
        elif command_str == "change-dir-prop":
            value_list = _as_list(args[2])
            new_value = None if len(value_list) == 0 else _as_bytes(value_list[0])
            _dir(tokens[args[0]]).change_prop(_as_str(args[1]), new_value)
        elif command_str == "close-dir":
            _dir(tokens[args[0]]).close()
        elif command_str == "absent-dir":
            _dir(tokens[args[1]]).absent(_as_str(args[0]))
        elif command_str == "add-file":
            parent = _dir(tokens[args[1]])
            copyfrom = _as_list(args[3])
            if len(copyfrom) == 0:
                tokens[args[2]] = parent.add_file(_as_str(args[0]))
            else:
                tokens[args[2]] = parent.add_file(
                    _as_str(args[0]),
                    _as_str(copyfrom[0]),
                    _as_int(_as_list(args[4])[0]),
                )
        elif command_str == "open-file":
            tokens[args[2]] = _dir(tokens[args[1]]).open_file(
                _as_str(args[0]), _as_int(args[3])
            )
        elif command_str == "apply-textdelta":
            base_checksum_list = _as_list(args[1])
            base_checksum = (
                None if len(base_checksum_list) == 0 else _as_str(base_checksum_list[0])
            )
            txdelta_handler[args[0]] = _file(tokens[args[0]]).apply_textdelta(
                base_checksum
            )
            diff[args[0]] = b""
        elif command_str == "textdelta-chunk":
            diff[args[0]] += _as_bytes(args[1])
        elif command_str == "textdelta-end":
            for w in unpack_svndiff0(diff[args[0]]):
                txdelta_handler[args[0]](w)
            txdelta_handler[args[0]](None)
        elif command_str == "change-file-prop":
            value_list = _as_list(args[2])
            new_value = None if len(value_list) == 0 else _as_bytes(value_list[0])
            _file(tokens[args[0]]).change_prop(_as_str(args[1]), new_value)
        elif command_str == "close-file":
            checksum_list = _as_list(args[1])
            checksum = None if len(checksum_list) == 0 else _as_str(checksum_list[0])
            _file(tokens[args[0]]).close(checksum)
        elif command_str == "close-edit":
            editor.close()
            break
        elif command_str == "abort-edit":
            editor.abort()
            break

    conn.send_success()
    conn._unpack()


class Reporter:
    __slots__ = ("conn", "editor")

    def __init__(self, conn: "SVNClient", editor: EditorProto) -> None:
        self.conn = conn
        self.editor = editor

    def set_path(
        self,
        path: str,
        rev: int,
        start_empty: bool = False,
        lock_token: str | None = None,
        depth: str | None = None,
    ) -> None:
        args: list[MarshallValue] = [path, rev, start_empty]
        if lock_token is not None:
            args.append([lock_token])
        else:
            args.append([])
        if depth is not None:
            args.append(depth)

        self.conn.send_msg([literal("set-path"), args])

    def delete_path(self, path: str) -> None:
        self.conn.send_msg([literal("delete-path"), [path]])

    def link_path(
        self,
        path: str,
        url: str,
        rev: int,
        start_empty: bool = False,
        lock_token: str | None = None,
        depth: str | None = None,
    ) -> None:
        args: list[MarshallValue] = [path, url, rev, start_empty]
        if lock_token is not None:
            args.append([lock_token])
        else:
            args.append([])
        if depth is not None:
            args.append(depth)

        self.conn.send_msg([literal("link-path"), args])

    def finish(self) -> None:
        self.conn.send_msg([literal("finish-report"), []])
        self.conn.recv_msg()
        feed_editor(self.conn, self.editor)
        self.conn.busy = False

    def abort(self) -> None:
        self.conn.send_msg([literal("abort-report"), []])
        self.conn.busy = False


class Editor:
    __slots__ = "conn"

    def __init__(self, conn: "SVNConnection") -> None:
        self.conn = conn

    def set_target_revision(self, revnum: int) -> None:
        self.conn.send_msg([literal("target-rev"), [revnum]])

    def open_root(self, base_revision: int | None = None) -> "DirectoryEditor":
        id = generate_random_id()
        if base_revision is None:
            baserev: list[MarshallValue] = []
        else:
            baserev = [base_revision]
        self.conn.send_msg([literal("open-root"), [baserev, id]])
        # Track the currently open (nested) editor ids on the connection.
        self.conn._open_ids = []  # type: ignore[attr-defined]
        return DirectoryEditor(self.conn, id)

    def close(self) -> None:
        self.conn.send_msg([literal("close-edit"), []])

    def abort(self) -> None:
        self.conn.send_msg([literal("abort-edit"), []])

    def __enter__(self) -> "Editor":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        # Abort rather than close when an exception is propagating, so the
        # incomplete edit is not committed.
        if exc_type is None:
            self.close()
        else:
            self.abort()
        return False


class DirectoryEditor:
    __slots__ = ("conn", "id")

    def __init__(self, conn: "SVNConnection", id: str) -> None:
        self.conn = conn
        self.id = id
        self.conn._open_ids.append(id)  # type: ignore[attr-defined]

    def add_file(
        self,
        path: str,
        copyfrom_path: str | None = None,
        copyfrom_rev: int = -1,
    ) -> "FileEditor":
        self._is_last_open()
        child = generate_random_id()
        copyfrom_data: list[MarshallValue] = (
            [copyfrom_path, copyfrom_rev] if copyfrom_path is not None else []
        )
        self.conn.send_msg([literal("add-file"), [path, self.id, child, copyfrom_data]])
        return FileEditor(self.conn, child)

    def open_file(self, path: str, base_revnum: int) -> "FileEditor":
        self._is_last_open()
        child = generate_random_id()
        self.conn.send_msg([literal("open-file"), [path, self.id, child, base_revnum]])
        return FileEditor(self.conn, child)

    def delete_entry(self, path: str, base_revnum: int) -> None:
        self._is_last_open()
        self.conn.send_msg([literal("delete-entry"), [path, base_revnum, self.id]])

    def add_directory(
        self,
        path: str,
        copyfrom_path: str | None = None,
        copyfrom_rev: int = -1,
    ) -> "DirectoryEditor":
        self._is_last_open()
        child = generate_random_id()
        copyfrom_data: list[MarshallValue] = (
            [copyfrom_path, copyfrom_rev] if copyfrom_path is not None else []
        )
        self.conn.send_msg([literal("add-dir"), [path, self.id, child, copyfrom_data]])
        return DirectoryEditor(self.conn, child)

    def open_directory(self, path: str, base_revnum: int) -> "DirectoryEditor":
        self._is_last_open()
        child = generate_random_id()
        self.conn.send_msg([literal("open-dir"), [path, self.id, child, base_revnum]])
        return DirectoryEditor(self.conn, child)

    def change_prop(self, name: str, value: bytes | None) -> None:
        self._is_last_open()
        value_list: list[MarshallValue] = [] if value is None else [value]
        self.conn.send_msg([literal("change-dir-prop"), [self.id, name, value_list]])

    def absent(self, path: str) -> None:
        self.conn.send_msg([literal("absent-dir"), [path, self.id]])

    def _is_last_open(self) -> None:
        assert self.conn._open_ids[-1] == self.id  # type: ignore[attr-defined]

    def close(self) -> None:
        self._is_last_open()
        self.conn._open_ids.pop()  # type: ignore[attr-defined]
        self.conn.send_msg([literal("close-dir"), [self.id]])

    def __enter__(self) -> "DirectoryEditor":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        self.close()
        return False


class FileEditor:
    __slots__ = ("conn", "id")

    def __init__(self, conn: "SVNConnection", id: str) -> None:
        self.conn = conn
        self.id = id
        self.conn._open_ids.append(id)  # type: ignore[attr-defined]

    def _is_last_open(self) -> None:
        assert self.conn._open_ids[-1] == self.id  # type: ignore[attr-defined]

    def close(self, checksum: str | None = None) -> None:
        self._is_last_open()
        self.conn._open_ids.pop()  # type: ignore[attr-defined]
        checksum_list: list[MarshallValue] = [] if checksum is None else [checksum]
        self.conn.send_msg([literal("close-file"), [self.id, checksum_list]])

    def apply_textdelta(self, base_checksum: str | None = None) -> TxDeltaHandler:
        self._is_last_open()
        base_check: list[MarshallValue] = (
            [] if base_checksum is None else [base_checksum]
        )
        self.conn.send_msg([literal("apply-textdelta"), [self.id, base_check]])
        self.conn.send_msg([literal("textdelta-chunk"), [self.id, SVNDIFF0_HEADER]])

        def send_textdelta(delta: TxDeltaWindow | None) -> None:
            if delta is None:
                self.conn.send_msg([literal("textdelta-end"), [self.id]])
            else:
                self.conn.send_msg(
                    [literal("textdelta-chunk"), [self.id, pack_svndiff0_window(delta)]]
                )

        return send_textdelta

    def change_prop(self, name: str, value: bytes | None) -> None:
        self._is_last_open()
        value_list: list[MarshallValue] = [] if value is None else [value]
        self.conn.send_msg([literal("change-file-prop"), [self.id, name, value_list]])

    def __enter__(self) -> "FileEditor":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        self.close()
        return False


# Generic decorator preserving the wrapped method's signature.
_F = TypeVar("_F", bound=Callable[..., object])


def mark_busy(unbound: _F) -> _F:
    def convert(self: "SVNClient", *args: object, **kwargs: object) -> object:
        self.busy = True
        try:
            ret = unbound(self, *args, **kwargs)
        finally:
            self.busy = False
        return ret

    convert.__doc__ = unbound.__doc__
    convert.__name__ = unbound.__name__
    return cast(_F, convert)


def unmarshall_dirent(d: list[UnmarshalledValue]) -> Dirent:
    ret: Dirent = {
        "name": d[0],
        "kind": d[1],
        "size": d[2],
        "has-props": bool(_as_int(d[3])),
        "created-rev": d[4],
    }
    if d[5] != []:
        ret["created-date"] = d[5]
    if d[6] != []:
        ret["last-author"] = d[6]
    return ret


class SVNClient(SVNConnection):
    def __init__(
        self,
        url: str,
        progress_cb: ProgressFunc | None = None,
        auth: object = None,
        config: object = None,
        client_string_func: ClientStringFunc | None = None,
        open_tmp_file_func: OpenTmpFileFunc | None = None,
    ) -> None:
        self.url = url
        parsed = urlparse.urlparse(url)
        assert parsed.scheme in ("svn", "svn+ssh")
        self._progress_cb = progress_cb
        self._auth = auth
        self._config = config
        self._client_string_func = client_string_func
        # open_tmp_file_func is ignored, as it is not needed for svn://
        if parsed.scheme == "svn":
            (recv_func, send_func) = self._connect(parsed.netloc)
        else:
            (recv_func, send_func) = self._connect_ssh(parsed.netloc)
        super().__init__(recv_func, send_func)
        greeting = self._recv_greeting()
        _min_version = _as_int(greeting[0])
        max_version = _as_int(greeting[1])
        self._server_capabilities = _as_list(greeting[3])
        self.send_msg(
            [
                max_version,
                [
                    literal(x)
                    for x in CAPABILITIES
                    if literal(x) in self._server_capabilities
                ],
                self.url,
            ]
        )
        unpacked = self._unpack()
        self._server_mechanisms = _as_list(unpacked[0])
        if self._server_mechanisms != []:
            # FIXME: Support other mechanisms as well
            self.send_msg(
                [
                    literal("ANONYMOUS"),
                    [base64.b64encode(f"anonymous@{socket.gethostname()}".encode())],
                ]
            )
            self.recv_msg()
        msg = self._unpack()
        if len(msg) > 2:
            self._server_capabilities += _as_list(msg[2])
        self._uuid = _as_str(msg[0])
        self._root_url = _as_str(msg[1])
        self.busy = False

    def _unpack(self) -> list[UnmarshalledValue]:
        msg = _as_list(self.recv_msg())
        if msg[0] == literal("failure"):
            failure_body = msg[1]
            if isinstance(failure_body, list):
                first = failure_body[0]
                if isinstance(first, list):
                    num = _as_int(first[0])
                    text = _as_str(first[1])
                    if num == ERR_RA_SVN_UNKNOWN_CMD:
                        raise NotImplementedError(text)
                    raise SubversionException(text, num)
            raise SubversionException(f"unexpected failure: {failure_body!r}", 0)
        assert msg[0] == literal("success"), f"Got: {msg!r}"
        assert len(msg) == 2
        return _as_list(msg[1])

    def _recv_greeting(self) -> list[UnmarshalledValue]:
        greeting = self._unpack()
        assert len(greeting) == 4
        return greeting

    _recv_ack = _unpack

    def _connect(
        self, netloc: str
    ) -> tuple[Callable[[int], bytes], Callable[[bytes], int]]:
        host, sep, port_str = netloc.rpartition(":")
        if sep and port_str.isdigit():
            port = int(port_str)
        else:
            host = netloc
            port = SVN_PORT
        sockaddrs = socket.getaddrinfo(
            host, port, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, 0
        )
        self._socket = None
        last_err: Exception = RuntimeError(f"no addresses for {host}:{port}")
        for family, socktype, proto, canonname, sockaddr in sockaddrs:
            try:
                self._socket = socket.socket(family, socktype, proto)
                self._socket.connect(sockaddr)
            except OSError as err:
                last_err = err
                if self._socket is not None:
                    self._socket.close()
                self._socket = None
                continue
            break
        if self._socket is None:
            raise last_err
        self._socket.setblocking(True)
        return (self._socket.recv, self._socket.send)

    def _connect_ssh(
        self, netloc: str
    ) -> tuple[Callable[..., bytes], Callable[[bytes], int]]:
        userinfo, sep, hostport = netloc.rpartition("@")
        if not sep:
            hostport = netloc
            user: str | None = None
            password: str | None = None
        elif ":" in userinfo:
            user, _, password = userinfo.partition(":")
        else:
            user = userinfo
            password = None
        host, sep, port_str = hostport.rpartition(":")
        if sep and port_str.isdigit():
            port: int | None = int(port_str)
        else:
            host = hostport
            port = 22
        self._tunnel = get_ssh_vendor().connect_ssh(
            user, password, host, port, ["svnserve", "-t"]
        )
        return (self._tunnel.recv, self._tunnel.send)

    def get_file_revs(
        self,
        path: str,
        start: int,
        end: int,
        file_rev_handler: FileRevHandler,
    ) -> None:
        raise NotImplementedError(self.get_file_revs)

    @mark_busy
    def get_locations(
        self, path: str, peg_revision: int, location_revisions: list[int]
    ) -> dict[int, str]:
        revs: list[MarshallValue] = list(location_revisions)
        self.send_msg([literal("get-locations"), [path, peg_revision, revs]])
        self._recv_ack()
        ret: dict[int, str] = {}
        while True:
            msg = self.recv_msg()
            if msg == literal("done"):
                break
            entry = _as_list(msg)
            ret[_as_int(entry[0])] = _as_str(entry[1])
        self._unpack()
        return ret

    def get_locks(self, path: str) -> list[UnmarshalledValue]:
        self.send_msg([literal("get-lock"), [path]])
        self._recv_ack()
        return self._unpack()

    def lock(
        self,
        path_revs: dict[str | bytes, int],
        comment: str,
        steal_lock: bool,
        lock_func: Callable[
            [
                str,
                bool,
                tuple[str, bytes, str, str | None, str] | None,
                BaseException | None,
            ],
            object,
        ],
    ) -> None:
        raise NotImplementedError(self.lock)

    def unlock(
        self,
        path_tokens: dict[str | bytes, bytes | str],
        break_lock: bool,
        lock_func: Callable[
            [
                str,
                bool,
                tuple[str, bytes, str, str | None, str] | None,
                BaseException | None,
            ],
            object,
        ],
    ) -> None:
        raise NotImplementedError(self.unlock)

    def mergeinfo(
        self,
        paths: list[str],
        revision: int = -1,
        inherit: str | None = None,
        include_descendants: bool = False,
    ) -> dict[str, dict[str, list[tuple[int, int, bool]]]]:
        raise NotImplementedError(self.mergeinfo)

    def location_segments(
        self,
        path: str,
        start_revision: int | None,
        end_revision: int | None,
        include_merged_revisions: bool = False,
    ) -> Iterator[UnmarshalledValue]:
        args: list[MarshallValue] = [path]
        if start_revision is None or start_revision == -1:
            args.append([])
        else:
            args.append([start_revision])
        if end_revision is None or end_revision == -1:
            args.append([])
        else:
            args.append([end_revision])
        args.append(include_merged_revisions)
        self.send_msg([literal("get-location-segments"), args])
        self._recv_ack()
        while True:
            msg = self.recv_msg()
            if msg == literal("done"):
                break
            yield msg
        self._unpack()

    def get_location_segments(
        self,
        path: str,
        start_revision: int | None,
        end_revision: int | None,
        rcvr: Callable[[str, int, int], object],
    ) -> None:
        for msg in self.location_segments(path, start_revision, end_revision):
            seg = _as_list(msg)
            rcvr(_as_str(seg[0]), _as_int(seg[1]), _as_int(seg[2]))

    def has_capability(self, capability: str) -> bool:
        return literal(capability) in self._server_capabilities

    @mark_busy
    def check_path(self, path: str, revision: int | None = None) -> int:
        args: list[MarshallValue] = [path]
        if revision is None or revision == -1:
            args.append([])
        else:
            args.append([revision])
        self.send_msg([literal("check-path"), args])
        self._recv_ack()
        ret = _as_str(self._unpack()[0])
        return {
            "dir": NODE_DIR,
            "file": NODE_FILE,
            "unknown": NODE_UNKNOWN,
            "none": NODE_NONE,
        }[ret]

    def get_lock(self, path: str) -> UnmarshalledValue | None:
        self.send_msg([literal("get-lock"), [path]])
        self._recv_ack()
        ret = self._unpack()
        if len(ret) == 0:
            return None
        else:
            return ret[0]

    @mark_busy
    def get_dir(
        self,
        path: str,
        revision: int | None = -1,
        dirent_fields: int = 0,
        want_props: bool = True,
        want_contents: bool = True,
    ) -> tuple[dict[str, Dirent], int, dict[str, bytes]]:
        args: list[MarshallValue] = [path]
        if revision is None or revision == -1:
            args.append([])
        else:
            args.append([revision])

        args += [want_props, want_contents]

        fields: list[MarshallValue] = []
        if dirent_fields & DIRENT_KIND:
            fields.append(literal("kind"))
        if dirent_fields & DIRENT_SIZE:
            fields.append(literal("size"))
        if dirent_fields & DIRENT_HAS_PROPS:
            fields.append(literal("has-props"))
        if dirent_fields & DIRENT_CREATED_REV:
            fields.append(literal("created-rev"))
        if dirent_fields & DIRENT_TIME:
            fields.append(literal("time"))
        if dirent_fields & DIRENT_LAST_AUTHOR:
            fields.append(literal("last-author"))
        args.append(fields)

        self.send_msg([literal("get-dir"), args])
        self._recv_ack()
        ret = self._unpack()
        fetch_rev = _as_int(ret[0])
        props = _bytes_dict(ret[1])
        dirents: dict[str, Dirent] = {}
        for d in _as_list(ret[2]):
            entry = unmarshall_dirent(_as_list(d))
            dirents[_as_str(cast(UnmarshalledValue, entry["name"]))] = entry

        return (dirents, fetch_rev, props)

    @mark_busy
    def stat(self, path: str, revision: int | None = -1) -> Dirent | None:
        args: list[MarshallValue] = [path]
        if revision is None or revision == -1:
            args.append([revision] if revision is not None else [])
        else:
            args.append([])

        self.send_msg([literal("stat"), args])
        self._recv_ack()
        ret = self._unpack()
        if len(ret) == 0:
            return None
        return unmarshall_dirent(_as_list(ret[0]))

    @mark_busy
    def get_file(self, path: str, stream: IO[bytes], revision: int = -1) -> None:
        raise NotImplementedError(self.get_file)

    def change_rev_prop(self, rev: int, name: str, value: bytes | None) -> None:
        args: list[MarshallValue] = [rev, name]
        if value is not None:
            args.append(value)
        self.send_msg([literal("change-rev-prop"), args])
        self._recv_ack()
        self._unpack()

    def get_commit_editor(
        self,
        revprops: dict[str, bytes],
        callback: CommitFinalizer | None = None,
        lock_tokens: dict[str, str] | None = None,
        keep_locks: bool = False,
    ) -> EditorProto:
        args: list[MarshallValue] = [revprops[properties.PROP_REVISION_LOG]]
        if lock_tokens is not None:
            args.append(list(lock_tokens.items()))
        else:
            args.append([])
        args.append(keep_locks)
        if len(revprops) > 1:
            args.append(list(revprops.items()))
        self.send_msg([literal("commit"), args])
        self._recv_ack()
        raise NotImplementedError(self.get_commit_editor)

    def rev_proplist(self, revision: int) -> dict[str, bytes]:
        self.send_msg([literal("rev-proplist"), [revision]])
        self._recv_ack()
        return _bytes_dict(self._unpack()[0])

    def rev_prop(self, revision: int, name: str) -> bytes | None:
        self.send_msg([literal("rev-prop"), [revision, name]])
        self._recv_ack()
        ret = self._unpack()
        if len(ret) == 0:
            return None
        else:
            return _as_bytes(ret[0])

    @mark_busy
    def replay(
        self,
        revision: int,
        low_water_mark: int,
        update_editor: EditorProto,
        send_deltas: bool = True,
    ) -> None:
        self.send_msg([literal("replay"), [revision, low_water_mark, send_deltas]])
        self._recv_ack()
        feed_editor(self, update_editor)
        self._unpack()

    @mark_busy
    def replay_range(
        self,
        start_revision: int,
        end_revision: int,
        low_water_mark: int,
        cbs: tuple[ReplayRevStartCallback, ReplayRevFinishCallback],
        send_deltas: bool = True,
    ) -> None:
        self.send_msg(
            [
                literal("replay-range"),
                [start_revision, end_revision, low_water_mark, send_deltas],
            ]
        )
        self._recv_ack()
        for i in range(start_revision, end_revision + 1):
            msg = _as_list(self.recv_msg())
            assert msg[0] == literal("revprops")
            props = _bytes_dict(msg[1])
            edit = cbs[0](i, props)
            feed_editor(self, edit)
            cbs[1](i, props, edit)
        self._unpack()

    def do_switch(
        self,
        revision_to_update_to: int | None,
        update_target: str,
        recurse: bool,
        switch_url: str,
        update_editor: EditorProto,
        depth: str | None = None,
    ) -> Reporter:
        args: list[MarshallValue] = []
        if revision_to_update_to is None or revision_to_update_to == -1:
            args.append([])
        else:
            args.append([revision_to_update_to])
        args.append(update_target)
        args.append(recurse)
        args.append(switch_url)
        if depth is not None:
            args.append(literal(depth))

        self.busy = True
        try:
            self.send_msg([literal("switch"), args])
            self._recv_ack()
            return Reporter(self, update_editor)
        except BaseException:
            self.busy = False
            raise

    def do_update(
        self,
        revision_to_update_to: int | None,
        update_target: str,
        recurse: bool,
        update_editor: EditorProto,
        depth: str | None = None,
    ) -> Reporter:
        args: list[MarshallValue] = []
        if revision_to_update_to is None or revision_to_update_to == -1:
            args.append([])
        else:
            args.append([revision_to_update_to])
        args.append(update_target)
        args.append(recurse)
        if depth is not None:
            args.append(literal(depth))

        self.busy = True
        try:
            self.send_msg([literal("update"), args])
            self._recv_ack()
            return Reporter(self, update_editor)
        except BaseException:
            self.busy = False
            raise

    def do_diff(
        self,
        revision_to_update: int | None,
        diff_target: str,
        versus_url: str,
        diff_editor: EditorProto,
        recurse: bool = True,
        ignore_ancestry: bool = False,
        text_deltas: bool = False,
        depth: str | None = None,
    ) -> Reporter:
        args: list[MarshallValue] = []
        if revision_to_update is None or revision_to_update == -1:
            args.append([])
        else:
            args.append([revision_to_update])
        args += [diff_target, recurse, ignore_ancestry, versus_url, text_deltas]
        if depth is not None:
            args.append(literal(depth))
        self.busy = True
        try:
            self.send_msg([literal("diff"), args])
            self._recv_ack()
            return Reporter(self, diff_editor)
        except BaseException:
            self.busy = False
            raise

    def get_repos_root(self) -> str:
        return self._root_url

    @mark_busy
    def get_latest_revnum(self) -> int:
        self.send_msg([literal("get-latest-rev"), []])
        self._recv_ack()
        return _as_int(self._unpack()[0])

    @mark_busy
    def get_dated_rev(self, date: str) -> int:
        self.send_msg([literal("get-dated-rev"), [date]])
        self._recv_ack()
        return _as_int(self._unpack()[0])

    @mark_busy
    def reparent(self, url: str) -> None:
        self.send_msg([literal("reparent"), [url]])
        self._recv_ack()
        self._unpack()
        self.url = url

    def get_uuid(self) -> str:
        return self._uuid

    @mark_busy
    def log(
        self,
        paths: list[str] | None,
        start: int | None,
        end: int | None,
        limit: int = 0,
        discover_changed_paths: bool = True,
        strict_node_history: bool = True,
        include_merged_revisions: bool = True,
        revprops: list[str] | None = None,
    ) -> Iterator[
        tuple[
            dict[str, tuple[str, bytes | None, int]],
            int,
            dict[str, bytes],
            bool | None,
        ]
    ]:
        paths_arg: list[MarshallValue] = [] if paths is None else list(paths)
        args: list[MarshallValue] = [paths_arg]
        if start is None or start == -1:
            args.append([])
        else:
            args.append([start])
        if end is None or end == -1:
            args.append([])
        else:
            args.append([end])
        args.append(discover_changed_paths)
        args.append(strict_node_history)
        args.append(limit)
        args.append(include_merged_revisions)
        if revprops is None:
            args.append(literal("all-revprops"))
            args.append([])
        else:
            args.append(literal("revprops"))
            revprops_arg: list[MarshallValue] = list(revprops)
            args.append(revprops_arg)

        self.send_msg([literal("log"), args])
        self._recv_ack()
        while True:
            raw = self.recv_msg()
            if raw == literal("done"):
                break
            msg = _as_list(raw)
            changed: dict[str, tuple[str, bytes | None, int]] = {}
            for entry in _as_list(msg[0]):
                entry_list = _as_list(entry)
                p = _as_str(entry_list[0])
                action = _as_str(entry_list[1])
                cfd = _as_list(entry_list[2])
                if len(cfd) == 0:
                    changed[p] = (action, None, -1)
                else:
                    changed[p] = (action, _as_bytes(cfd[0]), _as_int(cfd[1]))

            has_children: bool | None
            if len(msg) > 5:
                has_children = bool(_as_int(msg[5]))
            else:
                has_children = None
            if len(msg) > 6 and msg[6]:
                revno = None
            else:
                revno = _as_int(msg[1])  # noqa: F841
                # TODO(jelmer): Do something with revno
            msg_revprops: dict[str, bytes] = {}
            author_list = _as_list(msg[2])
            if len(author_list) != 0:
                msg_revprops[properties.PROP_REVISION_AUTHOR] = _as_bytes(
                    author_list[0]
                )
            date_list = _as_list(msg[3])
            if len(date_list) != 0:
                msg_revprops[properties.PROP_REVISION_DATE] = _as_bytes(date_list[0])
            log_list = _as_list(msg[4])
            if len(log_list) != 0:
                msg_revprops[properties.PROP_REVISION_LOG] = _as_bytes(log_list[0])
            if len(msg) > 8:
                msg_revprops.update(_bytes_dict(msg[8]))
            yield changed, _as_int(msg[1]), msg_revprops, has_children

        self._unpack()

    def get_log(
        self,
        callback: Callable[
            [
                dict[str, tuple[str, bytes | None, int]],
                int,
                dict[str, bytes],
                bool,
            ],
            object,
        ],
        *args: object,
        **kwargs: object,
    ) -> None:
        for paths, rev, props, has_children in self.log(*args, **kwargs):  # type: ignore[arg-type]
            if has_children is None:
                callback(paths, rev, props, False)
            else:
                callback(paths, rev, props, has_children)


MIN_VERSION = 2
MAX_VERSION = 2
CAPABILITIES = ["edit-pipeline", "bazaar", "log-revprops"]
MECHANISMS = ["ANONYMOUS"]


class SVNServer(SVNConnection):
    def __init__(
        self,
        backend: ServerBackend,
        recv_fn: Callable[[int], bytes],
        send_fn: Callable[[bytes], int],
        logf: IO[str] | None = None,
    ) -> None:
        self.backend = backend
        self._stop = False
        self._logf = logf
        super().__init__(recv_fn, send_fn)

        self.send_success(
            MIN_VERSION,
            MAX_VERSION,
            [literal(x) for x in MECHANISMS],
            [literal(x) for x in CAPABILITIES],
        )

    def send_mechs(self) -> None:
        self.send_success([literal(x) for x in MECHANISMS], "")

    def send_failure(self, *contents: MarshallValue) -> None:
        self.send_msg([literal("failure"), list(contents)])

    def send_ack(self) -> None:
        self.send_success([], "")

    def send_unknown(self, cmd: str) -> None:
        self.send_failure(
            [ERR_RA_SVN_UNKNOWN_CMD, f"Unknown command '{cmd}'", __file__, 52]
        )

    def get_latest_rev(self) -> None:
        self.send_ack()
        self.send_success(self.repo_backend.get_latest_revnum())

    def check_path(self, path: str, rev: list[int]) -> None:
        if len(rev) == 0:
            revnum = None
        else:
            revnum = rev[0]
        kind = self.repo_backend.check_path(path, revnum)
        self.send_ack()
        self.send_success(
            literal(
                {
                    NODE_NONE: "none",
                    NODE_DIR: "dir",
                    NODE_FILE: "file",
                    NODE_UNKNOWN: "unknown",
                }[kind]
            )
        )

    def log(
        self,
        target_path: str,
        start_rev: list[int],
        end_rev: list[int],
        changed_paths: bool,
        strict_node: bool,
        limit: int | None = None,
        include_merged_revisions: bool = False,
        all_revprops: object = None,
        revprops: list[str] | None = None,
    ) -> None:
        def send_revision(
            revno: int,
            author: bytes,
            date: bytes,
            message: bytes,
            changed_paths: dict[str, ServerLogPathChange] | None = None,
        ) -> None:
            changes: list[MarshallValue] = []
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
        self.repo_backend.log(
            send_revision,
            target_path,
            start_revnum,
            end_revnum,
            changed_paths,
            strict_node,
            limit,
        )
        self.send_msg(literal("done"))
        self.send_success()

    def open_backend(self, url: str) -> None:
        parsed = urlparse.urlparse(url)
        location = parsed.path
        self.repo_backend, self.relpath = self.backend.open_repository(location)

    def reparent(self, parent: str) -> None:
        self.open_backend(parent)
        self.send_ack()
        self.send_success()

    def stat(self, path: str, rev: list[int]) -> None:
        if len(rev) == 0:
            revnum = None
        else:
            revnum = rev[0]
        self.send_ack()
        dirent = self.repo_backend.stat(path, revnum)
        if dirent is None:
            self.send_success([])
        else:
            args: list[MarshallValue] = [
                cast(MarshallValue, dirent["name"]),
                cast(MarshallValue, dirent["kind"]),
                cast(MarshallValue, dirent["size"]),
                cast(MarshallValue, dirent["has-props"]),
                cast(MarshallValue, dirent["created-rev"]),
            ]
            if "created-date" in dirent:
                args.append([cast(MarshallValue, dirent["created-date"])])
            else:
                args.append([])
            if "last-author" in dirent:
                args.append([cast(MarshallValue, dirent["last-author"])])
            else:
                args.append([])
            self.send_success([args])

    def commit(
        self,
        logmsg: bytes,
        locks: list[UnmarshalledValue],
        keep_locks: bool = False,
        rev_props: list[UnmarshalledValue] | None = None,
    ) -> None:
        self.send_failure(
            [ERR_UNSUPPORTED_FEATURE, "commit not yet supported", __file__, 42]
        )

    def rev_proplist(self, revnum: int) -> None:
        self.send_ack()
        revprops = self.repo_backend.rev_proplist(revnum)
        self.send_success(list(revprops.items()))

    def rev_prop(self, revnum: int, name: str) -> None:
        self.send_ack()
        revprops = self.repo_backend.rev_proplist(revnum)
        if name in revprops:
            self.send_success([revprops[name]])
        else:
            self.send_success()

    def get_locations(self, path: str, peg_revnum: int, revnums: list[int]) -> None:
        self.send_ack()
        locations = self.repo_backend.get_locations(path, peg_revnum, revnums)
        for rev, path in locations.items():
            self.send_msg([rev, path])
        self.send_msg(literal("done"))
        self.send_success()

    def update(
        self,
        rev: list[int],
        target: str,
        recurse: bool,
        depth: str | None = None,
        send_copyfrom_param: bool = True,
    ) -> None:
        self.send_ack()
        while True:
            msg = _as_list(self.recv_msg())
            assert msg[0] in (literal("set-path"), literal("finish-report"))
            if msg[0] == literal("finish-report"):
                break

        self.send_ack()

        if len(rev) == 0:
            revnum = None
        else:
            revnum = rev[0]
        self.repo_backend.update(Editor(self), revnum, target, recurse)
        self.send_success()
        client_result = _as_list(self.recv_msg())
        if client_result[0] == literal("success"):
            return
        else:
            self.mutter(f"Client reported error during update: {client_result!r}")
            # Needs to be sent back to the client to display
            failure_body = cast(
                "list[MarshallValue]",
                _as_list(_as_list(client_result[1])[0]),
            )
            self.send_failure(failure_body)

    commands: ClassVar[dict[str, Callable[..., None]]] = {
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

    def send_auth_request(self) -> None:
        pass

    def serve(self) -> None:
        msg = _as_list(self.recv_msg())
        version = _as_int(msg[0])
        capabilities = _as_list(msg[1])
        url = _as_str(msg[2])
        if len(msg) > 3:
            self.client_user_agent: str | None = _as_str(msg[3])
        else:
            self.client_user_agent = None
        self.capabilities = capabilities
        self.version = version
        self.url = url
        self.mutter("client supports:")
        self.mutter(f"  version {version!r}")
        self.mutter(f"  capabilities {capabilities!r} ")
        self.send_mechs()

        _mech_and_args = _as_list(self.recv_msg())
        # TODO: Proper authentication
        self.send_success()

        self.open_backend(url)
        self.send_success(self.repo_backend.get_uuid(), url)

        # Expect:
        while not self._stop:
            request = _as_list(self.recv_msg())
            cmd = _as_str(request[0])
            args = _as_list(request[1])
            if cmd not in self.commands:
                self.mutter(f"client used unknown command {cmd!r}")
                self.send_unknown(cmd)
                return
            else:
                self.commands[cmd](self, *args)

    def close(self) -> None:
        self._stop = True

    def mutter(self, text: str) -> None:
        if self._logf is not None:
            self._logf.write(f"{text}\n")


class TCPSVNRequestHandler(StreamRequestHandler):
    def __init__(
        self,
        request: object,
        client_address: object,
        server: "TCPSVNServer",
    ) -> None:
        self._server = server
        StreamRequestHandler.__init__(self, request, client_address, server)  # type: ignore[arg-type]

    def handle(self) -> None:
        server = SVNServer(
            self._server._backend, self.rfile.read, self.wfile.write, self._server._logf
        )
        try:
            server.serve()
        except OSError as e:
            if e.args[0] == EPIPE:
                return
            raise


class TCPSVNServer(TCPServer):
    allow_reuse_address = True
    serve = TCPServer.serve_forever

    def __init__(
        self,
        backend: ServerBackend,
        addr: tuple[str, int],
        logf: IO[str] | None = None,
    ) -> None:
        self._logf = logf
        self._backend = backend
        TCPServer.__init__(self, addr, TCPSVNRequestHandler)
