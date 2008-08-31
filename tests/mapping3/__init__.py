# Copyright (C) 2005-2008 Jelmer Vernooij <jelmer@samba.org>
 
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

import sha

from bzrlib.tests import TestCase

from bzrlib.plugins.svn.mapping3 import BzrSvnMappingv3FileProps
from bzrlib.plugins.svn.mapping3.scheme import NoBranchingScheme
from bzrlib.plugins.svn.tests.test_mapping import MappingTestAdapter

class Mappingv3FilePropTests(MappingTestAdapter, TestCase):
    def setUp(self):
        self.mapping = BzrSvnMappingv3FileProps(NoBranchingScheme())

    def test_generate_revid(self):
        self.assertEqual("svn-v3-undefined:myuuid:branch:5", 
                         BzrSvnMappingv3FileProps._generate_revision_id("myuuid", 5, "branch", "undefined"))

    def test_generate_revid_nested(self):
        self.assertEqual("svn-v3-undefined:myuuid:branch%2Fpath:5", 
                  BzrSvnMappingv3FileProps._generate_revision_id("myuuid", 5, "branch/path", "undefined"))

    def test_generate_revid_special_char(self):
        self.assertEqual("svn-v3-undefined:myuuid:branch%2C:5", 
             BzrSvnMappingv3FileProps._generate_revision_id("myuuid", 5, "branch\x2c", "undefined"))

    def test_generate_revid_nordic(self):
        self.assertEqual("svn-v3-undefined:myuuid:branch%C3%A6:5", 
             BzrSvnMappingv3FileProps._generate_revision_id("myuuid", 5, u"branch\xe6".encode("utf-8"), "undefined"))

    def test_parse_revid_simple(self):
        self.assertEqual(("uuid", "", 4, "undefined"),
                         BzrSvnMappingv3FileProps._parse_revision_id(
                             "svn-v3-undefined:uuid::4"))

    def test_parse_revid_nested(self):
        self.assertEqual(("uuid", "bp/data", 4, "undefined"),
                         BzrSvnMappingv3FileProps._parse_revision_id(
                     "svn-v3-undefined:uuid:bp%2Fdata:4"))

    def test_generate_file_id_root(self):
        self.assertEqual("2@uuid:bp:", self.mapping.generate_file_id("uuid", 2, "bp", u""))

    def test_generate_file_id_path(self):
        self.assertEqual("2@uuid:bp:mypath", 
                self.mapping.generate_file_id("uuid", 2, "bp", u"mypath"))

    def test_generate_file_id_long(self):
        dir = "this/is/a" + ("/very"*40) + "/long/path/"
        self.assertEqual("2@uuid:bp;" + sha1(dir+"filename"), 
                self.mapping.generate_file_id("uuid", 2, "bp", dir+u"filename"))

    def test_generate_file_id_long_nordic(self):
        dir = "this/is/a" + ("/very"*40) + "/long/path/"
        self.assertEqual("2@uuid:bp;" + sha1((dir+u"filename\x2c\x8a").encode('utf-8')), 
                self.mapping.generate_file_id("uuid", 2, "bp", dir+u"filename\x2c\x8a"))

    def test_generate_file_id_special_char(self):
        self.assertEqual("2@uuid:bp:mypath%2C%C2%8A",
                         self.mapping.generate_file_id("uuid", 2, "bp", u"mypath\x2c\x8a"))

    def test_generate_file_id_spaces(self):
        self.assertFalse(" " in self.mapping.generate_file_id("uuid", 1, "b p", u"my path"))

    def test_generate_svn_file_id(self):
        self.assertEqual("2@uuid:bp:path", 
                self.mapping.generate_file_id("uuid", 2, "bp", u"path"))

    def test_generate_svn_file_id_nordic(self):
        self.assertEqual("2@uuid:bp:%C3%A6%C3%B8%C3%A5", 
                self.mapping.generate_file_id("uuid", 2, "bp", u"\xe6\xf8\xe5"))

    def test_generate_svn_file_id_nordic_branch(self):
        self.assertEqual("2@uuid:%C3%A6:%C3%A6%C3%B8%C3%A5", 
                self.mapping.generate_file_id("uuid", 2, u"\xe6".encode('utf-8'), u"\xe6\xf8\xe5"))
