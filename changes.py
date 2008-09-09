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

"""Utility functions for dealing with changes dictionaries as return by Subversions' log functions."""

def path_is_child(branch_path, path):
    """Check whether path is or is under branch_path."""
    return (branch_path == "" or 
            branch_path == path or 
            path.startswith(branch_path+"/"))


def find_prev_location(paths, branch_path, revnum):
    """Find the previous location at which branch_path can be found.
    
    :note: If branch_path wasn't copied, this will return revnum-1 as the 
        previous revision.
    """
    assert isinstance(branch_path, str)
    assert isinstance(revnum, int)
    if revnum == 0:
        assert branch_path == ""
        return None
    # If there are no special cases, just go try the 
    # next revnum in history
    revnum -= 1

    if branch_path == "":
        return (branch_path, revnum)

    # Make sure we get the right location for next time, if 
    # the branch itself was copied
    if (paths.has_key(branch_path) and 
        paths[branch_path][0] in ('R', 'A')):
        if paths[branch_path][1] is None: 
            return None # Was added here
        revnum = paths[branch_path][2]
        assert isinstance(paths[branch_path][1], str)
        branch_path = paths[branch_path][1]
        return (branch_path, revnum)
    
    # Make sure we get the right location for the next time if 
    # one of the parents changed

    # Path names need to be sorted so the longer paths 
    # override the shorter ones
    for p in sorted(paths.keys(), reverse=True):
        if paths[p][0] == 'M':
            continue
        if branch_path.startswith(p+"/"):
            assert paths[p][0] in ('A', 'R'), "Parent %r wasn't added" % p
            assert paths[p][1] is not None, \
                "Empty parent %r added, but child %r wasn't added !?" % (p, branch_path)

            revnum = paths[p][2]
            branch_path = paths[p][1].encode("utf-8") + branch_path[len(p):]
            return (branch_path, revnum)

    return (branch_path, revnum)


def changes_path(changes, path, parents=False):
    """Check if one of the specified changes applies 
    to path or one of its children.

    :param parents: Whether to consider a parent moving a change.
    """
    for p in changes:
        assert isinstance(p, str)
        if path_is_child(path, p):
            return True
        if parents and path.startswith(p+"/") and changes[p][0] in ('R', 'A'):
            return True
    return False


def changes_root(paths):
    """Find the root path that was changed.

    If there is more than one root, returns None
    """
    if paths == []:
        return None
    paths = sorted(paths)
    root = paths[0]
    for p in paths[1:]:
        if p.startswith("%s/" % root): # new path is child of root
            continue
        elif root.startswith("%s/" % p): # new path is parent of root
            root = p
        else:
            return None # Mismatch
    return root

def apply_reverse_changes(branches, changes):
    """

    :return: [(new_name, old_name)]
    """
    branches = set(branches)
    for p in sorted(changes):
        (action, cf, cr) = changes[p]
        if action == 'D':
            for b in list(branches):
                if path_is_child(p, b):
                    branches.remove(b)
                    yield b, None
        elif cf is not None:
            for b in list(branches):
                if path_is_child(p, b):
                    old_b = rebase_path(b, p, cf)
                    yield b, old_b
                    branches.remove(b)
                    branches.add(old_b)


def rebase_path(path, orig_parent, new_parent):
    """Rebase a path on a different parent."""
    return (new_parent+"/"+path[len(orig_parent):].strip("/")).strip("/")

