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

"""Branch tests."""

from bzrlib import urlutils
from bzrlib.branch import Branch
from bzrlib.bzrdir import BzrDir
from bzrlib.errors import NoSuchFile, NoSuchRevision, NotBranchError, NoSuchTag
from bzrlib.repository import Repository
from bzrlib.revision import NULL_REVISION
from bzrlib.trace import mutter

import os
from unittest import TestCase

from bzrlib.plugins.svn import core
from bzrlib.plugins.svn.branch import FakeControlFiles, SvnBranchFormat
from bzrlib.plugins.svn.convert import load_dumpfile
from bzrlib.plugins.svn.mapping import SVN_PROP_BZR_REVISION_ID, mapping_registry
from bzrlib.plugins.svn.tests import SubversionTestCase

class WorkingSubversionBranch(SubversionTestCase):

    def setUp(self):
        super(WorkingSubversionBranch, self).setUp()
        self._old_mapping = mapping_registry._get_default_key()
        mapping_registry.set_default(self.mapping_name)

    def tearDown(self):
        super(WorkingSubversionBranch, self).tearDown()
        mapping_registry.set_default(self._old_mapping)

    def test_revision_id_to_revno_simple(self):
        repos_url = self.make_repository('a')

        dc = self.get_commit_editor(repos_url)
        dc.add_file("foo").modify()
        dc.change_prop("bzr:revision-id:v3-none", 
                            "2 myrevid\n")
        dc.close()

        branch = Branch.open(repos_url)
        self.assertEquals(2, branch.revision_id_to_revno("myrevid"))

    def test_revision_id_to_revno_older(self):
        repos_url = self.make_repository('a')

        dc = self.get_commit_editor(repos_url)
        dc.add_file("foo").modify()
        dc.change_prop("bzr:revision-id:v3-none", 
                            "2 myrevid\n")
        dc.close()

        dc = self.get_commit_editor(repos_url)
        dc.open_file("foo").modify()
        dc.change_prop("bzr:revision-id:v3-none", 
                            "2 myrevid\n3 mysecondrevid\n")
        dc.close()

        branch = Branch.open(repos_url)
        self.assertEquals(3, branch.revision_id_to_revno("mysecondrevid"))
        self.assertEquals(2, branch.revision_id_to_revno("myrevid"))


