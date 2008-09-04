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

from bzrlib.errors import InvalidRevisionId, NotBranchError
from bzrlib.inventory import ROOT_ID
from bzrlib.plugins.svn.layout import RepositoryLayout
from bzrlib.plugins.svn.mapping import BzrSvnMapping, escape_svn_path, unescape_svn_path, parse_svn_revprops

SVN_PROP_BZR_MERGE = 'bzr:merge'

class BzrSvnMappingv1(BzrSvnMapping):
    """This was the initial version of the mappings as used by bzr-svn
    0.2.
    
    It does not support pushing revisions to Subversion as-is, but only 
    as part of a merge.
    """
    name = "v1"

    def __init__(self, layout=None):
        super(BzrSvnMappingv1, self).__init__()
        self._layout = layout

    @classmethod
    def revision_id_bzr_to_foreign(cls, revid):
        if not revid.startswith("svn-v1:"):
            raise InvalidRevisionId(revid, "")
        revid = revid[len("svn-v1:"):]
        at = revid.index("@")
        fash = revid.rindex("-")
        uuid = revid[at+1:fash]
        branch_path = unescape_svn_path(revid[fash+1:])
        revnum = int(revid[0:at])
        assert revnum >= 0
        return (uuid, branch_path, revnum, cls())

    def revision_id_foreign_to_bzr(self, (uuid, revnum, path)):
        return "svn-v1:%d@%s-%s" % (revnum, uuid, escape_svn_path(path))

    def __eq__(self, other):
        return type(self) == type(other)

    def is_branch(self, branch_path):
        return self._layout.is_branch(branch_path)

    def is_tag(self, tag_path):
        return False

    def import_revision(self, svn_revprops, fileprops, uuid, branch, revnum, rev):
        parse_svn_revprops(svn_revprops, rev)

    @staticmethod
    def generate_file_id(uuid, revnum, branch, inv_path):
        if inv_path == "":
            return ROOT_ID
        return "%s-%s" % (self.revision_id_foreign_to_bzr((uuid, revnum, branch)), escape_svn_path(inv_path))

    def import_fileid_map(self, revprops, fileprops):
        return {}

    def import_text_parents(self, revprops, fileprops):
        return {}

    def get_rhs_parents(self, branch_path, revprops, fileprops):
        value = fileprops.get(SVN_PROP_BZR_MERGE, "")
        if value == "":
            return ()
        return (value.splitlines()[-1])

    @classmethod
    def from_repository(cls, repository, _hinted_branch_path=None):
        if _hinted_branch_path is None:
            return cls(TrunkLegacyLayout(repository))
    
        parts = _hinted_branch_path.strip("/").split("/")
        for i in range(0,len(parts)):
            if parts[i] == "trunk" or \
               parts[i] == "branches" or \
               parts[i] == "tags":
                return cls(TrunkLegacyLayout(repository, level=i))

        return cls(RootLegacyLayout(repository))

    def get_guessed_layout(self, repository):
        return self._layout


class BzrSvnMappingv2(BzrSvnMappingv1):
    """The second version of the mappings as used in the 0.3.x series.

    It does not support pushing revisions to Subversion as-is, but only 
    as part of a merge.
    """
    name = "v2"

    @classmethod
    def revision_id_bzr_to_foreign(cls, revid):
        if not revid.startswith("svn-v2:"):
            raise InvalidRevisionId(revid, "")
        revid = revid[len("svn-v2:"):]
        at = revid.index("@")
        fash = revid.rindex("-")
        uuid = revid[at+1:fash]
        branch_path = unescape_svn_path(revid[fash+1:])
        revnum = int(revid[0:at])
        assert revnum >= 0
        return (uuid, branch_path, revnum, cls())

    def revision_id_foreign_to_bzr(self, (uuid, revnum, path)):
        return "svn-v2:%d@%s-%s" % (revnum, uuid, escape_svn_path(path))

    def __eq__(self, other):
        return type(self) == type(other)


class LegacyLayout(RepositoryLayout):

    def get_tag_path(self, name, project=""):
        return None

    def get_branch_path(self, name, project=""):
        return None


class TrunkLegacyLayout(LegacyLayout):

    def __init__(self, repository, level=0):
        super(TrunkLegacyLayout, self).__init__(repository)
        self.level = level
    
    def parse(self, path):
        parts = path.strip("/").split("/")
        if len(parts) == 0 or self.level >= len(parts):
            raise NotBranchError(path=path)

        if parts[self.level] == "trunk" or parts[self.level] == "hooks":
            return ("branch", "/".join(parts[0:self.level]), "/".join(parts[0:self.level+1]).strip("/"), 
                    "/".join(parts[self.level+1:]).strip("/"))
        elif ((parts[self.level] == "tags" or parts[self.level] == "branches") and 
              len(parts) >= self.level+2):
            return ("branch", "/".join(parts[0:self.level]), "/".join(parts[0:self.level+2]).strip("/"), 
                    "/".join(parts[self.level+2:]).strip("/"))
        else:
            raise NotBranchError(path=path)

    def is_branch(self, path, project=None):
        parts = path.strip("/").split("/")
        if len(parts) == self.level+1 and parts[self.level] == "trunk":
            return True

        if len(parts) == self.level+2 and \
           (parts[self.level] == "branches" or parts[self.level] == "tags"):
            return True

        return False



class RootLegacyLayout(RepositoryLayout):

    def parse(self, path):
        return ("branch", "", "", path)

    def is_branch(self, branch_path, project=None):
        return branch_path == ""

