# Copyright (C) 2006 Jelmer Vernooij <jelmer@jelmer.uk>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA

"""Server backend base classes."""

from subvertpy._typing import Dirent, Editor, SendRevisionCallback


class ServerBackend:
    """A server backend."""

    def open_repository(self, location: str) -> tuple["ServerRepositoryBackend", str]:
        raise NotImplementedError(self.open_repository)


def generate_random_id() -> str:
    """Create a UUID for a repository."""
    import uuid

    return str(uuid.uuid4())


class ServerRepositoryBackend:
    def get_uuid(self) -> str:
        raise NotImplementedError(self.get_uuid)

    def get_latest_revnum(self) -> int:
        raise NotImplementedError(self.get_latest_revnum)

    def log(
        self,
        send_revision: SendRevisionCallback,
        target_path: str,
        start_rev: int | None,
        end_rev: int | None,
        changed_paths: bool,
        strict_node: bool,
        limit: int | None,
    ) -> None:
        raise NotImplementedError(self.log)

    def update(
        self,
        editor: Editor,
        revnum: int | None,
        target_path: str,
        recurse: bool = True,
    ) -> None:
        raise NotImplementedError(self.update)

    def check_path(self, path: str, revnum: int | None) -> int:
        raise NotImplementedError(self.check_path)

    def stat(self, path: str, revnum: int | None) -> Dirent | None:
        """Stat a path.

        Should return a dictionary with the following keys: name, kind, size,
        has-props, created-rev, created-date, last-author.
        """
        raise NotImplementedError(self.stat)

    def rev_proplist(self, revnum: int) -> dict[str, bytes]:
        raise NotImplementedError(self.rev_proplist)

    def get_locations(
        self, path: str, peg_revnum: int, revnums: list[int]
    ) -> dict[int, str]:
        raise NotImplementedError(self.get_locations)
