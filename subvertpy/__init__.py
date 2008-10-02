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

NODE_DIR = 2
NODE_FILE = 1
NODE_NONE = 0
NODE_UNKNOWN = 3

class SubversionException(Exception):
    """A Subversion exception"""

def _check_mtime(m):
    """Check whether a C extension is out of date."""
    import os
    (base, _) = os.path.splitext(m.__file__)
    c_file = "%s.c" % base
    if not os.path.exists(c_file):
        return True
    if os.path.getmtime(m.__file__) < os.path.getmtime(c_file):
        return False
    return True

try:
    import client, ra, repos, wc
    for x in client, ra, repos, wc:
        if not _check_mtime(x):
            warn("bzr-svn extensions are outdated and need to be rebuilt")
            break
except ImportError:
    raise ImportError("Unable to load bzr-svn extensions - did you build it?")

