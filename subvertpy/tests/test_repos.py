# Copyright (C) 2005-2007 Jelmer Vernooij <jelmer@samba.org>
 
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

"""Subversion rpeository library tests."""

import os

from subvertpy import repos, SubversionException
from subvertpy.tests import TestCase, TestCaseInTempDir

class TestClient(TestCaseInTempDir):

    def setUp(self):
        super(TestClient, self).setUp()

    def test_create(self):
        repos.create(os.path.join(self.test_dir, "foo"))

    def test_open(self):
        repos.create(os.path.join(self.test_dir, "foo"))
        repos.Repository("foo")

    def test_uuid(self):
        repos.create(os.path.join(self.test_dir, "foo"))
        self.assertIsInstance(repos.Repository("foo").fs().get_uuid(), str)

    def test_youngest_rev(self):
        repos.create(os.path.join(self.test_dir, "foo"))
        self.assertEquals(0, repos.Repository("foo").fs().youngest_revision())

    def test_rev_root(self):
        repos.create(os.path.join(self.test_dir, "foo"))
        self.assertTrue(repos.Repository("foo").fs().revision_root(0) is not None)

    def test_rev_props(self):
        repos.create(os.path.join(self.test_dir, "foo"))
        self.assertEquals(["svn:date"], repos.Repository("foo").fs().revision_proplist(0).keys())

    def test_rev_root_invalid(self):
        repos.create(os.path.join(self.test_dir, "foo"))
        self.assertRaises(SubversionException, repos.Repository("foo").fs().revision_root, 1)

    def test_paths_changed(self):
        repos.create(os.path.join(self.test_dir, "foo"))
        root = repos.Repository("foo").fs().revision_root(0)
        self.assertEquals({}, root.paths_changed())


class StreamTests(TestCase):

    def test_read(self):
        s = repos.Stream()
        self.assertEquals("", s.read())
        self.assertEquals("", s.read(15))
        s.close()
