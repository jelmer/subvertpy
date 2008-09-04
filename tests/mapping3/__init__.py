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

from bzrlib.bzrdir import BzrDir
from bzrlib.repository import Repository
from bzrlib.tests import TestCase

from bzrlib.plugins.svn.mapping import SVN_PROP_BZR_REVISION_ID
from bzrlib.plugins.svn.mapping3 import BzrSvnMappingv3FileProps, SVN_PROP_BZR_BRANCHING_SCHEME, set_property_scheme
from bzrlib.plugins.svn.mapping3.scheme import NoBranchingScheme, ListBranchingScheme
from bzrlib.plugins.svn.tests import SubversionTestCase
from bzrlib.plugins.svn.tests.test_mapping import sha1

class Mappingv3FilePropTests(TestCase):
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


class RepositoryTests(SubversionTestCase):

    def setUp(self):
        super(RepositoryTests, self).setUp()
        self.repos_url = self.make_repository("d")
        self._old_mapping = mapping_registry._get_default_key()
        mapping_registry.set_default("v3")

    def tearDown(self):
        super(RepositoryTests, self).tearDown()
        mapping_registry.set_default("v3")

    def test_generate_revision_id_forced_revid(self):
        dc = self.get_commit_editor(self.repos_url)
        dc.change_prop(SVN_PROP_BZR_REVISION_ID+"v3-none", 
                             "2 someid\n")
        dc.close()

        repos = Repository.open(self.repos_url)
        mapping = repos.get_mapping()
        if not mapping.roundtripping:
            raise TestNotApplicable()
        revid = repos.generate_revision_id(1, "", mapping)
        self.assertEquals("someid", revid)

    def test_generate_revision_id_forced_revid_invalid(self):

        dc = self.get_commit_editor(self.repos_url)
        dc.change_prop(SVN_PROP_BZR_REVISION_ID+"v3-none", "corrupt-id\n")
        dc.close()

        repos = Repository.open(self.repos_url)
        mapping = repos.get_mapping()
        if not mapping.roundtripping:
            raise TestNotApplicable()
        revid = repos.generate_revision_id(1, "", mapping)
        self.assertEquals(
                mapping.revision_id_foreign_to_bzr((repos.uuid, 1, "")),
                revid)

    def test_revision_ghost_parents(self):
        dc = self.get_commit_editor(self.repos_url)
        dc.add_file("foo").modify("data")
        dc.close()

        dc = self.get_commit_editor(self.repos_url)
        dc.open_file("foo").modify("data2")
        dc.change_prop("bzr:ancestry:v3-none", "ghostparent\n")
        dc.close()

        repository = Repository.open(self.repos_url)
        mapping = repository.get_mapping()
        self.assertEqual((),
                repository.get_revision(
                    repository.generate_revision_id(0, "", mapping)).parent_ids)
        self.assertEqual((repository.generate_revision_id(0, "", mapping),),
                repository.get_revision(
                    repository.generate_revision_id(1, "", mapping)).parent_ids)
        self.assertEqual((repository.generate_revision_id(1, "", mapping),
            "ghostparent"), 
                repository.get_revision(
                    repository.generate_revision_id(2, "", mapping)).parent_ids)
 
    def test_get_revision_id_overriden(self):
        self.make_checkout(self.repos_url, 'dc')
        repository = Repository.open(self.repos_url)
        self.assertRaises(NoSuchRevision, repository.get_revision, "nonexisting")
        self.build_tree({'dc/foo': "data"})
        self.client_add("dc/foo")
        self.client_commit("dc", "My Message")
        self.build_tree({'dc/foo': "data2"})
        self.client_set_prop("dc", "bzr:revision-id:v3-none", 
                            "3 myrevid\n")
        self.client_update("dc")
        (num, date, author) = self.client_commit("dc", "Second Message")
        repository = Repository.open(self.repos_url)
        mapping = repository.get_mapping()
        if not mapping.roundtripping:
            raise TestNotApplicable
        revid = mapping.revision_id_foreign_to_bzr((repository.uuid, 2, ""))
        rev = repository.get_revision("myrevid")
        self.assertEqual((repository.generate_revision_id(1, "", mapping),),
                rev.parent_ids)
        self.assertEqual(rev.revision_id, 
                         repository.generate_revision_id(2, "", mapping))
        self.assertEqual(author, rev.committer)
        self.assertIsInstance(rev.properties, dict)

    def test_get_ancestry_merged(self):
        self.make_checkout(self.repos_url, 'dc')
        self.build_tree({'dc/foo': "data"})
        self.client_add("dc/foo")
        self.client_commit("dc", "My Message")
        self.client_update("dc")
        self.client_set_prop("dc", "bzr:ancestry:v3-none", "a-parent\n")
        self.build_tree({'dc/foo': "data2"})
        self.client_commit("dc", "Second Message")
        repository = Repository.open(self.repos_url)
        mapping = repository.get_mapping()
        self.assertEqual([None, repository.generate_revision_id(0, "", mapping)],
                repository.get_ancestry(
                    repository.generate_revision_id(0, "", mapping)))
        self.assertEqual([None, repository.generate_revision_id(0, "", mapping),
            repository.generate_revision_id(1, "", mapping)],
                repository.get_ancestry(
                    repository.generate_revision_id(1, "", mapping)))
        self.assertEqual([None, 
            repository.generate_revision_id(0, "", mapping), "a-parent", 
            repository.generate_revision_id(1, "", mapping), 
                  repository.generate_revision_id(2, "", mapping)], 
                repository.get_ancestry(
                    repository.generate_revision_id(2, "", mapping)))

    def test_lookup_revision_id_overridden(self):
        dc = self.get_commit_editor(self.repos_url)
        dc.add_dir("bloe")
        dc.change_prop(SVN_PROP_BZR_REVISION_ID+"v3-none", "2 myid\n")
        dc.close()
        repository = Repository.open(self.repos_url)
        mapping = repository.get_mapping()
        self.assertEqual(("", 1), repository.lookup_revision_id( 
            mapping.revision_id_foreign_to_bzr((repository.uuid, 1, "")))[:2])
        self.assertEqual(("", 1), 
                repository.lookup_revision_id("myid")[:2])

    def test_lookup_revision_id_overridden_invalid(self):
        dc = self.get_commit_editor(self.repos_url)
        dc.add_dir("bloe")
        dc.change_prop(SVN_PROP_BZR_REVISION_ID+"v3-none", "corrupt-entry\n")
        dc.close()

        repository = Repository.open(self.repos_url)
        mapping = repository.get_mapping()
        self.assertEqual(("", 1), repository.lookup_revision_id( 
            mapping.revision_id_foreign_to_bzr((repository.uuid, 1, "")))[:2])
        self.assertRaises(NoSuchRevision, repository.lookup_revision_id, 
            "corrupt-entry")

    def test_lookup_revision_id_overridden_invalid_dup(self):
        self.make_checkout(self.repos_url, 'dc')
        self.build_tree({'dc/bloe': None})
        self.client_add("dc/bloe")
        self.client_set_prop("dc", SVN_PROP_BZR_REVISION_ID+"v3-none", 
                             "corrupt-entry\n")
        self.client_commit("dc", "foobar")
        self.build_tree({'dc/bla': None})
        self.client_add("dc/bla")
        self.client_set_prop("dc", SVN_PROP_BZR_REVISION_ID+"v3-none", 
                "corrupt-entry\n2 corrupt-entry\n")
        self.client_commit("dc", "foobar")
        repository = Repository.open(self.repos_url)
        mapping = repository.get_mapping()
        self.assertEqual(("", 2), repository.lookup_revision_id( 
            mapping.revision_id_foreign_to_bzr((repository.uuid, 2, "")))[:2])
        self.assertEqual(("", 1), repository.lookup_revision_id( 
            mapping.revision_id_foreign_to_bzr((repository.uuid, 1, "")))[:2])
        self.assertEqual(("", 2), repository.lookup_revision_id( 
            "corrupt-entry")[:2])

    def test_lookup_revision_id_overridden_not_found(self):
        """Make sure a revision id that is looked up but doesn't exist 
        doesn't accidently end up in the revid cache."""
        self.make_checkout(self.repos_url, 'dc')
        self.build_tree({'dc/bloe': None})
        self.client_add("dc/bloe")
        self.client_set_prop("dc", SVN_PROP_BZR_REVISION_ID+"v3-none", "2 myid\n")
        self.client_commit("dc", "foobar")
        repository = Repository.open(self.repos_url)
        self.assertRaises(NoSuchRevision, 
                repository.lookup_revision_id, "foobar")

    def test_set_branching_scheme_property(self):
        self.make_checkout(self.repos_url, 'dc')
        self.client_set_prop("dc", SVN_PROP_BZR_BRANCHING_SCHEME, 
            "trunk\nbranches/*\nbranches/tmp/*")
        self.client_commit("dc", "set scheme")
        repository = Repository.open(self.repos_url)
        self.assertEquals(ListBranchingScheme(["trunk", "branches/*", "branches/tmp/*"]).branch_list,
                          repository.get_mapping().scheme.branch_list)

    def test_set_property_scheme(self):
        self.make_checkout(self.repos_url, 'dc')
        repos = Repository.open(repos_url)
        set_property_scheme(repos, ListBranchingScheme(["bla/*"]))
        self.client_update("dc")
        self.assertEquals("bla/*\n", 
                   self.client_get_prop("dc", SVN_PROP_BZR_BRANCHING_SCHEME))
        self.assertEquals("Updating branching scheme for Bazaar.", 
                self.client_log(repos_url, 1, 1)[1][3])

    def test_fetch_fileid_renames(self):
        dc = self.get_commit_editor(self.repos_url)
        dc.add_file("test").modify("data")
        dc.change_prop("bzr:file-ids", "test\tbla\n")
        dc.change_prop("bzr:revision-info", "")
        dc.close()

        oldrepos = Repository.open(self.repos_url)
        dir = BzrDir.create("f", format.get_rich_root_format())
        newrepos = dir.create_repository()
        oldrepos.copy_content_into(newrepos)
        mapping = oldrepos.get_mapping()
        self.assertEqual("bla", newrepos.get_inventory(
            oldrepos.generate_revision_id(1, "", mapping)).path2id("test"))

    def test_fetch_ghosts(self):
        dc = self.get_commit_editor(self.repos_url)
        dc.add_file("bla").modify("data")
        dc.change_prop("bzr:ancestry:v3-none", "aghost\n")
        dc.close()

        oldrepos = Repository.open(self.repos_url)
        dir = BzrDir.create("f", format.get_rich_root_format())
        newrepos = dir.create_repository()
        oldrepos.copy_content_into(newrepos)
        mapping = oldrepos.get_mapping()

        rev = newrepos.get_revision(oldrepos.generate_revision_id(1, "", mapping))
        self.assertTrue("aghost" in rev.parent_ids)

    def test_fetch_invalid_ghosts(self):
        dc = self.get_commit_editor(self.repos_url)
        dc.add_file("bla").modify("data")
        dc.change_prop("bzr:ancestry:v3-none", "a ghost\n")
        dc.close()

        oldrepos = Repository.open(self.repos_url)
        dir = BzrDir.create("f", format.get_rich_root_format())
        newrepos = dir.create_repository()
        oldrepos.copy_content_into(newrepos)
        
        mapping = oldrepos.get_mapping()

        rev = newrepos.get_revision(oldrepos.generate_revision_id(1, "", mapping))
        self.assertEqual([oldrepos.generate_revision_id(0, "", mapping)], rev.parent_ids)

    def test_fetch_complex_ids_dirs(self):
        dc = self.get_commit_editor(self.repos_url)
        dir = dc.add_dir("dir")
        dir.add_dir("dir/adir")
        dc.change_prop("bzr:revision-info", "")
        dc.change_prop("bzr:file-ids", "dir\tbloe\ndir/adir\tbla\n")
        dc.close()

        dc = self.get_commit_editor(self.repos_url)
        dc.add_dir("bdir", "dir/adir")
        dir = dc.open_dir("dir")
        dir.delete("dir/adir")
        dc.change_prop("bzr:revision-info", "properties: \n")
        dc.change_prop("bzr:file-ids", "bdir\tbla\n")
        dc.close()

        oldrepos = Repository.open(self.repos_url)
        dir = BzrDir.create("f", format.get_rich_root_format())
        newrepos = dir.create_repository()
        oldrepos.copy_content_into(newrepos)
        mapping = oldrepos.get_mapping()
        tree = newrepos.revision_tree(oldrepos.generate_revision_id(2, "", mapping))
        self.assertEquals("bloe", tree.path2id("dir"))
        self.assertIs(None, tree.path2id("dir/adir"))
        self.assertEquals("bla", tree.path2id("bdir"))

    def test_fetch_complex_ids_files(self):
        dc = self.get_commit_editor(self.repos_url)
        dir = dc.add_dir("dir")
        dir.add_file("dir/adir").modify("contents")
        dc.change_prop("bzr:revision-info", "")
        dc.change_prop("bzr:file-ids", "dir\tbloe\ndir/adir\tbla\n")
        dc.close()

        dc = self.get_commit_editor(self.repos_url)
        dc.add_file("bdir", "dir/adir")
        dir = dc.open_dir("dir")
        dir.delete("dir/adir")
        dc.change_prop("bzr:revision-info", "properties: \n")
        dc.change_prop("bzr:file-ids", "bdir\tbla\n")
        dc.close()

        oldrepos = Repository.open(self.repos_url)
        dir = BzrDir.create("f", format.get_rich_root_format())
        newrepos = dir.create_repository()
        oldrepos.copy_content_into(newrepos)
        mapping = oldrepos.get_mapping()
        tree = newrepos.revision_tree(oldrepos.generate_revision_id(2, "", mapping))
        self.assertEquals("bloe", tree.path2id("dir"))
        self.assertIs(None, tree.path2id("dir/adir"))
        mutter('entries: %r' % tree.inventory.entries())
        self.assertEquals("bla", tree.path2id("bdir"))


