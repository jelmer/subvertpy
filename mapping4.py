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

from bzrlib import errors

from bzrlib.plugins.svn import mapping

supported_features = set()


class BzrSvnMappingv4(mapping.BzrSvnMappingRevProps):
    """Mapping between Subversion and Bazaar, introduced in bzr-svn 0.5.

    Tries to use revision properties when possible.

    TODO: Add variable with required features.
    """
    revid_prefix = "svn-v4"
    experimental = True

    @staticmethod
    def supports_roundtripping():
        return True

    def import_revision(self, svn_revprops, fileprops, uuid, branch, revnum, rev):
        super(BzrSvnMappingv4, self).import_revision(svn_revprops, fileprops, uuid, branch, revnum, rev)
        if revprops.has_key(mapping.SVN_REVPROP_BZR_REQUIRED_FEATURES):
            features = set(revprops[mapping.SVN_REVPROP_BZR_REQUIRED_FEATURES].split(","))
            assert features.issubset(supported_features)

    def export_revision(self, can_use_custom_revprops, branch_root, timestamp, timezone, committer, revprops, revision_id, revno, merges, fileprops):
        (revprops, fileprops) = mapping.BzrSvnMappingRevProps.export_revision(self, can_use_custom_revprops, branch_root, timestamp, timezone, committer, revprops, revision_id, revno, merges, fileprops)
        revprops[mapping.SVN_REVPROP_BZR_MAPPING_VERSION] = "4"
        revprops[mapping.SVN_REVPROP_BZR_REQUIRED_FEATURES] = ",".join([])
        return (revprops, fileprops)

    @classmethod
    def parse_revision_id(cls, revid):
        assert isinstance(revid, str)

        if not revid.startswith(cls.revid_prefix):
            raise errors.InvalidRevisionId(revid, "")

        try:
            (version, uuid, branch_path, srevnum) = revid.split(":")
        except ValueError:
            raise errors.InvalidRevisionId(revid, "")

        branch_path = mapping.unescape_svn_path(branch_path)

        return (uuid, branch_path, int(srevnum), cls())

    def generate_revision_id(self, uuid, revnum, path):
        return "svn-v4:%s:%s:%d" % (uuid, path, revnum)

    def generate_file_id(self, uuid, revnum, branch, inv_path):
        return "%d@%s:%s/%s" % (revnum, uuid, branch, inv_path.encode("utf-8"))

    def is_branch(self, branch_path):
        return True

    def is_tag(self, tag_path):
        return True

    def __eq__(self, other):
        return type(self) == type(other)



