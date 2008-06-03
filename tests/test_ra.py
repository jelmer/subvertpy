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

"""Subversion ra library tests."""

from bzrlib.tests import TestCase
import ra
from tests import TestCaseWithSubversionRepository

class VersionTest(TestCase):
    def test_version_length(self):
        self.assertEquals(4, len(ra.version()))

class TestRemoteAccess(TestCaseWithSubversionRepository):
    def setUp(self):
        super(TestRemoteAccess, self).setUp()
        self.repos_url = self.make_client("d", "dc")
        self.ra = ra.RemoteAccess(self.repos_url)

    def test_repr(self):
        self.assertEquals("RemoteAccess(%s)" % self.repos_url,
                          repr(self.ra))

    def test_latest_revnum(self):
        self.assertEquals(0, self.ra.get_latest_revnum())

    def test_get_uuid(self):
        self.assertIsInstance(self.ra.get_uuid(), str)

    def test_get_repos_root(self):
        self.assertEqual(self.repos_url, self.ra.get_repos_root())

    def test_reparent(self):
        self.ra.reparent(self.repos_url)
