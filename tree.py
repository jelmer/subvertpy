# Copyright (C) 2005-2006 Jelmer Vernooij <jelmer@samba.org>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""Access to stored Subversion basis trees."""

from bzrlib.inventory import Inventory

from bzrlib import osutils, urlutils
from bzrlib.trace import mutter
from bzrlib.revisiontree import RevisionTree

import os
import md5
from cStringIO import StringIO
import urllib

import constants
import core, wc

class SvnRevisionTree(RevisionTree):
    """A tree that existed in a historical Subversion revision."""
    def __init__(self, repository, revision_id):
        self._repository = repository
        self._revision_id = revision_id
        (self.branch_path, self.revnum, mapping) = repository.lookup_revision_id(revision_id)
        self._inventory = Inventory()
        self.id_map = repository.get_fileid_map(self.revnum, self.branch_path, 
                                                mapping)
        editor = TreeBuildEditor(self)
        self.file_data = {}
        root_repos = repository.transport.get_svn_repos_root()
        reporter = repository.transport.do_switch(
                self.revnum, True, 
                urlutils.join(root_repos, self.branch_path), editor)
        reporter.set_path("", 0, True, None)
        reporter.finish_report()

    def get_file_lines(self, file_id):
        return osutils.split_lines(self.file_data[file_id])


class TreeBuildEditor:
    """Builds a tree given Subversion tree transform calls."""
    def __init__(self, tree):
        self.tree = tree
        self.repository = tree._repository
        self.last_revnum = {}
        self.dir_revnum = {}
        self.dir_ignores = {}

    def set_target_revision(self, revnum):
        self.revnum = revnum

    def open_root(self, revnum):
        file_id, revision_id = self.tree.id_map[""]
        ie = self.tree._inventory.add_path("", 'directory', file_id)
        ie.revision = revision_id
        self.tree._inventory.revision_id = revision_id
        return file_id

    def close(self):
        pass

    def abort(self):
        pass

class DirectoryTreeEditor:
    def __init__(self, tree, file_id):
        self.tree = tree
        self.file_id = file_id
        self.dir_ignores = None

    def add_directory(self, path, copyfrom_path=None, copyfrom_revnum=-1):
        path = path.decode("utf-8")
        file_id, revision_id = self.tree.id_map[path]
        ie = self.tree._inventory.add_path(path, 'directory', file_id)
        ie.revision = revision_id
        return DirectoryTreeEditor(self.editor, file_id)

    def change_prop(self, name, value):
        from mapping import (SVN_PROP_BZR_ANCESTRY, 
                        SVN_PROP_BZR_PREFIX, SVN_PROP_BZR_REVISION_INFO, 
                        SVN_PROP_BZR_FILEIDS, SVN_PROP_BZR_REVISION_ID,
                        SVN_PROP_BZR_BRANCHING_SCHEME, SVN_PROP_BZR_MERGE)

        if name == constants.PROP_ENTRY_COMMITTED_REV:
            self.dir_revnum = int(value)
        elif name == constants.PROP_IGNORE:
            self.dir_ignores = value
        elif name.startswith(SVN_PROP_BZR_ANCESTRY):
            if self.file_id != self.tree._inventory.root.file_id:
                mutter('%r set on non-root dir!' % name)
                return
        elif name in (SVN_PROP_BZR_FILEIDS, SVN_PROP_BZR_BRANCHING_SCHEME):
            if self.file_id != self.tree._inventory.root.file_id:
                mutter('%r set on non-root dir!' % name)
                return
        elif name in (SVN_PROP_ENTRY_COMMITTED_DATE,
                      SVN_PROP_ENTRY_LAST_AUTHOR,
                      SVN_PROP_ENTRY_LOCK_TOKEN,
                      SVN_PROP_ENTRY_UUID,
                      SVN_PROP_EXECUTABLE):
            pass
        elif name.startswith(constants.PROP_WC_PREFIX):
            pass
        elif (name == SVN_PROP_BZR_REVISION_INFO or 
              name.startswith(SVN_PROP_BZR_REVISION_ID)):
            pass
        elif name == SVN_PROP_BZR_MERGE:
            pass
        elif (name.startswith(constants.PROP_PREFIX) or
              name.startswith(SVN_PROP_BZR_PREFIX)):
            mutter('unsupported dir property %r' % name)

    def add_file(self, path, copyfrom_path=None, copyfrom_revnum=-1):
        path = path.decode("utf-8")
        return FileTreeEditor(self.tree, path)

    def close(self):
        if (self.dir_ignores is not None and 
            self.file_id in self.tree._inventory):
            self.tree._inventory[self.file_id].ignores = self.dir_ignores


class FileTreeEditor:
    def __init__(self, tree, path):
        self.tree = tree
        self.path = path
        self.is_executable = False
        self.is_symlink = False
        self.last_file_rev = None

    def change_prop(self, name, value):
        from mapping import SVN_PROP_BZR_PREFIX

        if name == constants.PROP_EXECUTABLE:
            self.is_executable = (value != None)
        elif name == constants.PROP_SPECIAL:
            self.is_symlink = (value != None)
        elif name == constants.PROP_ENTRY_COMMITTED_REV:
            self.last_file_rev = int(value)
        elif name in (constants.PROP_ENTRY_COMMITTED_DATE,
                      constants.PROP_ENTRY_LAST_AUTHOR,
                      constants.PROP_ENTRY_LOCK_TOKEN,
                      constants.PROP_ENTRY_UUID,
                      constants.PROP_MIME_TYPE):
            pass
        elif name.startswith(constants.PROP_WC_PREFIX):
            pass
        elif (name.startswith(constants.PROP_PREFIX) or
              name.startswith(SVN_PROP_BZR_PREFIX)):
            mutter('unsupported file property %r' % name)

    def close(self, checksum=None):
        file_id, revision_id = self.tree.id_map[self.path]
        if self.is_symlink:
            ie = self.tree._inventory.add_path(path, 'symlink', file_id)
        else:
            ie = self.tree._inventory.add_path(path, 'file', file_id)
        ie.revision = revision_id

        if self.file_stream:
            self.file_stream.seek(0)
            file_data = self.file_stream.read()
        else:
            file_data = ""

        actual_checksum = md5.new(file_data).hexdigest()
        assert(checksum is None or checksum == actual_checksum,
                "checksum mismatch: %r != %r" % (checksum, actual_checksum))

        if self.is_symlink:
            ie.symlink_target = file_data[len("link "):]
            ie.text_sha1 = None
            ie.text_size = None
            ie.text_id = None
            ie.executable = False
        else:
            ie.text_sha1 = osutils.sha_string(file_data)
            ie.text_size = len(file_data)
            self.tree.file_data[file_id] = file_data
            ie.executable = self.is_executable

        self.file_stream = None

    def apply_textdelta(self, file_id, base_checksum):
        self.file_stream = StringIO()
        return apply_txdelta_handler(StringIO(""), self.file_stream)


class SvnBasisTree(RevisionTree):
    """Optimized version of SvnRevisionTree."""
    def __init__(self, workingtree):
        self.workingtree = workingtree
        self._revision_id = workingtree.branch.generate_revision_id(
                                      workingtree.base_revnum)
        self.id_map = workingtree.branch.repository.get_fileid_map(
                workingtree.base_revnum, 
                workingtree.branch.get_branch_path(workingtree.base_revnum), 
                workingtree.branch.mapping)
        self._inventory = Inventory(root_id=None)
        self._repository = workingtree.branch.repository

        def add_file_to_inv(relpath, id, revid, wc):
            props = wc.get_prop_diffs(self.workingtree.abspath(relpath))
            if isinstance(props, list): # Subversion 1.5
                props = props[1]
            if props.has_key(constants.PROP_SPECIAL):
                ie = self._inventory.add_path(relpath, 'symlink', id)
                ie.symlink_target = open(self._abspath(relpath)).read()[len("link "):]
                ie.text_sha1 = None
                ie.text_size = None
                ie.text_id = None
                ie.executable = False
            else:
                ie = self._inventory.add_path(relpath, 'file', id)
                data = osutils.fingerprint_file(open(self._abspath(relpath)))
                ie.text_sha1 = data['sha1']
                ie.text_size = data['size']
                ie.executable = props.has_key(constants.PROP_EXECUTABLE)
            ie.revision = revid
            return ie

        def find_ids(entry):
            relpath = urllib.unquote(entry.url[len(entry.repos):].strip("/"))
            if entry.schedule in (wc.schedule_normal, 
                                  wc.schedule_delete, 
                                  wc.schedule_replace):
                return self.id_map[workingtree.branch.unprefix(relpath)]
            return (None, None)

        def add_dir_to_inv(relpath, wc, parent_id):
            entries = wc.entries_read(False)
            entry = entries[""]
            (id, revid) = find_ids(entry)
            if id == None:
                return

            # First handle directory itself
            ie = self._inventory.add_path(relpath, 'directory', id)
            ie.revision = revid
            if relpath == "":
                self._inventory.revision_id = revid

            for name in entries:
                if name == "":
                    continue

                subrelpath = os.path.join(relpath, name)

                entry = entries[name]
                assert entry
                
                if entry.kind == core.NODE_DIR:
                    subwc = wc.WorkingCopy(
                            self.workingtree.abspath(subrelpath), 
                                             False, 0, None)
                    try:
                        add_dir_to_inv(subrelpath, subwc, id)
                    finally:
                        subwc.close()
                else:
                    (subid, subrevid) = find_ids(entry)
                    if subid is not None:
                        add_file_to_inv(subrelpath, subid, subrevid, wc)

        wc = workingtree._get_wc() 
        try:
            add_dir_to_inv("", wc, None)
        finally:
            wc.adm_close()

    def _abspath(self, relpath):
        return wc.get_pristine_copy_path(self.workingtree.abspath(relpath))

    def get_file_lines(self, file_id):
        base_copy = self._abspath(self.id2path(file_id))
        return osutils.split_lines(open(base_copy).read())

