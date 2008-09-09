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

from bzrlib import errors as bzr_errors, urlutils
from bzrlib.plugins.svn.layout import RepositoryLayout, get_root_paths

from functools import partial

class TrunkLayout(RepositoryLayout):

    def __init__(self, level=None):
        assert level is None or isinstance(level, int)
        self.level = level
    
    def get_tag_path(self, name, project=""):
        """Return the path at which the tag with specified name should be found.

        :param name: Name of the tag. 
        :param project: Optional name of the project the tag is for. Can include slashes.
        :return: Path of the tag."
        """
        subpath = urlutils.join("tags", name.encode("utf-8")).strip("/")
        if project in (None, ""):
            return subpath
        return urlutils.join(project, subpath)

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
        return False

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
        path = path.strip("/")
        parts = path.split("/")
        for i, p in enumerate(parts):
            if (i > 0 and parts[i-1] in ("branches", "tags")) or p == "trunk":
                if parts[i-1] == "tags":
                    t = "tag"
                    j = i-1
                elif parts[i-1] == "branches":
                    t = "branch"
                    j = i-1
                else:
                    t = "branch"
                    j = i
                if self.level in (j, None):
                    return (t, 
                        "/".join(parts[:j]).strip("/"), 
                        "/".join(parts[:i+1]).strip("/"), 
                        "/".join(parts[i+1:]).strip("/"))
        raise bzr_errors.NotBranchError(path)

    def _add_project(self, path, project=None):
        if project is None:
            return path
        return urlutils.join(project, path)

    def get_branches(self, repository, revnum, project=None, pb=None):
        """Retrieve a list of paths that refer to branches in a specific revision.

        :result: Iterator over tuples with (project, branch path)
        """
        return get_root_paths(repository, 
             [self._add_project(x, project) for x in "branches/*", "trunk"], 
             revnum, self.is_branch, project)

    def get_tags(self, repository, revnum, project=None, pb=None):
        """Retrieve a list of paths that refer to tags in a specific revision.

        :result: Iterator over tuples with (project, branch path)
        """
        return get_root_paths(repository, [self._add_project("tags/*", project)], revnum, self.is_tag, project)

    def __repr__(self):
        if self.level is None:
            return "%s()" % self.__class__.__name__
        else:
            return "%s(%d)" % (self.__class__.__name__, self.level)

TrunkLayout0 = partial(TrunkLayout, 0)
TrunkLayout1 = partial(TrunkLayout, 1)
TrunkLayout2 = partial(TrunkLayout, 2)


class RootLayout(RepositoryLayout):
    """Layout where the root of the repository is a branch."""

    def __init__(self):
        pass

    def supports_tags(self):
        return False

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
        raise AssertionError("can't created branches in this layout")

    def parse(self, path):
        """Parse a path.

        :return: Tuple with type ('tag', 'branch'), project name, branch path and path 
            inside the branch
        """
        return ('branch', '', '', path)

    def get_branches(self, repository, revnum, project=None, pb=None):
        """Retrieve a list of paths that refer to branches in a specific revision.

        :result: Iterator over tuples with (project, branch path)
        """
        return [("", "", "trunk")]

    def get_tags(self, repository, revnum, project=None, pb=None):
        """Retrieve a list of paths that refer to tags in a specific revision.

        :result: Iterator over tuples with (project, branch path)
        """
        return []

    def __repr__(self):
        return "%s()" % self.__class__.__name__


class CustomLayout(RepositoryLayout):

    def __init__(self, branches=[], tags=[]):
        self.branches = branches
        self.tags = tags

    def supports_tags(self):
        return (self.tags != [])
    
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
        return None

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
        for bp in sorted(self.branches):
            if path.startswith("%s/" % bp) or bp == path:
                return ("branch", bp, bp, path[len(bp):].strip("/"))

        for tp in sorted(self.tags):
            if path.startswith("%s/" % tp) or tp == path:
                return ("tag", tp, tp, path[len(tp):].strip("/"))

        raise bzr_errors.NotBranchError(path)

    def get_branches(self, repository, revnum, project=None, pb=None):
        """Retrieve a list of paths that refer to branches in a specific revision.

        :result: Iterator over tuples with (project, branch path)
        """
        return self.branches

    def get_tags(self, repository, revnum, project=None, pb=None):
        """Retrieve a list of paths that refer to tags in a specific revision.

        :result: Iterator over tuples with (project, branch path)
        """
        return self.tags

    def __repr__(self):
        return "%s(%r,%r)" % (self.__class__.__name__, self.branches, self.tags)


class WildcardLayout(RepositoryLayout):

    def __init__(self, branches=[], tags=[]):
        self.branches = branches
        self.tags = tags

    def supports_tags(self):
        return (self.tags != [])
    
    def get_tag_path(self, name, project=""):
        """Return the path at which the tag with specified name should be found.

        :param name: Name of the tag. 
        :param project: Optional name of the project the tag is for. Can include slashes.
        :return: Path of the tag."
        """
        # FIXME
        return None

    def get_tag_name(self, path, project=""):
        """Determine the tag name from a tag path.

        :param path: Path inside the repository.
        """
        # FIXME
        return None

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

    def is_branch(self, path, project=None):
        for bp in self.branches:
            if wildcard_matches(path, bp):
                return True
        return False

    def is_tag(self, path, project=None):
        for tp in self.tags:
            if wildcard_matches(path, tp):
                return True
        return False

    def parse(self, path):
        """Parse a path.

        :return: Tuple with type ('tag', 'branch'), project name, branch path and path 
            inside the branch
        """
        parts = path.strip("/").split("/")
        for i in range(len(parts)+1):
            bp = "/".join(parts[:i])
            if self.is_branch(bp):
                return ("branch", bp, bp, path[len(bp):].strip("/"))
            if self.is_tag(bp):
                return ("tag", bp, bp, path[len(bp):].strip("/"))

        raise bzr_errors.NotBranchError(path)

    def get_branches(self, repository, revnum, project=None, pb=None):
        """Retrieve a list of paths that refer to branches in a specific revision.

        :result: Iterator over tuples with (project, branch path)
        """
        return get_root_paths(repository, self.branches,
             revnum, self.is_branch, project)

    def get_tags(self, repository, revnum, project=None, pb=None):
        """Retrieve a list of paths that refer to tags in a specific revision.

        :result: Iterator over tuples with (project, branch path)
        """
        return get_root_paths(repository, self.tags,
             revnum, self.is_tag, project)

    def __repr__(self):
        return "%s(%r,%r)" % (self.__class__.__name__, self.branches, self.tags)


class ConfigBasedLayout(WildcardLayout):

    def _get_list(self, name):
        try:
            return self._config.get_user_option(name).split(";")
        except TypeError:
            return []

    def __init__(self, repository):
        self.repository = repository
        self._config = repository.get_config()
        super(ConfigBasedLayout, self).__init__(self._get_list("branches"),
                                                self._get_list("tags"))

