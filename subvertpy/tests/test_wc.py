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

"""Subversion ra library tests."""

from subvertpy import (
    wc,
    )
from subvertpy.tests import (
    SubversionTestCase,
    TestCase,
    )


class VersionTest(TestCase):

    def test_version_length(self):
        self.assertEqual(4, len(wc.version()))

    def test_api_version_length(self):
        self.assertEqual(4, len(wc.api_version()))

    def test_api_version_later_same(self):
        self.assertTrue(wc.api_version() <= wc.version())


class AdmTests(TestCase):

    def test_get_adm_dir(self):
        self.assertEqual(".svn", wc.get_adm_dir())

    def test_set_adm_dir(self):
        old_dir_name = wc.get_adm_dir()
        try:
            wc.set_adm_dir(b"_svn")
            self.assertEqual("_svn", wc.get_adm_dir())
        finally:
            wc.set_adm_dir(old_dir_name)

    def test_is_normal_prop(self):
        self.assertTrue(wc.is_normal_prop("svn:ignore"))

    def test_is_entry_prop(self):
        self.assertTrue(wc.is_entry_prop("svn:entry:foo"))

    def test_is_wc_prop(self):
        self.assertTrue(wc.is_wc_prop("svn:wc:foo"))

    def test_match_ignore_list(self):
        self.assertTrue(wc.match_ignore_list("foo", ["f*"]))
        self.assertTrue(wc.match_ignore_list("foo", ["foo"]))
        self.assertFalse(wc.match_ignore_list("foo", []))
        self.assertFalse(wc.match_ignore_list("foo", ["bar"]))


class WcTests(SubversionTestCase):

    def test_revision_status(self):
        self.make_client("repos", "checkout")
        ret = wc.revision_status("checkout")
        self.assertEqual((0, 0, 0, 0), ret)

    def test_revision_status_trailing(self):
        self.make_client("repos", "checkout")
        ret = wc.revision_status("checkout/")
        self.assertEqual((0, 0, 0, 0), ret)
