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

from bzrlib import urlutils, ui
from bzrlib.errors import NotBranchError
from bzrlib.trace import mutter
from bzrlib.plugins.svn.core import SubversionException, NODE_DIR
from bzrlib.plugins.svn.errors import ERR_FS_NOT_DIRECTORY, ERR_FS_NOT_FOUND, ERR_RA_DAV_PATH_NOT_FOUND
from bzrlib.plugins.svn.ra import DIRENT_KIND

class RepositoryLayout(object):
    """Describes a repository layout."""

    def __init__(self, repository):
        self.repository = repository
        self._config = repository.get_config()

    def get_tag_path(self, name, project=""):
        """Return the path at which the tag with specified name should be found.

        :param name: Name of the tag. 
        :param project: Optional name of the project the tag is for. Can include slashes.
        :return: Path of the tag."
        """
        raise NotImplementedError

    def get_tag_name(self, path, project=""):
        """Determine the tag name from a tag path.

        :param path: Path inside the repository.
        """
        raise NotImplementedError

    def push_merged_revisions(self, project=""):
        """Determine whether or not right hand side (merged) revisions should be pushed.

        Defaults to False.
        
        :param project: Name of the project.
        """
        return False

    def get_branch_path(self, name, project=""):
        """Return the path at which the branch with specified name should be found.

        :param name: Name of the branch. 
        :param project: Optional name of the project the branch is for. Can include slashes.
        :return: Path of the branch.
        """
        raise NotImplementedError

    def parse(self, path):
        """Parse a path.

        :return: Tuple with type ('tag', 'branch'), project name, branch path and path 
            inside the branch
        """
        raise NotImplementedError

    def is_branch(self, path, project=None):
        """Check whether a specified path points at a branch."""
        try:
            (type, proj, bp, rp) = self.parse(path)
        except NotBranchError:
            return False
        if (type == "branch" and rp == "" and 
            (project is None or proj == project)):
            return True
        return False

    def is_tag(self, path, project=None):
        """Check whether a specified path points at a tag."""
        try:
            (type, proj, bp, rp) = self.parse(path)
        except NotBranchError:
            return False
        if (type == "tag" and rp == "" and
            (project is None or proj == project)):
            return True
        return False

    def is_branch_parent(self, path, project=None):
        return self.is_branch(urlutils.join(path, "trunk"), project)

    def is_tag_parent(self, path, project=None):
        return self.is_tag(urlutils.join(path, "trunk"), project)

    def is_branch_or_tag(self, path, project=None):
        return self.is_branch(path, project) or self.is_tag(path, project)

    def is_branch_or_tag_parent(self, path, project=None):
        return self.is_branch_parent(path, project) or self.is_tag_parent(path, project)

    def get_branches(self, revnum, project="", pb=None):
        """Retrieve a list of paths that refer to branches in a specific revision.

        :result: Iterator over tuples with (project, branch path)
        """
        raise NotImplementedError

    def get_tags(self, revnum, project="", pb=None):
        """Retrieve a list of paths that refer to tags in a specific revision.

        :result: Iterator over tuples with (project, branch path)
        """
        raise NotImplementedError


class TrunkLayout(RepositoryLayout):
    
    def get_tag_path(self, name, project=""):
        """Return the path at which the tag with specified name should be found.

        :param name: Name of the tag. 
        :param project: Optional name of the project the tag is for. Can include slashes.
        :return: Path of the tag."
        """
        return urlutils.join(project, "tags", name.encode("utf-8")).strip("/")

    def get_tag_name(self, path, project=""):
        """Determine the tag name from a tag path.

        :param path: Path inside the repository.
        """
        return urlutils.basename(path).strip("/")

    def push_merged_revisions(self, project=""):
        """Determine whether or not right hand side (merged) revisions should be pushed.

        Defaults to False.
        
        :param project: Name of the project.
        """
        return self._config.get_push_merged_revisions()

    def get_branch_path(self, name, project=""):
        """Return the path at which the branch with specified name should be found.

        :param name: Name of the branch. 
        :param project: Optional name of the project the branch is for. Can include slashes.
        :return: Path of the branch.
        """
        return urlutils.join(project, "branches", name).strip("/")

    def parse(self, path):
        """Parse a path.

        :return: Tuple with type ('tag', 'branch'), project name, branch path and path 
            inside the branch
        """
        assert isinstance(path, str)
        parts = path.split("/")
        for i, p in enumerate(parts):
            if (i > 0 and parts[i-1] in ("branches", "tags")) or p == "trunk":
                if p == "tags":
                    t = "tag"
                    j = i-1
                elif p == "branches":
                    t = "branch"
                    j = i-1
                else:
                    t = "branch"
                    j = i
                return (t, "/".join(parts[:j-1]).strip("/"), "/".join(parts[:i]).strip("/"), "/".join(parts[i+1:]).strip("/"))
        raise NotBranchError(path)

    def _add_project(self, path, project=None):
        if project is None:
            return path
        return urlutils.join(project, path)

    def get_branches(self, revnum, project=None, pb=None):
        """Retrieve a list of paths that refer to branches in a specific revision.

        :result: Iterator over tuples with (project, branch path)
        """
        return get_root_paths(self.repository, 
             [self._add_project(x, project) for x in "branches/*", "trunk"], 
             revnum, self.is_tag, project)

    def get_tags(self, revnum, project=None, pb=None):
        """Retrieve a list of paths that refer to tags in a specific revision.

        :result: Iterator over tuples with (project, branch path)
        """
        return get_root_paths(self.repository, [self._add_project("tags/*", project)], revnum, self.is_tag, project)

    def __repr__(self):
        return "%s()" % self.__class__.__name__


class RootLayout(RepositoryLayout):
    """Layout where the root of the repository is a branch."""

    def __init__(self):
        pass
    
    def get_tag_path(self, name, project=""):
        """Return the path at which the tag with specified name should be found.

        :param name: Name of the tag. 
        :param project: Optional name of the project the tag is for. Can include slashes.
        :return: Path of the tag."
        """
        return None

    def get_tag_name(self, path, project=""):
        """Determine the tag name from a tag path.

        :param path: Path inside the repository.
        """
        raise AssertionError("should never be reached, there can't be any tag paths in this layout")

    def push_merged_revisions(self, project=""):
        """Determine whether or not right hand side (merged) revisions should be pushed.

        Defaults to False.
        
        :param project: Name of the project.
        """
        return False

    def get_branch_path(self, name, project=""):
        """Return the path at which the branch with specified name should be found.

        :param name: Name of the branch. 
        :param project: Optional name of the project the branch is for. Can include slashes.
        :return: Path of the branch.
        """
        return None

    def parse(self, path):
        """Parse a path.

        :return: Tuple with type ('tag', 'branch'), project name, branch path and path 
            inside the branch
        """
        return ('branch', '', '', path)

    def get_branches(self, revnum, project=None, pb=None):
        """Retrieve a list of paths that refer to branches in a specific revision.

        :result: Iterator over tuples with (project, branch path)
        """
        return []

    def get_tags(self, revnum, project=None, pb=None):
        """Retrieve a list of paths that refer to tags in a specific revision.

        :result: Iterator over tuples with (project, branch path)
        """
        return []

    def __repr__(self):
        return "%s()" % self.__class__.__name__


class ConfigBasedLayout(RepositoryLayout):

    def __init__(self, repository):
        self.repository = repository
        self._config = repository.get_config()


def expand_branch_pattern(begin, todo, check_path, get_children, project=None):
    """Find the paths in the repository that match the expected branch pattern.

    :param begin: List of path elements currently opened.
    :param todo: List of path elements to still evaluate (including wildcards)
    :param check_path: Function for checking a path exists
    :param get_children: Function for retrieving the children of a path
    """
    mutter('expand branches: %r, %r', begin, todo)
    path = "/".join(begin)
    if (project is not None and 
        not project.startswith(path) and 
        not path.startswith(project)):
        return []
    # If all elements have already been handled, just check the path exists
    if len(todo) == 0:
        if check_path(path):
            return [path]
        else:
            return []
    # Not a wildcard? Just expand next bits
    if todo[0] != "*":
        return expand_branch_pattern(begin+[todo[0]], todo[1:], check_path, 
                                     get_children, project)
    children = get_children(path)
    if children is None:
        return []
    ret = []
    pb = ui.ui_factory.nested_progress_bar()
    try:
        for idx, c in enumerate(children):
            pb.update("browsing branches", idx, len(children))
            if len(todo) == 1:
                # Last path element, so return directly
                ret.append("/".join(begin+[c]))
            else:
                ret += expand_branch_pattern(begin+[c], todo[1:], check_path, 
                                             get_children, project)
    finally:
        pb.finished()
    return ret


def get_root_paths(repository, itemlist, revnum, verify_fn, project=None, pb=None):
    """Find all the paths in the repository matching a list of items.

    :param repository: Repository to search in.
    :param itemlist: List of glob-items to match on.
    :param revnum: Revision number in repository to analyse.
    :param verify_fn: Function that checks if a path is acceptable.
    :param project: Optional project branch/tag should be in.
    :param pb: OPtional progress bar.
    """
    def check_path(path):
        return repository.transport.check_path(path, revnum) == NODE_DIR
    def find_children(path):
        try:
            assert not path.startswith("/")
            dirents = repository.transport.get_dir(path, revnum, DIRENT_KIND)[0]
        except SubversionException, (msg, num):
            if num in (ERR_FS_NOT_DIRECTORY, ERR_FS_NOT_FOUND, ERR_RA_DAV_PATH_NOT_FOUND):
                return None
            raise
        return [d for d in dirents if dirents[d]['kind'] == NODE_DIR]

    for idx, pattern in enumerate(itemlist):
        if pb is not None:
            pb.update("finding branches", idx, len(itemlist))
        for bp in expand_branch_pattern([], pattern.split("/"), check_path,
                find_children, project):
            if verify_fn(bp, project):
                yield "", bp, bp.split("/")[-1]


