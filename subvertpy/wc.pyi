from collections.abc import Callable
from types import TracebackType
from typing import IO

SCHEDULE_NORMAL: int
SCHEDULE_ADD: int
SCHEDULE_DELETE: int
SCHEDULE_REPLACE: int

CONFLICT_CHOOSE_POSTPONE: int
CONFLICT_CHOOSE_BASE: int
CONFLICT_CHOOSE_THEIRS_FULL: int
CONFLICT_CHOOSE_MINE_FULL: int
CONFLICT_CHOOSE_THEIRS_CONFLICT: int
CONFLICT_CHOOSE_MINE_CONFLICT: int
CONFLICT_CHOOSE_MERGED: int

STATUS_NONE: int
STATUS_UNVERSIONED: int
STATUS_NORMAL: int
STATUS_ADDED: int
STATUS_MISSING: int
STATUS_DELETED: int
STATUS_REPLACED: int
STATUS_MODIFIED: int
STATUS_MERGED: int
STATUS_CONFLICTED: int
STATUS_IGNORED: int
STATUS_OBSTRUCTED: int
STATUS_EXTERNAL: int
STATUS_INCOMPLETE: int

TRANSLATE_FROM_NF: int
TRANSLATE_TO_NF: int
TRANSLATE_FORCE_EOL_REPAIR: int
TRANSLATE_NO_OUTPUT_CLEANUP: int
TRANSLATE_FORCE_COPY: int
TRANSLATE_USE_GLOBAL_TMP: int

# The Rust WC bindings invoke the notify callback only when the
# underlying notification carries an error, passing the corresponding
# Python exception. See wc/src/context.rs::make_notify_closure.
WcNotifyFunc = Callable[[BaseException], object]

class Status:
    node_status: int
    text_status: int
    prop_status: int
    copied: bool
    switched: bool
    locked: bool
    revision: int
    changed_rev: int
    kind: int
    depth: int
    filesize: int
    versioned: bool
    repos_uuid: str | None
    repos_root_url: str | None

class Lock:
    path: str | None
    token: bytes | None

class Entry:
    name: str | None
    revision: int
    url: str | None
    repos: str | None
    uuid: str | None
    kind: int
    schedule: int
    copied: bool
    deleted: bool
    absent: bool
    incomplete: bool
    copyfrom_url: str | None
    copyfrom_revision: int

class Adm: ...

class CommittedQueue:
    def __init__(self) -> None: ...
    def queue(
        self,
        path: str | bytes,
        adm: Context,
        recurse: bool = ...,
        wcprop_changes: dict[str, bytes] | None = ...,
        remove_lock: bool = ...,
        remove_changelist: bool = ...,
        md5_digest: bytes | None = ...,
        sha1_digest: bytes | None = ...,
    ) -> None: ...

class UpdateEditor:
    """Opaque editor returned by Context.get_update_editor."""

    def abort(self) -> None: ...
    def close(self) -> None: ...

class Context:
    def __init__(self) -> None: ...
    def __enter__(self) -> Context: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...
    def close(self) -> None: ...
    def locked(self, path: str | bytes) -> tuple[bool, bool]: ...
    def check_wc(self, path: str | bytes) -> int: ...
    def text_modified(self, path: str | bytes) -> bool: ...
    def props_modified(self, path: str | bytes) -> bool: ...
    def conflicted(self, path: str | bytes) -> tuple[bool, bool, bool]: ...
    def add(
        self,
        path: str | bytes,
        depth: int | None = ...,
        copyfrom_url: str | None = ...,
        copyfrom_rev: int = ...,
    ) -> None: ...
    def delete(
        self,
        path: str | bytes,
        keep_local: bool = ...,
        notify: WcNotifyFunc | None = ...,
    ) -> None: ...
    def copy(
        self,
        src_path: str | bytes,
        dest_path: str | bytes,
        notify: WcNotifyFunc | None = ...,
    ) -> None: ...
    def prop_get(self, name: str, path: str | bytes) -> bytes | None: ...
    def prop_set(
        self,
        name: str,
        value: bytes | str | None,
        path: str | bytes,
        recursive: bool = ...,
        skip_checks: bool = ...,
        depth: int | None = ...,
    ) -> None: ...
    def read_kind(self, path: str | bytes) -> int: ...
    def status(self, path: str | bytes) -> Status: ...
    def walk_status(
        self,
        path: str | bytes,
        statuses: bool = ...,
        get_all: bool = ...,
        no_ignore: bool = ...,
        show_updates: bool = ...,
        depth_as_sticky: bool = ...,
        server_time: int | None = ...,
        ignore_patterns: list[str] | None = ...,
    ) -> None: ...
    def get_prop_diffs(
        self, path: str | bytes
    ) -> tuple[dict[str, bytes | None], dict[str, bytes | None]]: ...
    def ensure_adm(
        self,
        path: str | bytes,
        uuid: str,
        url: str,
        repos: str | None = ...,
        rev: int = ...,
        depth: int = ...,
    ) -> None: ...
    def add_lock(self, path: str | bytes, lock: Lock) -> None: ...
    def remove_lock(self, path: str | bytes) -> None: ...
    def add_from_disk(
        self,
        path: str | bytes,
        notify: WcNotifyFunc | None = ...,
    ) -> None: ...
    def process_committed_queue(
        self,
        q: CommittedQueue,
        recurse: bool = ...,
        remove_lock: bool = ...,
        remove_changelist: bool = ...,
    ) -> None: ...
    def crawl_revisions(
        self,
        path: str | bytes,
        notify: WcNotifyFunc | None = ...,
        use_commit_times: bool = ...,
    ) -> None: ...
    def get_update_editor(
        self,
        target_revision: int,
        dst_wcpath: str | bytes,
        allow_unver_obstructions: bool = ...,
        depth_is_sticky: bool = ...,
        depth: int = ...,
        use_commit_times: bool = ...,
        notify: WcNotifyFunc | None = ...,
    ) -> UpdateEditor: ...

def version() -> tuple[int, int, int, str]: ...
def api_version() -> tuple[int, int, int, str]: ...
def check_wc(path: str | bytes) -> int: ...
def cleanup(path: str | bytes, diff3_cmd: str | None = ...) -> None: ...
def ensure_adm(
    path: str | bytes,
    uuid: str,
    url: str,
    repos: str | None = ...,
    rev: int = ...,
    depth: int = ...,
) -> None: ...
def get_adm_dir() -> str: ...
def set_adm_dir(name: str | bytes) -> None: ...
def is_adm_dir(name: str | bytes) -> bool: ...
def is_normal_prop(name: str) -> bool: ...
def is_entry_prop(name: str) -> bool: ...
def is_wc_prop(name: str) -> bool: ...
def match_ignore_list(s: str, patterns: list[str]) -> bool: ...
def get_actual_target(path: str | bytes) -> tuple[str, str]: ...
def get_pristine_copy_path(path: str | bytes) -> str: ...
def get_pristine_contents(path: str | bytes) -> IO[bytes] | None: ...
def revision_status(
    wc_path: str | bytes,
    trail_url: str | None = ...,
    committed: bool = ...,
) -> tuple[int, int, bool, bool]: ...
