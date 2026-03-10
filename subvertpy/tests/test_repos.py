# Copyright (C) 2005-2007 Jelmer Vernooij <jelmer@jelmer.uk>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Subversion repository library tests."""

from io import BytesIO
import os
import textwrap

from subvertpy import repos, SubversionException
from subvertpy.tests import SubversionTestCase, TestCaseInTempDir, TestCase


class VersionTest(TestCase):
    def test_version_length(self):
        self.assertEqual(4, len(repos.version()))

    def test_api_version_length(self):
        self.assertEqual(4, len(repos.api_version()))

    def test_api_version_later_same(self):
        self.assertTrue(repos.api_version() <= repos.version())


class TestRepository(TestCaseInTempDir):
    def setUp(self):
        super(TestRepository, self).setUp()

    def test_create(self):
        repos.create(os.path.join(self.test_dir, "foo"))

    def test_capability(self):
        r = repos.create(os.path.join(self.test_dir, "foo"))
        self.assertIsInstance(r.has_capability("mergeinfo"), bool)

    def test_verify_fs(self):
        r = repos.create(os.path.join(self.test_dir, "foo"))
        f = BytesIO()
        r.verify_fs(f, 0, 0)
        self.assertEqual(b"* Verified revision 0.\n", f.getvalue())

    def test_open(self):
        repos.create(os.path.join(self.test_dir, "foo"))
        repos.Repository("foo")

    def test_uuid(self):
        repos.create(os.path.join(self.test_dir, "foo"))
        self.assertEqual(36, len(repos.Repository("foo").fs().get_uuid()))

    def test_youngest_rev(self):
        repos.create(os.path.join(self.test_dir, "foo"))
        self.assertEqual(0, repos.Repository("foo").fs().youngest_revision())

    def test_rev_root(self):
        repos.create(os.path.join(self.test_dir, "foo"))
        self.assertTrue(repos.Repository("foo").fs().revision_root(0) is not None)

    def test_load_fs_with_hooks(self):
        r = repos.create(os.path.join(self.test_dir, "hooks_test"))
        dumpfile = textwrap.dedent("""\
        SVN-fs-dump-format-version: 2

        UUID: 38f0a982-fd1f-4e00-aa6b-a20720f4b9ca

        Revision-number: 0
        Prop-content-length: 56
        Content-length: 56

        K 8
        svn:date
        V 27
        2011-08-26T13:08:30.187858Z
        PROPS-END
        """).encode("ascii")
        feedback = BytesIO()
        r.load_fs(
            BytesIO(dumpfile),
            feedback,
            repos.LOAD_UUID_DEFAULT,
            use_pre_commit_hook=False,
            use_post_commit_hook=False,
        )

    def test_hotcopy(self):
        src = os.path.join(self.test_dir, "hotcopy_src")
        dest = os.path.join(self.test_dir, "hotcopy_dest")
        repos.create(src)
        repos.hotcopy(src, dest, True)
        self.assertTrue(os.path.exists(dest))

    def test_load_fs_invalid(self):
        r = repos.create(os.path.join(self.test_dir, "foo"))
        dumpfile = b"Malformed"
        feedback = BytesIO()
        self.assertRaises(
            SubversionException,
            r.load_fs,
            BytesIO(dumpfile),
            feedback,
            repos.LOAD_UUID_DEFAULT,
        )

    def test_load_fs(self):
        r = repos.create(os.path.join(self.test_dir, "foo"))
        dumpfile = textwrap.dedent("""\
        SVN-fs-dump-format-version: 2

        UUID: 38f0a982-fd1f-4e00-aa6b-a20720f4b9ca

        Revision-number: 0
        Prop-content-length: 56
        Content-length: 56

        K 8
        svn:date
        V 27
        2011-08-26T13:08:30.187858Z
        PROPS-END
        """).encode("ascii")
        feedback = BytesIO()
        r.load_fs(BytesIO(dumpfile), feedback, repos.LOAD_UUID_DEFAULT)
        self.assertEqual(r.fs().get_uuid(), "38f0a982-fd1f-4e00-aa6b-a20720f4b9ca")

    def test_rev_props(self):
        repos.create(os.path.join(self.test_dir, "foo"))
        self.assertEqual(
            ["svn:date"], list(repos.Repository("foo").fs().revision_proplist(0).keys())
        )

    def test_rev_root_invalid(self):
        repos.create(os.path.join(self.test_dir, "foo"))
        self.assertRaises(
            SubversionException, repos.Repository("foo").fs().revision_root, 1
        )

    def test_pack_fs(self):
        r = repos.create(os.path.join(self.test_dir, "foo"))
        r.pack_fs()

    def test_pack_fs_with_notify(self):
        r = repos.create(os.path.join(self.test_dir, "pack_notify"))
        notifications = []

        def notify_func(shard, action):
            notifications.append((shard, action))

        r.pack_fs(notify_func)

    def test_create_with_config_none(self):
        path = os.path.join(self.test_dir, "cfg_repo")
        r = repos.create(path, config=None)
        self.assertIsNotNone(r)

    def test_create_with_fs_config_none(self):
        path = os.path.join(self.test_dir, "fscfg_repo")
        r = repos.create(path, fs_config=None)
        self.assertIsNotNone(r)

    def test_load_fs_with_parent_dir(self):
        r = repos.create(os.path.join(self.test_dir, "parentdir"))
        dumpfile = textwrap.dedent("""\
        SVN-fs-dump-format-version: 2

        UUID: 38f0a982-fd1f-4e00-aa6b-a20720f4b9ca

        Revision-number: 0
        Prop-content-length: 56
        Content-length: 56

        K 8
        svn:date
        V 27
        2011-08-26T13:08:30.187858Z
        PROPS-END
        """).encode("ascii")
        feedback = BytesIO()
        r.load_fs(BytesIO(dumpfile), feedback, repos.LOAD_UUID_DEFAULT, parent_dir="")

    def test_paths_changed(self):
        repos.create(os.path.join(self.test_dir, "foo"))
        root = repos.Repository("foo").fs().revision_root(0)
        self.assertEqual({}, root.paths_changed())

    def test_is_dir(self):
        repos.create(os.path.join(self.test_dir, "foo"))
        root = repos.Repository("foo").fs().revision_root(0)
        self.assertEqual(True, root.is_dir(""))
        # TODO(jelmer): Newer versions of libsvn_repos crash when passed a
        # nonexistant path.
        # self.assertEqual(False, root.is_dir("nonexistant"))

    def test_is_file(self):
        repos.create(os.path.join(self.test_dir, "foo"))
        root = repos.Repository("foo").fs().revision_root(0)
        self.assertEqual(False, root.is_file(""))
        # TODO(jelmer): Newer versions of libsvn_repos crash when passed a
        # nonexistant path.
        # self.assertEqual(False, root.is_file("nonexistant"))


class TestRepositoryDelete(TestCaseInTempDir):
    def test_delete(self):
        path = os.path.join(self.test_dir, "todelete")
        repos.create(path)
        self.assertTrue(os.path.exists(path))
        repos.delete(path)
        self.assertFalse(os.path.exists(path))


class TestRepositoryHotcopy(TestCaseInTempDir):
    def test_hotcopy(self):
        src = os.path.join(self.test_dir, "src")
        dest = os.path.join(self.test_dir, "dest")
        repos.create(src)
        repos.hotcopy(src, dest)
        self.assertTrue(os.path.exists(dest))
        # Verify the copy is a valid repository
        r = repos.Repository(dest)
        self.assertEqual(0, r.fs().youngest_revision())


class TestFileSystemRoot(TestCaseInTempDir):
    def setUp(self):
        super(TestFileSystemRoot, self).setUp()
        self.repo_path = os.path.join(self.test_dir, "repo")
        repos.create(self.repo_path)

    def test_file_length(self):
        # Commit a file first using the repos API
        r = repos.Repository(self.repo_path)
        root = r.fs().revision_root(0)
        # Root has no files, so we just test on what's available
        # after creation, the root dir exists
        self.assertTrue(root.is_dir(""))

    def test_proplist_root(self):
        r = repos.Repository(self.repo_path)
        root = r.fs().revision_root(0)
        props = root.proplist("")
        self.assertIsInstance(props, dict)


class TestFileSystemRootWithFile(SubversionTestCase):
    """Tests for FileSystemRoot methods that require a committed file."""

    def setUp(self):
        super(TestFileSystemRootWithFile, self).setUp()
        self.repos_url = self.make_repository("d")
        dc = self.get_commit_editor(self.repos_url)
        f = dc.add_file("testfile")
        f.modify(b"hello world")
        dc.close()

    def _get_repo_path(self):
        # file:// URL to path
        import sys

        if sys.platform == "win32":
            from urllib.request import url2pathname

            # On Windows, repos_url is file:///D:/... via pathname2url
            return url2pathname(self.repos_url[len("file:") :])
        return self.repos_url[len("file://") :]

    def test_file_length(self):
        r = repos.Repository(self._get_repo_path())
        root = r.fs().revision_root(1)
        length = root.file_length("testfile")
        self.assertEqual(11, length)

    def test_file_content(self):
        r = repos.Repository(self._get_repo_path())
        root = r.fs().revision_root(1)
        stream = root.file_content("testfile")
        data = stream.read()
        self.assertEqual(b"hello world", data)

    def test_file_checksum_md5(self):
        r = repos.Repository(self._get_repo_path())
        root = r.fs().revision_root(1)
        # kind=0 is svn_checksum_md5
        checksum = root.file_checksum("testfile", 0)
        self.assertIsInstance(checksum, str)
        self.assertEqual(32, len(checksum))

    def test_file_checksum_sha1(self):
        r = repos.Repository(self._get_repo_path())
        root = r.fs().revision_root(1)
        # kind=1 is svn_checksum_sha1
        checksum = root.file_checksum("testfile", 1)
        self.assertIsInstance(checksum, str)
        self.assertEqual(40, len(checksum))

    def test_file_checksum_force(self):
        r = repos.Repository(self._get_repo_path())
        root = r.fs().revision_root(1)
        checksum = root.file_checksum("testfile", 0, True)
        self.assertIsInstance(checksum, str)
        self.assertEqual(32, len(checksum))


class StreamTests(TestCase):
    def test_read(self):
        s = repos.Stream()
        self.assertEqual(b"", s.read())
        self.assertEqual(b"", s.read(15))
        s.close()

    def test_write(self):
        s = repos.Stream()
        self.assertEqual(0, s.write(b""))
        self.assertEqual(2, s.write(b"ab"))
        s.close()

    def test_close(self):
        s = repos.Stream()
        s.close()

    def test_read_full(self):
        s = repos.Stream()
        self.assertEqual(b"", s.read())
        s.close()


class ConstantsTests(TestCase):
    def test_load_uuid_constants(self):
        self.assertIsInstance(repos.LOAD_UUID_DEFAULT, int)
        self.assertIsInstance(repos.LOAD_UUID_IGNORE, int)
        self.assertIsInstance(repos.LOAD_UUID_FORCE, int)

    def test_path_change_constants(self):
        self.assertIsInstance(repos.PATH_CHANGE_MODIFY, int)
        self.assertIsInstance(repos.PATH_CHANGE_ADD, int)
        self.assertIsInstance(repos.PATH_CHANGE_DELETE, int)
        self.assertIsInstance(repos.PATH_CHANGE_REPLACE, int)

    def test_checksum_constants(self):
        self.assertIsInstance(repos.CHECKSUM_MD5, int)
        self.assertIsInstance(repos.CHECKSUM_SHA1, int)
