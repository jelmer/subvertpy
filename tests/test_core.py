# Copyright (C) 2005-2007 Jelmer Vernooij <jelmer@jelmer.uk>

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

"""Subversion core library tests."""

import os
import tempfile
import types

import subvertpy
from tests import TestCase


class TestCore(TestCase):
    def setUp(self):
        super().setUp()

    def test_exc(self):
        self.assertTrue(isinstance(subvertpy.SubversionException("foo", 1), Exception))

    def test_exc_args(self):
        exc = subvertpy.SubversionException("test message", 42)
        self.assertEqual(exc.args, ("test message", 42))

    def test_exc_child(self):
        child = subvertpy.SubversionException("child", 2)
        exc = subvertpy.SubversionException("parent", 1, child=child)
        self.assertEqual(exc.child, child)

    def test_exc_location(self):
        exc = subvertpy.SubversionException("msg", 1, location="file.c:42")
        self.assertEqual(exc.location, "file.c:42")

    def test_exc_child_default_none(self):
        exc = subvertpy.SubversionException("msg", 1)
        self.assertIsNone(exc.child)

    def test_exc_location_default_none(self):
        exc = subvertpy.SubversionException("msg", 1)
        self.assertIsNone(exc.location)


class TestConstants(TestCase):
    def test_node_constants(self):
        self.assertEqual(subvertpy.NODE_NONE, 0)
        self.assertEqual(subvertpy.NODE_FILE, 1)
        self.assertEqual(subvertpy.NODE_DIR, 2)
        self.assertEqual(subvertpy.NODE_UNKNOWN, 3)

    def test_error_constants_are_ints(self):
        self.assertIsInstance(subvertpy.ERR_UNSUPPORTED_FEATURE, int)
        self.assertIsInstance(subvertpy.ERR_RA_SVN_UNKNOWN_CMD, int)
        self.assertIsInstance(subvertpy.ERR_FS_NO_SUCH_REVISION, int)
        self.assertIsInstance(subvertpy.ERR_CANCELLED, int)

    def test_error_constants_values(self):
        self.assertEqual(subvertpy.ERR_UNSUPPORTED_FEATURE, 200007)
        self.assertEqual(subvertpy.ERR_RA_SVN_UNKNOWN_CMD, 210001)
        self.assertEqual(subvertpy.ERR_RA_SVN_CONNECTION_CLOSED, 210002)
        self.assertEqual(subvertpy.ERR_WC_LOCKED, 155004)
        self.assertEqual(subvertpy.ERR_RA_NOT_AUTHORIZED, 170001)
        self.assertEqual(subvertpy.ERR_INCOMPLETE_DATA, 200003)
        self.assertEqual(subvertpy.ERR_FS_NO_SUCH_REVISION, 160006)
        self.assertEqual(subvertpy.ERR_CANCELLED, 200015)

    def test_wc_not_working_copy_aliases(self):
        self.assertEqual(
            subvertpy.ERR_WC_NOT_WORKING_COPY, subvertpy.ERR_WC_NOT_DIRECTORY
        )

    def test_auth_param_constants(self):
        self.assertEqual(subvertpy.AUTH_PARAM_DEFAULT_USERNAME, "svn:auth:username")
        self.assertEqual(subvertpy.AUTH_PARAM_DEFAULT_PASSWORD, "svn:auth:password")

    def test_ssl_constants(self):
        self.assertEqual(subvertpy.SSL_NOTYETVALID, 0x00000001)
        self.assertEqual(subvertpy.SSL_EXPIRED, 0x00000002)
        self.assertEqual(subvertpy.SSL_CNMISMATCH, 0x00000004)
        self.assertEqual(subvertpy.SSL_UNKNOWNCA, 0x00000008)
        self.assertEqual(subvertpy.SSL_OTHER, 0x40000000)

    def test_apr_error_constants(self):
        self.assertEqual(subvertpy.ERR_APR_OS_START_EAIERR, 670000)
        self.assertEqual(subvertpy.ERR_APR_OS_ERRSPACE_SIZE, 50000)
        self.assertEqual(subvertpy.ERR_CATEGORY_SIZE, 5000)


class TestCheckMtime(TestCase):
    def test_check_mtime_c_file_missing(self):
        # When no .c file exists, _check_mtime should return True
        module = types.ModuleType("fake")
        module.__file__ = "/nonexistent/path/fake.so"
        self.assertTrue(subvertpy._check_mtime(module))

    def test_check_mtime_c_file_older(self):
        # When .c file exists but is older than the module, return True
        tmpdir = tempfile.mkdtemp()
        try:
            so_path = os.path.join(tmpdir, "mod.so")
            c_path = os.path.join(tmpdir, "mod.c")
            # Create .c first (older)
            with open(c_path, "w") as f:
                f.write("/* c */")
            # Then .so (newer) - ensure different mtime
            os.utime(c_path, (1000, 1000))
            with open(so_path, "w") as f:
                f.write("so")
            os.utime(so_path, (2000, 2000))
            module = types.ModuleType("mod")
            module.__file__ = so_path
            self.assertTrue(subvertpy._check_mtime(module))
        finally:
            import shutil

            shutil.rmtree(tmpdir)

    def test_check_mtime_c_file_newer(self):
        # When .c file exists and is newer than the module, return False
        tmpdir = tempfile.mkdtemp()
        try:
            so_path = os.path.join(tmpdir, "mod.so")
            c_path = os.path.join(tmpdir, "mod.c")
            # Create .so first (older)
            with open(so_path, "w") as f:
                f.write("so")
            os.utime(so_path, (1000, 1000))
            # Then .c (newer)
            with open(c_path, "w") as f:
                f.write("/* c */")
            os.utime(c_path, (2000, 2000))
            module = types.ModuleType("mod")
            module.__file__ = so_path
            self.assertFalse(subvertpy._check_mtime(module))
        finally:
            import shutil

            shutil.rmtree(tmpdir)

    def test_version(self):
        self.assertIsInstance(subvertpy.__version__, tuple)
        self.assertEqual(len(subvertpy.__version__), 3)
