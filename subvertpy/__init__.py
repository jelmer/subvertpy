# Copyright (C) 2006-2017 Jelmer Vernooij <jelmer@jelmer.uk>

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

import os

__author__ = "Jelmer Vernooij <jelmer@jelmer.uk>"
__version__ = (0, 12, 0)

NODE_DIR = 2
NODE_FILE = 1
NODE_NONE = 0
NODE_UNKNOWN = 3

ERR_UNSUPPORTED_FEATURE = 200007
ERR_RA_SVN_UNKNOWN_CMD = 210001
ERR_RA_SVN_CONNECTION_CLOSED = 210002
ERR_WC_LOCKED = 155004
ERR_RA_NOT_AUTHORIZED = 170001
ERR_INCOMPLETE_DATA = 200003
ERR_DIR_NOT_EMPTY = 200011
ERR_RA_SVN_MALFORMED_DATA = 210004
ERR_RA_NOT_IMPLEMENTED = 170003
ERR_FS_NO_SUCH_REVISION = 160006
ERR_FS_TXN_OUT_OF_DATE = 160028
ERR_REPOS_DISABLED_FEATURE = 165006
ERR_STREAM_MALFORMED_DATA = 140001
ERR_RA_ILLEGAL_URL = 170000
ERR_RA_LOCAL_REPOS_OPEN_FAILED = 180001
ERR_BAD_FILENAME = 125001
ERR_BAD_URL = 125002
ERR_BAD_DATE = 125003
ERR_RA_DAV_REQUEST_FAILED = 175002
ERR_RA_DAV_PATH_NOT_FOUND = 175007
ERR_FS_NOT_DIRECTORY = 160016
ERR_FS_NOT_FOUND = 160013
ERR_FS_ALREADY_EXISTS = 160020
ERR_RA_SVN_REPOS_NOT_FOUND = 210005
ERR_WC_NOT_WORKING_COPY = ERR_WC_NOT_DIRECTORY = 155007
ERR_ENTRY_EXISTS = 150002
ERR_WC_PATH_NOT_FOUND = 155010
ERR_WC_PATH_UNEXPECTED_STATUS = 155035
ERR_CANCELLED = 200015
ERR_WC_UNSUPPORTED_FORMAT = 155021
ERR_UNKNOWN_CAPABILITY = 200026
ERR_AUTHN_NO_PROVIDER = 215001
ERR_RA_DAV_RELOCATED = 175011
ERR_FS_NOT_FILE = 160017
ERR_WC_BAD_ADM_LOG = 155009
ERR_WC_BAD_ADM_LOG_START = 155020
ERR_WC_NOT_LOCKED = 155005
ERR_RA_DAV_NOT_VCC = 20014
ERR_REPOS_HOOK_FAILURE = 165001
ERR_XML_MALFORMED = 130003
ERR_MALFORMED_FILE = 200002
ERR_FS_PATH_SYNTAX = 160005
ERR_RA_DAV_FORBIDDEN = 175013
ERR_WC_SCHEDULE_CONFLICT = 155013
ERR_RA_DAV_PROPPATCH_FAILED = 175008
ERR_SVNDIFF_CORRUPT_WINDOW = 185001
ERR_FS_CONFLICT = 160024
ERR_NODE_UNKNOWN_KIND = 145000
ERR_RA_SERF_SSL_CERT_UNTRUSTED = 230001
ERR_ENTRY_NOT_FOUND = 150000
ERR_BAD_PROPERTY_VALUE = 125005
ERR_FS_ROOT_DIR = 160021
ERR_WC_NODE_KIND_CHANGE = 155018
ERR_WC_UPGRADE_REQUIRED = 155036
ERR_RA_CANNOT_CREATE_SESSION = 170013
ERR_REPOS_BAD_ARGS = 165002

ERR_APR_OS_START_EAIERR = 670000
ERR_APR_OS_ERRSPACE_SIZE = 50000
ERR_CATEGORY_SIZE = 5000


# These will be removed in the next version of subvertpy
ERR_EAI_NONAME = 670008
ERR_UNKNOWN_HOSTNAME = 670002

AUTH_PARAM_DEFAULT_USERNAME = "svn:auth:username"
AUTH_PARAM_DEFAULT_PASSWORD = "svn:auth:password"

SSL_NOTYETVALID = 0x00000001
SSL_EXPIRED = 0x00000002
SSL_CNMISMATCH = 0x00000004
SSL_UNKNOWNCA = 0x00000008
SSL_OTHER = 0x40000000

_module_dir = os.path.dirname(__file__)
_wheel_libs_dir = os.path.join(_module_dir, "../subvertpy.libs")
_wheel_dylibs_dir = os.path.join(_module_dir, ".dylibs")

if os.path.exists(_wheel_libs_dir) or os.path.exists(_wheel_dylibs_dir):
    # when subvertpy is installed from a binary wheel the hardcoded path to
    # certificates in bundled openssl does not necessarily exist on the host
    # system so we ensure one can be found or manipulating remote svn repos
    # through HTTPS does not work
    os.environ["SSL_CERT_FILE"] = os.path.join(_module_dir, "cert/cacert.pem")


class SubversionException(Exception):
    """A Subversion exception."""

    def __init__(self, msg, num, child=None, location=None):
        self.args = (msg, num)
        self.child = child
        self.location = location


class UnsupportedFeature(SubversionException):
    """Trying to use an unsupported feature."""


class RaSvnUnknownCmd(SubversionException):
    """Unknown svn protocol command."""


class RaSvnConnectionClosed(SubversionException):
    """Network connection closed unexpectedly."""


class WcLocked(SubversionException):
    """Attempted to lock an already-locked directory."""


class RaNotAuthorized(SubversionException):
    """Authorization failed."""


class IncompleteData(SubversionException):
    """Incomplete data."""


class DirNotEmpty(SubversionException):
    """Directory needs to be empty but is not."""


class RaSvnMalformedData(SubversionException):
    """Malformed network data."""


class RaNotImplemented(SubversionException):
    """Repository access method not implemented."""


class FsNoSuchRevision(SubversionException):
    """Invalid filesystem revision number."""


class FsTxnOutOfDate(SubversionException):
    """Transaction is out of date."""


class ReposDisabledFeature(SubversionException):
    """Disabled repository feature."""


class StreamMalformedData(SubversionException):
    """Malformed stream data."""


class RaIllegalUrl(SubversionException):
    """Bad URL passed to RA layer."""


class RaLocalReposOpenFailed(SubversionException):
    """Couldn't open a repository."""


class BadFilename(SubversionException):
    """Bogus filename."""


class BadUrl(SubversionException):
    """Bogus URL."""


class BadDate(SubversionException):
    """Bogus date."""


class RaDavRequestFailed(SubversionException):
    """RA layer request failed."""


class RaDavPathNotFound(SubversionException):
    """HTTP path not found."""


class FsNotDirectory(SubversionException):
    """Name does not refer to a filesystem directory."""


class FsNotFound(SubversionException):
    """Filesystem has no item."""


class FsAlreadyExists(SubversionException):
    """Item already exists in filesystem."""


class RaSvnReposNotFound(SubversionException):
    """Couldn't find a repository."""


class WcNotWorkingCopy(SubversionException):
    """Path is not a working copy directory."""


class EntryExists(SubversionException):
    """Entry already exists."""


class WcPathNotFound(SubversionException):
    """Can't find a working copy path."""


class Cancelled(SubversionException):
    """The operation was interrupted."""


class WcUnsupportedFormat(SubversionException):
    """Unsupported working copy format."""


class UnknownCapability(SubversionException):
    """Inquiry about unknown capability."""


class AuthnNoProvider(SubversionException):
    """No authentication provider available."""


class RaDavRelocated(SubversionException):
    """Repository has been moved."""


class FsNotFile(SubversionException):
    """Name does not refer to a filesystem file."""


class WcBadAdmLog(SubversionException):
    """Problem running log."""


class WcBadAdmLogStart(SubversionException):
    """Problem on first log entry in a working copy."""


class WcNotLocked(SubversionException):
    """Working copy not locked."""


class RaDavNotVcc(SubversionException):
    """DAV version-controlled configuration error."""


class ReposHookFailure(SubversionException):
    """A repository hook failed."""


class XmlMalformed(SubversionException):
    """XML data was not well-formed."""


class MalformedFile(SubversionException):
    """Malformed file."""


class FsPathSyntax(SubversionException):
    """Invalid filesystem path syntax."""


class RaDavForbidden(SubversionException):
    """URL access forbidden."""


class WcScheduleConflict(SubversionException):
    """Unmergeable scheduling requested on an entry."""


class RaDavProppatchFailed(SubversionException):
    """Failed to execute WebDAV PROPPATCH."""


class SvndiffCorruptWindow(SubversionException):
    """Svndiff data contains corrupt window."""


class FsConflict(SubversionException):
    """Merge conflict during commit."""


class NodeUnknownKind(SubversionException):
    """Unknown node kind."""


class RaSerfSslCertUntrusted(SubversionException):
    """Server SSL certificate untrusted."""


class EntryNotFound(SubversionException):
    """Can't find an entry."""


class BadPropertyValue(SubversionException):
    """Wrong or unexpected property value."""


class FsRootDir(SubversionException):
    """Attempt to remove or recreate filesystem root directory."""


class WcNodeKindChange(SubversionException):
    """Cannot change node kind."""


class WcUpgradeRequired(SubversionException):
    """The working copy needs to be upgraded."""


class RaCannotCreateSession(SubversionException):
    """Can't create session."""


class ReposBadArgs(SubversionException):
    """Incorrect arguments supplied."""


class EaiNoname(SubversionException):
    """Name or service not known."""


class UnknownHostname(SubversionException):
    """Unknown hostname."""


_error_code_to_class: dict[int, type[SubversionException]] = {
    ERR_UNSUPPORTED_FEATURE: UnsupportedFeature,
    ERR_RA_SVN_UNKNOWN_CMD: RaSvnUnknownCmd,
    ERR_RA_SVN_CONNECTION_CLOSED: RaSvnConnectionClosed,
    ERR_WC_LOCKED: WcLocked,
    ERR_RA_NOT_AUTHORIZED: RaNotAuthorized,
    ERR_INCOMPLETE_DATA: IncompleteData,
    ERR_DIR_NOT_EMPTY: DirNotEmpty,
    ERR_RA_SVN_MALFORMED_DATA: RaSvnMalformedData,
    ERR_RA_NOT_IMPLEMENTED: RaNotImplemented,
    ERR_FS_NO_SUCH_REVISION: FsNoSuchRevision,
    ERR_FS_TXN_OUT_OF_DATE: FsTxnOutOfDate,
    ERR_REPOS_DISABLED_FEATURE: ReposDisabledFeature,
    ERR_STREAM_MALFORMED_DATA: StreamMalformedData,
    ERR_RA_ILLEGAL_URL: RaIllegalUrl,
    ERR_RA_LOCAL_REPOS_OPEN_FAILED: RaLocalReposOpenFailed,
    ERR_BAD_FILENAME: BadFilename,
    ERR_BAD_URL: BadUrl,
    ERR_BAD_DATE: BadDate,
    ERR_RA_DAV_REQUEST_FAILED: RaDavRequestFailed,
    ERR_RA_DAV_PATH_NOT_FOUND: RaDavPathNotFound,
    ERR_FS_NOT_DIRECTORY: FsNotDirectory,
    ERR_FS_NOT_FOUND: FsNotFound,
    ERR_FS_ALREADY_EXISTS: FsAlreadyExists,
    ERR_RA_SVN_REPOS_NOT_FOUND: RaSvnReposNotFound,
    ERR_WC_NOT_WORKING_COPY: WcNotWorkingCopy,
    ERR_ENTRY_EXISTS: EntryExists,
    ERR_WC_PATH_NOT_FOUND: WcPathNotFound,
    ERR_CANCELLED: Cancelled,
    ERR_WC_UNSUPPORTED_FORMAT: WcUnsupportedFormat,
    ERR_UNKNOWN_CAPABILITY: UnknownCapability,
    ERR_AUTHN_NO_PROVIDER: AuthnNoProvider,
    ERR_RA_DAV_RELOCATED: RaDavRelocated,
    ERR_FS_NOT_FILE: FsNotFile,
    ERR_WC_BAD_ADM_LOG: WcBadAdmLog,
    ERR_WC_BAD_ADM_LOG_START: WcBadAdmLogStart,
    ERR_WC_NOT_LOCKED: WcNotLocked,
    ERR_RA_DAV_NOT_VCC: RaDavNotVcc,
    ERR_REPOS_HOOK_FAILURE: ReposHookFailure,
    ERR_XML_MALFORMED: XmlMalformed,
    ERR_MALFORMED_FILE: MalformedFile,
    ERR_FS_PATH_SYNTAX: FsPathSyntax,
    ERR_RA_DAV_FORBIDDEN: RaDavForbidden,
    ERR_WC_SCHEDULE_CONFLICT: WcScheduleConflict,
    ERR_RA_DAV_PROPPATCH_FAILED: RaDavProppatchFailed,
    ERR_SVNDIFF_CORRUPT_WINDOW: SvndiffCorruptWindow,
    ERR_FS_CONFLICT: FsConflict,
    ERR_NODE_UNKNOWN_KIND: NodeUnknownKind,
    ERR_RA_SERF_SSL_CERT_UNTRUSTED: RaSerfSslCertUntrusted,
    ERR_ENTRY_NOT_FOUND: EntryNotFound,
    ERR_BAD_PROPERTY_VALUE: BadPropertyValue,
    ERR_FS_ROOT_DIR: FsRootDir,
    ERR_WC_NODE_KIND_CHANGE: WcNodeKindChange,
    ERR_WC_UPGRADE_REQUIRED: WcUpgradeRequired,
    ERR_RA_CANNOT_CREATE_SESSION: RaCannotCreateSession,
    ERR_REPOS_BAD_ARGS: ReposBadArgs,
    ERR_EAI_NONAME: EaiNoname,
    ERR_UNKNOWN_HOSTNAME: UnknownHostname,
}


def _check_mtime(m):
    """Check whether a C extension is out of date.

    :param m: Python module that is a C extension
    """
    import os

    (base, _) = os.path.splitext(m.__file__)
    c_file = f"{base}.c"
    if not os.path.exists(c_file):
        return True
    if os.path.getmtime(m.__file__) < os.path.getmtime(c_file):
        return False
    return True
