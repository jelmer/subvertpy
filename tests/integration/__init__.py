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

"""Integration tests that exercise the ra_svn and ra_serf backends.

The tests in ``tests`` only reach Subversion over ``file://`` (ra_local).
Some bugs only show up in the backends that talk to a server, so the test
cases here re-run those tests against ``svn://`` and ``http://``.

Each backend needs a server that is not part of the build dependencies
(``svnserve`` for svn://, Apache with mod_dav_svn for http://), so the
tests skip when the server is not installed.
"""

import errno
import os
import shutil
import signal
import socket
import subprocess
import time
import unittest


def find_executable(name, extra_dirs=()):
    """Look up an executable by name.

    :param name: Executable to look for
    :param extra_dirs: Directories to search besides $PATH
    :return: Full path, or None if it could not be found
    """
    path = shutil.which(name)
    if path is not None:
        return path
    for directory in extra_dirs:
        candidate = os.path.join(directory, name)
        if os.access(candidate, os.X_OK):
            return candidate
    return None


def allocate_port():
    """Return a port number that was free a moment ago."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_until_listening(port, process, timeout=10.0):
    """Wait for a server to accept connections on a port.

    :param port: Port the server should listen on
    :param process: The server process, checked so a server that dies
        during startup is reported rather than waited out
    :param timeout: How long to wait, in seconds
    :raise AssertionError: If the server did not come up in time
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise AssertionError(
                f"server exited with status {process.returncode} during startup"
            )
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError as e:
            if e.errno not in (errno.ECONNREFUSED, errno.ETIMEDOUT):
                raise
            time.sleep(0.05)
    raise AssertionError(f"server did not listen on port {port} within {timeout}s")


def stop_process_group(process, timeout=10.0):
    """Stop a server and any children it forked.

    Both svnserve and Apache fork worker processes. Signalling only the
    parent leaves those children running and holding the listening socket,
    so the whole process group is signalled instead.

    :param process: Process started with start_new_session=True
    :param timeout: How long to wait for a clean exit before killing
    """
    try:
        pgid = os.getpgid(process.pid)
    except ProcessLookupError:
        process.wait()
        return

    def signal_group(sig):
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            pass

    signal_group(signal.SIGTERM)
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        signal_group(signal.SIGKILL)
        process.wait()
    # The parent is gone; make sure no worker outlived it.
    signal_group(signal.SIGKILL)


def test_suite():
    names = ["svnserve", "serf"]
    module_names = ["tests.integration.test_" + name for name in names]
    loader = unittest.TestLoader()
    result = unittest.TestSuite()
    result.addTests(loader.loadTestsFromNames(module_names))
    return result
