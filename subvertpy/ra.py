# Copyright (C) 2006-2008 Jelmer Vernooij <jelmer@samba.org>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA
"""Python bindings for Subversion."""

__author__ = "Jelmer Vernooij <jelmer@samba.org>"

from subvertpy import SubversionException, ERR_BAD_URL 

from subvertpy import _ra
from subvertpy._ra import *
from subvertpy import ra_svn
from subvertpy.six.moves import urllib_parse
from subvertpy import six

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
    """Connect to a remote Subversion server

    :param url: URL to connect to
    :return: RemoteAccess object
    """
    if six.PY3 and isinstance(url, six.binary_type):
        url = url.decode("utf-8")
    (type, opaque) = urllib_parse.splittype(url)
    if not type in url_handlers:
        raise SubversionException("Unknown URL type '%s'" % type, ERR_BAD_URL)
    return url_handlers[type](url, *args, **kwargs)
