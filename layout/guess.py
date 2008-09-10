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

from bzrlib.plugins.svn.layout.standard import TrunkLayout

def find_commit_paths(changed_paths):
    """Find the commit-paths used in a bunch of revisions.

    :param changed_paths: List of changed_paths (dictionary with path -> action)
    :return: List of potential commit paths.
    """
    for changes in changed_paths:
        yield _find_common_prefix(changes.keys())


def _find_common_prefix(paths):
    prefix = ""
    # Find a common prefix
    parts = paths[0].split("/")
    for i in range(len(parts)+1):
        for j in paths:
            if j.split("/")[:i] != parts[:i]:
                return prefix
        prefix = "/".join(parts[:i])
    return prefix

def repository_guess_layout(repository, revnum):
    # FIXME
    return TrunkLayout(), TrunkLayout()



