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

from bzrlib.errors import InvalidRevisionId
from bzrlib.revision import Revision
from bzrlib.tests import TestCase, TestNotApplicable

from bzrlib.plugins.svn.mapping import mapping_registry

class RoundtripMappingTests(TestCase):

    def setUp(self):
        super(RoundtripMappingTests, self).setUp()
        self.mapping = mapping_registry.get(self.mapping_name).get_test_instance()

    def test_roundtrip_revision(self):
        revid = self.mapping.revision_id_foreign_to_bzr(("myuuid", "path", 42))
        (uuid, path, revnum), mapping = self.mapping.revision_id_bzr_to_foreign(revid)
        self.assertEquals(uuid, "myuuid")
        self.assertEquals(revnum, 42)
        self.assertEquals(path, "path")
        self.assertEquals(mapping, self.mapping)

    def test_fileid_map(self):
        if not self.mapping.roundtripping:
            raise TestNotApplicable
        fileids = {"": "some-id", "bla/blie": "other-id"}
        revprops = {}
        fileprops = {}
        self.mapping.export_revision("branchp", 432432432.0, 0, "somebody", {}, "arevid", 4, ["merge1"], revprops, fileprops)
        self.mapping.export_fileid_map(fileids, revprops, fileprops)
        revprops["svn:date"] = "2008-11-03T09:33:00.716938Z"
        self.assertEquals(fileids, 
                self.mapping.import_fileid_map(revprops, fileprops))

    def test_text_parents(self):
        if not self.mapping.roundtripping:
            raise TestNotApplicable
        revprops = {}
        fileprops = {}
        text_parents = {"bla": ["bloe"], "ll": ["12", "bli"]}
        self.mapping.export_text_parents(text_parents, revprops, fileprops)
        self.assertEquals(text_parents,
            self.mapping.import_text_parents(revprops, fileprops))

    def test_text_revisions(self):
        if not self.mapping.roundtripping:
            raise TestNotApplicable
        revprops = {}
        fileprops = {}
        text_revisions = {"bla": "bloe", "ll": "12"}
        self.mapping.export_text_revisions(text_revisions, revprops, fileprops)
        self.assertEquals(text_revisions,
            self.mapping.import_text_revisions(revprops, fileprops))

    def test_message(self):
        if not self.mapping.roundtripping:
            raise TestNotApplicable
        revprops = {}
        fileprops = {}
        self.mapping.export_revision("branchp", 432432432.0, 0, "somebody", 
                                     {"arevprop": "val"}, "arevid", 4, ["merge1"], revprops, fileprops)
        revprops["svn:date"] = "2008-11-03T09:33:00.716938Z"
        try:
            self.mapping.export_message("My Commit message", revprops, fileprops)
        except NotImplementedError:
            raise TestNotApplicable
        targetrev = Revision(None)
        self.mapping.import_revision(revprops, fileprops, "someuuid", "somebp", 4, targetrev)
        self.assertEquals("My Commit message", targetrev.message)

    def test_revision(self):
        if not self.mapping.roundtripping:
            raise TestNotApplicable
        revprops = {}
        fileprops = {}
        self.mapping.export_revision("branchp", 432432432.0, 0, "somebody", 
                                     {"arevprop": "val" }, "arevid", 4, ["parent", "merge1"], revprops, fileprops)
        targetrev = Revision(None)
        revprops["svn:date"] = "2008-11-03T09:33:00.716938Z"
        self.mapping.import_revision(revprops, fileprops, "someuuid", "somebp", 4, targetrev)
        self.assertEquals(targetrev.committer, "somebody")
        self.assertEquals(targetrev.properties, {"arevprop": "val"})
        self.assertEquals(targetrev.timestamp, 432432432.0)
        self.assertEquals(targetrev.timezone, 0)

    def test_revision_id(self):
        if not self.mapping.roundtripping:
            raise TestNotApplicable
        revprops = {}
        fileprops = {}
        self.mapping.export_revision("branchp", 432432432.0, 0, "somebody", {}, "arevid", 4, ["parent", "merge1"], revprops, fileprops)
        self.assertEquals((4, "arevid"), self.mapping.get_revision_id("branchp", revprops, fileprops))
    
    def test_revision_id_none(self):
        if not self.mapping.roundtripping:
            raise TestNotApplicable
        self.assertEquals((None, None), self.mapping.get_revision_id("bp", {}, dict()))

    def test_parse_revision_id_unknown(self):
        self.assertRaises(InvalidRevisionId, 
                lambda: self.mapping.revision_id_bzr_to_foreign("bla"))

    def test_parse_revision_id(self):
        self.assertEquals((("myuuid", "bla", 5), self.mapping), 
            self.mapping.revision_id_bzr_to_foreign(
                self.mapping.revision_id_foreign_to_bzr(("myuuid", "bla", 5))))


    def test_import_revision_svnprops(self):
        rev = Revision(None)
        self.mapping.import_revision({"svn:log": "A log msg",
                                      "svn:author": "Somebody",
                                      "svn:date": "2008-11-03T09:33:00.716938Z"}, {}, "someuuid", "trunk", 23, rev)
        self.assertEquals("Somebody", rev.committer)
        self.assertEquals("A log msg", rev.message)
        self.assertEquals({}, rev.properties)
        self.assertEquals(1225704780.716938, rev.timestamp)
        self.assertEquals(0.0, rev.timezone)

