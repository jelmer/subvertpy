from collections.abc import Callable
from typing import IO, Any

DIRENT_KIND: int
DIRENT_SIZE: int
DIRENT_HAS_PROPS: int
DIRENT_CREATED_REV: int
DIRENT_TIME: int
DIRENT_LAST_AUTHOR: int
DIRENT_ALL: int

NODE_NONE: int
NODE_FILE: int
NODE_DIR: int
NODE_UNKNOWN: int
NODE_SYMLINK: int

DEPTH_UNKNOWN: int
DEPTH_EXCLUDE: int
DEPTH_EMPTY: int
DEPTH_FILES: int
DEPTH_IMMEDIATES: int
DEPTH_INFINITY: int

MERGEINFO_EXPLICIT: int
MERGEINFO_INHERITED: int
MERGEINFO_NEAREST_ANCESTOR: int

SVN_REVISION: int

class BusyException(Exception): ...

class AuthProvider: ...

class CredentialsIter:
    def __iter__(self) -> CredentialsIter: ...
    def __next__(self) -> Any: ...

class Auth:
    def __init__(self, providers: list[AuthProvider]) -> None: ...
    def set_parameter(self, name: str, value: Any) -> None: ...
    def get_parameter(self, name: str) -> Any: ...
    def credentials(self, cred_kind: str, realmstring: str) -> CredentialsIter: ...

class Reporter:
    def set_path(
        self,
        path: str,
        revision: int,
        start_empty: bool,
        lock_token: str | None = ...,
        depth: int | None = ...,
    ) -> None: ...
    def delete_path(self, path: str) -> None: ...
    def link_path(
        self,
        path: str,
        url: str,
        revision: int,
        start_empty: bool,
        lock_token: str | None = ...,
        depth: int | None = ...,
    ) -> None: ...
    def finish_report(self) -> None: ...
    def abort_report(self) -> None: ...

class LogIterator:
    def __iter__(self) -> LogIterator: ...
    def __next__(self) -> Any: ...

class RemoteAccess:
    url: str
    busy: bool

    def __init__(
        self,
        url: str,
        progress_cb: Callable[..., Any] | None = ...,
        auth: Auth | None = ...,
        config: Any | None = ...,
        client_string_func: Callable[..., Any] | None = ...,
        open_tmp_file_func: Callable[..., Any] | None = ...,
    ) -> None: ...
    def get_uuid(self) -> str: ...
    def get_repos_root(self) -> str: ...
    def get_session_url(self) -> str: ...
    def get_latest_revnum(self) -> int: ...
    def reparent(self, url: str) -> None: ...
    def has_capability(self, capability: str) -> bool: ...
    def check_path(self, path: str, revnum: int) -> int: ...
    def stat(self, path: str, revnum: int) -> dict[str, Any] | None: ...
    def rev_proplist(self, revnum: int) -> dict[str, bytes]: ...
    def rev_prop(self, revnum: int, name: str) -> bytes | None: ...
    def change_rev_prop(
        self,
        revnum: int,
        name: str,
        value: bytes | str | None = ...,
        old_value: bytes | str | None = ...,
    ) -> None: ...
    def get_file(
        self,
        path: str,
        stream: IO[bytes] | None,
        revnum: int | None = ...,
    ) -> tuple[int, dict[str, bytes]]: ...
    def get_dir(
        self,
        path: str,
        revision: int = ...,
        dirent_fields: int = ...,
        want_props: bool = ...,
        want_contents: bool = ...,
    ) -> tuple[dict[str, Any], int, dict[str, bytes]]: ...
    def get_lock(self, path: str) -> Any | None: ...
    def get_locks(
        self, path: str, depth: int | None = ...
    ) -> dict[str, Any]: ...
    def lock(
        self,
        path_revs: dict[str, int],
        comment: str,
        steal_lock: bool,
        lock_func: Callable[..., Any],
    ) -> None: ...
    def unlock(
        self,
        path_tokens: dict[str, bytes | str],
        break_lock: bool,
        unlock_func: Callable[..., Any],
    ) -> None: ...
    def get_log(
        self,
        callback: Callable[..., Any],
        paths: list[str] | None = ...,
        start: int = ...,
        end: int = ...,
        limit: int | None = ...,
        discover_changed_paths: bool = ...,
        strict_node_history: bool = ...,
        include_merged_revisions: bool = ...,
        revprops: list[str] | None = ...,
    ) -> None: ...
    def iter_log(
        self,
        paths: list[str] | None = ...,
        start: int = ...,
        end: int = ...,
        limit: int | None = ...,
        discover_changed_paths: bool = ...,
        strict_node_history: bool = ...,
        include_merged_revisions: bool = ...,
        revprops: list[str] | None = ...,
    ) -> LogIterator: ...
    def do_update(
        self,
        revision_to_update_to: int,
        update_target: str,
        recurse: bool,
        update_editor: Any,
        depth: int | None = ...,
    ) -> Reporter: ...
    def do_switch(
        self,
        revision_to_update_to: int,
        update_target: str,
        recurse: bool,
        switch_url: str,
        update_editor: Any,
        depth: int | None = ...,
    ) -> Reporter: ...
    def do_diff(
        self,
        revision_to_update: int,
        diff_target: str,
        versus_url: str,
        diff_editor: Any,
        recurse: bool = ...,
        ignore_ancestry: bool = ...,
        text_deltas: bool = ...,
        depth: int | None = ...,
    ) -> Reporter: ...
    def replay(
        self,
        revision: int,
        low_water_mark: int,
        update_editor: Any,
        send_deltas: bool = ...,
    ) -> None: ...
    def replay_range(
        self,
        start_revision: int,
        end_revision: int,
        low_water_mark: int,
        cbs: tuple[Callable[..., Any], Callable[..., Any]],
        send_deltas: bool = ...,
    ) -> None: ...
    def get_locations(
        self,
        path: str,
        peg_revision: int,
        location_revisions: list[int],
    ) -> dict[int, str]: ...
    def get_file_revs(
        self,
        path: str,
        start: int,
        end: int,
        file_rev_handler: Callable[..., Any],
    ) -> None: ...
    def mergeinfo(
        self,
        paths: list[str],
        revision: int = ...,
        inherit: int | None = ...,
        include_descendants: bool = ...,
    ) -> Any: ...
    def get_dated_rev(self, date: int) -> int: ...

def version() -> tuple[int, int, int, str]: ...
def api_version() -> tuple[int, int, int, str]: ...
def get_modules() -> str: ...
def print_modules() -> bytes: ...
def get_simple_provider() -> AuthProvider: ...
def get_username_provider() -> AuthProvider: ...
def get_ssl_server_trust_file_provider() -> AuthProvider: ...
def get_ssl_client_cert_file_provider() -> AuthProvider: ...
def get_ssl_client_cert_pw_file_provider() -> AuthProvider: ...
def get_platform_specific_client_providers() -> list[AuthProvider]: ...
def get_username_prompt_provider(
    prompt_func: Callable[..., Any], retry_limit: int = ...
) -> AuthProvider: ...
def get_simple_prompt_provider(
    prompt_func: Callable[..., Any], retry_limit: int = ...
) -> AuthProvider: ...
def get_ssl_server_trust_prompt_provider(
    prompt_func: Callable[..., Any],
) -> AuthProvider: ...
def get_ssl_client_cert_prompt_provider(
    prompt_func: Callable[..., Any], retry_limit: int = ...
) -> AuthProvider: ...
def get_ssl_client_cert_pw_prompt_provider(
    prompt_func: Callable[..., Any], retry_limit: int = ...
) -> AuthProvider: ...
