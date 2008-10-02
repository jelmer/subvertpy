# Copyright (C) 2007 Jelmer Vernooij <jelmer@samba.org>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""Basis and revision tree tests."""

import os

from bzrlib.inventory import Inventory, TreeReference
from bzrlib.osutils import has_symlinks
from bzrlib.repository import Repository
from bzrlib.revision import NULL_REVISION
from bzrlib.tests import TestSkipped
from bzrlib.workingtree import WorkingTree

from bzrlib.plugins.svn import subvertpy
from bzrlib.plugins.svn.layout.standard import RootLayout
from bzrlib.plugins.svn.tests import SubversionTestCase
from bzrlib.plugins.svn.tree import SvnBasisTree, inventory_add_external


class TestBasisTree(SubversionTestCase):
    def test_executable(self):
        repos_url = self.make_client("d", "dc")

        dc = self.get_commit_editor(repos_url)
        f = dc.add_file("file")
        f.modify("x")
        f.change_prop("svn:executable", "*")
        dc.close()

        self.client_update("dc")

        tree = SvnBasisTree(WorkingTree.open("dc"))
        self.assertTrue(tree.inventory[tree.inventory.path2id("file")].executable)

    def test_executable_changed(self):
        repos_url = self.make_client("d", "dc")

        dc = self.get_commit_editor(repos_url)
        dc.add_file("file").modify("x")
        dc.close()

        self.client_update("dc")
        self.client_set_prop("dc/file", "svn:executable", "*")
        tree = SvnBasisTree(WorkingTree.open("dc"))
        self.assertFalse(tree.inventory[tree.inventory.path2id("file")].executable)

    def test_symlink(self):
        repos_url = self.make_client("d", "dc")

        dc = self.get_commit_editor(repos_url)
        file = dc.add_file("file")
        file.modify("link target")
        file.change_prop("svn:special", "*")
        dc.close()

        self.client_update("dc")
        tree = SvnBasisTree(WorkingTree.open("dc"))
        self.assertEqual('symlink', 
                         tree.inventory[tree.inventory.path2id("file")].kind)
        self.assertEqual("target",
                         tree.inventory[tree.inventory.path2id("file")].symlink_target)

    def test_symlink_with_newlines_in_target(self):
        repos_url = self.make_client("d", "dc")

        dc = self.get_commit_editor(repos_url)
        file = dc.add_file("file")
        file.modify("link target\nbar\nbla")
        file.change_prop("svn:special", "*")
        dc.close()

        self.client_update("dc")
        tree = SvnBasisTree(WorkingTree.open("dc"))
        self.assertEqual('symlink', 
                         tree.inventory[tree.inventory.path2id("file")].kind)
        self.assertEqual("target\nbar\nbla",
                         tree.inventory[tree.inventory.path2id("file")].symlink_target)

    def test_symlink_not_special(self):
        repos_url = self.make_client("d", "dc")

        dc = self.get_commit_editor(repos_url)
        file = dc.add_file("file")
        file.modify("fsdfdslhfdsk h")
        file.change_prop("svn:special", "*")
        file2 = dc.add_file("file2")
        file.modify("a")
        file.change_prop("svn:special", "*")
        dc.close()

        try:
            self.client_update("dc")
        except subvertpy.SubversionException, (msg, num):
            if num == subvertpy.ERR_WC_BAD_ADM_LOG:
                raise TestSkipped("Unable to run test with svn 1.4")
            raise
        tree = SvnBasisTree(WorkingTree.open("dc"))
        self.assertEqual('file', 
                         tree.inventory[tree.inventory.path2id("file")].kind)

    def test_symlink_next(self):
        repos_url = self.make_client("d", "dc")

        dc = self.get_commit_editor(repos_url)
        dc.add_file("bla").modify("p")
        file = dc.add_file("file")
        file.modify("link target")
        file.change_prop("svn:special", "*")
        dc.close()

        dc = self.get_commit_editor(repos_url)
        dc.open_file("bla").modify("pa")
        dc.close()

        self.client_update("dc")

        tree = SvnBasisTree(WorkingTree.open("dc"))
        self.assertEqual('symlink', 
                         tree.inventory[tree.inventory.path2id("file")].kind)
        self.assertEqual("target",
                         tree.inventory[tree.inventory.path2id("file")].symlink_target)

    def test_annotate_iter(self):
        repos_url = self.make_client("d", "dc")

        dc = self.get_commit_editor(repos_url)
        dc.add_file("file").modify("x\n")
        dc.close()

        dc = self.get_commit_editor(repos_url)
        dc.open_file("file").modify("x\ny\n")
        dc.close()

        self.client_update('dc')
        tree = SvnBasisTree(WorkingTree.open("dc"))
        self.assertRaises(NotImplementedError, tree.annotate_iter, tree.path2id("file"))

    def test_executable_link(self):
        if not has_symlinks():
            return
        repos_url = self.make_client("d", "dc")

        dc = self.get_commit_editor(repos_url)
        file = dc.add_file("file")
        file.modify("link target")
        file.change_prop("svn:special", "*")
        file.change_prop("svn:executable", "*")
        dc.close()

        try:
            self.client_update("dc")
        except subvertpy.SubversionException, (msg, num):
            if num == subvertpy.ERR_WC_BAD_ADM_LOG:
                raise TestSkipped("Unable to run test with svn 1.4")
            raise

        wt = WorkingTree.open("dc")
        tree = SvnBasisTree(wt)
        self.assertFalse(tree.inventory[tree.inventory.path2id("file")].executable)
        self.assertFalse(wt.inventory[wt.inventory.path2id("file")].executable)


class TestInventoryExternals(SubversionTestCase):
    def test_add_nested_norev(self):
        """Add a nested tree with no specific revision referenced."""
        repos_url = self.make_client('d', 'dc')
        repos = Repository.open(repos_url)
        mapping = repos.get_mapping()
        inv = Inventory(root_id='blabloe')
        inventory_add_external(inv, 'blabloe', 'blie/bla', 
                mapping.revision_id_foreign_to_bzr((repos.uuid, "", 1)), 
                None, repos_url)
        self.assertEqual(TreeReference(
            mapping.generate_file_id(repos.uuid, 0, "", u""),
             'bla', inv.path2id('blie'), 
             revision=mapping.revision_id_foreign_to_bzr((repos.uuid, "", 1))), 
             inv[inv.path2id('blie/bla')])

    def test_add_simple_norev(self):
        repos_url = self.make_client('d', 'dc')
        repos = Repository.open(repos_url)
        mapping = repos.get_mapping()
        inv = Inventory(root_id='blabloe')
        inventory_add_external(inv, 'blabloe', 'bla', 
            mapping.revision_id_foreign_to_bzr((repos.uuid, "", 1)), None, 
            repos_url)

        self.assertEqual(TreeReference(
            mapping.generate_file_id(repos.uuid, 0, "", u""),
             'bla', 'blabloe', 
             revision=mapping.revision_id_foreign_to_bzr((repos.uuid, "", 1))), 
             inv[inv.path2id('bla')])

    def test_add_simple_rev(self):
        repos_url = self.make_client('d', 'dc')
        repos = Repository.open(repos_url)
        inv = Inventory(root_id='blabloe')
        mapping = repos.get_mapping()
        inventory_add_external(inv, 'blabloe', 'bla', 
            mapping.revision_id_foreign_to_bzr((repos.uuid, "", 1)), 0, repos_url)
        expected_ie = TreeReference(mapping.generate_file_id(repos.uuid, 0, "", u""),
            'bla', 'blabloe', 
            revision=mapping.revision_id_foreign_to_bzr((repos.uuid, "", 1)),
            reference_revision=NULL_REVISION)
        ie = inv[inv.path2id('bla')]
        self.assertEqual(NULL_REVISION, ie.reference_revision)
        self.assertEqual(mapping.revision_id_foreign_to_bzr((repos.uuid, "", 1)), 
                         ie.revision)
        self.assertEqual(expected_ie, inv[inv.path2id('bla')])


class TestSvnRevisionTree(SubversionTestCase):
    def setUp(self):
        super(TestSvnRevisionTree, self).setUp()
        repos_url = self.make_client('d', 'dc')
        self.build_tree({'dc/foo/bla': "data"})
        self.client_add("dc/foo")
        self.client_commit("dc", "My Message")
        self.repos = Repository.open(repos_url)
        self.repos.set_layout(RootLayout())
        mapping = self.repos.get_mapping()
        self.inventory = self.repos.get_inventory(
                self.repos.generate_revision_id(1, "", mapping))
        self.tree = self.repos.revision_tree(
                self.repos.generate_revision_id(1, "", mapping))

    def test_inventory(self):
        self.assertIsInstance(self.tree.inventory, Inventory)
        self.assertEqual(self.inventory, self.tree.inventory)

    def test_get_parent_ids(self):
        mapping = self.repos.get_mapping()
        self.assertEqual((self.repos.generate_revision_id(0, "", mapping),), self.tree.get_parent_ids())

    def test_get_parent_ids_zero(self):
        mapping = self.repos.get_mapping()
        tree = self.repos.revision_tree(
                self.repos.generate_revision_id(0, "", mapping))
        self.assertEqual((), tree.get_parent_ids())

    def test_get_revision_id(self):
        mapping = self.repos.get_mapping()
        self.assertEqual(self.repos.generate_revision_id(1, "", mapping),
                         self.tree.get_revision_id())

    def test_get_file_lines(self):
        self.assertEqual(["data"], 
                self.tree.get_file_lines(self.inventory.path2id("foo/bla")))

    def test_executable(self):
        self.client_set_prop("dc/foo/bla", "svn:executable", "*")
        self.client_commit("dc", "My Message")

        mapping = self.repos.get_mapping()
        
        inventory = self.repos.get_inventory(
                self.repos.generate_revision_id(2, "", mapping))

        self.assertTrue(inventory[inventory.path2id("foo/bla")].executable)

    def test_symlink(self):
        if not has_symlinks():
            return
        os.symlink('foo/bla', 'dc/bar')
        self.client_add('dc/bar')
        self.client_commit("dc", "My Message")

        mapping = self.repos.get_mapping()
        
        inventory = self.repos.get_inventory(
                self.repos.generate_revision_id(2, "", mapping))

        self.assertEqual('symlink', inventory[inventory.path2id("bar")].kind)
        self.assertEqual('foo/bla', 
                inventory[inventory.path2id("bar")].symlink_target)

    def test_not_executable(self):
        self.assertFalse(self.inventory[
            self.inventory.path2id("foo/bla")].executable)
