# Copyright (C) 2006 Jelmer Vernooij <jelmer@samba.org>

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
"""Simple transport for accessing Subversion smart servers."""

from bzrlib import debug, urlutils
from bzrlib.errors import (NoSuchFile, NotBranchError, TransportNotPossible, 
                           FileExists, NotLocalUrl, InvalidURL)
from bzrlib.trace import mutter
from bzrlib.transport import Transport

from core import SubversionException
from auth import create_auth_baton
import ra
import core
import client
import constants

from errors import convert_svn_error, NoSvnRepositoryPresent

svn_config = core.get_config(None)

def get_client_string():
    """Return a string that can be send as part of the User Agent string."""
    return "bzr%s+bzr-svn%s" % (bzrlib.__version__, bzrlib.plugins.svn.__version__)


def create_svn_client():
    ret = client.Client()
    # FIXME ret.
    return ret


# Don't run any tests on SvnTransport as it is not intended to be 
# a full implementation of Transport
def get_test_permutations():
    return []


def get_svn_ra_transport(bzr_transport):
    """Obtain corresponding SvnRaTransport for a stock Bazaar transport."""
    if isinstance(bzr_transport, SvnRaTransport):
        return bzr_transport

    return SvnRaTransport(bzr_transport.base)


def bzr_to_svn_url(url):
    """Convert a Bazaar URL to a URL understood by Subversion.

    This will possibly remove the svn+ prefix.
    """
    if (url.startswith("svn+http://") or 
        url.startswith("svn+file://") or
        url.startswith("svn+https://")):
        url = url[len("svn+"):] # Skip svn+

    # The SVN libraries don't like trailing slashes...
    return url.rstrip('/')


class SvnRaTransport(Transport):
    """Fake transport for Subversion-related namespaces.
    
    This implements just as much of Transport as is necessary 
    to fool Bazaar. """
    @convert_svn_error
    def __init__(self, url="", _backing_url=None):
        bzr_url = url
        self.svn_url = bzr_to_svn_url(url)
        self._root = None
        # _backing_url is an evil hack so the root directory of a repository 
        # can be accessed on some HTTP repositories. 
        if _backing_url is None:
            _backing_url = self.svn_url
        self._backing_url = _backing_url.rstrip("/")
        Transport.__init__(self, bzr_url)

        try:
            self.mutter('opening SVN RA connection to %r' % self._backing_url)
            self._ra = ra.RemoteAccess(self._backing_url.encode('utf8'))
            # FIXME: Callbacks
            # FIXME: self._ra = create_auth_baton()
        except SubversionException, (_, num):
            if num in (constants.ERR_RA_SVN_REPOS_NOT_FOUND,):
                raise NoSvnRepositoryPresent(url=url)
            if num == constants.ERR_BAD_URL:
                raise InvalidURL(url)
            raise

        from bzrlib.plugins.svn import lazy_check_versions
        lazy_check_versions()

    def mutter(self, text):
        if 'transport' in debug.debug_flags:
            mutter(text)

    def has(self, relpath):
        """See Transport.has()."""
        # TODO: Raise TransportNotPossible here instead and 
        # catch it in bzrdir.py
        return False

    def get(self, relpath):
        """See Transport.get()."""
        # TODO: Raise TransportNotPossible here instead and 
        # catch it in bzrdir.py
        raise NoSuchFile(path=relpath)

    def stat(self, relpath):
        """See Transport.stat()."""
        raise TransportNotPossible('stat not supported on Subversion')

    @convert_svn_error
    def get_uuid(self):
        self.mutter('svn get-uuid')
        return self._ra.get_uuid()

    def get_repos_root(self):
        root = self.get_svn_repos_root()
        if (self.base.startswith("svn+http:") or 
            self.base.startswith("svn+https:")):
            return "svn+%s" % root
        return root

    @convert_svn_error
    def get_svn_repos_root(self):
        if self._root is None:
            self.mutter("svn get-repos-root")
            self._root = self._ra.get_repos_root()
        return self._root

    @convert_svn_error
    def get_latest_revnum(self):
        self.mutter("svn get-latest-revnum")
        return self._ra.get_latest_revnum()

    @convert_svn_error
    def do_switch(self, switch_rev, recurse, switch_url, editor):
        self._open_real_transport()
        self.mutter('svn switch -r %d -> %r' % (switch_rev, switch_url))
        return self._ra.do_switch(switch_rev, "", recurse, switch_url, editor)

    @convert_svn_error
    def get_log(self, path, from_revnum, to_revnum, limit, discover_changed_paths, 
                strict_node_history, revprops, rcvr):
        self.mutter('svn log %r:%r %r' % (from_revnum, to_revnum, path))
        return self._ra.get_log(rcvr, [self._request_path(path)], 
                              from_revnum, to_revnum, limit, discover_changed_paths, 
                              strict_node_history, revprops)

    def _open_real_transport(self):
        if self._backing_url != self.svn_url:
            self.reparent(self.base)
        assert self._backing_url == self.svn_url

    def reparent_root(self):
        if self._is_http_transport():
            self.svn_url = self.get_svn_repos_root()
            self.base = self.get_repos_root()
        else:
            self.reparent(self.get_repos_root())

    @convert_svn_error
    def change_rev_prop(self, revnum, name, value):
        self.mutter('svn revprop -r%d --set %s=%s' % (revnum, name, value))
        self._ra.change_rev_prop(revnum, name, value)

    @convert_svn_error
    def reparent(self, url):
        url = url.rstrip("/")
        self.base = url
        self.svn_url = bzr_to_svn_url(url)
        if self.svn_url == self._backing_url:
            return
        if hasattr(self._ra, 'reparent'):
            self.mutter('svn reparent %r' % url)
            self._ra.reparent(self.svn_url)
        else:
            self.mutter('svn reparent (reconnect) %r' % url)
            self._ra = self._client.open_ra_session(self.svn_url.encode('utf8'))
        self._backing_url = self.svn_url

    @convert_svn_error
    def get_dir(self, path, revnum, kind=False):
        self.mutter("svn ls -r %d '%r'" % (revnum, path))
        assert len(path) == 0 or path[0] != "/"
        path = self._request_path(path)
        # ra_dav backends fail with strange errors if the path starts with a 
        # slash while other backends don't.
        fields = 0
        if kind:
            fields += core.SVN_DIRENT_KIND
        return self._ra.get_dir(path, revnum, fields)

    def _request_path(self, relpath):
        if self._backing_url == self.svn_url:
            return relpath.strip("/")
        newrelpath = urlutils.join(
                urlutils.relative_url(self._backing_url+"/", self.svn_url+"/"),
                relpath).strip("/")
        self.mutter('request path %r -> %r' % (relpath, newrelpath))
        return newrelpath

    @convert_svn_error
    def list_dir(self, relpath):
        assert len(relpath) == 0 or relpath[0] != "/"
        if relpath == ".":
            relpath = ""
        try:
            (dirents, _, _) = self.get_dir(self._request_path(relpath),
                                           self.get_latest_revnum())
        except SubversionException, (msg, num):
            if num == constants.ERR_FS_NOT_DIRECTORY:
                raise NoSuchFile(relpath)
            raise
        return dirents.keys()

    @convert_svn_error
    def get_lock(self, path):
        return self._ra.get_lock(path)

    class SvnLock:
        def __init__(self, transport, tokens):
            self._tokens = tokens
            self._transport = transport

        def unlock(self):
            self.transport.unlock(self.locks)

    @convert_svn_error
    def unlock(self, locks, break_lock=False):
        def lock_cb(baton, path, do_lock, lock, ra_err):
            pass
        return self._ra.unlock(locks, break_lock, lock_cb)

    @convert_svn_error
    def lock_write(self, path_revs, comment=None, steal_lock=False):
        return self.PhonyLock() # FIXME
        tokens = {}
        def lock_cb(baton, path, do_lock, lock, ra_err):
            tokens[path] = lock
        self._ra.lock(path_revs, comment, steal_lock, lock_cb)
        return SvnLock(self, tokens)

    @convert_svn_error
    def check_path(self, path, revnum):
        assert len(path) == 0 or path[0] != "/"
        path = self._request_path(path)
        self.mutter("svn check_path -r%d %s" % (revnum, path))
        return self._ra.check_path(path.encode('utf-8'), revnum)

    @convert_svn_error
    def mkdir(self, relpath, mode=None):
        assert len(relpath) == 0 or relpath[0] != "/"
        path = urlutils.join(self.svn_url, relpath)
        try:
            self._client.mkdir([path.encode("utf-8")])
        except SubversionException, (msg, num):
            if num == constants.ERR_FS_NOT_FOUND:
                raise NoSuchFile(path)
            if num == constants.ERR_FS_ALREADY_EXISTS:
                raise FileExists(path)
            raise

    @convert_svn_error
    def replay(self, revision, low_water_mark, editor, send_deltas=True):
        self._open_real_transport()
        self.mutter('svn replay -r%r:%r' % (low_water_mark, revision))
        self._ra.replay(revision, low_water_mark, editor, send_deltas)

    @convert_svn_error
    def do_update(self, revnum, recurse, editor):
        self._open_real_transport()
        self.mutter('svn update -r %r' % revnum)
        return self._ra.do_update(revnum, "", recurse, editor)

    @convert_svn_error
    def has_capability(self, cap):
        return self._ra.has_capability(cap)

    @convert_svn_error
    def revprop_list(self, revnum):
        self.mutter('svn revprop-list -r %r' % revnum)
        return self._ra.rev_proplist(revnum)

    @convert_svn_error
    def get_commit_editor(self, revprops, done_cb, lock_token, keep_locks):
        self._open_real_transport()
        return self._ra.get_commit_editor(revprops, done_cb, lock_token, 
                                          keep_locks)

    def listable(self):
        """See Transport.listable().
        """
        return True

    # There is no real way to do locking directly on the transport 
    # nor is there a need to as the remote server will take care of 
    # locking
    class PhonyLock:
        def unlock(self):
            pass

    def lock_read(self, relpath):
        """See Transport.lock_read()."""
        return self.PhonyLock()

    def _is_http_transport(self):
        return (self.svn_url.startswith("http://") or 
                self.svn_url.startswith("https://"))

    def clone_root(self):
        if self._is_http_transport():
            return SvnRaTransport(self.get_repos_root(), 
                                  bzr_to_svn_url(self.base))
        return SvnRaTransport(self.get_repos_root())

    def clone(self, offset=None):
        """See Transport.clone()."""
        if offset is None:
            return SvnRaTransport(self.base)

        return SvnRaTransport(urlutils.join(self.base, offset))

    def local_abspath(self, relpath):
        """See Transport.local_abspath()."""
        absurl = self.abspath(relpath)
        if self.base.startswith("file:///"):
            return urlutils.local_path_from_url(absurl)
        raise NotLocalUrl(absurl)

    def abspath(self, relpath):
        """See Transport.abspath()."""
        return urlutils.join(self.base, relpath)
