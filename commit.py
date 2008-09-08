# Copyright (C) 2006-2008 Jelmer Vernooij <jelmer@samba.org>

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
"""Committing and pushing to Subversion repositories."""

from bzrlib import debug, urlutils, ui
from bzrlib.branch import Branch
from bzrlib.errors import (BzrError, InvalidRevisionId, DivergedBranches, 
                           UnrelatedBranches, AppendRevisionsOnlyViolation,
                           NoSuchRevision)
from bzrlib.inventory import Inventory
from bzrlib.repository import RootCommitBuilder, InterRepository, Repository
from bzrlib.revision import NULL_REVISION, ensure_null
from bzrlib.trace import mutter, warning

from cStringIO import StringIO

from bzrlib.plugins.svn import core, mapping, properties
from bzrlib.plugins.svn.core import SubversionException
from bzrlib.plugins.svn.delta import send_stream
from bzrlib.plugins.svn.errors import ChangesRootLHSHistory, MissingPrefix, RevpropChangeFailed, ERR_FS_TXN_OUT_OF_DATE
from bzrlib.plugins.svn.svk import (
    generate_svk_feature, serialize_svk_features, 
    parse_svk_features, SVN_PROP_SVK_MERGE)
from bzrlib.plugins.svn.logwalker import lazy_dict
from bzrlib.plugins.svn.mapping import mapping_registry
from bzrlib.plugins.svn.repository import SvnRepositoryFormat, SvnRepository

def _revision_id_to_svk_feature(revid):
    """Create a SVK feature identifier from a revision id.

    :param revid: Revision id to convert.
    :return: Matching SVK feature identifier.
    """
    assert isinstance(revid, str)
    (uuid, branch, revnum, _) = mapping_registry.parse_revision_id(revid)
    # TODO: What about renamed revisions? Should use 
    # repository.lookup_revision_id here.
    return generate_svk_feature(uuid, branch, revnum)


def _check_dirs_exist(transport, bp_parts, base_rev):
    """Make sure that the specified directories exist.

    :param transport: SvnRaTransport to use.
    :param bp_parts: List of directory names in the format returned by 
        os.path.split()
    :param base_rev: Base revision to check.
    :return: List of the directories that exists in base_rev.
    """
    for i in range(len(bp_parts), 0, -1):
        current = bp_parts[:i]
        path = "/".join(current).strip("/")
        assert isinstance(path, str)
        if transport.check_path(path, base_rev) == core.NODE_DIR:
            return current
    return []


def update_svk_features(oldvalue, merges):
    old_svk_features = parse_svk_features(oldvalue)
    svk_features = set(old_svk_features)

    # SVK compatibility
    for merge in merges:
        try:
            svk_features.add(_revision_id_to_svk_feature(merge))
        except InvalidRevisionId:
            pass

    if old_svk_features != svk_features:
        return serialize_svk_features(svk_features)
    return None


def update_mergeinfo(repository, graph, oldvalue, baserevid, merges):
    pb = ui.ui_factory.nested_progress_bar()
    try:
        mergeinfo = properties.parse_mergeinfo_property(oldvalue)
        for i, merge in enumerate(merges):
            pb.update("updating mergeinfo property", i, len(merges))
            for (revid, parents) in graph.iter_ancestry([merge]):
                if graph.is_ancestor(revid, baserevid):
                    break
                try:
                    (path, revnum, mapping) = repository.lookup_revision_id(revid)
                except NoSuchRevision:
                    break

                properties.mergeinfo_add_revision(mergeinfo, "/" + path, revnum)
    finally:
        pb.finished()
    newvalue = properties.generate_mergeinfo_property(mergeinfo)
    if newvalue != oldvalue:
        return newvalue
    return None


def set_svn_revprops(transport, revnum, revprops):
    """Attempt to change the revision properties on the
    specified revision.

    :param transport: SvnRaTransport connected to target repository
    :param revnum: Revision number of revision to change metadata of.
    :param revprops: Dictionary with revision properties to set.
    """
    for (name, value) in revprops.items():
        try:
            transport.change_rev_prop(revnum, name, value)
        except SubversionException, (_, ERR_REPOS_DISABLED_FEATURE):
            raise RevpropChangeFailed(name)


class SvnCommitBuilder(RootCommitBuilder):
    """Commit Builder implementation wrapped around svn_delta_editor. """

    def __init__(self, repository, branch_path, parents, config, timestamp, 
                 timezone, committer, revprops, revision_id, old_inv=None,
                 push_metadata=True, graph=None, opt_signature=None,
                 append_revisions_only=True):
        """Instantiate a new SvnCommitBuilder.

        :param repository: SvnRepository to commit to.
        :param branch: branch path to commit to.
        :param parents: List of parent revision ids.
        :param config: Branch configuration to use.
        :param timestamp: Optional timestamp recorded for commit.
        :param timezone: Optional timezone for timestamp.
        :param committer: Optional committer to set for commit.
        :param revprops: Bazaar revision properties to set.
        :param revision_id: Revision id for the new revision.
        :param old_inv: Optional revision on top of which 
            the commit is happening
        :param push_metadata: Whether or not to push all bazaar metadata
                              (in svn file properties, etc).
        :param graph: Optional graph object
        :param opt_signature: Optional signature to write.
        """
        super(SvnCommitBuilder, self).__init__(repository, parents, 
            config, timestamp, timezone, committer, revprops, revision_id)
        self.branch_path = branch_path
        self.push_metadata = push_metadata
        self._append_revisions_only = append_revisions_only
        self._text_parents = {}

        # Gather information about revision on top of which the commit is 
        # happening
        if parents == []:
            self.base_revid = NULL_REVISION
        else:
            self.base_revid = parents[0]

        if graph is None:
            graph = self.repository.get_graph()
        self.base_revno = graph.find_distance_to_null(self.base_revid, [])
        if self.base_revid == NULL_REVISION:
            self._base_revmeta = None
            self._base_branch_props = {}
            self.base_revnum = -1
            self.base_path = None
            self.base_mapping = repository.get_mapping()
        else:
            (self.base_path, self.base_revnum, self.base_mapping) = \
                repository.lookup_revision_id(self.base_revid)
            self._base_revmeta = self.repository._revmeta_provider.get_revision(self.base_path, self.base_revnum)
            self._base_branch_props = self._base_revmeta.get_fileprops()

        if old_inv is None:
            if self.base_revid == NULL_REVISION:
                self.old_inv = Inventory(root_id=None)
            else:
                self.old_inv = self.repository.get_inventory(self.base_revid)
        else:
            self.old_inv = old_inv
            # Not all repositories appear to set Inventory.revision_id, 
            # so allow None as well.
            assert self.old_inv.revision_id in (None, self.base_revid), \
                    "%s != %s" % (self.old_inv.revision_id, self.base_revid)

        # Determine revisions merged in this one
        merges = filter(lambda x: x != self.base_revid, parents)

        self.visit_dirs = set()
        self.modified_files = {}
        self.supports_custom_revprops = self.repository.transport.has_capability("commit-revprops")
        if (self.supports_custom_revprops is None and 
            self.base_mapping.can_use_revprops and 
            self.repository.seen_bzr_revprops()):
            raise BzrError("Please upgrade your Subversion client libraries to 1.5 or higher to be able to commit with Subversion mapping %s" % self.base_mapping.name)

        if self.supports_custom_revprops == True:
            self._svn_revprops = {}
            # If possible, submit signature directly
            if opt_signature is not None:
                self._svn_revprops[mapping.SVN_REVPROP_BZR_SIGNATURE] = opt_signature
        else:
            self._svn_revprops = None
        self._svnprops = lazy_dict({}, lambda: dict(self._base_branch_props.items()))
        self.base_mapping.export_revision(
            self.branch_path, timestamp, timezone, committer, revprops, 
            revision_id, self.base_revno+1, parents, self._svn_revprops, self._svnprops)

        if len(merges) > 0:
            new_svk_merges = update_svk_features(self._base_branch_props.get(SVN_PROP_SVK_MERGE, ""), merges)
            if new_svk_merges is not None:
                self._svnprops[SVN_PROP_SVK_MERGE] = new_svk_merges

            new_mergeinfo = update_mergeinfo(self.repository, graph, self._base_branch_props.get(properties.PROP_MERGEINFO, ""), self.base_revid, merges)
            if new_mergeinfo is not None:
                self._svnprops[properties.PROP_MERGEINFO] = new_mergeinfo

    @staticmethod
    def mutter(text, *args):
        if 'commit' in debug.debug_flags:
            mutter(text, *args)

    def _generate_revision_if_needed(self):
        """See CommitBuilder._generate_revision_if_needed()."""

    def finish_inventory(self):
        """See CommitBuilder.finish_inventory()."""

    def _file_process(self, file_id, contents, file_editor):
        """Pass the changes to a file to the Subversion commit editor.

        :param file_id: Id of the file to modify.
        :param contents: Contents of the file.
        :param file_editor: Subversion FileEditor object.
        """
        assert file_editor is not None
        txdelta = file_editor.apply_textdelta()
        digest = send_stream(StringIO(contents), txdelta)
        if 'validate' in debug.debug_flags:
            from fetch import md5_strings
            assert digest == md5_strings(contents)

    def _dir_process(self, path, file_id, dir_editor):
        """Pass the changes to a directory to the commit editor.

        :param path: Path (from repository root) to the directory.
        :param file_id: File id of the directory
        :param dir_editor: Subversion DirEditor object.
        """
        assert dir_editor is not None
        # Loop over entries of file_id in self.old_inv
        # remove if they no longer exist with the same name
        # or parents
        if file_id in self.old_inv:
            for child_name in self.old_inv[file_id].children:
                child_ie = self.old_inv.get_child(file_id, child_name)
                # remove if...
                if (
                    # ... path no longer exists
                    not child_ie.file_id in self.new_inventory or 
                    # ... parent changed
                    child_ie.parent_id != self.new_inventory[child_ie.file_id].parent_id or
                    # ... name changed
                    self.new_inventory[child_ie.file_id].name != child_name):
                    self.mutter('removing %r(%r)', (child_name, child_ie.file_id))
                    dir_editor.delete_entry(
                        urlutils.join(self.branch_path, path, child_name), 
                        self.base_revnum)

        # Loop over file children of file_id in self.new_inventory
        for child_name in self.new_inventory[file_id].children:
            child_ie = self.new_inventory.get_child(file_id, child_name)
            assert child_ie is not None

            if not (child_ie.kind in ('file', 'symlink')):
                continue

            new_child_path = self.new_inventory.id2path(child_ie.file_id).encode("utf-8")
            full_new_child_path = urlutils.join(self.branch_path, 
                                  new_child_path)
            # add them if they didn't exist in old_inv 
            if not child_ie.file_id in self.old_inv:
                self.mutter('adding %s %r', child_ie.kind, new_child_path)
                child_editor = dir_editor.add_file(full_new_child_path)

            # copy if they existed at different location
            elif (self.old_inv.id2path(child_ie.file_id) != new_child_path or
                    self.old_inv[child_ie.file_id].parent_id != child_ie.parent_id):
                self.mutter('copy %s %r -> %r', child_ie.kind, 
                                  self.old_inv.id2path(child_ie.file_id), 
                                  new_child_path)
                child_editor = dir_editor.add_file(
                        full_new_child_path, 
                    urlutils.join(self.repository.transport.svn_url, self.base_path, self.old_inv.id2path(child_ie.file_id)),
                    self.base_revnum)

            # open if they existed at the same location
            elif child_ie.file_id in self.modified_files:
                self.mutter('open %s %r', child_ie.kind, new_child_path)

                child_editor = dir_editor.open_file(
                        full_new_child_path, self.base_revnum)

            else:
                # Old copy of the file was retained. No need to send changes
                child_editor = None

            if child_ie.file_id in self.old_inv:
                old_executable = self.old_inv[child_ie.file_id].executable
                old_special = (self.old_inv[child_ie.file_id].kind == 'symlink')
            else:
                old_special = False
                old_executable = False

            if child_editor is not None:
                if old_executable != child_ie.executable:
                    if child_ie.executable:
                        value = properties.PROP_EXECUTABLE_VALUE
                    else:
                        value = None
                    child_editor.change_prop(
                            properties.PROP_EXECUTABLE, value)

                if old_special != (child_ie.kind == 'symlink'):
                    if child_ie.kind == 'symlink':
                        value = properties.PROP_SPECIAL_VALUE
                    else:
                        value = None

                    child_editor.change_prop(
                            properties.PROP_SPECIAL, value)

            # handle the file
            if child_ie.file_id in self.modified_files:
                self._file_process(child_ie.file_id, 
                    self.modified_files[child_ie.file_id], child_editor)

            if child_editor is not None:
                child_editor.close()

        # Loop over subdirectories of file_id in self.new_inventory
        for child_name in self.new_inventory[file_id].children:
            child_ie = self.new_inventory.get_child(file_id, child_name)
            if child_ie.kind != 'directory':
                continue

            new_child_path = self.new_inventory.id2path(child_ie.file_id)
            # add them if they didn't exist in old_inv 
            if not child_ie.file_id in self.old_inv:
                self.mutter('adding dir %r', child_ie.name)
                child_editor = dir_editor.add_directory(
                    urlutils.join(self.branch_path, 
                                  new_child_path))

            # copy if they existed at different location
            elif self.old_inv.id2path(child_ie.file_id) != new_child_path:
                old_child_path = self.old_inv.id2path(child_ie.file_id)
                self.mutter('copy dir %r -> %r', old_child_path, new_child_path)
                child_editor = dir_editor.add_directory(
                    urlutils.join(self.branch_path, new_child_path),
                    urlutils.join(self.repository.transport.svn_url, self.base_path, old_child_path), self.base_revnum)

            # open if they existed at the same location and 
            # the directory was touched
            elif child_ie.file_id in self.visit_dirs:
                self.mutter('open dir %r', new_child_path)

                child_editor = dir_editor.open_directory(
                        urlutils.join(self.branch_path, new_child_path), 
                        self.base_revnum)
            else:
                continue

            # Handle this directory
            self._dir_process(new_child_path, child_ie.file_id, child_editor)

            child_editor.close()

    def open_branch_editors(self, root, elements, existing_elements, 
                           base_path, base_rev, replace_existing):
        """Open a specified directory given an editor for the repository root.

        :param root: Editor for the repository root
        :param elements: List of directory names to open
        :param existing_elements: List of directory names that exist
        :param base_path: Path to base top-level branch on
        :param base_rev: Revision of path to base top-level branch on
        :param replace_existing: Whether the current branch should be replaced
        """
        ret = [root]

        self.mutter('opening branch %r (base %r:%r)', elements, base_path, 
                                                   base_rev)

        # Open paths leading up to branch
        for i in range(0, len(elements)-1):
            # Does directory already exist?
            ret.append(ret[-1].open_directory(
                "/".join(existing_elements[0:i+1]), -1))

        if (len(existing_elements) != len(elements) and
            len(existing_elements)+1 != len(elements)):
            raise MissingPrefix("/".join(elements), "/".join(existing_elements))

        # Branch already exists and stayed at the same location, open:
        # TODO: What if the branch didn't change but the new revision 
        # was based on an older revision of the branch?
        # This needs to also check that base_rev was the latest version of 
        # branch_path.
        if (len(existing_elements) == len(elements) and 
            not replace_existing):
            ret.append(ret[-1].open_directory(
                "/".join(elements), base_rev))
        else: # Branch has to be created
            # Already exists, old copy needs to be removed
            name = "/".join(elements)
            if replace_existing:
                if name == "":
                    raise ChangesRootLHSHistory()
                self.mutter("removing branch dir %r", name)
                ret[-1].delete_entry(name, -1)
            if base_path is not None:
                base_url = urlutils.join(self.repository.transport.svn_url, base_path)
            else:
                base_url = None
            self.mutter("adding branch dir %r", name)
            ret.append(ret[-1].add_directory(
                name, base_url, base_rev))

        return ret

    def _determine_texts_identity(self):
        # Store file ids
        def _dir_process_file_id(old_inv, new_inv, path, file_id):
            ret = []
            for child_name in new_inv[file_id].children:
                child_ie = new_inv.get_child(file_id, child_name)
                new_child_path = new_inv.id2path(child_ie.file_id)
                assert child_ie is not None

                if (not child_ie.file_id in old_inv or 
                    old_inv.id2path(child_ie.file_id) != new_child_path or
                    old_inv[child_ie.file_id].revision != child_ie.revision or
                    old_inv[child_ie.file_id].parent_id != child_ie.parent_id):
                    ret.append((child_ie.file_id, new_child_path, child_ie.revision, self._text_parents[child_ie.file_id]))

                if (child_ie.kind == 'directory' and 
                    child_ie.file_id in self.visit_dirs):
                    ret += _dir_process_file_id(old_inv, new_inv, new_child_path, child_ie.file_id)
            return ret

        fileids = {}
        text_parents = {}
        text_revisions = {}
        changes = []

        if (self.old_inv.root is None or 
            self.new_inventory.root.file_id != self.old_inv.root.file_id):
            changes.append((self.new_inventory.root.file_id, "", self.new_inventory.root.revision, self._text_parents[self.new_inventory.root.file_id]))

        changes += _dir_process_file_id(self.old_inv, self.new_inventory, "", self.new_inventory.root.file_id)

        for id, path, revid, parents in changes:
            fileids[path] = id
            if revid is not None and revid != self.base_revid and revid != self._new_revision_id:
                text_revisions[path] = revid
            if ((id not in self.old_inv and parents != []) or 
                (id in self.old_inv and parents != [self.base_revid])):
                text_parents[path] = parents
        return (fileids, text_revisions, text_parents)

    def commit(self, message):
        """Finish the commit.

        """
        def done(*args):
            """Callback that is called by the Subversion commit editor 
            once the commit finishes.

            :param revision_data: Revision metadata
            """
            self.revision_metadata = args
        
        bp_parts = self.branch_path.split("/")
        repository_latest_revnum = self.repository.get_latest_revnum()
        lock = self.repository.transport.lock_write(".")

        self._changed_fileprops = {}

        if self.push_metadata:
            (fileids, text_revisions, text_parents) = self._determine_texts_identity()

            self.base_mapping.export_text_revisions(text_revisions, self._svn_revprops, self._svnprops)
            self.base_mapping.export_text_parents(text_parents, self._svn_revprops, self._svnprops)
            self.base_mapping.export_fileid_map(fileids, self._svn_revprops, self._svnprops)
            if self._config.get_log_strip_trailing_newline():
                self.base_mapping.export_message(message, self._svn_revprops, self._svnprops)
                message = message.rstrip("\n")
        if not self.supports_custom_revprops:
            self._svn_revprops = {}
        self._svn_revprops[properties.PROP_REVISION_LOG] = message.encode("utf-8")

        try:
            # Shortcut - no need to see if dir exists if our base 
            # was the last revision in the repo. This situation 
            # happens a lot when pushing multiple subsequent revisions.
            if (self.base_revnum == self.repository.get_latest_revnum() and 
                self.base_path == self.branch_path):
                existing_bp_parts = bp_parts
            else:
                existing_bp_parts = _check_dirs_exist(self.repository.transport, 
                                              bp_parts, -1)
            self.revision_metadata = None
            for prop in self._svn_revprops:
                assert prop.split(":")[0] in ("bzr", "svk", "svn")
                if not properties.is_valid_property_name(prop):
                    warning("Setting property %r with invalid characters in name", prop)
            conn = self.repository.transport.get_connection()
            assert self.supports_custom_revprops or self._svn_revprops.keys() == [properties.PROP_REVISION_LOG], \
                    "revprops: %r" % self._svn_revprops.keys()
            self.editor = conn.get_commit_editor(
                    self._svn_revprops, done, None, False)
            try:
                root = self.editor.open_root(self.base_revnum)

                replace_existing = False
                # See whether the base of the commit matches the lhs parent
                # if not, we need to replace the existing directory
                if len(bp_parts) == len(existing_bp_parts):
                    if self.base_path is None or self.base_path.strip("/") != "/".join(bp_parts).strip("/"):
                        replace_existing = True
                    elif self.base_revnum < self.repository._log.find_latest_change(self.branch_path, repository_latest_revnum):
                        replace_existing = True

                if replace_existing and self._append_revisions_only:
                    raise AppendRevisionsOnlyViolation(urlutils.join(self.repository.base, self.branch_path))

                # TODO: Accept create_prefix argument
                branch_editors = self.open_branch_editors(root, bp_parts,
                    existing_bp_parts, self.base_path, self.base_revnum, 
                    replace_existing)

                self._dir_process("", self.new_inventory.root.file_id, 
                    branch_editors[-1])

                # Set all the revprops
                if self.push_metadata and self._svnprops.is_loaded:
                    for prop, value in self._svnprops.items():
                        if value == self._base_branch_props.get(prop):
                            continue
                        self._changed_fileprops[prop] = value
                        if not properties.is_valid_property_name(prop):
                            warning("Setting property %r with invalid characters in name", prop)
                        assert isinstance(value, str)
                        branch_editors[-1].change_prop(prop, value)
                        self.mutter("Setting root file property %r -> %r", prop, value)

                for dir_editor in reversed(branch_editors):
                    dir_editor.close()
            except:
                self.editor.abort()
                self.repository.transport.add_connection(conn)
                raise

            self.editor.close()
            self.repository.transport.add_connection(conn)
        finally:
            lock.unlock()

        (result_revision, result_date, result_author) = self.revision_metadata
        
        self._svn_revprops[properties.PROP_REVISION_AUTHOR] = result_author
        self._svn_revprops[properties.PROP_REVISION_DATE] = result_date

        self.repository._clear_cached_state(result_revision)

        self.mutter('commit %d finished. author: %r, date: %r',
               result_revision, result_author, 
                   result_date)

        override_svn_revprops = self._config.get_override_svn_revprops()
        if override_svn_revprops is not None:
            new_revprops = {}
            if properties.PROP_REVISION_AUTHOR in override_svn_revprops:
                new_revprops[properties.PROP_REVISION_AUTHOR] = self._committer.encode("utf-8")
            if properties.PROP_REVISION_DATE in override_svn_revprops:
                new_revprops[properties.PROP_REVISION_DATE] = properties.time_to_cstring(1000000*self._timestamp)
            set_svn_revprops(self.repository.transport, result_revision, new_revprops)
            self._svn_revprops.update(new_revprops)

        self.revmeta = self.repository._revmeta_provider.get_revision(self.branch_path, result_revision, 
                None, # FIXME: Generate changes dictionary
                revprops=self._svn_revprops,
                changed_fileprops=self._changed_fileprops,
                fileprops=self._svnprops,
                metabranch=None # FIXME: Determine from base_revmeta ?
                )

        revid = self.revmeta.get_revision_id(self.base_mapping)

        assert not self.push_metadata or self._new_revision_id is None or self._new_revision_id == revid
        return revid

    def record_entry_contents(self, ie, parent_invs, path, tree,
                              content_summary):
        """Record the content of ie from tree into the commit if needed.

        Side effect: sets ie.revision when unchanged

        :param ie: An inventory entry present in the commit.
        :param parent_invs: The inventories of the parent revisions of the
            commit.
        :param path: The path the entry is at in the tree.
        :param tree: The tree which contains this entry and should be used to 
            obtain content.
        :param content_summary: Summary data from the tree about the paths
                content - stat, length, exec, sha/link target. This is only
                accessed when the entry has a revision of None - that is when 
                it is a candidate to commit.
        """
        self._text_parents[ie.file_id] = []
        for parent_inv in parent_invs:
            if ie.file_id in parent_inv:
                self._text_parents[ie.file_id].append(parent_inv[ie.file_id].revision)
        self.new_inventory.add(ie)
        assert (ie.file_id not in self.old_inv or 
                self.old_inv[ie.file_id].revision is not None)
        version_recorded = (ie.revision is None)
        # If nothing changed since the lhs parent, return:
        if (ie.file_id in self.old_inv and ie == self.old_inv[ie.file_id] and 
            (ie.kind != 'directory' or ie.children == self.old_inv[ie.file_id].children)):
            return self._get_delta(ie, self.old_inv, self.new_inventory.id2path(ie.file_id)), version_recorded
        if ie.kind == 'file':
            self.modified_files[ie.file_id] = tree.get_file_text(ie.file_id)
        elif ie.kind == 'symlink':
            self.modified_files[ie.file_id] = "link %s" % ie.symlink_target
        elif ie.kind == 'directory':
            self.visit_dirs.add(ie.file_id)
        fid = ie.parent_id
        while fid is not None and fid not in self.visit_dirs:
            self.visit_dirs.add(fid)
            fid = self.new_inventory[fid].parent_id
        return self._get_delta(ie, self.old_inv, self.new_inventory.id2path(ie.file_id)), version_recorded


def replay_delta(builder, old_trees, new_tree):
    """Replays a delta to a commit builder.

    :param builder: The commit builder.
    :param old_tree: Original tree on top of which the delta should be applied
    :param new_tree: New tree that should be committed
    """
    for path, ie in new_tree.inventory.iter_entries():
        builder.record_entry_contents(ie.copy(), 
            [old_tree.inventory for old_tree in old_trees], 
            path, new_tree, None)
    builder.finish_inventory()


def create_branch_with_hidden_commit(repository, branch_path, revid, deletefirst=False):
    revprops = {properties.PROP_REVISION_LOG: "Create new branch."}
    revmeta, mapping = repository._get_revmeta(revid)
    fileprops = dict(revmeta.get_fileprops().items())
    mapping.export_hidden(revprops, fileprops)
    parent = urlutils.dirname(branch_path)
    conn = repository.transport.get_connection(parent)
    try:
        ci = conn.get_commit_editor(revprops)
        try:
            root = ci.open_root()
            if deletefirst:
                root.delete_entry(urlutils.basename(branch_path))
            branch_dir = root.add_directory(urlutils.basename(branch_path), urlutils.join(repository.base, revmeta.branch_path), revmeta.revnum)
            for k, v in properties.diff(fileprops, revmeta.get_fileprops()).items():
                branch_dir.change_prop(k, v)
            branch_dir.close()
            root.close()
        except:
            ci.abort()
            raise
        ci.close()
    finally:
        repository.transport.add_connection(conn)


def push_new(graph, target_repository, target_branch_path, source, stop_revision,
             push_metadata=True, append_revisions_only=False):
    """Push a revision into Subversion, creating a new branch.

    This will do a new commit in the target branch.

    :param graph: Repository graph.
    :param target_repository: Repository to push to
    :param target_branch_path: Path to create new branch at
    :param source: Source repository
    """
    assert isinstance(source, Repository)
    start_revid = stop_revision
    for revid in source.iter_reverse_revision_history(stop_revision):
        if target_repository.has_revision(revid):
            break
        start_revid = revid
    rev = source.get_revision(start_revid)
    if rev.parent_ids == []:
        start_revid_parent = NULL_REVISION
    else:
        start_revid_parent = rev.parent_ids[0]
    # If this is just intended to create a new branch
    mapping = target_repository.get_mapping()
    if (stop_revision != NULL_REVISION and stop_revision == start_revid and mapping.supports_hidden):
        create_branch_with_hidden_commit(target_repository, target_branch_path, start_revid, mapping)
    else:
        return push_revision_tree(graph, target_repository, target_branch_path, 
                              target_repository.get_config(), 
                              source, start_revid_parent, start_revid, 
                              rev, push_metadata=push_metadata,
                              append_revisions_only=append_revisions_only)



def dpush(target, source, stop_revision=None):
    """Push derivatives of the revisions missing from target from source into 
    target.

    :param target: Branch to push into
    :param source: Branch to retrieve revisions from
    :param stop_revision: If not None, stop at this revision.
    :return: Map of old revids to new revids.
    """
    source.lock_write()
    try:
        if stop_revision is None:
            stop_revision = ensure_null(source.last_revision())
        if target.last_revision() in (stop_revision, source.last_revision()):
            return {}
        graph = target.repository.get_graph()
        if not source.repository.get_graph().is_ancestor(target.last_revision(), 
                                                        stop_revision):
            if graph.is_ancestor(stop_revision, target.last_revision()):
                return {}
            raise DivergedBranches(source, target)
        todo = target.mainline_missing_revisions(source, stop_revision)
        revid_map = {}
        pb = ui.ui_factory.nested_progress_bar()
        try:
            for revid in todo:
                pb.update("pushing revisions", todo.index(revid), 
                          len(todo))
                revid_map[revid] = push(graph, target, source.repository, 
                                        revid, push_metadata=False)
                source.repository.fetch(target.repository, 
                                        revision_id=revid_map[revid])
                target._clear_cached_state()
        finally:
            pb.finished()
        return revid_map
    finally:
        source.unlock()


def push_revision_tree(graph, target_repo, branch_path, config, source_repo, base_revid, 
                       revision_id, rev, push_metadata=True,
                       append_revisions_only=True):
    """Push a revision tree into a target repository.

    :param graph: Repository graph.
    :param target_repo: Target repository.
    :param branch_path: Branch path.
    :param config: Branch configuration.
    :param source_repo: Source repository.
    :param base_revid: Base revision id.
    :param revision_id: Revision id to push.
    :param rev: Revision object of revision to push.
    :param push_metadata: Whether to push metadata.
    :param append_revisions_only: Append revisions only.
    :return: Revision id of newly created revision.
    """
    assert rev.revision_id in (None, revision_id)
    old_tree = source_repo.revision_tree(revision_id)
    base_tree = source_repo.revision_tree(base_revid)

    if push_metadata:
        base_revids = rev.parent_ids
    else:
        base_revids = [base_revid]

    try:
        opt_signature = source_repo.get_signature_text(rev.revision_id)
    except NoSuchRevision:
        opt_signature = None

    builder = SvnCommitBuilder(target_repo, branch_path, base_revids,
                               config, rev.timestamp,
                               rev.timezone, rev.committer, rev.properties, 
                               revision_id, base_tree.inventory, 
                               push_metadata=push_metadata,
                               graph=graph, opt_signature=opt_signature,
                               append_revisions_only=append_revisions_only)
                         
    replay_delta(builder, source_repo.revision_trees(rev.parent_ids), old_tree)
    try:
        revid = builder.commit(rev.message)
    except SubversionException, (_, num):
        if num == ERR_FS_TXN_OUT_OF_DATE:
            raise DivergedBranches(source, target_repo)
        raise
    except ChangesRootLHSHistory:
        raise BzrError("Unable to push revision %r because it would change the ordering of existing revisions on the Subversion repository root. Use rebase and try again or push to a non-root path" % revision_id)

    return revid


def push(graph, target, source_repo, revision_id, push_metadata=True):
    """Push a revision into Subversion.

    This will do a new commit in the target branch.

    :param target: Branch to push to
    :param source_repo: Branch to pull the revision from
    :param revision_id: Revision id of the revision to push
    :return: revision id of revision that was pushed
    """
    assert isinstance(source_repo, Repository)
    rev = source_repo.get_revision(revision_id)
    mutter('pushing %r (%r)', revision_id, rev.parent_ids)

    # revision on top of which to commit
    if push_metadata:
        if rev.parent_ids == []:
            base_revid = NULL_REVISION
        else:
            base_revid = rev.parent_ids[0]
    else:
        base_revid = target.last_revision()

    source_repo.lock_read()
    try:
        revid = push_revision_tree(graph, target.repository, target.get_branch_path(), target.get_config(), 
                                   source_repo, base_revid, revision_id, 
                                   rev, push_metadata=push_metadata,
                                   append_revisions_only=target._get_append_revisions_only())
    finally:
        source_repo.unlock()

    assert revid == revision_id or not push_metadata

    if 'validate' in debug.debug_flags and push_metadata:
        crev = target.repository.get_revision(revision_id)
        ctree = target.repository.revision_tree(revision_id)
        assert crev.committer == rev.committer
        assert crev.timezone == rev.timezone
        assert crev.timestamp == rev.timestamp
        assert crev.message == rev.message
        assert crev.properties == rev.properties

    return revid


class InterToSvnRepository(InterRepository):
    """Any to Subversion repository actions."""

    _matching_repo_format = SvnRepositoryFormat()

    @staticmethod
    def _get_repo_format_to_test():
        """See InterRepository._get_repo_format_to_test()."""
        return None

    def copy_content(self, revision_id=None, pb=None):
        """See InterRepository.copy_content."""
        self.source.lock_read()
        try:
            assert revision_id is not None, "fetching all revisions not supported"
            # Go back over the LHS parent until we reach a revid we know
            todo = []
            while not self.target.has_revision(revision_id):
                todo.append(revision_id)
                try:
                    revision_id = self.source.get_parent_map([revision_id])[revision_id][0]
                except KeyError:
                    # We hit a ghost
                    break
                if revision_id == NULL_REVISION:
                    raise UnrelatedBranches()
            if todo == []:
                # Nothing to do
                return
            mutter("pushing %r into svn", todo)
            target_branch = None
            layout = self.target.get_layout()
            graph = self.target.get_graph()
            for revision_id in todo:
                if pb is not None:
                    pb.update("pushing revisions", todo.index(revision_id), len(todo))
                rev = self.source.get_revision(revision_id)

                mutter('pushing %r', revision_id)

                parent_revid = rev.parent_ids[0]

                (bp, _, _) = self.target.lookup_revision_id(parent_revid)
                if target_branch is None:
                    target_branch = Branch.open(urlutils.join(self.target.base, bp))
                if target_branch.get_branch_path() != bp:
                    target_branch.set_branch_path(bp)

                target_config = target_branch.get_config()
                if (layout.push_merged_revisions(target_branch.project) and 
                    len(rev.parent_ids) > 1 and
                    target_config.get_push_merged_revisions()):
                    push_ancestors(self.target, self.source, layout, "", rev.parent_ids, graph,
                                   create_prefix=True)

                push_revision_tree(graph, target_branch.repository, target_branch.get_branch_path(), 
                                   target_config, self.source, parent_revid, revision_id, rev,
                                   append_revisions_only=target_branch._get_append_revisions_only())
        finally:
            self.source.unlock()
 

    def fetch(self, revision_id=None, pb=None, find_ghosts=False):
        """Fetch revisions. """
        self.copy_content(revision_id=revision_id, pb=pb)

    @staticmethod
    def is_compatible(source, target):
        """Be compatible with SvnRepository."""
        return isinstance(target, SvnRepository)


def push_ancestors(target_repo, source_repo, layout, project, parent_revids, graph, create_prefix=False):
    for parent_revid in parent_revids[1:]:
        if target_repo.has_revision(parent_revid):
            continue
        # Push merged revisions
        unique_ancestors = graph.find_unique_ancestors(parent_revid, [parent_revids[0]])
        for x in graph.iter_topo_order(unique_ancestors):
            if target_repo.has_revision(x):
                continue
            rev = source_repo.get_revision(x)
            nick = (rev.properties.get('branch-nick') or "merged").encode("utf-8").replace("/","_")
            rhs_branch_path = layout.get_branch_path(nick, project)
            try:
                push_new(graph, target_repo, rhs_branch_path, source_repo, x, append_revisions_only=False)
            except MissingPrefix, e:
                if not create_prefix:
                    raise
                revprops = {properties.PROP_REVISION_LOG: "Add branches directory."}
                if target_repo.transport.has_capability("commit-revprops"):
                    revprops[mapping.SVN_REVPROP_BZR_SKIP] = ""
                create_branch_prefix(target_repo, revprops, e.path.split("/")[:-1], filter(lambda x: x != "", e.existing_path.split("/")))
                push_new(graph, target_repo, rhs_branch_path, source_repo, x, append_revisions_only=False)


def create_branch_prefix(repository, revprops, bp_parts, existing_bp_parts):
    conn = repository.transport.get_connection()
    try:
        ci = conn.get_commit_editor(revprops)
        try:
            root = ci.open_root()
            name = None
            batons = [root]
            for p in existing_bp_parts:
                if name is None:
                    name = p
                else:
                    name += "/" + p
                batons.append(batons[-1].open_directory(name))
            for p in bp_parts[len(existing_bp_parts):]:
                if name is None:
                    name = p
                else:
                    name += "/" + p
                batons.append(batons[-1].add_directory(name))
            for baton in reversed(batons):
                baton.close()
        except:
            ci.abort()
            raise
        ci.close()
    finally:
        repository.transport.add_connection(conn)
