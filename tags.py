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

from bzrlib import urlutils
from bzrlib.errors import NoSuchRevision, NoSuchTag
from bzrlib.tag import BasicTags
from bzrlib.trace import mutter

from bzrlib.plugins.svn import commit, core, mapping, properties

class SubversionTags(BasicTags):
    """Subversion tags object."""

    def __init__(self, branch):
        self.branch = branch
        self.repository = branch.repository
        self._parent_exists = False

    def _ensure_tag_parent_exists(self, parent):
        if self._parent_exists:
            return
        assert isinstance(parent, str)
        bp_parts = parent.split("/")
        existing_bp_parts = commit._check_dirs_exist(
                self.repository.transport, 
                bp_parts, self.repository.get_latest_revnum())
        if existing_bp_parts == bp_parts:
            self._parent_exists = True
            return
        commit.create_branch_prefix(self.repository, self._revprops("Add tags base directory."),
                             bp_parts, existing_bp_parts)
        self._parent_exists = True

    def set_tag(self, tag_name, tag_target):
        path = self.branch.layout.get_tag_path(tag_name, self.branch.project)
        assert isinstance(path, str)
        parent = urlutils.dirname(path)
        try:
            (from_bp, from_revnum, mapping) = self.repository.lookup_revision_id(tag_target, project=self.branch.project)
        except NoSuchRevision:
            mutter("not setting tag %s; unknown revision %s", tag_name, tag_target)
            return
        if from_bp == path:
            return
        self._ensure_tag_parent_exists(parent)
        conn = self.repository.transport.get_connection(parent)
        deletefirst = (conn.check_path(urlutils.basename(path), self.repository.get_latest_revnum()) != core.NODE_NONE)
        try:
            ci = conn.get_commit_editor(self._revprops("Add tag %s" % tag_name.encode("utf-8"),
                                        {tag_name.encode("utf-8"): tag_target}))
            try:
                root = ci.open_root()
                if deletefirst:
                    root.delete_entry(urlutils.basename(path))
                tag_dir = root.add_directory(urlutils.basename(path), urlutils.join(self.repository.base, from_bp), from_revnum)
                tag_dir.close()
                root.close()
            except:
                ci.abort()
                raise
            ci.close()
        finally:
            self.repository.transport.add_connection(conn)

    def _revprops(self, message, tags_dict=None):
        """Create a revprops dictionary.

        Optionally sets bzr:skip to slightly optimize fetching of this revision later.
        """
        revprops = {properties.PROP_REVISION_LOG: message, }
        if self.repository.transport.has_capability("commit-revprops"):
            revprops[mapping.SVN_REVPROP_BZR_SKIP] = ""
            if tags_dict is not None:
                revprops[mapping.SVN_REVPROP_BZR_TAGS] = mapping.generate_tags_property(tags_dict)
        return revprops

    def lookup_tag(self, tag_name):
        try:
            return self.get_tag_dict()[tag_name]
        except KeyError:
            raise NoSuchTag(tag_name)

    def get_tag_dict(self):
        return self.repository.find_tags(project=self.branch.project, 
                              layout=self.branch.layout,
                              mapping=self.branch.mapping)

    def get_reverse_tag_dict(self):
        """Returns a dict with revisions as keys
           and a list of tags for that revision as value"""
        d = self.get_tag_dict()
        rev = {}
        for key in d:
            try:
                rev[d[key]].append(key)
            except KeyError:
                rev[d[key]] = [key]
        return rev

    def delete_tag(self, tag_name):
        path = self.branch.layout.get_tag_path(tag_name, self.branch.project)
        parent = urlutils.dirname(path)
        conn = self.repository.transport.get_connection(parent)
        try:
            if conn.check_path(urlutils.basename(path), self.repository.get_latest_revnum()) != core.NODE_DIR:
                raise NoSuchTag(tag_name)
            ci = conn.get_commit_editor(self._revprops("Remove tag %s" % tag_name.encode("utf-8"),
                                        {tag_name: ""}))
            try:
                root = ci.open_root()
                root.delete_entry(urlutils.basename(path))
                root.close()
            except:
                ci.abort()
                raise
            ci.close()
        finally:
            assert not conn.busy
            self.repository.transport.add_connection(conn)

    def _set_tag_dict(self, dest_dict):
        cur_dict = self.get_tag_dict()
        for k, v in dest_dict.iteritems():
            if cur_dict.get(k) != v:
                self.set_tag(k, v)
        for k in cur_dict:
            if k not in dest_dict:
                self.delete_tag(k)

