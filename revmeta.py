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

from bzrlib.revision import NULL_REVISION, Revision

from bzrlib.plugins.svn import changes, errors, properties
from bzrlib.plugins.svn.mapping import is_bzr_revision_fileprops, is_bzr_revision_revprops, contains_bzr_fileprops
from bzrlib.plugins.svn.svk import (SVN_PROP_SVK_MERGE, svk_features_merged_since, 
                 parse_svk_feature)

class RevisionMetadata(object):
    def __init__(self, repository, branch_path, revnum, paths, revprops, changed_fileprops=None, consider_fileprops=True):
        self.repository = repository
        self.branch_path = branch_path
        self._paths = paths
        self.revnum = revnum
        self.revprops = revprops
        self._changed_fileprops = changed_fileprops
        self.uuid = repository.uuid
        self.consider_fileprops = consider_fileprops

    def __repr__(self):
        return "<RevisionMetadata for revision %d in repository %s>" % (self.revnum, self.repository.uuid)

    def get_paths(self):
        if self._paths is None:
            self._paths = self.repository._log.get_revision_paths(self.revnum)
        return self._paths

    def get_revision_id(self, mapping):
        return self.repository.get_revmap().get_revision_id(self.revnum, self.branch_path, mapping, 
                                                            self.revprops, self.get_changed_fileprops())

    def get_fileprops(self):
        return self.repository.branchprop_list.get_properties(self.branch_path, self.revnum)

    def get_previous_fileprops(self):
        prev = changes.find_prev_location(self.get_paths(), self.branch_path, self.revnum)
        if prev is None:
            return {}
        (prev_path, prev_revnum) = prev
        return self.repository.branchprop_list.get_properties(prev_path, prev_revnum)

    def get_changed_fileprops(self):
        if self._changed_fileprops is None:
            if self.branch_path in self.get_paths():
                self._changed_fileprops = properties.diff(self.get_fileprops(), self.get_previous_fileprops())
            else:
                self._changed_fileprops = {}
        return self._changed_fileprops

    def get_lhs_parent(self, mapping):
        lhs_parent = mapping.get_lhs_parent(self.branch_path, self.revprops, self.get_changed_fileprops())
        if lhs_parent is None:
            # Determine manually
            lhs_parent = self.repository.lhs_revision_parent(self.branch_path, self.revnum, mapping)
        return lhs_parent

    def has_bzr_fileprop_ancestors(self):
        """Check whether there are any bzr file properties present in this revision.

        This can tell us whether one of the ancestors of this revision is a 
        fileproperty-based bzr revision.
        """
        if not self.consider_fileprops:
            # This revisions descendant doesn't have bzr fileprops set, so this one can't have them either.
            return False
        return contains_bzr_fileprops(self.get_fileprops())

    def is_bzr_revision(self):
        """Determine (with as few network requests as possible) if this is a bzr revision.

        """
        # If the server already sent us all revprops, look at those first
        order = []
        if self.repository.quick_log_revprops:
            order.append(lambda: is_bzr_revision_revprops(self.revprops))
        if self.consider_fileprops:
            order.append(lambda: is_bzr_revision_fileprops(self.get_changed_fileprops()))
        # Only look for revprops if they could've been committed
        if (not self.repository.quick_log_revprops and 
                self.repository.check_revprops):
            order.append(lambda: is_bzr_revision_revprops(self.revprops))
        for fn in order:
            ret = fn()
            if ret is not None:
                return ret
        return None

    def get_rhs_parents(self, mapping):
        extra_rhs_parents = mapping.get_rhs_parents(self.branch_path, self.revprops, self.get_changed_fileprops())

        if extra_rhs_parents != ():
            return extra_rhs_parents

        if self.is_bzr_revision():
            return ()

        current = self.get_fileprops().get(SVN_PROP_SVK_MERGE, "")
        if current == "":
            return ()

        previous = self.get_previous_fileprops().get(SVN_PROP_SVK_MERGE, "")

        return tuple(self._svk_merged_revisions(mapping, current, previous))

    def get_parent_ids(self, mapping):
        parents_cache = getattr(self.repository._real_parents_provider, "_cache", None)
        if parents_cache is not None:
            parent_ids = parents_cache.lookup_parents(self.get_revision_id(mapping))
            if parent_ids is not None:
                return parent_ids

        lhs_parent = self.get_lhs_parent(mapping)
        if lhs_parent == NULL_REVISION:
            parent_ids = (NULL_REVISION,)
        else:
            parent_ids = (lhs_parent,) + self.get_rhs_parents(mapping)

        if parents_cache is not None:
            parents_cache.insert_parents(self.get_revision_id(mapping), 
                                         parent_ids)

        return parent_ids

    def get_revision(self, mapping):
        parent_ids = self.get_parent_ids(mapping)
        if parent_ids == (NULL_REVISION,):
            parent_ids = ()
        rev = Revision(revision_id=self.get_revision_id(mapping), 
                       parent_ids=parent_ids,
                       inventory_sha1="")

        rev.svn_meta = self
        rev.svn_mapping = mapping

        mapping.import_revision(self.revprops, self.get_changed_fileprops(), self.repository.uuid, self.branch_path, 
                                self.revnum, rev)

        return rev

    def get_fileid_map(self, mapping):
        return mapping.import_fileid_map(self.revprops, self.get_changed_fileprops())

    def __hash__(self):
        return hash((self.__class__, self.repository.uuid, self.branch_path, self.revnum))

    def _svk_merged_revisions(self, mapping, current, previous):
        """Find out what SVK features were merged in a revision.

        """
        for feature in svk_features_merged_since(current, previous):
            # We assume svk:merge is only relevant on non-bzr-svn revisions. 
            # If this is a bzr-svn revision, the bzr-svn properties 
            # would be parsed instead.
            #
            # This saves one svn_get_dir() call.
            revid = svk_feature_to_revision_id(feature, mapping)
            if revid is not None:
                yield revid



def svk_feature_to_revision_id(feature, mapping):
    """Convert a SVK feature to a revision id for this repository.

    :param feature: SVK feature.
    :return: revision id.
    """
    try:
        (uuid, bp, revnum) = parse_svk_feature(feature)
    except errors.InvalidPropertyValue:
        return None
    if not mapping.is_branch(bp) and not mapping.is_tag(bp):
        return None
    return mapping.revision_id_foreign_to_bzr((uuid, revnum, bp))



