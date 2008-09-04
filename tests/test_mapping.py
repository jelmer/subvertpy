# -*- coding: utf-8 -*-

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

from bzrlib.errors import InvalidRevisionId, NotBranchError
from bzrlib.tests import TestCase, TestNotApplicable
from bzrlib.revision import Revision

from bzrlib.plugins.svn.errors import InvalidPropertyValue
from bzrlib.plugins.svn.mapping import (generate_revision_metadata, parse_revision_metadata, 
                     parse_revid_property, parse_merge_property, parse_text_parents_property,
                     generate_text_parents_property, BzrSvnMappingv1, BzrSvnMappingv2, 
                     parse_revision_id, escape_svn_path, unescape_svn_path)
from bzrlib.plugins.svn.mapping3 import BzrSvnMappingv3FileProps
from bzrlib.plugins.svn.mapping4 import BzrSvnMappingv4


class MetadataMarshallerTests(TestCase):
    def test_generate_revision_metadata_none(self):
        self.assertEquals("", 
                generate_revision_metadata(None, None, None, None))

    def test_generate_revision_metadata_committer(self):
        self.assertEquals("committer: bla\n", 
                generate_revision_metadata(None, None, "bla", None))

    def test_generate_revision_metadata_timestamp(self):
        self.assertEquals("timestamp: 2005-06-30 17:38:52.350850105 +0000\n", 
                generate_revision_metadata(1120153132.350850105, 0, 
                    None, None))
            
    def test_generate_revision_metadata_properties(self):
        self.assertEquals("properties: \n" + 
                "\tpropbla: bloe\n" +
                "\tpropfoo: bla\n",
                generate_revision_metadata(None, None,
                    None, {"propbla": "bloe", "propfoo": "bla"}))

    def test_parse_revision_metadata_empty(self):
        parse_revision_metadata("", None)

    def test_parse_revision_metadata_committer(self):
        rev = Revision('someid')
        parse_revision_metadata("committer: somebody\n", rev)
        self.assertEquals("somebody", rev.committer)

    def test_parse_revision_metadata_timestamp(self):
        rev = Revision('someid')
        parse_revision_metadata("timestamp: 2005-06-30 12:38:52.350850105 -0500\n", rev)
        self.assertEquals(1120153132.3508501, rev.timestamp)
        self.assertEquals(-18000, rev.timezone)

    def test_parse_revision_metadata_timestamp_day(self):
        rev = Revision('someid')
        parse_revision_metadata("timestamp: Thu 2005-06-30 12:38:52.350850105 -0500\n", rev)
        self.assertEquals(1120153132.3508501, rev.timestamp)
        self.assertEquals(-18000, rev.timezone)

    def test_parse_revision_metadata_properties(self):
        rev = Revision('someid')
        parse_revision_metadata("properties: \n" + 
                                "\tfoo: bar\n" + 
                                "\tha: ha\n", rev)
        self.assertEquals({"foo": "bar", "ha": "ha"}, rev.properties)

    def test_parse_revision_metadata_no_colon(self):
        rev = Revision('someid')
        self.assertRaises(InvalidPropertyValue, 
                lambda: parse_revision_metadata("bla", rev))

    def test_parse_revision_metadata_specialchar(self):
        rev = Revision('someid')
        parse_revision_metadata("committer: Adeodato Simó <dato@net.com.org.es>", rev)
        self.assertEquals(u"Adeodato Simó <dato@net.com.org.es>", rev.committer)

    def test_parse_revision_metadata_invalid_name(self):
        rev = Revision('someid')
        self.assertRaises(InvalidPropertyValue, 
                lambda: parse_revision_metadata("bla: b", rev))

    def test_parse_revid_property(self):
        self.assertEquals((1, "bloe"), parse_revid_property("1 bloe"))

    def test_parse_revid_property_space(self):
        self.assertEquals((42, "bloe bla"), parse_revid_property("42 bloe bla"))

    def test_parse_revid_property_invalid(self):
        self.assertRaises(InvalidPropertyValue, 
                lambda: parse_revid_property("blabla"))

    def test_parse_revid_property_empty_revid(self):
        self.assertRaises(InvalidPropertyValue, 
                lambda: parse_revid_property("2 "))

    def test_parse_revid_property_newline(self):
        self.assertRaises(InvalidPropertyValue, 
                lambda: parse_revid_property("foo\nbar"))


class ParseTextParentsTestCase(TestCase):
    def test_text_parents(self):
        self.assertEquals({"bla": "bloe"}, parse_text_parents_property("bla\tbloe\n"))

    def test_text_parents_empty(self):
        self.assertEquals({}, parse_text_parents_property(""))


class GenerateTextParentsTestCase(TestCase):
    def test_generate_empty(self):
        self.assertEquals("", generate_text_parents_property({}))

    def test_generate_simple(self):
        self.assertEquals("bla\tbloe\n", generate_text_parents_property({"bla": "bloe"}))


class ParseMergePropertyTestCase(TestCase):
    def test_parse_merge_space(self):
        self.assertEqual((), parse_merge_property("bla bla"))

    def test_parse_merge_empty(self):
        self.assertEqual((), parse_merge_property(""))

    def test_parse_merge_simple(self):
        self.assertEqual(("bla", "bloe"), parse_merge_property("bla\tbloe"))



def sha1(text):
    return sha.new(text).hexdigest()


class ParseRevisionIdTests(object):

    def test_v4(self):
        self.assertEqual(("uuid", "trunk", 1, BzrSvnMappingv4()), 
                parse_revision_id("svn-v3:uuid:trunk:1"))

    def test_v3(self):
        self.assertEqual(("uuid", "trunk", 1, BzrSvnMappingv3FileProps(TrunkBranchingScheme())), 
                parse_revision_id("svn-v3-trunk0:uuid:trunk:1"))

    def test_v3_undefined(self):
        self.assertEqual(("uuid", "trunk", 1, BzrSvnMappingv3FileProps(TrunkBranchingScheme())), 
                parse_revision_id("svn-v3-undefined:uuid:trunk:1"))

    def test_v2(self):
        self.assertEqual(("uuid", "trunk", 1, BzrSvnMappingv2()), 
                         parse_revision_id("svn-v2:1@uuid-trunk"))

    def test_v1(self):
        self.assertEqual(("uuid", "trunk", 1, BzrSvnMappingv1()), 
                         parse_revision_id("svn-v1:1@uuid-trunk"))

    def test_except(self):
        self.assertRaises(InvalidRevisionId, 
                         parse_revision_id, "svn-v0:1@uuid-trunk")

    def test_except_nonsvn(self):
        self.assertRaises(InvalidRevisionId, 
                         parse_revision_id, "blah")


class EscapeTest(TestCase):
    def test_escape_svn_path_none(self):      
        self.assertEqual("", escape_svn_path(""))

    def test_escape_svn_path_simple(self):
        self.assertEqual("ab", escape_svn_path("ab"))

    def test_escape_svn_path_percent(self):
        self.assertEqual("a%25b", escape_svn_path("a%b"))

    def test_escape_svn_path_whitespace(self):
        self.assertEqual("foobar%20", escape_svn_path("foobar "))

    def test_escape_svn_path_slash(self):
        self.assertEqual("foobar%2F", escape_svn_path("foobar/"))

    def test_escape_svn_path_special_char(self):
        self.assertEqual("foobar%8A", escape_svn_path("foobar\x8a"))

    def test_unescape_svn_path_slash(self):
        self.assertEqual("foobar/", unescape_svn_path("foobar%2F"))

    def test_unescape_svn_path_none(self):
        self.assertEqual("foobar", unescape_svn_path("foobar"))

    def test_unescape_svn_path_percent(self):
        self.assertEqual("foobar%b", unescape_svn_path("foobar%25b"))

    def test_escape_svn_path_nordic(self):
        self.assertEqual("foobar%C3%A6", escape_svn_path(u"foobar\xe6".encode("utf-8")))
