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

"""Subversion ra library tests."""

from unittest import TestCase

from subvertpy import (
    wc,
    )

class VersionTest(TestCase):

    def test_version_length(self):
        self.assertEquals(4, len(wc.version()))


class WorkingCopyTests(TestCase):

    def test_get_adm_dir(self):
        self.assertEquals(".svn", wc.get_adm_dir())

    def test_is_normal_prop(self):
        self.assertTrue(wc.is_normal_prop("svn:ignore"))

    def test_is_entry_prop(self):
        self.assertTrue(wc.is_entry_prop("svn:entry:foo"))

    def test_is_wc_prop(self):
        self.assertTrue(wc.is_wc_prop("svn:wc:foo"))

    def test_match_ignore_list(self):
        self.assertTrue(wc.match_ignore_list("foo", [ "f*"]))
        self.assertTrue(wc.match_ignore_list("foo", ["foo"]))
        self.assertFalse(wc.match_ignore_list("foo", []))
        self.assertFalse(wc.match_ignore_list("foo", ["bar"]))
