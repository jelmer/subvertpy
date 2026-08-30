# Copyright (C) 2026 Jelmer Vernooij <jelmer@jelmer.uk>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Run the ra tests against svn:// (ra_svn)."""

import os
import subprocess

from subvertpy import ra
from subvertpy.ra import Auth

# test_ra is imported as a module rather than by name: pulling its test
# classes into this namespace would make the test loader collect them a
# second time, against file:// instead of svn://.
from tests import SubversionTestCase, test_ra
from tests.integration import (
    allocate_port,
    find_executable,
    missing_dependency,
    stop_process_group,
    wait_until_listening,
)

# Debian and Fedora keep svnserve out of the default $PATH on some releases.
SVNSERVE_DIRS = ["/usr/sbin", "/usr/local/sbin", "/usr/bin", "/usr/local/bin"]


class SvnserveTestCase(SubversionTestCase):
    """Serve repositories over svn:// with a per-test svnserve."""

    USERNAME = "testuser"
    PASSWORD = "testpassword"
    REALM = "subvertpy tests"

    def setUp(self):
        self.svnserve = find_executable("svnserve", SVNSERVE_DIRS)
        if self.svnserve is None:
            missing_dependency("svnserve not available")
        # Set before super(), which already creates a repository and so
        # reaches repository_url() below.
        self.server = None
        self.port = None
        self.root = None
        super().setUp()

    def tearDown(self):
        self.stop_server()
        super().tearDown()

    def simple_prompt(self, realm, username, may_save):
        return (self.USERNAME, self.PASSWORD, False)

    def make_auth(self):
        return Auth(
            [
                ra.get_simple_prompt_provider(self.simple_prompt, 1),
                ra.get_username_provider(),
            ]
        )

    def make_client_auth(self):
        return self.make_auth()

    def stop_server(self):
        # svnserve forks per connection; signalling the process group rather
        # than just the parent stops children being left behind.
        if self.server is None:
            return
        stop_process_group(self.server)
        self.server = None

    def repository_url(self, abspath):
        # svnserve serves everything below a single root, so the first
        # repository decides where the server is anchored. Later
        # repositories in the same test are served from that same root.
        if self.server is None:
            self.root = os.path.dirname(abspath)
            self.port = allocate_port()
            self.server = subprocess.Popen(
                [
                    self.svnserve,
                    "--daemon",
                    "--foreground",
                    "--listen-host",
                    "127.0.0.1",
                    "--listen-port",
                    str(self.port),
                    "--root",
                    self.root,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            wait_until_listening(self.port, self.server)

        self.configure_repository(abspath)
        relpath = os.path.relpath(abspath, self.root)
        return f"svn://127.0.0.1:{self.port}/{relpath}"

    def configure_repository(self, abspath):
        """Require an authenticated user with write access.

        Anonymous access would be simpler, but svnserve records no author
        for anonymous commits and refuses to hand out locks, so a fair
        number of the tests would not be testing what they mean to.
        """
        conf_dir = os.path.join(abspath, "conf")
        with open(os.path.join(conf_dir, "svnserve.conf"), "w") as f:
            f.write(
                "[general]\n"
                "anon-access = none\n"
                "auth-access = write\n"
                "password-db = passwd\n"
                f"realm = {self.REALM}\n"
            )
        with open(os.path.join(conf_dir, "passwd"), "w") as f:
            f.write(f"[users]\n{self.USERNAME} = {self.PASSWORD}\n")


class SvnserveRemoteAccessTests(SvnserveTestCase, test_ra.TestRemoteAccess):
    pass


class SvnserveEditorTests(SvnserveTestCase, test_ra.TestEditorOperations):
    pass


class SvnservePropertiesTests(SvnserveTestCase, test_ra.TestRemoteAccessProperties):
    pass
