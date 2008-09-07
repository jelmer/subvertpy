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

from bzrlib import urlutils
from bzrlib.branch import Branch
from bzrlib.bzrdir import BzrDir, format_registry
from bzrlib.config import GlobalConfig
from bzrlib.errors import NoSuchRevision, UninitializableFormat
from bzrlib.inventory import Inventory
from bzrlib.osutils import has_symlinks
from bzrlib.repository import Repository
from bzrlib.revision import NULL_REVISION
from bzrlib.tests import TestCase, TestSkipped, TestNotApplicable

from bzrlib.plugins.svn import errors as svn_errors, format, ra
from bzrlib.plugins.svn.layout import TrunkLayout, RootLayout, CustomLayout
from bzrlib.plugins.svn.mapping import mapping_registry
from bzrlib.plugins.svn.tests import SubversionTestCase


class TestSubversionMappingRepositoryWorks(SubversionTestCase):
    """Mapping-dependent tests for Subversion repositories."""

    def setUp(self):
        super(TestSubversionMappingRepositoryWorks, self).setUp()
        self._old_mapping = mapping_registry._get_default_key()
        mapping_registry.set_default(self.mapping_name)

    def tearDown(self):
        super(TestSubversionMappingRepositoryWorks, self).tearDown()
        mapping_registry.set_default(self._old_mapping)

    def test_get_branch_log(self):
        repos_url = self.make_repository("a")
        cb = self.get_commit_editor(repos_url)
        cb.add_file("foo").modify()
        cb.close()

        repos = Repository.open(repos_url)
        repos.set_layout(RootLayout())

        self.assertEqual([
            ('', {'foo': ('A', None, -1)}, 1), 
            ('', {'': ('A', None, -1)}, 0)],
            [(l.branch_path, l.get_paths(), l.revnum) for l in repos._revmeta_provider.iter_reverse_branch_changes("", 1, 0, repos.get_mapping())])

    def test_iter_changes_parent_rename(self):
        repos_url = self.make_repository("a")

        dc = self.get_commit_editor(repos_url)
        foo = dc.add_dir("foo")
        foo.add_dir("foo/bar")
        dc.close()

        dc = self.get_commit_editor(repos_url)
        dc.add_dir("bla", "foo")
        dc.close()

        repos = Repository.open(repos_url)
        try:
            repos.set_layout(CustomLayout(["bla/bar"]))
        except svn_errors.LayoutUnusable:
            raise TestNotApplicable
        ret = list(repos._revmeta_provider.iter_changes('bla/bar', 2, 0, repos.get_mapping()))
        self.assertEquals(1, len(ret))
        if repos.get_mapping().is_branch("foo/bar"):
            self.assertEquals("foo/bar", ret[0][0])
        else:
            self.assertEquals("bla/bar", ret[0][0])

    def test_set_make_working_trees(self):
        repos_url = self.make_repository("a")
        repos = Repository.open(repos_url)
        repos.set_make_working_trees(True)
        self.assertFalse(repos.make_working_trees())

    def test_get_fileid_map(self):
        repos_url = self.make_repository("a")
        repos = Repository.open(repos_url)
        mapping = repos.get_mapping()
        self.assertEqual({u"": (mapping.generate_file_id(repos.uuid, 0, "", u""), mapping.revision_id_foreign_to_bzr((repos.uuid, 0, "")))}, repos.get_fileid_map(0, "", mapping))

    def test_add_revision(self):
        repos_url = self.make_repository("a")
        repos = Repository.open(repos_url)
        self.assertRaises(NotImplementedError, repos.add_revision, "revid", 
                None)

    def test_has_signature_for_revision_id_no(self):
        repos_url = self.make_repository("a")
        repos = Repository.open(repos_url)
        self.assertFalse(repos.has_signature_for_revision_id("foo"))

    def test_set_signature(self):
        repos_url = self.make_client("a", "dc")
        repos = Repository.open(repos_url)
        cb = self.get_commit_editor(repos_url)
        cb.add_file("foo").modify("bar")
        cb.close()
        revid = repos.get_mapping().revision_id_foreign_to_bzr((repos.uuid, 1, ""))
        repos.add_signature_text(revid, "TEXT")
        self.assertTrue(repos.has_signature_for_revision_id(revid))
        self.assertEquals(repos.get_signature_text(revid), "TEXT")

    def test_get_branch_invalid_revision(self):
        repos_url = self.make_repository("a")
        repos = Repository.open(repos_url)
        repos.set_layout(RootLayout())
        self.assertRaises(NoSuchRevision, list, 
               repos._revmeta_provider.iter_reverse_branch_changes("/", 20, 0))

    def test_follow_branch_switched_parents(self):
        repos_url = self.make_client('a', 'dc')
        self.build_tree({'dc/pykleur/trunk/pykleur': None})
        self.client_add("dc/pykleur")
        self.client_commit("dc", "initial")
        self.build_tree({'dc/pykleur/trunk/pykleur/afile': 'contents'})
        self.client_add("dc/pykleur/trunk/pykleur/afile")
        self.client_commit("dc", "add file")
        self.client_copy("dc/pykleur", "dc/pygments", 1)
        self.client_delete('dc/pykleur')
        self.client_update("dc")
        self.client_commit("dc", "commit")
        repos = Repository.open(repos_url)
        repos.set_layout(TrunkLayout(1))
        results = [(l.branch_path, l.get_paths(), l.revnum) for l in repos._revmeta_provider.iter_reverse_branch_changes("pygments/trunk", 3, 0)]

        # Results differ per Subversion version, yay
        # For <= 1.4:
        if ra.version()[1] <= 4:
            self.assertEquals([
            ('pygments/trunk', {'pygments': (u'A', 'pykleur', 1),
                                'pygments/trunk': (u'R', 'pykleur/trunk', 2),
                                'pykleur': (u'D', None, -1)}, 3),
            ('pykleur/trunk', {'pykleur/trunk/pykleur/afile': (u'A', None, -1)}, 2),
            ('pykleur/trunk',
                    {'pykleur': (u'A', None, -1),
                     'pykleur/trunk': (u'A', None, -1),
                     'pykleur/trunk/pykleur': (u'A', None, -1)},
             1)], results
            )
        else:
            self.assertEquals(
               [
                ('pykleur/trunk', {'pykleur': (u'A', None, -1), 
                                   'pykleur/trunk': (u'A', None, -1), 
                                   'pykleur/trunk/pykleur': (u'A', None, -1)}, 
                1)], results
            )

    def test_follow_branch_move_single(self):
        repos_url = self.make_repository('a')

        dc = self.get_commit_editor(repos_url)
        pykleur = dc.add_dir("pykleur")
        pykleur.add_dir("pykleur/bla")
        dc.close()

        dc = self.get_commit_editor(repos_url)
        dc.add_dir("pygments", "pykleur", 1)
        dc.close()

        repos = Repository.open(repos_url)
        try:
            repos.set_layout(CustomLayout(["pygments"]))
        except svn_errors.LayoutUnusable:
            raise TestNotApplicable
        changes = repos._revmeta_provider.iter_reverse_branch_changes("pygments", 2, 0, mapping=repos.get_mapping())
        if repos.get_mapping().is_branch("pykleur"):
            self.assertEquals([('pygments',
                  {'pygments': ('A', 'pykleur', 1)},
                    2),
                    ('pykleur', {'pykleur': ('A', None, -1), 'pykleur/bla': ('A', None, -1)}, 1)],
                    [(l.branch_path, l.get_paths(), l.revnum) for l in changes])
        else:
            self.assertEquals([('pygments',
              {'pygments/bla': ('A', None, -1), 'pygments': ('A', None, -1)},
                2)],
                [(l.branch_path, l.get_paths(), l.revnum) for l in changes])

    def test_history_all(self):
        repos_url = self.make_repository("a")

        dc = self.get_commit_editor(repos_url)
        trunk = dc.add_dir("trunk")
        trunk.add_file("trunk/file").modify("data")
        foo = dc.add_dir("foo")
        foo.add_file("foo/file").modify("data")
        dc.close()

        repos = Repository.open(repos_url)

        self.assertEqual(1, 
                   len(set(repos.all_revision_ids(TrunkLayout()))))

    def test_all_revs_empty(self):
        repos_url = self.make_repository("a")
        repos = Repository.open(repos_url)
        repos.set_layout(TrunkLayout(0))
        self.assertEqual(set([]), set(repos.all_revision_ids()))

    def test_all_revs(self):
        repos_url = self.make_repository("a")

        dc = self.get_commit_editor(repos_url)
        trunk = dc.add_dir("trunk")
        trunk.add_file("trunk/file").modify("data")
        foo = dc.add_dir("foo")
        foo.add_file("foo/file").modify("data")
        dc.close()

        dc = self.get_commit_editor(repos_url)
        branches = dc.add_dir("branches")
        somebranch = branches.add_dir("branches/somebranch")
        somebranch.add_file("branches/somebranch/somefile").modify("data")
        dc.close()

        dc = self.get_commit_editor(repos_url)
        branches = dc.open_dir("branches")
        branches.delete("branches/somebranch")
        dc.close()

        repos = Repository.open(repos_url)
        repos.set_layout(TrunkLayout(0))
        mapping = repos.get_mapping()
        self.assertEqual(set([
            repos.generate_revision_id(1, "trunk", mapping), 
            repos.generate_revision_id(2, "branches/somebranch", mapping)]),
            set(repos.all_revision_ids()))

    def test_follow_history_empty(self):
        repos_url = self.make_repository("a")
        repos = Repository.open(repos_url)
        repos.set_layout(RootLayout())
        self.assertEqual(set([repos.generate_revision_id(0, '', repos.get_mapping())]), 
              set(repos.all_revision_ids(repos.get_layout())))

    def test_follow_history_empty_branch(self):
        repos_url = self.make_repository("a")

        dc = self.get_commit_editor(repos_url)
        trunk = dc.add_dir("trunk")
        trunk.add_file("trunk/afile").modify("data")
        dc.add_dir("branches")
        dc.close()

        repos = Repository.open(repos_url)
        repos.set_layout(TrunkLayout(0))
        self.assertEqual(set([repos.generate_revision_id(1, 'trunk', repos.get_mapping())]), 
                set(repos.all_revision_ids(repos.get_layout())))

    def test_follow_history_follow(self):
        repos_url = self.make_repository("a")

        dc = self.get_commit_editor(repos_url)
        trunk = dc.add_dir("trunk")
        trunk.add_file("trunk/afile").modify("data")
        dc.add_dir("branches")
        dc.close()

        dc = self.get_commit_editor(repos_url)
        branches = dc.open_dir("branches")
        branches.add_dir("branches/abranch", "trunk", 1)
        dc.close()

        repos = Repository.open(repos_url)
        repos.set_layout(TrunkLayout(0))

        items = set(repos.all_revision_ids(repos.get_layout()))
        self.assertEqual(set([repos.generate_revision_id(1, 'trunk', repos.get_mapping()),
                          repos.generate_revision_id(2, 'branches/abranch', repos.get_mapping())
                          ]), items)

    def test_branch_log_specific(self):
        repos_url = self.make_client("a", "dc")
        self.build_tree({
            'dc/branches': None,
            'dc/branches/brancha': None,
            'dc/branches/branchab': None,
            'dc/branches/brancha/data': "data", 
            "dc/branches/branchab/data":"data"})
        self.client_add("dc/branches")
        self.client_commit("dc", "My Message")

        repos = Repository.open(repos_url)
        repos.set_layout(TrunkLayout(0))

        self.assertEqual(1, len(list(repos._revmeta_provider.iter_reverse_branch_changes("branches/brancha",
            1, 0))))

    def test_branch_log_specific_ignore(self):
        repos_url = self.make_client("a", "dc")
        self.build_tree({'dc/branches': None})
        self.client_add("dc/branches")
        self.build_tree({
            'dc/branches/brancha': None,
            'dc/branches/branchab': None,
            'dc/branches/brancha/data': "data", 
            "dc/branches/branchab/data":"data"})
        self.client_add("dc/branches/brancha")
        self.client_commit("dc", "My Message")

        self.client_add("dc/branches/branchab")
        self.client_commit("dc", "My Message2")

        repos = Repository.open(repos_url)
        repos.set_layout(TrunkLayout(0))

        self.assertEqual(1, len(list(repos._revmeta_provider.iter_reverse_branch_changes("branches/brancha",
            2, 0))))

    def test_find_branches(self):
        repos_url = self.make_client("a", "dc")
        self.build_tree({
            'dc/branches/brancha': None,
            'dc/branches/branchab': None,
            'dc/branches/brancha/data': "data", 
            "dc/branches/branchab/data":"data"})
        self.client_add("dc/branches")
        self.client_commit("dc", "My Message")
        repos = Repository.open(repos_url)
        repos.set_layout(TrunkLayout(0))
        branches = repos.find_branches()
        self.assertEquals(2, len(branches))
        self.assertEquals(urlutils.join(repos.base, "branches/brancha"), 
                          branches[1].base)
        self.assertEquals(urlutils.join(repos.base, "branches/branchab"), 
                          branches[0].base)

    def test_find_tags(self):
        repos_url = self.make_repository('a')

        dc = self.get_commit_editor(repos_url)
        tags = dc.add_dir("tags")
        tags.add_dir("tags/brancha").add_file("tags/brancha/data").modify()
        tags.add_dir("tags/branchab").add_file("tags/branchab/data").modify()
        dc.close()

        repos = Repository.open(repos_url)
        repos.set_layout(TrunkLayout(0))
        tags = repos.find_tags("")
        self.assertEquals({"brancha": repos.generate_revision_id(1, "tags/brancha", repos.get_mapping()),
                           "branchab": repos.generate_revision_id(1, "tags/branchab", repos.get_mapping())}, tags)

    def test_find_tags_unmodified(self):
        repos_url = self.make_repository('a')

        dc = self.get_commit_editor(repos_url)
        dc.add_dir("trunk").add_file("trunk/data").modify()
        dc.close()

        dc = self.get_commit_editor(repos_url)
        tags = dc.add_dir("tags")
        tags.add_dir("tags/brancha", "trunk")
        dc.close()

        repos = Repository.open(repos_url)
        repos.set_layout(TrunkLayout(0))
        tags = repos.find_tags("")
        self.assertEquals({"brancha": repos.generate_revision_id(1, "trunk", repos.get_mapping())}, tags)

    def test_find_tags_modified(self):
        repos_url = self.make_repository('a')

        dc = self.get_commit_editor(repos_url)
        dc.add_dir("trunk").add_file("trunk/data").modify()
        dc.close()

        dc = self.get_commit_editor(repos_url)
        tags = dc.add_dir("tags")
        tags.add_dir("tags/brancha", "trunk")
        dc.close()

        dc = self.get_commit_editor(repos_url)
        tags = dc.open_dir("tags")
        brancha = tags.open_dir("tags/brancha")
        brancha.add_file("tags/brancha/release-notes").modify()
        dc.close()

        repos = Repository.open(repos_url)
        repos.set_layout(TrunkLayout(0))
        tags = repos.find_tags("")
        self.assertEquals({"brancha": repos.generate_revision_id(3, "tags/brancha", repos.get_mapping())}, tags)

    def test_find_branchpaths_moved(self):
        repos_url = self.make_client("a", "dc")
        self.build_tree({
            'dc/tmp/branches/brancha': None,
            'dc/tmp/branches/branchab': None,
            'dc/tmp/branches/brancha/data': "data", 
            "dc/tmp/branches/branchab/data":"data"})
        self.client_add("dc/tmp")
        self.client_commit("dc", "My Message")
        self.client_copy("dc/tmp/branches", "dc/tags")
        self.client_commit("dc", "My Message 2")

        repos = Repository.open(repos_url)
        repos.set_layout(TrunkLayout(0))

        self.assertEqual([("tags/branchab", 2, True), 
                          ("tags/brancha", 2, True)], 
                list(repos.find_branchpaths(TrunkLayout(0), to_revnum=2)))

    def test_find_branchpaths_start_revno(self):
        repos_url = self.make_repository("a")

        dc = self.get_commit_editor(repos_url)
        branches = dc.add_dir("branches")
        branches.add_dir("branches/brancha")
        dc.close()

        dc = self.get_commit_editor(repos_url)
        branches = dc.open_dir("branches")
        branches.add_dir("branches/branchb")
        dc.close()

        repos = Repository.open(repos_url)
        repos.set_layout(TrunkLayout(0))

        self.assertEqual([("branches/branchb", 2, True)],
                list(repos.find_branchpaths(TrunkLayout(0), from_revnum=2, to_revnum=2)))

    def test_find_branchpaths_file_moved_from_nobranch(self):
        repos_url = self.make_client("a", "dc")
        self.build_tree({
            'dc/tmp/trunk': None,
            'dc/bla/somefile': "contents"})
        self.client_add("dc/tmp")
        self.client_add("dc/bla")
        self.client_commit("dc", "My Message")
        self.client_copy("dc/bla", "dc/tmp/branches")
        self.client_delete("dc/tmp/branches/somefile")
        self.client_commit("dc", "My Message 2")

        Repository.open(repos_url).find_branchpaths(TrunkLayout(2))

    def test_find_branchpaths_deleted_from_nobranch(self):
        repos_url = self.make_client("a", "dc")
        self.build_tree({
            'dc/tmp/trunk': None,
            'dc/bla/somefile': "contents"})
        self.client_add("dc/tmp")
        self.client_add("dc/bla")
        self.client_commit("dc", "My Message")
        self.client_copy("dc/bla", "dc/tmp/branches")
        self.client_delete("dc/tmp/branches/somefile")
        self.client_commit("dc", "My Message 2")

        Repository.open(repos_url).find_branchpaths(TrunkLayout(1))

    def test_find_branchpaths_moved_nobranch(self):
        repos_url = self.make_client("a", "dc")
        self.build_tree({
            'dc/tmp/nested/foobar': None,
            'dc/tmp/nested/branches/brancha': None,
            'dc/tmp/nested/branches/branchab': None,
            'dc/tmp/nested/branches/brancha/data': "data", 
            "dc/tmp/nested/branches/branchab/data":"data"})
        self.client_add("dc/tmp")
        self.client_commit("dc", "My Message")
        self.client_copy("dc/tmp/nested", "dc/t2")
        self.client_commit("dc", "My Message 2")

        repos = Repository.open(repos_url)
        repos.set_layout(TrunkLayout(1))

        self.assertEqual([("t2/branches/brancha", 2, True), 
                          ("t2/branches/branchab", 2, True)], 
                list(repos.find_branchpaths(TrunkLayout(1), to_revnum=2)))

    def test_find_branchpaths_root(self):
        repos_url = self.make_repository("a")

        repos = Repository.open(repos_url)
        repos.set_layout(RootLayout())

        self.assertEqual([("", 0, True)], 
                list(repos.find_branchpaths(RootLayout(), to_revnum=0)))

    def test_find_branchpaths_no_later(self):
        repos_url = self.make_repository("a")

        repos = Repository.open(repos_url)
        repos.set_layout(RootLayout())

        self.assertEqual([("", 0, True)], 
                list(repos.find_branchpaths(RootLayout(), to_revnum=0)))

    def test_find_branchpaths_trunk_empty(self):
        repos_url = self.make_repository("a")

        repos = Repository.open(repos_url)
        repos.set_layout(TrunkLayout(0))

        self.assertEqual([], 
                list(repos.find_branchpaths(TrunkLayout(0), to_revnum=0)))

    def test_find_branchpaths_trunk_one(self):
        repos_url = self.make_repository("a")

        repos = Repository.open(repos_url)
        repos.set_layout(TrunkLayout(0))

        dc = self.get_commit_editor(repos_url)
        trunk = dc.add_dir("trunk")
        trunk.add_file("trunk/foo").modify("data")
        dc.close()

        self.assertEqual([("trunk", 1, True)], 
                list(repos.find_branchpaths(TrunkLayout(0), to_revnum=1)))

    def test_find_branchpaths_removed(self):
        repos_url = self.make_repository("a")

        repos = Repository.open(repos_url)
        repos.set_layout(TrunkLayout(0))

        dc = self.get_commit_editor(repos_url)
        trunk = dc.add_dir("trunk")
        trunk.add_file("trunk/foo").modify("data")
        dc.close()

        dc = self.get_commit_editor(repos_url)
        dc.delete("trunk")
        dc.close()

        self.assertEqual([("trunk", 1, True)], 
                list(repos.find_branchpaths(TrunkLayout(0), to_revnum=1)))
        self.assertEqual([("trunk", 1, False)], 
                list(repos.find_branchpaths(TrunkLayout(0), to_revnum=2)))

    def test_has_revision(self):
        bzrdir = self.make_client_and_bzrdir('d', 'dc')
        repository = bzrdir.find_repository()
        self.build_tree({'dc/foo': "data"})
        self.client_add("dc/foo")
        self.client_commit("dc", "My Message")
        self.assertTrue(repository.has_revision(
            repository.generate_revision_id(1, "", repository.get_mapping())))
        self.assertFalse(repository.has_revision("some-other-revision"))

    def test_has_revision_none(self):
        bzrdir = self.make_client_and_bzrdir('d', 'dc')
        repository = bzrdir.find_repository()
        self.assertTrue(repository.has_revision(None))

    def test_has_revision_future(self):
        bzrdir = self.make_client_and_bzrdir('d', 'dc')
        repository = bzrdir.find_repository()
        self.assertFalse(repository.has_revision(
            repository.get_mapping().revision_id_foreign_to_bzr((repository.uuid, 5, ""))))

    def test_get_parent_map(self):
        repos_url = self.make_client('d', 'dc')
        self.build_tree({'dc/foo': "data"})
        self.client_add("dc/foo")
        self.client_commit("dc", "My Message")
        self.build_tree({'dc/foo': "data2"})
        self.client_commit("dc", "Second Message")
        repository = Repository.open(repos_url)
        mapping = repository.get_mapping()
        revid = repository.generate_revision_id(0, "", mapping)
        self.assertEqual({revid: (NULL_REVISION,)}, repository.get_parent_map([revid]))
        revid = repository.generate_revision_id(1, "", mapping)
        self.assertEqual({revid: (repository.generate_revision_id(0, "", mapping),)}, repository.get_parent_map([revid]))
        revid = repository.generate_revision_id(2, "", mapping)
        self.assertEqual({revid: (repository.generate_revision_id(1, "", mapping),)},
            repository.get_parent_map([revid]))
        self.assertEqual({}, repository.get_parent_map(["notexisting"]))

    def test_get_revision_delta(self):
        repos_url = self.make_repository('d')

        dc = self.get_commit_editor(repos_url)
        dc.add_file("foo").modify("data")
        dc.close()

        dc = self.get_commit_editor(repos_url)
        dc.open_file("foo").modify("data2")
        dc.close()

        r = Repository.open(repos_url)
        r.set_layout(RootLayout())
        d1 = r.get_revision_delta(r.get_revision(r.generate_revision_id(1, "", r.get_mapping())))
        self.assertEquals(None, d1.unchanged)
        self.assertEquals(1, len(d1.added))
        self.assertEquals("foo", d1.added[0][0])
        self.assertEquals(0, len(d1.modified))
        self.assertEquals(0, len(d1.removed))

        d2 = r.get_revision_delta(r.get_revision(r.generate_revision_id(2, "", r.get_mapping())))
        self.assertEquals(None, d2.unchanged)
        self.assertEquals(0, len(d2.added))
        self.assertEquals("foo", d2.modified[0][0])
        self.assertEquals(0, len(d2.removed))

    def test_revision_svk_parent(self):
        repos_url = self.make_client('d', 'dc')
        self.build_tree({'dc/trunk/foo': "data", 'dc/branches/foo': None})
        self.client_add("dc/trunk")
        self.client_add("dc/branches")
        self.client_commit("dc", "My Message")
        self.client_update("dc")
        self.build_tree({'dc/trunk/foo': "data2"})
        repository = Repository.open(repos_url)
        repository.set_layout(TrunkLayout(0))
        self.client_set_prop("dc/trunk", "svk:merge", 
            "%s:/branches/foo:1\n" % repository.uuid)
        self.client_commit("dc", "Second Message")
        mapping = repository.get_mapping()
        self.assertEqual((repository.generate_revision_id(1, "trunk", mapping),
            repository.generate_revision_id(1, "branches/foo", mapping)), 
                repository.get_revision(
                    repository.generate_revision_id(2, "trunk", mapping)).parent_ids)
    
    def test_get_revision(self):
        repos_url = self.make_client('d', 'dc')
        repository = Repository.open(repos_url)
        self.assertRaises(NoSuchRevision, repository.get_revision, 
                "nonexisting")
        self.build_tree({'dc/foo': "data"})
        self.client_add("dc/foo")
        self.client_commit("dc", "My Message")
        self.client_update("dc")
        self.build_tree({'dc/foo': "data2"})
        (num, date, author) = self.client_commit("dc", "Second Message")
        repository = Repository.open(repos_url)
        mapping = repository.get_mapping()
        rev = repository.get_revision(
            repository.generate_revision_id(2, "", mapping))
        self.assertEqual((repository.generate_revision_id(1, "", mapping),),
                rev.parent_ids)
        self.assertEqual(rev.revision_id, 
                repository.generate_revision_id(2, "", mapping))
        self.assertEqual(author, rev.committer)
        self.assertIsInstance(rev.properties, dict)

    def test_get_revision_zero(self):
        repos_url = self.make_client('d', 'dc')
        repository = Repository.open(repos_url)
        mapping = repository.get_mapping()
        rev = repository.get_revision(
            repository.generate_revision_id(0, "", mapping))
        self.assertEqual(repository.generate_revision_id(0, "", mapping), 
                         rev.revision_id)
        self.assertEqual("", rev.committer)
        self.assertEqual({}, rev.properties)
        self.assertEqual(0, rev.timezone)

    def test_get_ancestry(self):
        repos_url = self.make_client('d', 'dc')
        repository = Repository.open(repos_url)
        self.assertRaises(NoSuchRevision, repository.get_revision, "nonexisting")
        self.build_tree({'dc/foo': "data"})
        self.client_add("dc/foo")
        self.client_commit("dc", "My Message")
        self.client_update("dc")
        self.build_tree({'dc/foo': "data2"})
        self.client_commit("dc", "Second Message")
        self.client_update("dc")
        self.build_tree({'dc/foo': "data3"})
        self.client_commit("dc", "Third Message")
        self.client_update("dc")
        repository = Repository.open(repos_url)
        mapping = repository.get_mapping()
        self.assertEqual([None, 
            repository.generate_revision_id(0, "", mapping),
            repository.generate_revision_id(1, "", mapping),
            repository.generate_revision_id(2, "", mapping),
            repository.generate_revision_id(3, "", mapping)],
                repository.get_ancestry(
                    repository.generate_revision_id(3, "", mapping)))
        self.assertEqual([None, 
            repository.generate_revision_id(0, "", mapping),
            repository.generate_revision_id(1, "", mapping),
            repository.generate_revision_id(2, "", mapping)],
                repository.get_ancestry(
                    repository.generate_revision_id(2, "", mapping)))
        self.assertEqual([None,
                    repository.generate_revision_id(0, "", mapping),
                    repository.generate_revision_id(1, "", mapping)],
                repository.get_ancestry(
                    repository.generate_revision_id(1, "", mapping)))
        self.assertEqual([None, repository.generate_revision_id(0, "", mapping)],
                repository.get_ancestry(
                    repository.generate_revision_id(0, "", mapping)))
        self.assertEqual([None], repository.get_ancestry(NULL_REVISION))

    def test_get_ancestry2(self):
        repos_url = self.make_client('d', 'dc')
        self.build_tree({'dc/foo': "data"})
        self.client_add("dc/foo")
        self.client_commit("dc", "My Message")
        self.build_tree({'dc/foo': "data2"})
        self.client_commit("dc", "Second Message")
        repository = Repository.open(repos_url)
        mapping = repository.get_mapping()
        self.assertEqual([None, repository.generate_revision_id(0, "", mapping)],
                repository.get_ancestry(
                    repository.generate_revision_id(0, "", mapping)))
        self.assertEqual([None, repository.generate_revision_id(0, "", mapping),
            repository.generate_revision_id(1, "", mapping)],
                repository.get_ancestry(
                    repository.generate_revision_id(1, "", mapping)))
        self.assertEqual([None, 
            repository.generate_revision_id(0, "", mapping),
            repository.generate_revision_id(1, "", mapping),
            repository.generate_revision_id(2, "", mapping)], 
                repository.get_ancestry(
                    repository.generate_revision_id(2, "", mapping)))

    def test_get_inventory(self):
        repos_url = self.make_client('d', 'dc')
        repository = Repository.open(repos_url)
        self.assertRaises(NoSuchRevision, repository.get_inventory, 
                "nonexisting")
        self.build_tree({'dc/foo': "data", 'dc/blah': "other data"})
        self.client_add("dc/foo")
        self.client_add("dc/blah")
        self.client_commit("dc", "My Message") #1
        self.client_update("dc")
        self.build_tree({'dc/foo': "data2", "dc/bar/foo": "data3"})
        self.client_add("dc/bar")
        self.client_commit("dc", "Second Message") #2
        self.client_update("dc")
        self.build_tree({'dc/foo': "data3"})
        self.client_commit("dc", "Third Message") #3
        self.client_update("dc")
        repository = Repository.open(repos_url)
        repository.set_layout(RootLayout())
        mapping = repository.get_mapping()
        inv = repository.get_inventory(
                repository.generate_revision_id(1, "", mapping))
        self.assertIsInstance(inv, Inventory)
        self.assertIsInstance(inv.path2id("foo"), basestring)
        inv = repository.get_inventory(
            repository.generate_revision_id(2, "", mapping))
        self.assertEqual(repository.generate_revision_id(2, "", mapping), 
                         inv[inv.path2id("foo")].revision)
        self.assertEqual(repository.generate_revision_id(1, "", mapping), 
                         inv[inv.path2id("blah")].revision)
        self.assertIsInstance(inv, Inventory)
        self.assertIsInstance(inv.path2id("foo"), basestring)
        self.assertIsInstance(inv.path2id("bar"), basestring)
        self.assertIsInstance(inv.path2id("bar/foo"), basestring)

    def test_generate_revision_id(self):
        repos_url = self.make_client('d', 'dc')
        self.build_tree({'dc/bla/bloe': None})
        self.client_add("dc/bla")
        self.client_commit("dc", "bla")
        repository = Repository.open(repos_url)
        mapping = repository.get_mapping()
        self.assertEqual(
               mapping.revision_id_foreign_to_bzr((repository.uuid, 1, "bla/bloe")), 
            repository.generate_revision_id(1, "bla/bloe", mapping))

    def test_generate_revision_id_zero(self):
        repos_url = self.make_client('d', 'dc')
        repository = Repository.open(repos_url)
        mapping = repository.get_mapping()
        self.assertEqual(mapping.revision_id_foreign_to_bzr((repository.uuid, 0, "")), 
                repository.generate_revision_id(0, "", mapping))

    def test_lookup_revision_id(self):
        repos_url = self.make_client('d', 'dc')
        self.build_tree({'dc/bloe': None})
        self.client_add("dc/bloe")
        self.client_commit("dc", "foobar")
        repository = Repository.open(repos_url)
        self.assertRaises(NoSuchRevision, repository.lookup_revision_id, 
            "nonexisting")
        mapping = repository.get_mapping()
        self.assertEqual(("bloe", 1), 
            repository.lookup_revision_id(
                repository.generate_revision_id(1, "bloe", mapping))[:2])

    def test_lookup_revision_id_invalid_uuid(self):
        repos_url = self.make_client('d', 'dc')
        repository = Repository.open(repos_url)
        mapping = repository.get_mapping()
        self.assertRaises(NoSuchRevision, 
            repository.lookup_revision_id, 
                mapping.revision_id_foreign_to_bzr(("invaliduuid", 0, "")))
        
    def test_check(self):
        repos_url = self.make_client('d', 'dc')
        self.build_tree({'dc/foo': "data"})
        self.client_add("dc/foo")
        self.client_commit("dc", "My Message")
        repository = Repository.open(repos_url)
        mapping = repository.get_mapping()
        repository.check([
            repository.generate_revision_id(0, "", mapping), 
            repository.generate_revision_id(1, "", mapping)])

    def test_copy_contents_into(self):
        repos_url = self.make_client('d', 'dc')
        self.build_tree({'dc/foo/bla': "data"})
        self.client_add("dc/foo")
        self.client_commit("dc", "My Message")
        self.build_tree({'dc/foo/blo': "data2", "dc/bar/foo": "data3", 'dc/foo/bla': "data"})
        self.client_add("dc/foo/blo")
        self.client_add("dc/bar")
        self.client_commit("dc", "Second Message")
        repository = Repository.open(repos_url)
        repository.set_layout(RootLayout())
        mapping = repository.get_mapping()

        to_bzrdir = BzrDir.create("e", format.get_rich_root_format())
        to_repos = to_bzrdir.create_repository()

        repository.copy_content_into(to_repos, 
                repository.generate_revision_id(2, "", mapping))

        self.assertTrue(repository.has_revision(
            repository.generate_revision_id(2, "", mapping)))
        self.assertTrue(repository.has_revision(
            repository.generate_revision_id(1, "", mapping)))

    def test_fetch_property_change_only_trunk(self):
        repos_url = self.make_client('d', 'dc')
        self.build_tree({'dc/trunk/bla': "data"})
        self.client_add("dc/trunk")
        self.client_commit("dc", "My Message")
        self.client_set_prop("dc/trunk", "some:property", "some data\n")
        self.client_commit("dc", "My 3")
        self.client_set_prop("dc/trunk", "some2:property", "some data\n")
        self.client_commit("dc", "My 2")
        self.client_set_prop("dc/trunk", "some:property", "some other data\n")
        self.client_commit("dc", "My 4")
        oldrepos = Repository.open(repos_url)
        oldrepos.set_layout(TrunkLayout(0))
        self.assertEquals([('trunk', {'trunk': (u'M', None, -1)}, 3), 
                           ('trunk', {'trunk': (u'M', None, -1)}, 2), 
                           ('trunk', {'trunk/bla': (u'A', None, -1), 'trunk': (u'A', None, -1)}, 1)], 
                   [(l.branch_path, l.get_paths(), l.revnum) for l in oldrepos._revmeta_provider.iter_reverse_branch_changes("trunk", 3, 0)])

    def test_control_code_msg(self):
        if ra.version()[1] >= 5:
            raise TestSkipped("Test not runnable with Subversion >= 1.5")
        repos_url = self.make_client('d', 'dc')

        self.build_tree({'dc/trunk': None})
        self.client_add("dc/trunk")
        self.client_commit("dc", "\x24")

        self.build_tree({'dc/trunk/hosts': 'hej2'})
        self.client_add("dc/trunk/hosts")
        self.client_commit("dc", "bla\xfcbla") #2

        self.build_tree({'dc/trunk/hosts': 'hej3'})
        self.client_commit("dc", "a\x0cb") #3

        self.build_tree({'dc/branches/foobranch/file': 'foohosts'})
        self.client_add("dc/branches")
        self.client_commit("dc", "foohosts") #4

        oldrepos = Repository.open(repos_url)
        oldrepos.set_layout(TrunkLayout(0))
        dir = BzrDir.create("f",format=format.get_rich_root_format())
        newrepos = dir.create_repository()
        oldrepos.copy_content_into(newrepos)

        mapping = oldrepos.get_mapping()

        self.assertTrue(newrepos.has_revision(
            oldrepos.generate_revision_id(1, "trunk", mapping)))
        self.assertTrue(newrepos.has_revision(
            oldrepos.generate_revision_id(2, "trunk", mapping)))
        self.assertTrue(newrepos.has_revision(
            oldrepos.generate_revision_id(3, "trunk", mapping)))
        self.assertTrue(newrepos.has_revision(
            oldrepos.generate_revision_id(4, "branches/foobranch", mapping)))
        self.assertFalse(newrepos.has_revision(
            oldrepos.generate_revision_id(4, "trunk", mapping)))
        self.assertFalse(newrepos.has_revision(
            oldrepos.generate_revision_id(2, "", mapping)))

        rev = newrepos.get_revision(oldrepos.generate_revision_id(1, "trunk", mapping))
        self.assertEqual("$", rev.message)

        rev = newrepos.get_revision(
            oldrepos.generate_revision_id(2, "trunk", mapping))
        self.assertEqual('bla\xc3\xbcbla', rev.message.encode("utf-8"))

        rev = newrepos.get_revision(oldrepos.generate_revision_id(3, "trunk", mapping))
        self.assertEqual(u"a\\x0cb", rev.message)

    def test_set_layout(self):
        repos_url = self.make_client('d', 'dc')
        repos = Repository.open(repos_url)
        repos.set_layout(RootLayout())

    def testlhs_revision_parent_none(self):
        repos_url = self.make_client('d', 'dc')
        repos = Repository.open(repos_url)
        repos.set_layout(RootLayout())
        self.assertEquals(NULL_REVISION, repos._revmeta_provider.get_revision("", 0).get_lhs_parent(repos.get_mapping()))

    def testlhs_revision_parent_first(self):
        repos_url = self.make_client('d', 'dc')
        repos = Repository.open(repos_url)
        repos.set_layout(RootLayout())
        self.build_tree({'dc/adir/afile': "data"})
        self.client_add("dc/adir")
        self.client_commit("dc", "Initial commit")
        mapping = repos.get_mapping()
        self.assertEquals(repos.generate_revision_id(0, "", mapping), \
                repos._revmeta_provider.get_revision("", 1).get_lhs_parent(mapping))

    def testlhs_revision_parent_simple(self):
        repos_url = self.make_client('d', 'dc')
        self.build_tree({'dc/trunk/adir/afile': "data", 
                         'dc/trunk/adir/stationary': None,
                         'dc/branches/abranch': None})
        self.client_add("dc/trunk")
        self.client_add("dc/branches")
        self.client_commit("dc", "Initial commit")
        self.build_tree({'dc/trunk/adir/afile': "bla"})
        self.client_commit("dc", "Incremental commit")
        repos = Repository.open(repos_url)
        repos.set_layout(TrunkLayout(0))
        mapping = repos.get_mapping()
        self.assertEquals(repos.generate_revision_id(1, "trunk", mapping), \
                repos._revmeta_provider.get_revision("trunk", 2).get_lhs_parent(mapping))

    def testlhs_revision_parent_copied(self):
        repos_url = self.make_client('d', 'dc')
        self.build_tree({'dc/py/trunk/adir/afile': "data", 
                         'dc/py/trunk/adir/stationary': None})
        self.client_add("dc/py")
        self.client_commit("dc", "Initial commit")
        self.client_copy("dc/py", "dc/de")
        self.client_commit("dc", "Incremental commit")
        self.build_tree({'dc/de/trunk/adir/afile': "bla"})
        self.client_commit("dc", "Change de")
        repos = Repository.open(repos_url)
        repos.set_layout(TrunkLayout(1))
        mapping = repos.get_mapping()
        self.assertEquals(repos.generate_revision_id(1, "py/trunk", mapping), \
                repos._revmeta_provider.get_revision("de/trunk", 3).get_lhs_parent(mapping))

    def test_mainline_revision_copied(self):
        repos_url = self.make_client('d', 'dc')
        self.build_tree({'dc/py/trunk/adir/afile': "data", 
                         'dc/py/trunk/adir/stationary': None})
        self.client_add("dc/py")
        self.client_commit("dc", "Initial commit")
        self.build_tree({'dc/de':None})
        self.client_add("dc/de")
        self.client_copy("dc/py/trunk", "dc/de/trunk")
        self.client_commit("dc", "Copy trunk")
        repos = Repository.open(repos_url)
        repos.set_layout(TrunkLayout(1))
        mapping = repos.get_mapping()
        self.assertEquals(repos.generate_revision_id(1, "py/trunk", mapping), \
                repos._revmeta_provider.get_revision("de/trunk", 2).get_lhs_parent(mapping))

    def test_mainline_revision_nested_deleted(self):
        repos_url = self.make_client('d', 'dc')
        self.build_tree({'dc/py/trunk/adir/afile': "data", 
                         'dc/py/trunk/adir/stationary': None})
        self.client_add("dc/py")
        self.client_commit("dc", "Initial commit")
        self.client_copy("dc/py", "dc/de")
        self.client_commit("dc", "Incremental commit")
        self.client_delete("dc/de/trunk/adir")
        self.client_commit("dc", "Another incremental commit")
        repos = Repository.open(repos_url)
        repos.set_layout(TrunkLayout(1))
        mapping = repos.get_mapping()
        self.assertEquals(repos.generate_revision_id(1, "py/trunk", mapping), \
                repos._revmeta_provider.get_revision("de/trunk", 3).get_lhs_parent(mapping))

    def test_item_keys_introduced_by(self):
        repos_url = self.make_repository('d')

        cb = self.get_commit_editor(repos_url)
        cb.add_file("foo").modify()
        cb.close()

        cb = self.get_commit_editor(repos_url)
        cb.open_file("foo").modify()
        cb.close()

        b = Branch.open(repos_url)
        mapping = b.repository.get_mapping()
        ch = list(b.repository.item_keys_introduced_by([b.last_revision()]))
        revid = b.last_revision()
        self.assertEquals([
            ('file', mapping.generate_file_id(b.repository.uuid, 1, "", u"foo"), set([revid])),
            ('inventory', None, [revid]),
            ('signatures', None, set([])),
            ('revisions', None, [revid])], ch)


