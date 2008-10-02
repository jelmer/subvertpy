# Copyright (C) 2007 Jelmer Vernooij <jelmer@samba.org>

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
"""Subversion-specific errors and conversion of Subversion-specific errors."""

from bzrlib.errors import (BzrError, ConnectionError, ConnectionReset, 
                           LockError, PermissionDenied, 
                           DependencyNotPresent, NoRepositoryPresent,
                           TransportError, UnexpectedEndOfContainerError,
                           NoSuchRevision)

import urllib
from bzrlib.plugins.svn import subvertpy


class InvalidBzrSvnRevision(NoSuchRevision):
    _fmt = """Revision id %(revid)s was added incorrectly"""

    def __init__(self, revid):
        self.revid = revid


class NotSvnBranchPath(BzrError):
    """Error raised when a path was specified that did not exist."""
    _fmt = """%(path)s is not a valid Subversion branch path. 
See 'bzr help svn-repository-layout' for details."""

    def __init__(self, branch_path, mapping=None):
        BzrError.__init__(self)
        self.branch_path = urllib.quote(branch_path)
        self.mapping = mapping


class NoSvnRepositoryPresent(NoRepositoryPresent):

    def __init__(self, url):
        BzrError.__init__(self)
        self.path = url


class ChangesRootLHSHistory(BzrError):
    _fmt = """changing lhs branch history not possible on repository root"""


class MissingPrefix(BzrError):
    _fmt = """Prefix missing for %(path)s; please create it before pushing. """

    def __init__(self, path, existing_path):
        BzrError.__init__(self)
        self.path = path
        self.existing_path = existing_path


class RaRequestFailed(BzrError):
    _fmt = """A Subversion remote access command failed: %(message)"""

    def __init__(self, message):
        BzrError.__init__(self)
        self.mesage = message


class RevpropChangeFailed(BzrError):
    _fmt = """Unable to set revision property %(name)s."""

    def __init__(self, name):
        BzrError.__init__(self)
        self.name = name


class DavRequestFailed(BzrError):
    _fmt = """%(msg)s"""

    def __init__(self, msg):
        BzrError.__init__(self)
        self.msg = msg


def convert_error(err):
    """Convert a Subversion exception to the matching BzrError.

    :param err: SubversionException.
    :return: BzrError instance if it could be converted, err otherwise
    """
    (msg, num) = err.args

    if num == subvertpy.ERR_RA_SVN_CONNECTION_CLOSED:
        return ConnectionReset(msg=msg)
    elif num == subvertpy.ERR_WC_LOCKED:
        return LockError(message=msg)
    elif num == subvertpy.ERR_RA_NOT_AUTHORIZED:
        return PermissionDenied('.', msg)
    elif num == subvertpy.ERR_INCOMPLETE_DATA:
        return UnexpectedEndOfContainerError()
    elif num == subvertpy.ERR_RA_SVN_MALFORMED_DATA:
        return TransportError("Malformed data", msg)
    elif num == subvertpy.ERR_RA_NOT_IMPLEMENTED:
        return NotImplementedError("Function not implemented in remote server")
    elif num == subvertpy.ERR_RA_DAV_REQUEST_FAILED:
        return RaRequestFailed(msg)
    elif num == subvertpy.ERR_UNKNOWN_HOSTNAME:
        return ConnectionError(msg=msg)
    elif num == subvertpy.ERR_RA_DAV_REQUEST_FAILED:
        return DavRequestFailed(msg)
    else:
        return err


def convert_svn_error(unbound):
    """Decorator that catches particular Subversion exceptions and 
    converts them to Bazaar exceptions.
    """
    def convert(*args, **kwargs):
        try:
            return unbound(*args, **kwargs)
        except subvertpy.SubversionException, e:
            raise convert_error(e)

    convert.__doc__ = unbound.__doc__
    convert.__name__ = unbound.__name__
    return convert


class InvalidPropertyValue(BzrError):
    _fmt = 'Invalid property value for Subversion property %(property)s: %(msg)s'

    def __init__(self, property, msg):
        BzrError.__init__(self)
        self.property = property
        self.msg = msg

class InvalidFileName(BzrError):
    _fmt = "Unable to convert Subversion path %(path)s because it contains characters invalid in Bazaar."

    def __init__(self, path):
        BzrError.__init__(self)
        self.path = path


class CorruptMappingData(BzrError):
    _fmt = """An invalid change was made to the bzr-specific properties in %(path)s."""

    def __init__(self, path):
        BzrError.__init__(self)
        self.path = path


class LayoutUnusable(BzrError):
    _fmt = """Unable to use layout %(layout)r with mapping %(mapping)r."""

    def __init__(self, layout, mapping):
        BzrError.__init__(self)
        self.layout = layout
        self.mapping = mapping
