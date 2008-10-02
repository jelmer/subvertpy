# Copyright (C) 2006 by Jelmer Vernooij
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""Upgrading revisions made with older versions of the mapping."""

from bzrlib import ui
from bzrlib.errors import BzrError, InvalidRevisionId
from bzrlib.revision import Revision
from bzrlib.trace import info

import itertools
from bzrlib.plugins.svn.mapping import mapping_registry


def set_revprops(repository, new_mapping, from_revnum=0, to_revnum=None):
    """Set bzr-svn revision properties for existing bzr-svn revisions.

    :param repository: Subversion Repository object.
    :param new_mapping: Mapping to upgrade to
    """
    from bzrlib.plugins.svn import changes, logwalker, mapping
    from bzrlib.plugins.svn.subvertpy import properties
    if to_revnum is None:
        to_revnum = repository.get_latest_revnum()
    graph = repository.get_graph()
    assert from_revnum <= to_revnum
    pb = ui.ui_factory.nested_progress_bar()
    logcache = getattr(repository._log, "cache", None)
    try:
        for (paths, revnum, revprops) in repository._log.iter_changes(None, to_revnum, from_revnum, pb=pb):
            if revnum == 0:
                # Never a bzr-svn revision
                continue
            # Find the root path of the change
            bp = changes.changes_root(paths.keys())
            if bp is None:
                fileprops = {}
            else:
                fileprops = logwalker.lazy_dict({}, repository.branchprop_list.get_properties, bp, revnum)
            old_mapping = mapping.find_mapping(revprops, fileprops)
            if old_mapping is None:
                # Not a bzr-svn revision
                if not mapping.SVN_REVPROP_BZR_SKIP in revprops:
                    repository.transport.change_rev_prop(revnum, mapping.SVN_REVPROP_BZR_SKIP, "")
                continue
            if old_mapping == new_mapping:
                # Already the latest mapping
                continue
            assert old_mapping.can_use_revprops or bp is not None
            new_revprops = dict(revprops.items())
            revmeta = repository._revmeta_provider.get_revision(bp, revnum, changes, revprops, fileprops)
            rev = revmeta.get_revision(old_mapping)
            revno = graph.find_distance_to_null(rev.revision_id, [])
            assert bp is not None
            new_mapping.export_revision(bp, rev.timestamp, rev.timezone, rev.committer, rev.properties, rev.revision_id, revno, rev.parent_ids, new_revprops, None)
            new_mapping.export_fileid_map(old_mapping.import_fileid_map(revprops, fileprops), 
                new_revprops, None)
            new_mapping.export_text_parents(old_mapping.import_text_parents(revprops, fileprops), new_revprops, None)
            new_mapping.export_text_revisions(old_mapping.import_text_revisions(revprops, fileprops), new_revprops, None)
            if rev.message != mapping.parse_svn_log(revprops.get(properties.PROP_REVISION_LOG)):
                new_mapping.export_message(rev.message, new_revprops, None)
            changed_revprops = dict(filter(lambda (k,v): k not in revprops or revprops[k] != v, new_revprops.items()))
            if logcache is not None:
                logcache.drop_revprops(revnum)
            for k, v in changed_revprops.items():
                repository.transport.change_rev_prop(revnum, k, v)
            # Might as well update the cache while we're at it
    finally:
        pb.finished()
