# Copyright (C) 2005-2008 Jelmer Vernooij <jelmer@samba.org>
 
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

ERR_UNKNOWN_HOSTNAME = 670002
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
ERR_FS_NOT_DIRECTORY = 160016
ERR_FS_NOT_FOUND = 160013
ERR_FS_ALREADY_EXISTS = 160020
ERR_RA_SVN_REPOS_NOT_FOUND = 210005
ERR_WC_NOT_DIRECTORY = 155007
ERR_ENTRY_EXISTS = 150002
ERR_WC_PATH_NOT_FOUND = 155010
ERR_CANCELLED = 200015
ERR_WC_UNSUPPORTED_FORMAT = 155021

AUTH_SSL_NOTYETVALID = 0x00000001
AUTH_SSL_EXPIRED     = 0x00000002
AUTH_SSL_CNMISMATCH  = 0x00000004
AUTH_SSL_UNKNOWNCA   = 0x00000008
AUTH_SSL_OTHER       = 0x40000000

PROP_EXECUTABLE = 'svn:executable'
PROP_EXECUTABLE_VALUE = '*'
PROP_EXTERNALS = 'svn:externals'
PROP_IGNORE = 'svn:ignore'
PROP_KEYWORDS = 'svn:keywords'
PROP_MIME_TYPE = 'svn:mime-type'
PROP_NEEDS_LOCK = 'svn:needs-lock'
PROP_NEEDS_LOCK_VALUE = '*'
PROP_PREFIX = 'svn:'
PROP_SPECIAL = 'svn:special'
PROP_SPECIAL_VALUE = '*'
PROP_WC_PREFIX = 'svn:wc:'
PROP_ENTRY_COMMITTED_DATE = 'svn:entry:committed-date'
PROP_ENTRY_COMMITTED_REV = 'svn:entry:committed-rev'
PROP_ENTRY_LAST_AUTHOR = 'svn:entry:last-author'
PROP_ENTRY_LOCK_TOKEN = 'svn:entry:lock-token'
PROP_ENTRY_UUID = 'svn:entry:uuid'

PROP_REVISION_LOG = "svn:log"
PROP_REVISION_AUTHOR = "svn:author"
PROP_REVISION_DATE = "svn:date"
