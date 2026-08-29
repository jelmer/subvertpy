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

"""Run the ra tests against http:// (ra_serf).

Serving Subversion over HTTP needs Apache with mod_dav_svn, which is not a
build dependency, so these tests skip unless both are installed.
"""

import base64
import hashlib
import os
import subprocess
import unittest

from subvertpy import ra
from subvertpy.ra import Auth

# test_ra is imported as a module rather than by name: pulling its test
# classes into this namespace would make the test loader collect them a
# second time, against file:// instead of http://.
from tests import SubversionTestCase, test_ra
from tests.integration import (
    allocate_port,
    find_executable,
    missing_dependency,
    stop_process_group,
    wait_until_listening,
)

HTTPD_DIRS = ["/usr/sbin", "/usr/local/sbin", "/usr/local/apache2/bin"]

MODULE_DIRS = [
    "/usr/lib/apache2/modules",
    "/usr/libexec/apache2",
    "/usr/lib64/httpd/modules",
    "/usr/lib/httpd/modules",
]

# Loaded in this order; mod_dav must come before mod_dav_svn.
REQUIRED_MODULES = [
    "mpm_prefork",
    "authn_core",
    "authn_file",
    "authz_core",
    "authz_user",
    "auth_basic",
    "dav",
    "dav_svn",
]


def find_module_dir():
    """Return the directory holding the Apache modules, or None.

    SUBVERTPY_APACHE_MODULES overrides the search for installations that
    keep the modules somewhere unusual.
    """
    override = os.environ.get("SUBVERTPY_APACHE_MODULES")
    directories = [override] if override else MODULE_DIRS
    for directory in directories:
        if os.path.exists(os.path.join(directory, "mod_dav_svn.so")):
            return directory
    return None


class SerfTestCase(SubversionTestCase):
    """Serve repositories over http:// with a per-test Apache."""

    USERNAME = "testuser"
    PASSWORD = "testpassword"
    REALM = "subvertpy tests"

    def setUp(self):
        self.httpd = find_executable("apache2", HTTPD_DIRS) or find_executable(
            "httpd", HTTPD_DIRS
        )
        if self.httpd is None:
            missing_dependency("apache2/httpd not available")
        self.module_dir = find_module_dir()
        if self.module_dir is None:
            missing_dependency("mod_dav_svn not available")
        # Set before super(), which already creates a repository and so
        # reaches repository_url() below.
        self.server = None
        self.port = None
        self.root = None
        super().setUp()

    def tearDown(self):
        self.stop_server()
        super().tearDown()

    def stop_server(self):
        # Apache forks worker children; signalling the process group rather
        # than just the parent stops them being left behind holding the port.
        if self.server is None:
            return
        stop_process_group(self.server)
        self.server = None

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

    def repository_url(self, abspath):
        # mod_dav_svn serves every repository below a single parent, so the
        # first repository decides where the server is anchored.
        if self.server is None:
            self.root = os.path.dirname(abspath)
            self.start_server()
        relpath = os.path.relpath(abspath, self.root)
        return f"http://127.0.0.1:{self.port}/svn/{relpath}"

    def start_server(self):
        self.port = allocate_port()
        server_dir = os.path.join(self.test_dir, "httpd")
        os.makedirs(server_dir, exist_ok=True)

        htpasswd = os.path.join(server_dir, "htpasswd")
        with open(htpasswd, "w") as f:
            f.write(f"{self.USERNAME}:{self.hashed_password()}\n")

        conf = os.path.join(server_dir, "httpd.conf")
        with open(conf, "w") as f:
            f.write(self.httpd_config(server_dir, htpasswd))

        self.server = subprocess.Popen(
            [self.httpd, "-f", conf, "-DFOREGROUND"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        wait_until_listening(self.port, self.server)

    def hashed_password(self):
        """Return the password in htpasswd's {SHA} format.

        Apache rejects plaintext htpasswd entries, and htpasswd(1) is not
        necessarily installed; {SHA} needs nothing but hashlib.
        """
        digest = hashlib.sha1(self.PASSWORD.encode()).digest()
        return "{SHA}" + base64.b64encode(digest).decode()

    def httpd_config(self, server_dir, htpasswd):
        modules = "\n".join(
            f"LoadModule {name}_module {os.path.join(self.module_dir, f'mod_{name}.so')}"
            for name in REQUIRED_MODULES
        )
        return f"""\
ServerName 127.0.0.1
ServerRoot {server_dir}
PidFile {os.path.join(server_dir, "httpd.pid")}
ErrorLog {os.path.join(server_dir, "error.log")}
Listen 127.0.0.1:{self.port}

{modules}

DocumentRoot {server_dir}

<Location /svn>
    DAV svn
    SVNParentPath {self.root}
    SVNListParentPath on
    AuthType Basic
    AuthName "{self.REALM}"
    AuthUserFile {htpasswd}
    Require valid-user
</Location>
"""


# ra_serf passes the delta handler from svn_file_rev_handler_t straight to
# svn_txdelta_parse_svndiff() without checking it for NULL
# (libsvn_ra_serf/blame.c), so a file_rev handler that returns no window
# callback segfaults the process. svn_delta.h documents NULL/NULL as
# allowed, and both ra_local and ra_svn check for it.
SERF_NULL_DELTA_HANDLER_CRASH = (
    "segfaults in ra_serf: NULL delta handler is not checked for"
)


class SerfRemoteAccessTests(SerfTestCase, test_ra.TestRemoteAccess):
    def test_get_file_revs(self):
        raise unittest.SkipTest(SERF_NULL_DELTA_HANDLER_CRASH)

    def test_get_file_revs_include_merged(self):
        raise unittest.SkipTest(SERF_NULL_DELTA_HANDLER_CRASH)


class SerfEditorTests(SerfTestCase, test_ra.TestEditorOperations):
    pass


class SerfPropertiesTests(SerfTestCase, test_ra.TestRemoteAccessProperties):
    pass
