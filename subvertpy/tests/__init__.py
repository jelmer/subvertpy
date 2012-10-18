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

"""Tests for subvertpy."""

__author__ = 'Jelmer Vernooij <jelmer@samba.org>'
__docformat__ = 'restructuredText'

import os
import shutil
import stat
import sys
import tempfile
import unittest
try:
    from unittest import SkipTest
except ImportError:
    try:
        from unittest2 import SkipTest
    except ImportError:
        from testtools.testcase import TestSkipped as SkipTest
import urllib2
import urllib
import urlparse

from subvertpy.six import BytesIO,b
from subvertpy import (
    client,
    delta,
    properties,
    ra,
    repos,
    )
from subvertpy.ra import (
    Auth,
    RemoteAccess,
    )


def rmtree_with_readonly(path):
    """Simple wrapper for shutil.rmtree that can remove read-only files.

    In Windows a read-only file cannot be removed, and shutil.rmtree fails.
    """
    def force_rm_handle(remove_path, path, excinfo):
        os.chmod(path, os.stat(path).st_mode | stat.S_IWUSR | stat.S_IWGRP |
            stat.S_IWOTH)
        remove_path(path)
    shutil.rmtree(path, onerror=force_rm_handle)


class TestCase(unittest.TestCase):
    """Base test case.

    :note: Adds assertIsInstance and assertIs.
    """

    def assertIsInstance(self, obj, kls, msg=None):
        """Fail if obj is not an instance of kls"""
        if not isinstance(obj, kls):
            if msg is None: msg = "%r is an instance of %s rather than %s" % (
                obj, obj.__class__, kls)
            self.fail(msg)

    def assertIs(self, left, right, message=None):
        if not (left is right):
            if message is not None:
                raise AssertionError(message)
            else:
                raise AssertionError("%r is not %r." % (left, right))


class TestCaseInTempDir(TestCase):
    """Test case that runs in a temporary directory."""

    def setUp(self):
        TestCase.setUp(self)
        self._oldcwd = os.getcwd()
        self.test_dir = tempfile.mkdtemp()
        os.chdir(self.test_dir)

    def tearDown(self):
        TestCase.tearDown(self)
        os.chdir(self._oldcwd)
        rmtree_with_readonly(self.test_dir)


class TestFileEditor(object):
    """Simple file editor wrapper that doesn't require closing."""

    def __init__(self, file):
        self.file = file
        self.is_closed = False

    def change_prop(self, name, value):
        self.file.change_prop(name, value)

    def modify(self, contents=None):
        if contents is None:
            contents = os.urandom(100)
        txdelta = self.file.apply_textdelta()
        delta.send_stream(BytesIO(b(contents)), txdelta)

    def close(self):
        assert not self.is_closed
        self.is_closed = True
        self.file.close()


class TestDirEditor(object):
    """Simple dir editor wrapper that doesn't require closing."""

    def __init__(self, dir, baseurl, revnum):
        self.dir = dir
        self.baseurl = baseurl
        self.revnum = revnum
        self.is_closed = False
        self.children = []

    def close_children(self):
        for c in reversed(self.children):
            if not c.is_closed:
                c.close()

    def close(self):
        assert not self.is_closed
        self.is_closed = True
        self.close_children()
        self.dir.close()

    def change_prop(self, name, value):
        self.close_children()
        self.dir.change_prop(name, value)

    def open_dir(self, path):
        self.close_children()
        child = TestDirEditor(self.dir.open_directory(path, -1), self.baseurl, self.revnum)
        self.children.append(child)
        return child

    def open_file(self, path):
        self.close_children()
        child = TestFileEditor(self.dir.open_file(path, -1))
        self.children.append(child)
        return child

    def add_dir(self, path, copyfrom_path=None, copyfrom_rev=-1):
        self.close_children()
        if copyfrom_path is not None:
            copyfrom_path = urlparse.urljoin(self.baseurl+"/", copyfrom_path)
        if copyfrom_path is not None and copyfrom_rev == -1:
            copyfrom_rev = self.revnum
        assert (copyfrom_path is None and copyfrom_rev == -1) or \
               (copyfrom_path is not None and copyfrom_rev > -1)
        child = TestDirEditor(self.dir.add_directory(path, copyfrom_path,
            copyfrom_rev), self.baseurl, self.revnum)
        self.children.append(child)
        return child

    def add_file(self, path, copyfrom_path=None, copyfrom_rev=-1):
        self.close_children()
        if copyfrom_path is not None:
            copyfrom_path = urlparse.urljoin(self.baseurl+"/", copyfrom_path)
        if copyfrom_path is not None and copyfrom_rev == -1:
            copyfrom_rev = self.revnum
        child = TestFileEditor(self.dir.add_file(path, copyfrom_path,
            copyfrom_rev))
        self.children.append(child)
        return child

    def delete(self, path):
        self.close_children()
        self.dir.delete_entry(path)


class TestCommitEditor(TestDirEditor):
    """Simple commit editor wrapper."""

    def __init__(self, editor, baseurl, revnum):
        self.editor = editor
        TestDirEditor.__init__(self, self.editor.open_root(), baseurl, revnum)

    def close(self):
        TestDirEditor.close(self)
        self.editor.close()


class SubversionTestCase(TestCaseInTempDir):
    """A test case that provides the ability to build Subversion
    repositories."""

    def _init_client(self):
        self.client_ctx = client.Client()
        self.client_ctx.auth = Auth([ra.get_simple_provider(),
                                     ra.get_username_provider(),
                                     ra.get_ssl_client_cert_file_provider(),
                                     ra.get_ssl_client_cert_pw_file_provider(),
                                     ra.get_ssl_server_trust_file_provider()])
        self.client_ctx.log_msg_func = self.log_message_func
        #self.client_ctx.notify_func = lambda err: mutter("Error: %s" % err)

    def setUp(self):
        super(SubversionTestCase, self).setUp()
        self._init_client()

    def tearDown(self):
        del self.client_ctx
        super(SubversionTestCase, self).tearDown()

    def log_message_func(self, items):
        return self.next_message

    def make_repository(self, relpath, allow_revprop_changes=True):
        """Create a repository.

        :return: Handle to the repository.
        """
        abspath = os.path.join(self.test_dir, relpath)

        repos.create(abspath)

        if allow_revprop_changes:
            if sys.platform == 'win32':
                revprop_hook = os.path.join(abspath, "hooks",
                        "pre-revprop-change.bat")
                f = open(revprop_hook, 'w')
                try:
                    f.write("exit 0\n")
                finally:
                    f.close()
            else:
                revprop_hook = os.path.join(abspath, "hooks",
                        "pre-revprop-change")
                f = open(revprop_hook, 'w')
                try:
                    f.write("#!/bin/sh\n")
                finally:
                    f.close()
                os.chmod(revprop_hook, os.stat(revprop_hook).st_mode | 0111)

        if sys.platform == 'win32':
            return 'file:%s' % urllib.pathname2url(abspath)
        else:
            return "file://%s" % abspath


    def make_checkout(self, repos_url, relpath):
        """Create a new checkout."""
        self.client_ctx.checkout(repos_url, relpath, "HEAD")

    def client_set_prop(self, path, name, value):
        """Set a property on a local file or directory."""
        if value is None:
            value = ""
        self.client_ctx.propset(name, value, path, False, True)

    def client_get_prop(self, path, name, revnum=None, recursive=False):
        """Retrieve a property from a local or remote file or directory."""
        if revnum is None:
            rev = "WORKING"
        else:
            rev = revnum
        ret = self.client_ctx.propget(name, path, rev, rev, recursive)
        if recursive:
            return ret
        else:
            return ret.values()[0]

    def client_get_revprop(self, url, revnum, name):
        """Get the revision property.

        :param url: URL of the repository
        :param revnum: Revision number
        :param name: Property name
        :return: Revision property value
        """
        r = ra.RemoteAccess(url)
        return r.rev_proplist(revnum)[name]

    def client_set_revprop(self, url, revnum, name, value):
        """Set a revision property on a repository.

        :param url: URL of the repository
        :param revnum: Revision number of the revision
        :param name: Name of the property
        :param value: Value of the property, None to remove
        """
        r = ra.RemoteAccess(url, auth=Auth([ra.get_username_provider()]))
        r.change_rev_prop(revnum, name, value)

    def client_resolve(self, path, choice, depth=0):
        """Resolve a conflict set on a local path."""
        self.client_ctx.resolve(path, depth, choice)

    def client_commit(self, dir, message=None, recursive=True):
        """Commit current changes in specified working copy.

        :param dir: List of paths to commit.
        """
        olddir = os.path.abspath('.')
        self.next_message = message
        os.chdir(dir)
        info = self.client_ctx.commit(["."], recursive, False)
        os.chdir(olddir)
        assert info is not None
        return info

    def client_add(self, relpath, recursive=True):
        """Add specified files to working copy.

        :param relpath: Path to the files to add.
        """
        self.client_ctx.add(relpath, recursive, False, False)

    def client_log(self, url, start_revnum, stop_revnum):
        """Fetch the log

        :param url: URL to log
        :param start_revnum: Start revision of the range to log over
        :param start_revnum: Stop revision of the range to log over
        :return: Dictionary
        """
        r = ra.RemoteAccess(url)
        assert isinstance(url, str)
        ret = {}
        def rcvr(orig_paths, rev, revprops, has_children=None):
            ret[rev] = (orig_paths,
                    revprops.get(properties.PROP_REVISION_AUTHOR),
                    revprops.get(properties.PROP_REVISION_DATE),
                    revprops.get(properties.PROP_REVISION_LOG))
        r.get_log(rcvr, [""], start_revnum, stop_revnum, 0, True, True,
                  revprops=[properties.PROP_REVISION_AUTHOR,
                      properties.PROP_REVISION_DATE,
                      properties.PROP_REVISION_LOG])
        return ret

    def client_delete(self, relpath):
        """Remove specified files from working copy.

        :param relpath: Path to the files to remove.
        """
        self.client_ctx.delete([relpath], True)

    def client_copy(self, oldpath, newpath, revnum=None):
        """Copy file in working copy.

        :param oldpath: Relative path to original file.
        :param newpath: Relative path to new file.
        """
        if revnum is None:
            rev = "HEAD"
        else:
            rev = revnum
        self.client_ctx.copy(oldpath, newpath, rev)

    def client_update(self, path):
        """Update path.

        :param path: Path
        """
        self.client_ctx.update([path], "HEAD", True)

    def build_tree(self, files):
        """Create a directory tree.

        :param files: Dictionary with filenames as keys, contents as
            values. None as value indicates a directory.
        """
        for name, content in files.iteritems():
            if content is None:
                try:
                    os.makedirs(name)
                except OSError:
                    pass
            else:
                try:
                    os.makedirs(os.path.dirname(name))
                except OSError:
                    pass
                f = open(name, 'w')
                try:
                    f.write(content)
                finally:
                    f.close()

    def make_client(self, repospath, clientpath, allow_revprop_changes=True):
        """Create a repository and a checkout. Return the checkout.

        :param repospath: Optional relpath to check out if not the full
            repository.
        :param clientpath: Path to checkout
        :return: Repository URL.
        """
        repos_url = self.make_repository(repospath,
            allow_revprop_changes=allow_revprop_changes)
        self.make_checkout(repos_url, clientpath)
        return repos_url

    def open_fs(self, relpath):
        """Open a fs.

        :return: FS.
        """
        return repos.Repository(relpath).fs()

    def get_commit_editor(self, url, message="Test commit"):
        """Obtain a commit editor.

        :param url: URL to connect to
        :param message: Commit message
        :return: Commit editor object
        """
        ra_ctx = RemoteAccess(url.encode("utf-8"),
            auth=Auth([ra.get_username_provider()]))
        revnum = ra_ctx.get_latest_revnum()
        return TestCommitEditor(ra_ctx.get_commit_editor({"svn:log": message}),
            ra_ctx.url, revnum)


def test_suite():
    names = [
        'client',
        'core',
        'delta',
        'marshall',
        'properties',
        'ra',
        'repos',
        'server',
        'wc',
        ]
    module_names = ['subvertpy.tests.test_' + name for name in names]
    result = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromNames(module_names)
    result.addTests(suite)
    return result
