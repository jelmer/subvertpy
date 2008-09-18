# Copyright (C) 2005-2007 Jelmer Vernooij <jelmer@samba.org>
 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from bzrlib.errors import NotBranchError
from bzrlib.tests import TestCase
from bzrlib.plugins.svn.errors import NotSvnBranchPath
from bzrlib.plugins.svn.layout.standard import RootLayout, TrunkLayout


class LayoutTests:

    def test_get_tag_path(self):
        path = self.layout.get_tag_path("foo", "")
        if path is None:
            return
        self.assertIsInstance(path, str)

    def test_tag_path_is_tag(self):
        path = self.layout.get_tag_path("foo", "")
        if path is None:
            return
        self.assertTrue(self.layout.is_tag(path))


class RootLayoutTests(TestCase,LayoutTests):

    def setUp(self):
        self.layout = RootLayout()


class TrunkLayoutTests(TestCase,LayoutTests):

    def setUp(self):
        self.layout = TrunkLayout()

    def test_parse_trunk(self):
        self.assertEquals(("branch", "", "trunk", ""), 
                          self.layout.parse("trunk"))

    def test_parse_tag(self):
        self.assertEquals(("tag", "", "tags/foo", ""), 
                          self.layout.parse("tags/foo"))

    def test_parse_branch(self):
        self.assertEquals(("branch", "", "branches/foo", ""), 
                          self.layout.parse("branches/foo"))

    def test_parse_branch_project(self):
        self.assertEquals(("branch", "bla", "bla/branches/foo", ""), 
                          self.layout.parse("bla/branches/foo"))

    def test_parse_branches(self):
        self.assertRaises(NotSvnBranchPath, self.layout.parse, "branches")
