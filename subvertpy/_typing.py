# Copyright (C) 2026 Jelmer Vernooĳ <jelmer@jelmer.uk>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.

"""Shared type aliases and Protocols for subvertpy.

Kept in a separate module so both the pure-Python code and the .pyi
stubs for the Rust extensions can import from a single place.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, Union

if TYPE_CHECKING:
    from subvertpy.delta import TxDeltaWindow
    from subvertpy.marshall import literal


# --- svn_ra wire protocol value types -------------------------------------

MarshallValue = Union[
    bool,
    int,
    str,
    bytes,
    bytearray,
    "literal",
    list["MarshallValue"],
    tuple["MarshallValue", ...],
]
"""Any value that can be sent over the svn_ra wire protocol."""

UnmarshalledValue = Union[int, bytes, "literal", list["UnmarshalledValue"]]
"""Any value that can be produced by unmarshalling the svn_ra wire
protocol. Distinct from MarshallValue because unmarshalling never
produces bool, str or tuple.
"""


# --- Editor protocols ------------------------------------------------------

# Editors are the duck-typed objects used to describe a tree delta (see
# the SVN editor interface in svn_delta.h). subvertpy accepts any object
# that satisfies the following Protocols.

TxDeltaHandler = Callable[["TxDeltaWindow | None"], None]
"""Handler for text-delta windows. Called with None to signal end-of-delta."""


class FileEditor(Protocol):
    """Editor for a single file within a directory."""

    def apply_textdelta(self, base_checksum: str | None = ...) -> TxDeltaHandler: ...
    def change_prop(self, name: str, value: bytes | None) -> None: ...
    def close(self, checksum: str | None = ...) -> None: ...


class DirectoryEditor(Protocol):
    """Editor for a directory."""

    def add_file(
        self,
        path: str,
        copyfrom_path: str | None = ...,
        copyfrom_rev: int = ...,
    ) -> FileEditor: ...
    def open_file(self, path: str, base_revnum: int) -> FileEditor: ...
    def delete_entry(self, path: str, base_revnum: int) -> None: ...
    def add_directory(
        self,
        path: str,
        copyfrom_path: str | None = ...,
        copyfrom_rev: int = ...,
    ) -> DirectoryEditor: ...
    def open_directory(self, path: str, base_revnum: int) -> DirectoryEditor: ...
    def change_prop(self, name: str, value: bytes | None) -> None: ...
    def absent(self, path: str) -> None: ...
    def close(self) -> None: ...


class Editor(Protocol):
    """Top-level editor for a tree delta."""

    def set_target_revision(self, revnum: int) -> None: ...
    def open_root(self, base_revision: int | None = ...) -> DirectoryEditor: ...
    def close(self) -> None: ...
    def abort(self) -> None: ...


# --- Log entries -----------------------------------------------------------

# Description of a single path change in a log entry:
# (action, copyfrom_path, copyfrom_rev, node_kind). action is one of
# "A", "M", "D", "R"; node_kind is one of "file", "dir", "unknown" etc.
LogPathChange = tuple[str, str | None, int, str]

# A single log entry as passed to LogEntryReceiver / yielded by iter_log:
# (changed_paths, revision, revprops, has_children).
LogEntry = tuple[
    dict[str, LogPathChange] | None,
    int,
    dict[str, bytes],
    bool | None,
]

LogEntryReceiver = Callable[
    [dict[str, LogPathChange] | None, int, dict[str, bytes], bool],
    object,
]

# Changed-path map used by the ra_svn server backend (bytes-flavored).
# (action, copyfrom_path, copyfrom_rev).
ServerLogPathChange = tuple[str, "str | None", int]

SendRevisionCallback = Callable[
    [int, bytes, bytes, bytes, "dict[str, ServerLogPathChange] | None"],
    None,
]
"""Callback used by ServerRepositoryBackend.log to emit a revision."""


# --- SVN dirents / locks ---------------------------------------------------

# svn_dirent_t exposed as a dictionary. Not every request populates every
# field, so values are heterogeneous.
Dirent = dict[str, object]

# svn_lock_t exposed as a dictionary. Fields: path, token, owner, comment,
# is_dav_comment, creation_date, expiration_date.
Lock = dict[str, object]


# --- Callback signatures ---------------------------------------------------

ProgressFunc = Callable[[int, int], object]
"""RemoteAccess progress callback: (bytes_transferred, total_bytes)."""

ClientStringFunc = Callable[[], str]
"""RemoteAccess client identification callback."""

OpenTmpFileFunc = Callable[[], object]
"""RemoteAccess temp-file callback."""

CommitFinalizer = Callable[[int, str | None, str | None], object]
"""Client commit callback: (new_revision, date, author)."""

LogMsgFunc = Callable[[list[object]], "str | bytes | None"]
"""Client log-message callback: takes a list of commit-item dicts."""

NotifyFunc = Callable[[object], object]
"""Client / WC notification callback: receives a notify info object.
For wc.Context.get_update_editor it is invoked only when an error
occurs and the argument is the corresponding exception."""

PackNotifyFunc = Callable[[int, int], object]
"""repos.Repository.pack notify callback: (revision, action)."""

LockCallback = Callable[
    [
        str,
        bool,
        "tuple[str, bytes, str, str | None, str] | None",
        "BaseException | None",
    ],
    object,
]
"""RemoteAccess.lock / RemoteAccess.unlock callback:
(path, do_lock, lock_tuple, error).
"""

FileRevHandler = Callable[
    [str, int, dict[str, bytes], TxDeltaHandler | None, list[tuple[str, bytes | None]]],
    object,
]
"""svn_ra_file_rev_handler_t. Exact fields depend on subversion version."""

ReplayRevStartCallback = Callable[[int, dict[str, bytes]], Editor]
"""Called at the start of each revision in replay_range."""

ReplayRevFinishCallback = Callable[[int, dict[str, bytes], Editor], object]
"""Called at the end of each revision in replay_range."""


# --- Auth prompt callback signatures --------------------------------------

# The return-tuple convention across SVN prompt providers: the final
# `bool` is may_save.

SimpleProviderCallback = Callable[[str], object]
"""get_simple_provider callback: (kwallet_folder) — optional acceptance."""

UsernamePromptCallback = Callable[[str, bool], tuple[str, bool]]
"""(realm, may_save) -> (username, save)."""

SimplePromptCallback = Callable[[str, "str | None", bool], tuple[str, str, bool]]
"""(realm, default_username, may_save) -> (username, password, save)."""

SslServerTrustPromptCallback = Callable[
    [str, int, "dict[str, str] | None", bool],
    "tuple[int, bool] | None",
]
"""(realm, failures, cert_info, may_save) -> (accepted_failures, save) | None."""

SslClientCertPromptCallback = Callable[[str, bool], tuple[str, bool]]
"""(realm, may_save) -> (cert_file, save)."""

SslClientCertPwPromptCallback = Callable[[str, bool], tuple[str, bool]]
"""(realm, may_save) -> (password, save)."""
