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

from bzrlib import ui
from bzrlib.trace import mutter

from bzrlib.plugins.svn.layout.standard import TrunkLayout

# Number of revisions to evaluate when guessing the repository layout
GUESS_SAMPLE_SIZE = 2000

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


def guess_layout_from_branch_path(relpath):
    """Try to guess the branching layout from a branch path.

    :param relpath: Relative URL to a branch.
    :return: New Branchinglayout instance.
    """
    parts = relpath.strip("/").split("/")
    for i in range(0, len(parts)):
        if parts[i] == "trunk" and i == len(parts)-1:
            return TrunkLayout(level=i)
        elif parts[i] in ("branches", "tags") and i == len(parts)-2:
            return TrunkLayout(level=i)

    if parts == [""]:
        return RootLayout()
    return CustomLayout([relpath])


def guess_layout_from_path(relpath):
    """Try to guess the branching layout from a path in the repository, 
    not necessarily a branch path.

    :param relpath: Relative path in repository
    :return: New Branchinglayout instance.
    """
    parts = relpath.strip("/").split("/")
    for i in range(0, len(parts)):
        if parts[i] == "trunk":
            return TrunkLayout(level=i)
        elif parts[i] in ("branches", "tags"):
            return TrunkLayout(level=i)

    return RootLayout()


def guess_layout_from_history(changed_paths, last_revnum, relpath=None):
    """Try to determine the best fitting layout.

    :param changed_paths: Iterator over (branch_path, changes, revnum, revprops)
        as returned from LogWalker.iter_changes().
    :param last_revnum: Number of entries in changed_paths.
    :param relpath: Branch path that should be accepted by the branching 
                    scheme as a branch.
    :return: Tuple with layout that best matches history and 
             layout instance that best matches but also considers
             relpath a valid branch path.
    """
    potentials = {}
    pb = ui.ui_factory.nested_progress_bar()
    layout_cache = {}
    try:
        for (revpaths, revnum, revprops) in changed_paths:
            assert isinstance(revpaths, dict)
            pb.update("analyzing repository layout", last_revnum-revnum, 
                      last_revnum)
            if revpaths == {}:
                continue
            for path in find_commit_paths([revpaths]):
                layout = guess_layout_from_path(path)
                if not potentials.has_key(str(layout)):
                    potentials[str(layout)] = 0
                potentials[str(layout)] += 1
                layout_cache[str(layout)] = layout
    finally:
        pb.finished()
    
    entries = potentials.items()
    entries.sort(lambda (a, b), (c, d): d - b)

    mutter('potential branching layouts: %r' % entries)

    if len(entries) > 0:
        best_match = layout_cache[entries[0][0]]
    else:
        best_match = None

    if relpath is None:
        if best_match is None:
            return (None, RootLayout())
        return (best_match, best_match)

    for (layoutname, _) in entries:
        layout = layout_cache[layoutname]
        if layout.is_branch(relpath):
            return (best_match, layout)

    return (best_match, guess_layout_from_branch_path(relpath))


def repository_guess_layout(repository, revnum, branch_path=None):
    pb = ui.ui_factory.nested_progress_bar()
    try:
        (guessed_layout, layout) = guess_layout_from_history(
            repository._log.iter_changes(None, revnum, max(0, revnum-GUESS_SAMPLE_SIZE), pb=pb), revnum, branch_path)
    finally:
        pb.finished()
    mutter("Guessed repository layout: %r, guess layout to use: %r" % 
            (guessed_layout, layout))
    return (guessed_layout, layout)



