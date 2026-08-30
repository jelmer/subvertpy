import builtins
from typing import IO

from subvertpy._ra import Auth
from subvertpy._typing import (
    CommitFinalizer,
    LogEntry,
    LogEntryReceiver,
    LogMsgFunc,
    NotifyFunc,
)

class ConfigItem: ...

class Config:
    def get_default_ignores(self) -> list[bytes]: ...

class WCInfo:
    schedule: int
    copyfrom_url: str | None
    copyfrom_rev: int
    changelist: str | None
    recorded_size: int
    recorded_time: int
    wcroot_abspath: str | None

class Info:
    url: str
    revision: int
    kind: str
    repos_root_url: str
    repos_uuid: str
    last_changed_rev: int
    last_changed_date: str
    last_changed_author: str
    size: int
    wc_info: WCInfo | None

class ClientLogIterator:
    def __iter__(self) -> ClientLogIterator: ...
    def __next__(self) -> LogEntry: ...

class Client:
    auth: Auth | None
    log_msg_func: LogMsgFunc | None
    notify_func: NotifyFunc | None
    config: Config | None

    def __init__(
        self,
        auth: Auth | None = ...,
        config: Config | None = ...,
        log_msg_func: LogMsgFunc | None = ...,
        notify_func: NotifyFunc | None = ...,
    ) -> None: ...
    def checkout(
        self,
        url: str,
        path: str,
        rev: str | int | None = ...,
        peg_rev: str | int | None = ...,
        recurse: bool = ...,
        ignore_externals: bool = ...,
        allow_unver_obstructions: bool = ...,
    ) -> int: ...
    def update(
        self,
        path: str | list[str],
        rev: str | int | None = ...,
        recurse: bool = ...,
        ignore_externals: bool = ...,
        depth_is_sticky: bool = ...,
        allow_unver_obstructions: bool = ...,
        adds_as_modification: bool = ...,
        make_parents: bool = ...,
    ) -> list[int]: ...
    def add(
        self,
        path: str,
        recursive: bool = ...,
        force: bool = ...,
        no_ignore: bool = ...,
        add_parents: bool = ...,
        no_autoprops: bool = ...,
        depth: int | None = ...,
    ) -> None: ...
    def delete(
        self,
        paths: list[str],
        force: bool = ...,
        keep_local: bool = ...,
        revprops: dict[str, str] | None = ...,
        callback: CommitFinalizer | None = ...,
    ) -> None: ...
    def revert(
        self,
        paths: list[str],
        depth: int | None = ...,
        recursive: bool = ...,
    ) -> None: ...
    def commit(
        self,
        paths: list[str],
        message: str,
        revprops: dict[str, str] | None = ...,
        keep_locks: bool = ...,
        keep_changelists: bool = ...,
        recurse: bool = ...,
        no_unlock: bool = ...,
        exclude_paths: list[str] | None = ...,
        changelist: str | None = ...,
        callback: CommitFinalizer | None = ...,
    ) -> tuple[int, str | None, str | None]: ...
    def log(
        self,
        callback: LogEntryReceiver,
        paths: list[str] | None = ...,
        start_rev: str | int | None = ...,
        end_rev: str | int | None = ...,
        limit: int | None = ...,
        discover_changed_paths: bool = ...,
        strict_node_history: bool = ...,
        include_merged_revisions: bool = ...,
        revprops: list[str] | None = ...,
    ) -> None: ...
    def iter_log(
        self,
        paths: list[str] | None = ...,
        start_rev: str | int | None = ...,
        end_rev: str | int | None = ...,
        limit: int | None = ...,
        discover_changed_paths: bool = ...,
        strict_node_history: bool = ...,
        include_merged_revisions: bool = ...,
        revprops: list[str] | None = ...,
    ) -> ClientLogIterator: ...
    def mkdir(
        self,
        paths: list[str],
        message: str,
        revprops: dict[str, str] | None = ...,
        make_parents: bool = ...,
        callback: CommitFinalizer | None = ...,
    ) -> tuple[int, str | None, str | None]: ...
    def propset(
        self,
        name: str,
        value: str | bytes | None,
        path: str,
        recursive: bool = ...,
        skip_checks: bool = ...,
        base_revision: int | None = ...,
        depth: int | None = ...,
    ) -> None: ...
    def propget(
        self,
        name: str,
        path: str,
        peg_rev: str | int | None = ...,
        rev: str | int | None = ...,
        recurse: bool = ...,
    ) -> dict[str, bytes]: ...
    def proplist(
        self,
        path: str,
        peg_rev: str | int | None = ...,
        rev: str | int | None = ...,
        recurse: bool = ...,
    ) -> list[tuple[str, dict[str, bytes]]]: ...
    def info(
        self,
        paths: list[str] | str,
        peg_rev: str | int | None = ...,
        rev: str | int | None = ...,
        depth: int | None = ...,
        fetch_excluded: bool = ...,
        fetch_actual_only: bool = ...,
        include_externals: bool = ...,
    ) -> Info | list[Info]: ...
    def export(
        self,
        url: str,
        path: str,
        peg_rev: str | int | None = ...,
        rev: str | int | None = ...,
        force: bool = ...,
        ignore_externals: bool = ...,
        native_eol: str | None = ...,
    ) -> int: ...
    def diff(
        self,
        rev1: str | int | None = ...,
        path1: str = ...,
        rev2: str | int | None = ...,
        path2: str = ...,
        outfile: IO[bytes] | None = ...,
        errfile: IO[bytes] | None = ...,
    ) -> None: ...
    def cat(
        self,
        url: str,
        peg_rev: str | int | None = ...,
        rev: str | int | None = ...,
    ) -> bytes: ...
    def copy(
        self,
        src_path: str,
        dest_path: str,
        src_rev: str | int | None = ...,
        revprops: dict[str, str] | None = ...,
        callback: CommitFinalizer | None = ...,
    ) -> tuple[int, str | None, str | None]: ...
    def list(
        self,
        url: str,
        peg_rev: str | int | None = ...,
        rev: str | int | None = ...,
        recurse: bool = ...,
        include_externals: bool = ...,
    ) -> builtins.list[tuple[str, int, bool, int, int]]: ...
    def lock(
        self,
        targets: builtins.list[str],
        comment: str = ...,
        steal_lock: bool = ...,
    ) -> None: ...
    def unlock(
        self,
        targets: builtins.list[str],
        break_lock: bool = ...,
    ) -> None: ...
    def resolve(
        self,
        path: str,
        depth: int,
        conflict_choice: int,
    ) -> None: ...

def version() -> tuple[int, int, int, str]: ...
def api_version() -> tuple[int, int, int, str]: ...
def get_config(config_dir: str | None = ...) -> Config: ...
