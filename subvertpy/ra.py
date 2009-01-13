# Copyright (C) 2006-2008 Jelmer Vernooij <jelmer@samba.org>

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
"""Python bindings for Subversion."""

__author__ = "Jelmer Vernooij <jelmer@samba.org>"

from __init__ import SubversionException, ERR_BAD_URL 

import _ra
from _ra import *
import ra_svn

import urllib

url_handlers = {
        "svn": _ra.RemoteAccess,
#       "svn": ra_svn.Client,
        "svn+ssh": _ra.RemoteAccess,
#       "svn+ssh": ra_svn.Client,
        "http": _ra.RemoteAccess,
        "https": _ra.RemoteAccess,
        "file": _ra.RemoteAccess,
}

def RemoteAccess(url, *args, **kwargs):
    (type, opaque) = urllib.splittype(url)
    if not type in url_handlers:
        raise SubversionException("Unknown URL type '%s'" % type, ERR_BAD_URL)
    return url_handlers[type](url, *args, **kwargs)
