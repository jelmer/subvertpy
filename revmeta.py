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

from bzrlib.plugins.svn import changes, errors, logwalker, properties
from bzrlib.plugins.svn.mapping import is_bzr_revision_fileprops, is_bzr_revision_revprops, estimate_bzr_ancestors, SVN_REVPROP_BZR_SIGNATURE
from bzrlib.plugins.svn.svk import (SVN_PROP_SVK_MERGE, svk_features_merged_since, 
                 parse_svk_feature, estimate_svk_ancestors)

class RevisionMetadata(object):
    """Object describing a revision with bzr semantics in a Subversion repository."""

    def __init__(self, repository, branch_path, revnum, paths, revprops, changed_fileprops=None, metabranch=None):
        self.repository = repository
        self.uuid = repository.uuid
        self._log = repository._log
        self.branch_path = branch_path
        self._paths = paths
        self.revnum = revnum
        self._revprops = revprops
        self._changed_fileprops = changed_fileprops
        self.metabranch = metabranch

    def __repr__(self):
        return "<RevisionMetadata for revision %d in repository %s>" % (self.revnum, self.uuid)

    def get_paths(self):
        if self._paths is None:
            self._paths = self._log.get_revision_paths(self.revnum)
        return self._paths

    def get_revision_id(self, mapping):
        return self.repository.get_revmap().get_revision_id(self.revnum, self.branch_path, mapping, 
                                                            self.get_revprops(), self.get_changed_fileprops())

    def get_fileprops(self):
        return self.repository.branchprop_list.get_properties(self.branch_path, self.revnum)

    def get_revprops(self):
        if self._revprops is None:
            self._revprops = self._log.revprop_list(self.revnum)

        return self._revprops

    def knows_fileprops(self):
        fileprops = self.get_fileprops()
        return isinstance(fileprops, dict) or fileprops.is_loaded

    def get_previous_fileprops(self):
        prev = changes.find_prev_location(self.get_paths(), self.branch_path, self.revnum)
        if prev is None:
            return {}
        (prev_path, prev_revnum) = prev
        return self.repository.branchprop_list.get_properties(prev_path, prev_revnum)

    def get_changed_fileprops(self):
        if self._changed_fileprops is None:
            if self.branch_path in self.get_paths():
                self._changed_fileprops = logwalker.lazy_dict({}, properties.diff, self.get_fileprops(), self.get_previous_fileprops())
            else:
                self._changed_fileprops = {}
        return self._changed_fileprops

    def get_lhs_parent_revmeta(self, mapping):
        if self.metabranch is not None and self.metabranch.mapping == mapping:
            # Perhaps the metabranch already has the parent?
            parentrevmeta = self.metabranch.get_lhs_parent(self)
            if parentrevmeta is not None:
                return parentrevmeta
        # FIXME: Don't use self.repository.branch_prev_location,
        #        since it browses history
        return self.repository.branch_prev_location(self.branch_path, self.revnum, mapping)

    def get_lhs_parent(self, mapping):
        # Sometimes we can retrieve the lhs parent from the revprop data
        lhs_parent = mapping.get_lhs_parent(self.branch_path, self.get_revprops(), self.get_changed_fileprops())
        if lhs_parent is not None:
            return lhs_parent
        parentrevmeta = self.get_lhs_parent_revmeta(mapping)
        if parentrevmeta is None:
            return NULL_REVISION
        return parentrevmeta.get_revision_id(mapping)

    def estimate_bzr_fileprop_ancestors(self):
        """Estimate how many ancestors with bzr file properties this revision has.

        """
        if self.metabranch is not None and not self.metabranch.consider_bzr_fileprops(self):
            # This revisions descendant doesn't have bzr fileprops set, so this one can't have them either.
            return 0
        return estimate_bzr_ancestors(self.get_fileprops())

    def estimate_svk_fileprop_ancestors(self):
        if self.metabranch is not None and not self.metabranch.consider_svk_fileprops(self):
            # This revisions descendant doesn't have svk fileprops set, so this one can't have them either.
            return 0
        return estimate_svk_ancestors(self.get_fileprops())

    def is_bzr_revision(self):
        """Determine (with as few network requests as possible) if this is a bzr revision.

        """
        order = []
        # If the server already sent us all revprops, look at those first
        if self._log.quick_revprops:
            order.append(lambda: is_bzr_revision_revprops(self.get_revprops()))
        if self.metabranch is None or self.metabranch.consider_bzr_fileprops(self) == True:
            order.append(lambda: is_bzr_revision_fileprops(self.get_changed_fileprops()))
        # Only look for revprops if they could've been committed
        if (not self._log.quick_revprops and 
                self.repository.check_revprops):
            order.append(lambda: is_bzr_revision_revprops(self.get_revprops()))
        for fn in order:
            ret = fn()
            if ret is not None:
                return ret
        return None

    def get_bzr_merges(self, mapping):
        return mapping.get_rhs_parents(self.branch_path, self.get_revprops(), self.get_changed_fileprops())

    def get_svk_merges(self, mapping):
        if not self.branch_path in self.get_paths():
            return ()

        current = self.get_fileprops().get(SVN_PROP_SVK_MERGE, "")
        if current == "":
            return ()

        previous = self.get_previous_fileprops().get(SVN_PROP_SVK_MERGE, "")

        ret = []
        for feature in svk_features_merged_since(current, previous):
            # We assume svk:merge is only relevant on non-bzr-svn revisions. 
            # If this is a bzr-svn revision, the bzr-svn properties 
            # would be parsed instead.
            #
            # This saves one svn_get_dir() call.
            revid = svk_feature_to_revision_id(feature, mapping)
            if revid is not None:
                ret.append(revid)

        return tuple(ret)

    def get_rhs_parents(self, mapping):
        """Determine the right hand side parents for this revision.

        """
        if self.is_bzr_revision():
            return self.get_bzr_merges(mapping)

        return self.get_svk_merges(mapping)

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

    def get_signature(self):
        return self.get_revprops().get(SVN_REVPROP_BZR_SIGNATURE)

    def get_revision(self, mapping):
        parent_ids = self.get_parent_ids(mapping)
        if parent_ids == (NULL_REVISION,):
            parent_ids = ()
        rev = Revision(revision_id=self.get_revision_id(mapping), 
                       parent_ids=parent_ids,
                       inventory_sha1="")

        rev.svn_meta = self
        rev.svn_mapping = mapping

        mapping.import_revision(self.get_revprops(), self.get_changed_fileprops(), self.uuid, self.branch_path, 
                                self.revnum, rev)

        return rev

    def get_fileid_map(self, mapping):
        return mapping.import_fileid_map(self.get_revprops(), self.get_changed_fileprops())

    def __hash__(self):
        return hash((self.__class__, self.uuid, self.branch_path, self.revnum))


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


class RevisionMetadataBranch(object):
    """Describes a Bazaar-like branch in a Subversion repository."""

    def __init__(self, mapping):
        self._revs = []
        self.mapping = mapping

    def consider_bzr_fileprops(self, revmeta):
        """Check whether bzr file properties should be analysed for 
        this revmeta.
        """
        i = self._revs.index(revmeta)
        for desc in self._revs[i+1:]:
            if desc.knows_fileprops():
                return (desc.estimate_bzr_fileprop_ancestors() > 0)
        # assume the worst
        return True

    def consider_svk_fileprops(self, revmeta):
        """Check whether svk file propertise should be analysed for 
        this revmeta.
        """
        i = self._revs.index(revmeta)
        for desc in self._revs[i+1:]:
            if desc.knows_fileprops():
                return (desc.estimate_svk_fileprop_ancestors() > 0)
        # assume the worst
        return True

    def get_lhs_parent(self, revmeta):
        i = self._revs.index(revmeta)
        try:
            return self._revs[i+1]
        except IndexError:
            return None

    def append(self, revmeta):
        self._revs.append(revmeta)


class RevisionMetadataProvider(object):

    def __init__(self, repository):
        self._revmeta_cache = {}
        self.repository = repository

    def get_revision(self, path, revnum, changes=None, revprops=None, changed_fileprops=None, 
                     metabranch=None):
        if (path, revnum) in self._revmeta_cache:
            cached = self._revmeta_cache[path,revnum]
            if changes is not None:
                cached.paths = changes
            if cached._changed_fileprops is None:
                cached._changed_fileprops = changed_fileprops
            return self._revmeta_cache[path,revnum]

        ret = RevisionMetadata(self.repository, path, revnum, changes, revprops, 
                                   changed_fileprops=changed_fileprops, 
                                   metabranch=metabranch)
        self._revmeta_cache[path,revnum] = ret
        return ret

