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
from bzrlib.revision import NULL_REVISION, Revision

from bzrlib.plugins.svn import changes, core, errors as svn_errors, logwalker, properties
from bzrlib.plugins.svn.mapping import is_bzr_revision_fileprops, is_bzr_revision_revprops, estimate_bzr_ancestors, SVN_REVPROP_BZR_SIGNATURE
from bzrlib.plugins.svn.svk import (SVN_PROP_SVK_MERGE, svk_features_merged_since, 
                 parse_svk_feature, estimate_svk_ancestors)

def full_paths(find_children, paths, bp, from_bp, from_rev):
    """Generate the changes creating a specified branch path.

    :param find_children: Function that recursively lists all children 
                          of a path in a revision.
    :param paths: Paths dictionary to update
    :param bp: Branch path to create.
    :param from_bp: Path to look up children in
    :param from_rev: Revision to look up children in.
    """
    for c in find_children(from_bp, from_rev):
        paths[changes.rebase_path(c, from_bp, bp)] = ('A', None, -1)
    return paths


class RevisionMetadata(object):
    """Object describing a revision with bzr semantics in a Subversion repository."""

    def __init__(self, repository, check_revprops, get_fileprops_fn, logwalker, uuid, 
                 branch_path, revnum, paths, revprops, changed_fileprops=None, metabranch=None):
        self.repository = repository
        self.check_revprops = check_revprops
        self._get_fileprops_fn = get_fileprops_fn
        self._log = logwalker
        self.branch_path = branch_path
        self._paths = paths
        self.revnum = revnum
        self._revprops = revprops
        self._changed_fileprops = changed_fileprops
        self.metabranch = metabranch
        self.uuid = uuid

    def __eq__(self, other):
        return (type(self) == type(other) and 
                self.branch_path == other.branch_path and
                self.revnum == other.revnum and
                self.uuid == other.uuid)

    def __repr__(self):
        return "<RevisionMetadata for revision %d in repository %s>" % (self.revnum, repr(self.uuid))

    def get_paths(self):
        if self._paths is None:
            self._paths = self._log.get_revision_paths(self.revnum)
        return self._paths

    def get_revision_id(self, mapping):
        if mapping.roundtripping:
            # See if there is a bzr:revision-id revprop set
            try:
                (bzr_revno, revid) = mapping.get_revision_id(self.branch_path, self.get_revprops(), self.get_changed_fileprops())
            except core.SubversionException, (_, num):
                if num == svn_errors.ERR_FS_NO_SUCH_REVISION:
                    raise errors.NoSuchRevision(path, revnum)
                raise
        else:
            revid = None

        # Or generate it
        if revid is None:
            return mapping.revision_id_foreign_to_bzr((self.uuid, self.revnum, self.branch_path))

        return revid

    def get_fileprops(self):
        return self._get_fileprops_fn(self.branch_path, self.revnum)

    def get_revprops(self):
        if self._revprops is None:
            self._revprops = self._log.revprop_list(self.revnum)

        return self._revprops

    def knows_fileprops(self):
        fileprops = self.get_fileprops()
        return isinstance(fileprops, dict) or fileprops.is_loaded

    def knows_revprops(self):
        revprops = self.get_revprops()
        return isinstance(revprops, dict) or revprops.is_loaded

    def get_previous_fileprops(self):
        prev = changes.find_prev_location(self.get_paths(), self.branch_path, self.revnum)
        if prev is None:
            return {}
        (prev_path, prev_revnum) = prev
        return self._get_fileprops_fn(prev_path, prev_revnum)

    def get_changed_fileprops(self):
        if self._changed_fileprops is None:
            if self.branch_path in self.get_paths():
                self._changed_fileprops = logwalker.lazy_dict({}, properties.diff, self.get_fileprops(), self.get_previous_fileprops())
            else:
                self._changed_fileprops = {}
        return self._changed_fileprops

    def get_lhs_parent_revmeta(self, mapping):
        assert (mapping.is_branch(self.branch_path) or 
                mapping.is_tag(self.branch_path)), "%s not valid in %r" % (self.branch_path, mapping)
        if self.metabranch is not None and self.metabranch.mapping == mapping:
            # Perhaps the metabranch already has the parent?
            parentrevmeta = self.metabranch.get_lhs_parent(self)
            if parentrevmeta is not None:
                return parentrevmeta
        # FIXME: Don't use self.repository.branch_prev_location,
        #        since it browses history
        return self.repository._revmeta_provider.branch_prev_location(self, mapping)

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

    def is_bzr_revision_revprops(self):
        return is_bzr_revision_revprops(self.get_revprops())

    def is_bzr_revision_fileprops(self):
        return is_bzr_revision_fileprops(self.get_changed_fileprops())

    def is_bzr_revision(self):
        """Determine (with as few network requests as possible) if this is a bzr revision.

        """
        order = []
        # If the server already sent us all revprops, look at those first
        if self._log.quick_revprops:
            order.append(self.is_bzr_revision_revprops)
        if self.metabranch is None or self.metabranch.consider_bzr_fileprops(self) == True:
            order.append(self.is_bzr_revision_fileprops)
        # Only look for revprops if they could've been committed
        if (not self._log.quick_revprops and self.check_revprops):
            order.append(self.is_bzr_revision_revprops)
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
        lhs_parent = self.get_lhs_parent(mapping)

        if lhs_parent == NULL_REVISION:
            return (NULL_REVISION,)
        else:
            return (lhs_parent,) + self.get_rhs_parents(mapping)

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


class CachingRevisionMetadata(RevisionMetadata):

    def __init__(self, repository, *args, **kwargs):
        super(CachingRevisionMetadata, self).__init__(repository, *args, **kwargs)
        self._parents_cache = getattr(self.repository._real_parents_provider, "_cache", None)
        self._revid_cache = self.repository.revmap.cache

    def get_revision_id(self, mapping):
        # Look in the cache to see if it already has a revision id
        revid = self._revid_cache.lookup_branch_revnum(self.revnum, self.branch_path, mapping.name)
        if revid is not None:
            return revid

        revid = super(CachingRevisionMetadata, self).get_revision_id(mapping)

        self._revid_cache.insert_revid(revid, self.branch_path, self.revnum, self.revnum, mapping.name)
        self._revid_cache.commit_conditionally()
        return revid

    def get_parent_ids(self, mapping):
        myrevid = self.get_revision_id(mapping)

        if self._parents_cache is not None:
            parent_ids = self._parents_cache.lookup_parents(myrevid)
            if parent_ids is not None:
                return parent_ids

        parent_ids = super(CachingRevisionMetadata, self).get_parent_ids(mapping)

        self._parents_cache.insert_parents(myrevid, parent_ids)

        return parent_ids


def svk_feature_to_revision_id(feature, mapping):
    """Convert a SVK feature to a revision id for this repository.

    :param feature: SVK feature.
    :return: revision id.
    """
    try:
        (uuid, bp, revnum) = parse_svk_feature(feature)
    except svn_errors.InvalidPropertyValue:
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
        for desc in self._revs[:i]:
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

    def __init__(self, repository, cache, check_revprops):
        self._revmeta_cache = {}
        self.repository = repository
        self._get_fileprops_fn = self.repository.branchprop_list.get_properties
        self._log = repository._log
        self.check_revprops = check_revprops
        if cache:
            self._revmeta_cls = CachingRevisionMetadata
        else:
            self._revmeta_cls = RevisionMetadata

    def get_revision(self, path, revnum, changes=None, revprops=None, changed_fileprops=None, 
                     metabranch=None):
        if (path, revnum) in self._revmeta_cache:
            cached = self._revmeta_cache[path,revnum]
            if changes is not None:
                cached.paths = changes
            if cached._changed_fileprops is None:
                cached._changed_fileprops = changed_fileprops
            return self._revmeta_cache[path,revnum]

        ret = self._revmeta_cls(self.repository, self.check_revprops, self._get_fileprops_fn,
                               self._log, self.repository.uuid, path, revnum, changes, revprops, 
                               changed_fileprops=changed_fileprops, 
                               metabranch=metabranch)
        self._revmeta_cache[path,revnum] = ret
        return ret

    def iter_changes(self, branch_path, from_revnum, to_revnum, mapping=None, pb=None, limit=0):
        """Iterate over all revisions backwards.
        
        :return: iterator that returns tuples with branch path, 
            changed paths, revision number, changed file properties and 
        """
        assert isinstance(branch_path, str)
        assert mapping is None or mapping.is_branch(branch_path) or mapping.is_tag(branch_path), \
                "Mapping %r doesn't accept %s as branch or tag" % (mapping, branch_path)
        assert from_revnum >= to_revnum

        bp = branch_path
        i = 0

        # Limit can't be passed on directly to LogWalker.iter_changes() 
        # because we're skipping some revs
        # TODO: Rather than fetching everything if limit == 2, maybe just 
        # set specify an extra X revs just to be sure?
        for (paths, revnum, revprops) in self._log.iter_changes([branch_path], from_revnum, to_revnum, 
                                                                pb=pb):
            assert bp is not None
            next = changes.find_prev_location(paths, bp, revnum)
            assert revnum > 0 or bp == ""
            assert mapping is None or mapping.is_branch(bp) or mapping.is_tag(bp), "%r is not a valid path" % bp

            if (next is not None and 
                not (mapping is None or mapping.is_branch(next[0]) or mapping.is_tag(next[0]))):
                # Make it look like the branch started here if the mapping 
                # doesn't support weird paths as branches
                lazypaths = logwalker.lazy_dict(paths, full_paths, self._log.find_children, paths, bp, next[0], next[1])
                paths[bp] = ('A', None, -1)

                yield (bp, lazypaths, revnum, revprops)
                return
                     
            if changes.changes_path(paths, bp, False):
                yield (bp, paths, revnum, revprops)
                i += 1
                if limit != 0 and limit == i:
                    break

            if next is None:
                bp = None
            else:
                bp = next[0]

    def get_mainline(self, branch_path, revnum, mapping, pb=None):
        return list(self.iter_reverse_branch_changes(branch_path, revnum, to_revnum=0, mapping=mapping, pb=pb))

    def branch_prev_location(self, revmeta, mapping):
        iterator = self.iter_reverse_branch_changes(revmeta.branch_path, revmeta.revnum, to_revnum=0, mapping=mapping, limit=2)
        firstrevmeta = iterator.next()
        assert revmeta == firstrevmeta
        try:
            parentrevmeta = iterator.next()
            if (not mapping.is_branch(parentrevmeta.branch_path) and
                not mapping.is_tag(parentrevmeta.branch_path)):
                return None
            return parentrevmeta
        except StopIteration:
            return None

    def iter_reverse_branch_changes(self, branch_path, from_revnum, to_revnum, 
                                    mapping=None, pb=None, limit=0):
        """Return all the changes that happened in a branch 
        until branch_path,revnum. 

        :return: iterator that returns RevisionMetadata objects.
        """
        assert mapping is None or mapping.is_branch(branch_path) or mapping.is_tag(branch_path)
        history_iter = self.iter_changes(branch_path, from_revnum, to_revnum, 
                                         mapping, pb=pb, limit=limit)
        metabranch = RevisionMetadataBranch(mapping)
        prev = None
        # Always make sure there is one more revision in the metabranch
        # so the yielded rev can find its left hand side parent.
        for (bp, paths, revnum, revprops) in history_iter:
            ret = self.get_revision(bp, revnum, paths, revprops, metabranch=metabranch)
            metabranch.append(ret)
            if prev is not None:
                yield prev
            prev = ret
        if prev is not None:
            yield prev

    def iter_all_changes(self, layout, mapping, from_revnum, to_revnum=0, pb=None):
        assert from_revnum >= to_revnum
        metabranches = {}
        if mapping is None:
            mapping_check_path = lambda x:True
        else:
            mapping_check_path = lambda x: mapping.is_branch(x) or mapping.is_tag(x)
        # Layout decides which ones to pick up
        # Mapping decides which ones to keep
        def get_metabranch(bp):
            if not bp in metabranches:
                metabranches[bp] = RevisionMetadataBranch(mapping)
            return metabranches[bp]
        unusual = set()
        for (paths, revnum, revprops) in self._log.iter_changes(None, from_revnum, to_revnum, pb=pb):
            bps = {}
            if pb:
                pb.update("discovering revisions", revnum, from_revnum-revnum)

            for p in sorted(paths):
                action = paths[p][0]

                try:
                    (_, _, bp, ip) = layout.parse(p)
                except errors.NotBranchError:
                    pass
                    for u in unusual:
                        if p.startswith("%s/" % u):
                            bps[u] = metabranches[u]
                else:
                    if action != 'D' or ip != "":
                        bps[bp] = get_metabranch(bp)
            
            # Apply renames and the like for the next round
            for new_name, old_name in changes.apply_reverse_changes(metabranches.keys(), paths):
                if new_name in unusual:
                    unusual.remove(new_name)
                if old_name is None: 
                    # didn't exist previously
                    del metabranches[new_name]
                else:
                    data = metabranches[new_name]
                    del metabranches[new_name]
                    if mapping_check_path(old_name):
                        metabranches[old_name] = data
                        if not layout.is_branch_or_tag(old_name):
                            unusual.add(old_name)

            for bp in bps:
                revmeta = self.get_revision(bp, revnum, paths, revprops, metabranch=bps[bp])
                bps[bp].append(revmeta)
                yield revmeta
    
        # Make sure commit 0 is processed
        if to_revnum == 0 and layout.is_branch_or_tag(""):
            bps[""] = get_metabranch("")
            yield self.get_revision("", 0, {"": ('A', None, -1)}, {}, metabranch=bps[""])
