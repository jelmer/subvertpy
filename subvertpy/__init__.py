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

"""Python bindings for Subversion."""

__author__ = "Jelmer Vernooij <jelmer@samba.org>"
__version__ = (0, 5, 0)

NODE_DIR = 2
NODE_FILE = 1
NODE_NONE = 0
NODE_UNKNOWN = 3

ERR_UNKNOWN_HOSTNAME = 670002
ERR_UNSUPPORTED_FEATURE = 200007
ERR_RA_SVN_UNKNOWN_CMD = 210001
ERR_RA_SVN_CONNECTION_CLOSED = 210002
ERR_WC_LOCKED = 155004
ERR_RA_NOT_AUTHORIZED = 170001
ERR_INCOMPLETE_DATA = 200003
ERR_RA_SVN_MALFORMED_DATA = 210004
ERR_RA_NOT_IMPLEMENTED = 170003
ERR_FS_NO_SUCH_REVISION = 160006
ERR_FS_TXN_OUT_OF_DATE = 160028
ERR_REPOS_DISABLED_FEATURE = 165006
ERR_STREAM_MALFORMED_DATA = 140001
ERR_RA_ILLEGAL_URL = 170000
ERR_RA_LOCAL_REPOS_OPEN_FAILED = 180001
ERR_BAD_URL = 125002
ERR_RA_DAV_REQUEST_FAILED = 175002
ERR_RA_DAV_PATH_NOT_FOUND = 175007
ERR_FS_NOT_DIRECTORY = 160016
ERR_FS_NOT_FOUND = 160013
ERR_FS_ALREADY_EXISTS = 160020
ERR_RA_SVN_REPOS_NOT_FOUND = 210005
ERR_WC_NOT_DIRECTORY = 155007
ERR_ENTRY_EXISTS = 150002
ERR_WC_PATH_NOT_FOUND = 155010
ERR_CANCELLED = 200015
ERR_WC_UNSUPPORTED_FORMAT = 155021
ERR_UNKNOWN_CAPABILITY = 200026
ERR_AUTHN_NO_PROVIDER = 215001
ERR_RA_DAV_RELOCATED = 175011
ERR_FS_NOT_FILE = 160017
ERR_WC_BAD_ADM_LOG = 155009
ERR_RA_DAV_NOT_VCC = 20014

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
            warn("subvertpy extensions are outdated and need to be rebuilt")
            break
except ImportError:
    raise ImportError("Unable to load subvertpy extensions - did you build it?")

