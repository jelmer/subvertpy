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

from bzrlib.plugins.svn import layout, mapping

supported_features = set()


class BzrSvnMappingv4(mapping.BzrSvnMapping):
    """Mapping between Subversion and Bazaar, introduced in bzr-svn 0.5.

    Tries to use revision properties when possible.

    TODO: Add variable with required features.
    """
    revid_prefix = "svn-v4"
    upgrade_suffix = "-svn4"
    experimental = True
    roundtripping = True
    can_use_revprops = True
    can_use_fileprops = True
    supports_hidden = True

    def __init__(self, layout=None):
        self.name = "v4"
        self.layout = layout
        self.revprops = mapping.BzrSvnMappingRevProps()
        self.fileprops = mapping.BzrSvnMappingFileProps(self.name)

    @classmethod
    def from_repository(cls, repository, _hinted_branch_path=None):
        if _hinted_branch_path == "":
            return cls(layout.RootLayout())
        else:
            return cls(layout.TrunkLayout())

    @classmethod
    def from_revprops(cls, revprops):
        return cls()

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
        return "%d@%s:%s" % (revnum, uuid, mapping.escape_svn_path("%s/%s" % (branch, inv_path.encode("utf-8"))))

    def is_branch(self, branch_path):
        return True

    def is_tag(self, tag_path):
        return True

    def __eq__(self, other):
        return type(self) == type(other)

    def get_branch_root(self, revprops):
        return self.revprops.get_branch_root(revprops)

    def get_lhs_parent(self, branch_path, svn_revprops, fileprops):
        return self.revprops.get_lhs_parent(branch_path, svn_revprops, fileprops)

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

    def export_revision(self, branch_root, timestamp, timezone, committer, revprops, revision_id, 
                        revno, parent_ids, svn_revprops, svn_fileprops):
        if svn_revprops is not None:
            self.revprops.export_revision(branch_root, timestamp, timezone, committer, 
                                          revprops, revision_id, revno, parent_ids, svn_revprops, svn_fileprops)
            svn_revprops[mapping.SVN_REVPROP_BZR_MAPPING_VERSION] = self.name
        else:
            self.fileprops.export_revision(branch_root, timestamp, timezone, committer, 
                                      revprops, revision_id, revno, parent_ids, svn_revprops, svn_fileprops)

    def export_fileid_map(self, fileids, revprops, fileprops):
        if revprops is not None:
            self.revprops.export_fileid_map(fileids, revprops, fileprops)
        else:
            self.fileprops.export_fileid_map(fileids, revprops, fileprops)

    def export_text_parents(self, text_parents, revprops, fileprops):
        if revprops is not None:
            self.revprops.export_text_parents(text_parents, revprops, fileprops)
        else:
            self.fileprops.export_text_parents(text_parents, revprops, fileprops)

    def import_revision(self, svn_revprops, fileprops, uuid, branch, revnum, rev):
        if svn_revprops.has_key(mapping.SVN_REVPROP_BZR_REQUIRED_FEATURES):
            features = mapping.parse_required_features_property(svn_revprops[mapping.SVN_REVPROP_BZR_REQUIRED_FEATURES])
            assert features.issubset(supported_features), "missing feature: %r" % features.difference(supported_features)
        if svn_revprops.has_key(mapping.SVN_REVPROP_BZR_MAPPING_VERSION):
            assert svn_revprops[mapping.SVN_REVPROP_BZR_MAPPING_VERSION] == self.name, "unknown mapping: %s" % svn_revprops[mapping.SVN_REVPROP_BZR_MAPPING_VERSION]
            self.revprops.import_revision(svn_revprops, fileprops, uuid, branch, revnum, rev)
        else:
            if fileprops.has_key(mapping.SVN_PROP_BZR_REQUIRED_FEATURES):
                features = mapping.parse_required_features_property(fileprops[mapping.SVN_PROP_BZR_REQUIRED_FEATURES])
                assert features.issubset(supported_features), "missing feature: %r" % features.difference(supported_features)
            self.fileprops.import_revision(svn_revprops, fileprops, uuid, branch, revnum, rev)

    def get_mandated_layout(self, repository):
        return self.layout

    def is_bzr_revision_hidden(self, revprops, changed_fileprops):
        if revprops.has_key(mapping.SVN_REVPROP_BZR_HIDDEN):
            return True
        if (changed_fileprops.has_key(mapping.SVN_PROP_BZR_HIDDEN) and 
            changed_fileprops.get(mapping.SVN_PROP_BZR_HIDDEN) is not None):
            return True
        return False

    def export_hidden(self, revprops, fileprops):
        if revprops is not None:
            revprops[mapping.SVN_REVPROP_BZR_HIDDEN] = ""
            return
        old_value = fileprops.get(mapping.SVN_PROP_BZR_HIDDEN, "0")
        fileprops[mapping.SVN_PROP_BZR_HIDDEN] = str(int(old_value)+1)
