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
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""Checkouts and working trees (working copies)."""

import bzrlib, bzrlib.add
from bzrlib import osutils, urlutils
from bzrlib.branch import PullResult
from bzrlib.bzrdir import BzrDirFormat, BzrDir
from bzrlib.errors import (InvalidRevisionId, NotBranchError, NoSuchFile,
                           NoRepositoryPresent, 
                           OutOfDateTree, NoWorkingTree, UnsupportedFormatError)
from bzrlib.inventory import Inventory, InventoryFile, InventoryLink
from bzrlib.lockable_files import LockableFiles
from bzrlib.lockdir import LockDir
from bzrlib.revision import NULL_REVISION
from bzrlib.trace import mutter
from bzrlib.transport import get_transport
from bzrlib.workingtree import WorkingTree, WorkingTreeFormat

from bzrlib.plugins.svn import core, properties
from bzrlib.plugins.svn.auth import create_auth_baton
from bzrlib.plugins.svn.branch import SvnBranch
from bzrlib.plugins.svn.commit import _revision_id_to_svk_feature
from bzrlib.plugins.svn.core import SubversionException
from bzrlib.plugins.svn.errors import ERR_FS_TXN_OUT_OF_DATE, ERR_ENTRY_EXISTS, ERR_WC_PATH_NOT_FOUND, ERR_WC_NOT_DIRECTORY, NotSvnBranchPath
from bzrlib.plugins.svn.format import get_rich_root_format
from bzrlib.plugins.svn.mapping import escape_svn_path
from bzrlib.plugins.svn.remote import SvnRemoteAccess
from bzrlib.plugins.svn.repository import SvnRepository
from bzrlib.plugins.svn.svk import SVN_PROP_SVK_MERGE, parse_svk_features, serialize_svk_features
from bzrlib.plugins.svn.transport import (SvnRaTransport, bzr_to_svn_url, 
                       svn_config) 
from bzrlib.plugins.svn.tree import SvnBasisTree
from bzrlib.plugins.svn.wc import *

import os
import urllib

def update_wc(adm, basedir, conn, revnum):
    # FIXME: honor SVN_CONFIG_SECTION_HELPERS:SVN_CONFIG_OPTION_DIFF3_CMD
    # FIXME: honor SVN_CONFIG_SECTION_MISCELLANY:SVN_CONFIG_OPTION_USE_COMMIT_TIMES
    # FIXME: honor SVN_CONFIG_SECTION_MISCELLANY:SVN_CONFIG_OPTION_PRESERVED_CF_EXTS
    editor = adm.get_update_editor(basedir, False, True)
    assert editor is not None
    reporter = conn.do_update(revnum, "", True, editor)
    adm.crawl_revisions(basedir, reporter, restore_files=False, 
                        recurse=True, use_commit_times=False)
    # FIXME: handle externals


def generate_ignore_list(ignore_map):
    """Create a list of ignores, ordered by directory.
    
    :param ignore_map: Dictionary with paths as keys, patterns as values.
    :return: list of ignores
    """
    ignores = []
    keys = ignore_map.keys()
    for k in sorted(keys):
        elements = ["."]
        if k.strip("/") != "":
            elements.append(k.strip("/"))
        elements.append(ignore_map[k].strip("/"))
        ignores.append("/".join(elements))
    return ignores


class SvnWorkingTree(WorkingTree):
    """WorkingTree implementation that uses a Subversion Working Copy for storage."""
    def __init__(self, bzrdir, local_path, branch):
        version = check_wc(local_path)
        self._format = SvnWorkingTreeFormat(version)
        self.basedir = local_path
        assert isinstance(self.basedir, unicode)
        self.bzrdir = bzrdir
        self._branch = branch
        self.base_revnum = 0

        self._get_wc()
        max_rev = revision_status(self.basedir, None, True)[1]
        self.base_revnum = max_rev
        self.base_revid = branch.generate_revision_id(self.base_revnum)
        self.base_tree = SvnBasisTree(self)

        self.read_working_inventory()

        self._detect_case_handling()
        self._transport = bzrdir.get_workingtree_transport(None)
        self.controldir = os.path.join(bzrdir.svn_controldir, 'bzr')
        try:
            os.makedirs(self.controldir)
            os.makedirs(os.path.join(self.controldir, 'lock'))
        except OSError:
            pass
        control_transport = bzrdir.transport.clone(urlutils.join(
                                                   get_adm_dir(), 'bzr'))
        self._control_files = LockableFiles(control_transport, 'lock', LockDir)

    def get_ignore_list(self):
        ignores = set([get_adm_dir()])
        ignores.update(svn_config.get_default_ignores())

        def dir_add(wc, prefix, patprefix):
            ignorestr = wc.prop_get(properties.PROP_IGNORE, 
                                    self.abspath(prefix).rstrip("/"))
            if ignorestr is not None:
                for pat in ignorestr.splitlines():
                    ignores.add(urlutils.joinpath(patprefix, pat))

            entries = wc.entries_read(False)
            for entry in entries:
                if entry == "":
                    continue

                # Ignore ignores on things that aren't directories
                if entries[entry].kind != core.NODE_DIR:
                    continue

                subprefix = os.path.join(prefix, entry)

                subwc = WorkingCopy(wc, self.abspath(subprefix))
                try:
                    dir_add(subwc, subprefix, urlutils.joinpath(patprefix, entry))
                finally:
                    subwc.close()

        wc = self._get_wc()
        try:
            dir_add(wc, "", ".")
        finally:
            wc.close()

        return ignores

    def is_control_filename(self, path):
        return is_adm_dir(path)

    def apply_inventory_delta(self, changes):
        raise NotImplementedError(self.apply_inventory_delta)

    def _update(self, revnum=None):
        if revnum is None:
            # FIXME: should be able to use -1 here
            revnum = self.branch.get_revnum()
        adm = self._get_wc(write_lock=True)
        try:
            conn = self.branch.repository.transport.get_connection(self.branch.get_branch_path())
            try:
                update_wc(adm, self.basedir, conn, revnum)
            finally:
                self.branch.repository.transport.add_connection(conn)
        finally:
            adm.close()
        return revnum

    def update(self, change_reporter=None, possible_transports=None, revnum=None):
        orig_revnum = self.base_revnum
        self.base_revnum = self._update(revnum)
        self.base_revid = self.branch.generate_revision_id(self.base_revnum)
        self.base_tree = None
        self.read_working_inventory()
        return self.base_revnum - orig_revnum

    def remove(self, files, verbose=False, to_file=None, keep_files=True, 
               force=False):
        # FIXME: Use to_file argument
        # FIXME: Use verbose argument
        assert isinstance(files, list)
        wc = self._get_wc(write_lock=True)
        try:
            for file in files:
                wc.delete(self.abspath(file))
        finally:
            wc.close()

        for file in files:
            self._change_fileid_mapping(None, file)
        self.read_working_inventory()

    def _get_wc(self, relpath="", write_lock=False):
        return WorkingCopy(None, self.abspath(relpath).rstrip("/"), 
                                write_lock)

    def _get_rel_wc(self, relpath, write_lock=False):
        dir = os.path.dirname(relpath)
        file = os.path.basename(relpath)
        return (self._get_wc(dir, write_lock), file)

    def move(self, from_paths, to_dir=None, after=False, **kwargs):
        # FIXME: Use after argument
        assert after != True
        for entry in from_paths:
            try:
                to_wc = self._get_wc(to_dir, write_lock=True)
                to_wc.copy(self.abspath(entry), os.path.basename(entry))
            finally:
                to_wc.close()
            try:
                from_wc = self._get_wc(write_lock=True)
                from_wc.delete(self.abspath(entry))
            finally:
                from_wc.close()
            new_name = urlutils.join(to_dir, os.path.basename(entry))
            self._change_fileid_mapping(self.inventory.path2id(entry), new_name)
            self._change_fileid_mapping(None, entry)

        self.read_working_inventory()

    def rename_one(self, from_rel, to_rel, after=False):
        # FIXME: Use after
        assert after != True
        (to_wc, to_file) = self._get_rel_wc(to_rel, write_lock=True)
        if os.path.dirname(from_rel) == os.path.dirname(to_rel):
            # Prevent lock contention
            from_wc = to_wc
        else:
            (from_wc, _) = self._get_rel_wc(from_rel, write_lock=True)
        from_id = self.inventory.path2id(from_rel)
        try:
            to_wc.copy(self.abspath(from_rel), to_file)
            from_wc.delete(self.abspath(from_rel))
        finally:
            to_wc.close()
        self._change_fileid_mapping(None, from_rel)
        self._change_fileid_mapping(from_id, to_rel)
        self.read_working_inventory()

    def path_to_file_id(self, revnum, current_revnum, path):
        """Generate a bzr file id from a Subversion file name. 
        
        :param revnum: Revision number.
        :param path: Absolute path within the Subversion repository.
        :return: Tuple with file id and revision id.
        """
        assert isinstance(revnum, int) and revnum >= 0
        assert isinstance(path, str)

        rp = self.branch.unprefix(path)
        entry = self.basis_tree().id_map[rp.decode("utf-8")]
        assert entry[0] is not None
        assert isinstance(entry[0], str), "fileid %r for %r is not a string" % (entry[0], path)
        return entry

    def read_working_inventory(self):
        inv = Inventory()

        def add_file_to_inv(relpath, id, revid, parent_id):
            """Add a file to the inventory."""
            assert isinstance(relpath, unicode)
            if os.path.islink(self.abspath(relpath)):
                file = InventoryLink(id, os.path.basename(relpath), parent_id)
                file.revision = revid
                file.symlink_target = os.readlink(self.abspath(relpath))
                file.text_sha1 = None
                file.text_size = None
                file.executable = False
                inv.add(file)
            else:
                file = InventoryFile(id, os.path.basename(relpath), parent_id)
                file.revision = revid
                try:
                    data = osutils.fingerprint_file(open(self.abspath(relpath)))
                    file.text_sha1 = data['sha1']
                    file.text_size = data['size']
                    file.executable = self.is_executable(id, relpath)
                    inv.add(file)
                except IOError:
                    # Ignore non-existing files
                    pass

        def find_copies(url, relpath=""):
            wc = self._get_wc(relpath)
            entries = wc.entries_read(False)
            for entry in entries.values():
                subrelpath = os.path.join(relpath, entry.name)
                if entry.name == "" or entry.kind != 'directory':
                    if ((entry.copyfrom_url == url or entry.url == url) and 
                        not (entry.schedule in (SCHEDULE_DELETE,
                                                SCHEDULE_REPLACE))):
                        yield os.path.join(
                                self.branch.get_branch_path().strip("/"), 
                                subrelpath)
                else:
                    find_copies(subrelpath)
            wc.close()

        def find_ids(entry, rootwc):
            relpath = urllib.unquote(entry.url[len(entry.repos):].strip("/"))
            assert entry.schedule in (SCHEDULE_NORMAL, 
                                      SCHEDULE_DELETE,
                                      SCHEDULE_ADD,
                                      SCHEDULE_REPLACE)
            if entry.schedule == SCHEDULE_NORMAL:
                assert entry.revision >= 0
                # Keep old id
                return self.path_to_file_id(entry.cmt_rev, entry.revision, 
                        relpath)
            elif entry.schedule == SCHEDULE_DELETE:
                return (None, None)
            elif (entry.schedule == SCHEDULE_ADD or 
                  entry.schedule == SCHEDULE_REPLACE):
                # See if the file this file was copied from disappeared
                # and has no other copies -> in that case, take id of other file
                if (entry.copyfrom_url and 
                    list(find_copies(entry.copyfrom_url)) == [relpath]):
                    return self.path_to_file_id(entry.copyfrom_rev, 
                        entry.revision, entry.copyfrom_url[len(entry.repos):])
                ids = self._get_new_file_ids(rootwc)
                if ids.has_key(relpath):
                    return (ids[relpath], None)
                # FIXME: Generate more random file ids
                return ("NEW-" + escape_svn_path(entry.url[len(entry.repos):].strip("/")), None)

        def add_dir_to_inv(relpath, wc, parent_id):
            assert isinstance(relpath, unicode)
            entries = wc.entries_read(False)
            entry = entries[""]
            assert parent_id is None or isinstance(parent_id, str), \
                    "%r is not a string" % parent_id
            (id, revid) = find_ids(entry, rootwc)
            if id is None:
                mutter('no id for %r', entry.url)
                return
            assert revid is None or isinstance(revid, str), "%r is not a string" % revid
            assert isinstance(id, str), "%r is not a string" % id

            # First handle directory itself
            inv.add_path(relpath.decode("utf-8"), 'directory', id, parent_id).revision = revid
            if relpath == "":
                inv.revision_id = revid

            for name in entries:
                if name == "":
                    continue

                subrelpath = os.path.join(relpath, name.decode("utf-8"))

                entry = entries[name]
                assert entry
                
                if entry.kind == core.NODE_DIR:
                    subwc = WorkingCopy(wc, self.abspath(subrelpath))
                    try:
                        assert isinstance(subrelpath, unicode)
                        add_dir_to_inv(subrelpath, subwc, id)
                    finally:
                        subwc.close()
                else:
                    (subid, subrevid) = find_ids(entry, rootwc)
                    if subid:
                        assert isinstance(subrelpath, unicode)
                        add_file_to_inv(subrelpath, subid, subrevid, id)
                    else:
                        mutter('no id for %r', entry.url)

        rootwc = self._get_wc() 
        try:
            add_dir_to_inv(u"", rootwc, None)
        finally:
            rootwc.close()

        self._set_inventory(inv, dirty=False)
        return inv

    def set_last_revision(self, revid):
        mutter('setting last revision to %r', revid)
        if revid is None or revid == NULL_REVISION:
            self.base_revid = revid
            self.base_revnum = 0
            self.base_tree = None
            return

        rev = self.branch.lookup_revision_id(revid)
        self.base_revnum = rev
        self.base_revid = revid
        self.base_tree = None

    def set_parent_trees(self, parents_list, allow_leftmost_as_ghost=False):
        """See MutableTree.set_parent_trees."""
        self.set_parent_ids([rev for (rev, tree) in parents_list])

    def set_parent_ids(self, parent_ids):
        super(SvnWorkingTree, self).set_parent_ids(parent_ids)
        if parent_ids == [] or parent_ids[0] == NULL_REVISION:
            merges = []
        else:
            merges = parent_ids[1:]
        adm = self._get_wc(write_lock=True)
        try:
            svk_merges = parse_svk_features(self._get_svk_merges(self._get_base_branch_props()))

            # Set svk:merge
            for merge in merges:
                try:
                    svk_merges.add(_revision_id_to_svk_feature(merge))
                except InvalidRevisionId:
                    pass

            adm.prop_set(SVN_PROP_SVK_MERGE, 
                         serialize_svk_features(svk_merges), self.basedir)
        finally:
            adm.close()

    def smart_add(self, file_list, recurse=True, action=None, save=True):
        assert isinstance(recurse, bool)
        if action is None:
            action = bzrlib.add.AddAction()
        # TODO: use action
        if not file_list:
            # no paths supplied: add the entire tree.
            file_list = [u'.']
        ignored = {}
        added = []

        for file_path in file_list:
            todo = []
            file_path = os.path.abspath(file_path)
            f = self.relpath(file_path)
            wc = self._get_wc(os.path.dirname(f), write_lock=True)
            try:
                if not self.inventory.has_filename(f):
                    if save:
                        mutter('adding %r', file_path)
                        wc.add(file_path)
                    added.append(file_path)
                if recurse and osutils.file_kind(file_path) == 'directory':
                    # Filter out ignored files and update ignored
                    for c in os.listdir(file_path):
                        if self.is_control_filename(c):
                            continue
                        c_path = os.path.join(file_path, c)
                        ignore_glob = self.is_ignored(c)
                        if ignore_glob is not None:
                            ignored.setdefault(ignore_glob, []).append(c_path)
                        todo.append(c_path)
            finally:
                wc.close()
            if todo != []:
                cadded, cignored = self.smart_add(todo, recurse, action, save)
                added.extend(cadded)
                ignored.update(cignored)
        return added, ignored

    def add(self, files, ids=None, kinds=None):
        # TODO: Use kinds
        if isinstance(files, str):
            files = [files]
            if isinstance(ids, str):
                ids = [ids]
        if ids is not None:
            ids = iter(ids)
        assert isinstance(files, list)
        for f in files:
            wc = self._get_wc(os.path.dirname(f), write_lock=True)
            try:
                try:
                    wc.add(self.abspath(f))
                    if ids is not None:
                        self._change_fileid_mapping(ids.next(), f, wc)
                except SubversionException, (_, num):
                    if num == ERR_ENTRY_EXISTS:
                        continue
                    elif num == ERR_WC_PATH_NOT_FOUND:
                        raise NoSuchFile(path=f)
                    raise
            finally:
                wc.close()
        self.read_working_inventory()

    def basis_tree(self):
        if self.base_revid is None or self.base_revid == NULL_REVISION:
            return self.branch.repository.revision_tree(self.base_revid)

        if self.base_tree is None:
            self.base_tree = SvnBasisTree(self)

        return self.base_tree

    def pull(self, source, overwrite=False, stop_revision=None, 
             delta_reporter=None, possible_transports=None):
        # FIXME: Use delta_reporter
        # FIXME: Use source
        # FIXME: Use overwrite
        result = self.branch.pull(source, overwrite=overwrite, stop_revision=stop_revision)
        fetched = self._update(self.branch.get_revnum())
        self.base_revnum = fetched
        self.base_revid = self.branch.generate_revision_id(fetched)
        self.base_tree = None
        self.read_working_inventory()
        return result

    def get_file_sha1(self, file_id, path=None, stat_value=None):
        if not path:
            path = self._inventory.id2path(file_id)
        return osutils.fingerprint_file(open(self.abspath(path)))['sha1']

    def _change_fileid_mapping(self, id, path, wc=None):
        if wc is None:
            subwc = self._get_wc(write_lock=True)
        else:
            subwc = wc
        new_entries = self._get_new_file_ids(subwc)
        if id is None:
            if new_entries.has_key(path):
                del new_entries[path]
        else:
            assert isinstance(id, str)
            new_entries[path] = id
        fileprops = self._get_branch_props()
        self.branch.mapping.export_fileid_map(new_entries, None, fileprops)
        self._set_branch_props(subwc, fileprops)
        if wc is None:
            subwc.close()

    def _get_branch_props(self):
        wc = self._get_wc()
        try:
            (prop_changes, orig_props) = wc.get_prop_diffs(self.basedir)
            for k,v in prop_changes:
                if v is None:
                    del orig_props[k]
                else:
                    orig_props[k] = v
            return orig_props
        finally:
            wc.close()

    def _set_branch_props(self, wc, fileprops):
        for k,v in fileprops.items():
            wc.prop_set(k, v, self.basedir)

    def _get_base_branch_props(self):
        wc = self._get_wc()
        try:
            (prop_changes, orig_props) = wc.get_prop_diffs(self.basedir)
            return orig_props
        finally:
            wc.close()

    def _get_new_file_ids(self, wc):
        return self.branch.mapping.import_fileid_map({}, 
                self._get_branch_props())

    def _get_svk_merges(self, base_branch_props):
        return base_branch_props.get(SVN_PROP_SVK_MERGE, "")

    def apply_inventory_delta(self, delta):
        assert delta == []

    def _last_revision(self):
        return self.base_revid

    def path_content_summary(self, path, _lstat=os.lstat,
        _mapper=osutils.file_kind_from_stat_mode):
        """See Tree.path_content_summary."""
        abspath = self.abspath(path)
        try:
            stat_result = _lstat(abspath)
        except OSError, e:
            if getattr(e, 'errno', None) == errno.ENOENT:
                # no file.
                return ('missing', None, None, None)
            # propagate other errors
            raise
        kind = _mapper(stat_result.st_mode)
        if kind == 'file':
            size = stat_result.st_size
            # try for a stat cache lookup
            executable = self._is_executable_from_path_and_stat(path, stat_result)
            return (kind, size, executable, self._sha_from_stat(
                path, stat_result))
        elif kind == 'directory':
            return kind, None, None, None
        elif kind == 'symlink':
            return ('symlink', None, None, os.readlink(abspath))
        else:
            return (kind, None, None, None)

    def _reset_data(self):
        pass

    def unlock(self):
        # non-implementation specific cleanup
        self._cleanup()

        # reverse order of locking.
        try:
            return self._control_files.unlock()
        finally:
            self.branch.unlock()

    if not osutils.supports_executable():
        def is_executable(self, file_id, path=None):
            inv = self.basis_tree()._inventory
            if file_id in inv:
                return inv[file_id].executable
            # Default to not executable
            return False

    def update_basis_by_delta(self, new_revid, delta):
        """Update the parents of this tree after a commit.

        This gives the tree one parent, with revision id new_revid. The
        inventory delta is applied to the current basis tree to generate the
        inventory for the parent new_revid, and all other parent trees are
        discarded.

        All the changes in the delta should be changes synchronising the basis
        tree with some or all of the working tree, with a change to a directory
        requiring that its contents have been recursively included. That is,
        this is not a general purpose tree modification routine, but a helper
        for commit which is not required to handle situations that do not arise
        outside of commit.

        :param new_revid: The new revision id for the trees parent.
        :param delta: An inventory delta (see apply_inventory_delta) describing
            the changes from the current left most parent revision to new_revid.
        """
        rev = self.branch.lookup_revision_id(new_revid)
        self.base_revnum = rev
        self.base_revid = new_revid
        self.base_tree = None

        # TODO: Implement more efficient version
        newrev = self.branch.repository.get_revision(new_revid)
        newrevtree = self.branch.repository.revision_tree(new_revid)
        svn_revprops = self.branch.repository._log.revprop_list(rev)

        def update_settings(wc, path):
            id = newrevtree.inventory.path2id(path)
            mutter("Updating settings for %r", id)
            revnum = self.branch.lookup_revision_id(
                    newrevtree.inventory[id].revision)

            if newrevtree.inventory[id].kind != 'directory':
                return

            entries = wc.entries_read(True)
            for name, entry in entries.items():
                if name == "":
                    continue

                wc.process_committed(self.abspath(path).rstrip("/"), 
                              False, self.branch.lookup_revision_id(newrevtree.inventory[id].revision),
                              svn_revprops[properties.PROP_REVISION_DATE], 
                              svn_revprops.get(properties.PROP_REVISION_AUTHOR, ""))

                child_path = os.path.join(path, name.decode("utf-8"))

                fileid = newrevtree.inventory.path2id(child_path)

                if newrevtree.inventory[fileid].kind == 'directory':
                    subwc = WorkingCopy(wc, self.abspath(child_path).rstrip("/"), write_lock=True)
                    try:
                        update_settings(subwc, child_path)
                    finally:
                        subwc.close()

        # Set proper version for all files in the wc
        wc = self._get_wc(write_lock=True)
        try:
            wc.process_committed(self.basedir,
                          False, self.branch.lookup_revision_id(newrevtree.inventory.root.revision),
                          svn_revprops[properties.PROP_REVISION_DATE], 
                          svn_revprops.get(properties.PROP_REVISION_AUTHOR, ""))
            update_settings(wc, "")
        finally:
            wc.close()

        self.set_parent_ids([new_revid])


class SvnWorkingTreeFormat(WorkingTreeFormat):
    """Subversion working copy format."""
    def __init__(self, version):
        self.version = version

    def __get_matchingbzrdir(self):
        return SvnWorkingTreeDirFormat()

    _matchingbzrdir = property(__get_matchingbzrdir)

    def get_format_description(self):
        return "Subversion Working Copy Version %d" % self.version

    def get_format_string(self):
        raise NotImplementedError

    def initialize(self, a_bzrdir, revision_id=None):
        raise NotImplementedError(self.initialize)

    def open(self, a_bzrdir):
        raise NotImplementedError(self.initialize)


class SvnCheckout(BzrDir):
    """BzrDir implementation for Subversion checkouts (directories 
    containing a .svn subdirectory."""
    def __init__(self, transport, format):
        super(SvnCheckout, self).__init__(transport, format)
        self.local_path = transport.local_abspath(".")
        
        # Open related remote repository + branch
        try:
            wc = WorkingCopy(None, self.local_path)
        except SubversionException, (msg, ERR_WC_UNSUPPORTED_FORMAT):
            raise UnsupportedFormatError(msg, kind='workingtree')
        try:
            self.svn_url = wc.entry(self.local_path, True).url
        finally:
            wc.close()

        self._remote_transport = None
        self._remote_bzrdir = None
        self.svn_controldir = os.path.join(self.local_path, get_adm_dir())
        self.root_transport = self.transport = transport

    def get_remote_bzrdir(self):
        if self._remote_bzrdir is None:
            self._remote_bzrdir = SvnRemoteAccess(self.get_remote_transport())
        return self._remote_bzrdir

    def get_remote_transport(self):
        if self._remote_transport is None:
            self._remote_transport = SvnRaTransport(self.svn_url)
        return self._remote_transport
        
    def clone(self, path, revision_id=None, force_new_repo=False):
        raise NotImplementedError(self.clone)

    def open_workingtree(self, _unsupported=False, recommend_upgrade=False):
        try:
            return SvnWorkingTree(self, self.local_path, self.open_branch())
        except NotSvnBranchPath, e:
            raise NoWorkingTree(self.local_path)

    def sprout(self, url, revision_id=None, force_new_repo=False, 
               recurse='down', possible_transports=None, accelerator_tree=None,
               hardlink=False):
        # FIXME: honor force_new_repo
        # FIXME: Use recurse
        result = get_rich_root_format().initialize(url)
        repo = self._find_repository()
        repo.clone(result, revision_id)
        branch = self.open_branch()
        branch.sprout(result, revision_id)
        result.create_workingtree(hardlink=hardlink)
        return result

    def open_repository(self):
        raise NoRepositoryPresent(self)

    def find_repository(self):
        raise NoRepositoryPresent(self)

    def _find_repository(self):
        return SvnRepository(self, self.get_remote_transport().clone_root(), 
                             self.get_remote_bzrdir().branch_path)

    def needs_format_conversion(self, format=None):
        if format is None:
            format = BzrDirFormat.get_default_format()
        return not isinstance(self._format, format.__class__)

    def get_workingtree_transport(self, format):
        assert format is None
        return get_transport(self.svn_controldir)

    def create_workingtree(self, revision_id=None, hardlink=None):
        """See BzrDir.create_workingtree().

        Not implemented for Subversion because having a .svn directory
        implies having a working copy.
        """
        raise NotImplementedError(self.create_workingtree)

    def create_branch(self):
        """See BzrDir.create_branch()."""
        raise NotImplementedError(self.create_branch)

    def open_branch(self, unsupported=True):
        """See BzrDir.open_branch()."""
        repos = self._find_repository()

        try:
            branch = SvnBranch(repos, self.get_remote_bzrdir().branch_path)
        except SubversionException, (_, num):
            if num == ERR_WC_NOT_DIRECTORY:
                raise NotBranchError(path=self.base)
            raise

        branch.bzrdir = self.get_remote_bzrdir()
 
        return branch
