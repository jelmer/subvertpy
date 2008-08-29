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


class BzrSvnMappingv4(mapping.BzrSvnMapping):
    """Mapping between Subversion and Bazaar, introduced in bzr-svn 0.5.

    Tries to use revision properties when possible.

    TODO: Add variable with required features.
    """
    revid_prefix = "svn-v4"
    upgrade_suffix = "-svn4"
    experimental = True

    def __init__(self):
        self.name = "v4"
        self.revprops = mapping.BzrSvnMappingRevProps()
        self.fileprops = mapping.BzrSvnMappingFileProps(self.name)

    @staticmethod
    def supports_roundtripping():
        return True

    @classmethod
    def revision_id_bzr_to_foreign(cls, revid):
        assert isinstance(revid, str)

        if not revid.startswith(cls.revid_prefix):
            raise errors.InvalidRevisionId(revid, "")

        try:
            (version, uuid, branch_path, srevnum) = revid.split(":")
        except ValueError:
            raise errors.InvalidRevisionId(revid, "")

        branch_path = mapping.unescape_svn_path(branch_path)

        return (uuid, branch_path, int(srevnum), cls())

    def revision_id_foreign_to_bzr(self, (uuid, revnum, path)):
        return "svn-v4:%s:%s:%d" % (uuid, path, revnum)

    def generate_file_id(self, uuid, revnum, branch, inv_path):
        return "%d@%s:%s/%s" % (revnum, uuid, branch, inv_path.encode("utf-8"))

    def is_branch(self, branch_path):
        return True

    def is_tag(self, tag_path):
        return True

    def __eq__(self, other):
        return type(self) == type(other)

    def get_rhs_parents(self, branch_path, svn_revprops, fileprops):
        if svn_revprops.has_key(mapping.SVN_REVPROP_BZR_MAPPING_VERSION):
            return self.revprops.get_rhs_parents(branch_path, svn_revprops, fileprops)
        else:
            return self.fileprops.get_rhs_parents(branch_path, svn_revprops, fileprops)

    def get_revision_id(self, branch_path, revprops, fileprops):
        if revprops.has_key(mapping.SVN_REVPROP_BZR_MAPPING_VERSION):
            return self.revprops.get_revision_id(branch_path, revprops, fileprops)
        else:
            return self.fileprops.get_revision_id(branch_path, revprops, fileprops)

    def import_text_parents(self, svn_revprops, fileprops):
        if svn_revprops.has_key(mapping.SVN_REVPROP_BZR_TEXT_PARENTS):
            return self.revprops.import_text_parents(svn_revprops, fileprops)
        else:
            return self.fileprops.import_text_parents(svn_revprops, fileprops)

    def import_fileid_map(self, svn_revprops, fileprops):
        if svn_revprops.has_key(mapping.SVN_REVPROP_BZR_MAPPING_VERSION):
            return self.revprops.import_fileid_map(svn_revprops, fileprops)
        else:
            return self.fileprops.import_fileid_map(svn_revprops, fileprops)

    def export_revision(self, can_use_custom_revprops, branch_root, timestamp, timezone, committer, revprops, revision_id, 
                        revno, merges, fileprops):
        if can_use_custom_revprops:
            (svn_revprops, fileprops) = self.revprops.export_revision(can_use_custom_revprops, branch_root, timestamp, timezone, committer, 
                                          revprops, revision_id, revno, merges, fileprops)
            svn_revprops[mapping.SVN_REVPROP_BZR_MAPPING_VERSION] = "4"
            return (svn_revprops, fileprops)
        else:
            return self.fileprops.export_revision(can_use_custom_revprops, branch_root, timestamp, timezone, committer, 
                                      revprops, revision_id, revno, merges, fileprops)

    def export_fileid_map(self, can_use_custom_revprops, fileids, revprops, fileprops):
        if can_use_custom_revprops:
            self.revprops.export_fileid_map(can_use_custom_revprops, fileids, revprops, fileprops)
        else:
            self.fileprops.export_fileid_map(can_use_custom_revprops, fileids, revprops, fileprops)

    def export_text_parents(self, can_use_custom_revprops, text_parents, revprops, fileprops):
        if can_use_custom_revprops:
            self.revprops.export_text_parents(can_use_custom_revprops, text_parents, revprops, fileprops)
        else:
            self.fileprops.export_text_parents(can_use_custom_revprops, text_parents, revprops, fileprops)

    def import_revision(self, svn_revprops, fileprops, uuid, branch, revnum, rev):
        if svn_revprops.has_key(mapping.SVN_REVPROP_BZR_REQUIRED_FEATURES):
            features = set(svn_revprops[mapping.SVN_REVPROP_BZR_REQUIRED_FEATURES].split(","))
            assert features.issubset(supported_features), "missing feature: %r" % features.difference(supported_features)
        if svn_revprops.has_key(mapping.SVN_REVPROP_BZR_MAPPING_VERSION):
            self.revprops.import_revision(svn_revprops, fileprops, uuid, branch, revnum, rev)
        else:
            self.fileprops.import_revision(svn_revprops, fileprops, uuid, branch, revnum, rev)


