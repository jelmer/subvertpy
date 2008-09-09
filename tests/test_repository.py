# -*- coding: utf-8 -*-

# Copyright (C) 2006-2007 Jelmer Vernooij <jelmer@samba.org>

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

"""Subversion repository tests."""

from bzrlib import urlutils
from bzrlib.branch import Branch
from bzrlib.bzrdir import BzrDir, format_registry
from bzrlib.config import GlobalConfig
from bzrlib.errors import NoSuchRevision, UninitializableFormat
from bzrlib.inventory import Inventory
from bzrlib.osutils import has_symlinks
from bzrlib.repository import Repository
from bzrlib.revision import NULL_REVISION
from bzrlib.tests import TestCase, TestSkipped

import os

from bzrlib.plugins.svn import format, ra
from bzrlib.plugins.svn.tests import SubversionTestCase
from bzrlib.plugins.svn.repository import SvnRepositoryFormat


class TestSubversionRepositoryWorks(SubversionTestCase):
    """Generic Subversion Repository tests."""

    def setUp(self):
        super(TestSubversionRepositoryWorks, self).setUp()
        self.repos_path = 'a'
        self.repos_url = self.make_repository(self.repos_path)

    def test_get_config_global_set(self):
        cfg = GlobalConfig()
        cfg.set_user_option("foo", "Still Life")

        repos = Repository.open(self.repos_url)
        self.assertEquals("Still Life", 
                repos.get_config().get_user_option("foo"))

    def test_get_config(self):
        repos = Repository.open(self.repos_url)
        repos.get_config().set_user_option("foo", "Van Der Graaf Generator")

        repos = Repository.open(self.repos_url)
        self.assertEquals("Van Der Graaf Generator", 
                repos.get_config().get_user_option("foo"))

    def test_repr(self):
        dc = self.get_commit_editor(self.repos_url)
        dc.add_file("foo").modify("data")
        dc.close()

        repos = Repository.open(self.repos_url)

        self.assertEqual("SvnRepository('%s/')" % urlutils.local_path_to_url(urlutils.join(self.test_dir, "a")), repos.__repr__())

    def test_gather_stats(self):
        repos = Repository.open(self.repos_url)
        stats = repos.gather_stats()
        self.assertEquals(1, stats['revisions'])
        self.assertTrue(stats.has_key("firstrev"))
        self.assertTrue(stats.has_key("latestrev"))
        self.assertFalse(stats.has_key('committers'))

    def test_uuid(self):
        """ Test UUID is retrieved correctly """
        fs = self.open_fs(self.repos_path)
        repository = Repository.open(self.repos_url)
        self.assertEqual(fs.get_uuid(), repository.uuid)

    def test_is_shared(self):
        dc = self.get_commit_editor(self.repos_url)
        foo = dc.add_dir("foo")
        bla = foo.add_file("foo/bla").modify("data")
        dc.close()

        repository = Repository.open(self.repos_url)
        self.assertTrue(repository.is_shared())

    def test_format(self):
        """ Test repository format is correct """
        self.make_checkout(self.repos_url, 'ac')
        bzrdir = BzrDir.open("ac")
        self.assertEqual(bzrdir._format.get_format_string(), \
                "Subversion Local Checkout")
        
        self.assertEqual(bzrdir._format.get_format_description(), \
                "Subversion Local Checkout")

    def test_make_working_trees(self):
        repos = Repository.open(self.repos_url)
        self.assertFalse(repos.make_working_trees())

    def test_get_physical_lock_status(self):
        repos = Repository.open(self.repos_url)
        self.assertFalse(repos.get_physical_lock_status())

    def test_seen_bzr_revprops(self):
        repos = Repository.open(self.repos_url)
        dc = self.get_commit_editor(self.repos_url)
        dc.add_dir("foo")
        dc.close()

        self.assertFalse(repos.seen_bzr_revprops())


class SvnRepositoryFormatTests(TestCase):
    def setUp(self):
        self.format = SvnRepositoryFormat()

    def test_initialize(self):
        self.assertRaises(UninitializableFormat, self.format.initialize, None)

    def test_get_format_description(self):
        self.assertEqual("Subversion Repository", 
                         self.format.get_format_description())

    def test_conversion_target_self(self):
        self.assertTrue(self.format.check_conversion_target(self.format))

    def test_conversion_target_incompatible(self):
        self.assertFalse(self.format.check_conversion_target(
              format_registry.make_bzrdir('weave').repository_format))

    def test_conversion_target_compatible(self):
        self.assertTrue(self.format.check_conversion_target(
          format_registry.make_bzrdir('rich-root').repository_format))
