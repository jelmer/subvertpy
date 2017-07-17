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

"""Subversion ra library tests."""

from io import BytesIO

from subvertpy import (
    NODE_DIR, NODE_NONE, NODE_UNKNOWN,
    SubversionException,
    ra,
    )
from subvertpy.tests import (
    SubversionTestCase,
    TestCase,
    )


class VersionTest(TestCase):

    def test_version_length(self):
        self.assertEqual(4, len(ra.version()))

    def test_api_version_length(self):
        self.assertEqual(4, len(ra.api_version()))

    def test_api_version_later_same(self):
        self.assertTrue(ra.api_version() <= ra.version())


class TestRemoteAccessUnknown(TestCase):

    def test_unknown_url(self):
        self.assertRaises(SubversionException, ra.RemoteAccess, "bla://")


class TestRemoteAccess(SubversionTestCase):

    def setUp(self):
        super(TestRemoteAccess, self).setUp()
        self.repos_url = self.make_repository("d")
        self.ra = ra.RemoteAccess(
            self.repos_url, auth=ra.Auth([ra.get_username_provider()]))

    def tearDown(self):
        del self.ra
        super(TestRemoteAccess, self).tearDown()

    def commit_editor(self):
        return self.get_commit_editor(self.repos_url)

    def do_commit(self):
        dc = self.get_commit_editor(self.repos_url)
        dc.add_dir("foo")
        dc.close()

    def test_repr(self):
        self.assertEqual("RemoteAccess(\"%s\")" % self.repos_url,
                         repr(self.ra))

    def test_latest_revnum(self):
        self.assertEqual(0, self.ra.get_latest_revnum())

    def test_latest_revnum_one(self):
        self.do_commit()
        self.assertEqual(1, self.ra.get_latest_revnum())

    def test_get_uuid(self):
        self.assertEqual(36, len(self.ra.get_uuid()))

    def test_get_repos_root(self):
        self.assertEqual(self.repos_url, self.ra.get_repos_root())

    def test_get_url(self):
        if ra.api_version() < (1, 5):
            self.assertRaises(NotImplementedError, self.ra.get_url)
        else:
            self.assertEqual(self.repos_url, self.ra.get_url())

    def test_reparent(self):
        self.ra.reparent(self.repos_url)

    def test_has_capability(self):
        if ra.api_version() < (1, 5):
            self.assertRaises(NotImplementedError, self.ra.has_capability,
                              "FOO")
        else:
            self.assertRaises(SubversionException, self.ra.has_capability,
                              "FOO")

    def test_get_dir(self):
        ret = self.ra.get_dir("", 0)
        self.assertIsInstance(ret, tuple)

    def test_get_dir_leading_slash(self):
        ret = self.ra.get_dir("/", 0)
        self.assertIsInstance(ret, tuple)

    def test_get_dir_kind(self):
        self.do_commit()
        (dirents, fetch_rev, props) = self.ra.get_dir(
                "/", 1, fields=ra.DIRENT_KIND)
        self.assertIsInstance(props, dict)
        self.assertEqual(1, fetch_rev)
        self.assertEqual(NODE_DIR, dirents["foo"]["kind"])

    def test_change_rev_prop(self):
        self.do_commit()
        self.ra.change_rev_prop(1, "foo", "bar")

    def test_rev_proplist(self):
        self.assertIsInstance(self.ra.rev_proplist(0), dict)

    def test_do_diff(self):
        self.do_commit()

        class MyFileEditor:

            def change_prop(self, name, val): pass

            def close(self, checksum=None): pass

        class MyDirEditor:

            def change_prop(self, name, val): pass

            def add_directory(self, *args): return MyDirEditor()

            def add_file(self, *args): return MyFileEditor()

            def close(self): pass

        class MyEditor:

            def set_target_revision(self, rev): pass

            def open_root(self, base_rev):
                return MyDirEditor()

            def close(self): pass
        reporter = self.ra.do_diff(1, "", self.ra.get_repos_root(), MyEditor())
        reporter.set_path("", 0, True)
        reporter.finish()
        self.assertRaises(RuntimeError, reporter.finish)
        self.assertRaises(RuntimeError, reporter.set_path, "", 0, True)

    def test_iter_log_invalid(self):
        self.assertRaises(SubversionException, list, self.ra.iter_log(
                ["idontexist"], 0, 0, revprops=[
                    "svn:date", "svn:author", "svn:log"]))
        self.assertRaises(SubversionException, list, self.ra.iter_log(
                [""], 0, 1000, revprops=["svn:date", "svn:author", "svn:log"]))

    def test_iter_log(self):
        def check_results(returned):
            self.assertEqual(2, len(returned))
            self.assertTrue(len(returned[0]) in (3, 4))
            if len(returned[0]) == 3:
                (paths, revnum, props) = returned[0]
            else:
                (paths, revnum, props, has_children) = returned[0]
            self.assertEqual(None, paths)
            self.assertEqual(revnum, 0)
            self.assertEqual(["svn:date"], list(props.keys()))
            if len(returned[1]) == 3:
                (paths, revnum, props) = returned[1]
            else:
                (paths, revnum, props, has_children) = returned[1]
            if ra.api_version() < (1, 6):
                self.assertEqual({'/foo': ('A', None, -1, NODE_UNKNOWN)},
                                 paths)
            else:
                self.assertEqual({'/foo': ('A', None, -1, NODE_DIR)}, paths)
            self.assertEqual(revnum, 1)
            self.assertEqual(set(["svn:date", "svn:author", "svn:log"]),
                             set(props.keys()))

        returned = list(self.ra.iter_log(
            [""], 0, 0, revprops=["svn:date", "svn:author", "svn:log"]))
        self.assertEqual(1, len(returned))
        self.do_commit()
        returned = list(self.ra.iter_log(
            None, 0, 1, discover_changed_paths=True,
            strict_node_history=False,
            revprops=["svn:date", "svn:author", "svn:log"]))
        check_results(returned)

    def test_get_log(self):
        returned = []

        def cb(*args):
            returned.append(args)

        def check_results(returned):
            self.assertEqual(2, len(returned))
            self.assertTrue(len(returned[0]) in (3, 4))
            if len(returned[0]) == 3:
                (paths, revnum, props) = returned[0]
            else:
                (paths, revnum, props, has_children) = returned[0]
            self.assertEqual(None, paths)
            self.assertEqual(revnum, 0)
            self.assertEqual(["svn:date"], list(props.keys()))
            if len(returned[1]) == 3:
                (paths, revnum, props) = returned[1]
            else:
                (paths, revnum, props, has_children) = returned[1]
            self.assertEqual({'/foo': ('A', None, -1)}, paths)
            self.assertEqual(revnum, 1)
            self.assertEqual(set(["svn:date", "svn:author", "svn:log"]),
                             set(props.keys()))
        self.ra.get_log(cb, [""], 0, 0,
                        revprops=["svn:date", "svn:author", "svn:log"])
        self.assertEqual(1, len(returned))
        self.do_commit()
        returned = []
        self.ra.get_log(cb, None, 0, 1, discover_changed_paths=True,
                        strict_node_history=False,
                        revprops=["svn:date", "svn:author", "svn:log"])
        check_results(returned)

    def test_get_log_cancel(self):

        def cb(*args):
            raise KeyError

        self.do_commit()
        self.assertRaises(
            KeyError,
            self.ra.get_log, cb, [""], 0, 0,
            revprops=["svn:date", "svn:author", "svn:log"])

    def test_get_commit_editor_double_close(self):
        def mycb(*args):
            pass
        editor = self.ra.get_commit_editor({"svn:log": "foo"}, mycb)
        dir = editor.open_root()
        dir.close()
        self.assertRaises(RuntimeError, dir.close)
        editor.close()
        self.assertRaises(RuntimeError, editor.close)
        self.assertRaises(RuntimeError, editor.abort)

    def test_get_commit_editor_busy(self):
        def mycb(rev):
            pass
        editor = self.ra.get_commit_editor({"svn:log": "foo"}, mycb)
        self.assertRaises(
            ra.BusyException, self.ra.get_commit_editor,
            {"svn:log": "foo"}, mycb)
        editor.abort()

    def test_get_commit_editor_double_open(self):
        def mycb(rev):
            pass
        editor = self.ra.get_commit_editor({"svn:log": "foo"}, mycb)
        root = editor.open_root()
        root.add_directory("somedir")
        self.assertRaises(RuntimeError, root.add_directory, "foo")

    def test_get_commit_editor_custom_revprops(self):
        if ra.version()[:2] < (1, 5):
            return

        def mycb(paths, rev, revprops):
            pass

        editor = self.ra.get_commit_editor(
            {"svn:log": "foo", "bar:foo": "bla",
             "svn:custom:blie": "bloe"}, mycb)
        root = editor.open_root()
        root.add_directory("somedir").close()
        root.close()
        editor.close()

        revprops = self.ra.rev_proplist(1)
        self.assertEqual(
            set(['bar:foo', 'svn:author', 'svn:custom:blie', 'svn:date',
                 'svn:log']),
            set(revprops.keys()), "result: %r" % revprops)

    def test_get_commit_editor_context_manager(self):
        def mycb(paths, rev, revprops):
            pass
        editor = self.ra.get_commit_editor({"svn:log": "foo"}, mycb)
        self.assertIs(editor, editor.__enter__())
        dir = editor.open_root(0)
        subdir = dir.add_directory("foo")
        self.assertIs(subdir, subdir.__enter__())
        subdir.__exit__(None, None, None)
        dir.__exit__(None, None, None)
        editor.__exit__(None, None, None)

    def test_get_commit_editor(self):
        def mycb(paths, rev, revprops):
            pass
        editor = self.ra.get_commit_editor({"svn:log": "foo"}, mycb)
        dir = editor.open_root(0)
        subdir = dir.add_directory("foo")
        subdir.close()
        dir.close()
        editor.close()

    def test_commit_file_props(self):
        cb = self.commit_editor()
        f = cb.add_file("bar")
        f.modify(b"a")
        f.change_prop("bla:bar", "blie")
        cb.close()

        cb = self.commit_editor()
        f = cb.open_file("bar")
        f.change_prop("bla:bar", None)
        cb.close()

        stream = BytesIO()
        props = self.ra.get_file("bar", stream, 1)[1]
        self.assertEqual(b"blie", props.get("bla:bar"))
        stream = BytesIO()
        props = self.ra.get_file("bar", stream, 2)[1]
        self.assertIs(None, props.get("bla:bar"))

    def test_get_file_revs(self):
        cb = self.commit_editor()
        cb.add_file("bar").modify(b"a")
        cb.close()

        cb = self.commit_editor()
        f = cb.open_file("bar")
        f.modify(b"b")
        f.change_prop("bla", "bloe")
        cb.close()

        rets = []

        def handle(path, rev, props, from_merge=None):
            rets.append((path, rev, props))

        self.ra.get_file_revs("bar", 1, 2, handle)

        self.assertEqual(2, len(rets))
        self.assertEqual(1, rets[0][1])
        self.assertEqual(2, rets[1][1])
        self.assertEqual("/bar", rets[0][0])
        self.assertEqual("/bar", rets[1][0])

    def test_get_file(self):
        cb = self.commit_editor()
        cb.add_file("bar").modify(b"a")
        cb.close()

        stream = BytesIO()
        self.ra.get_file("bar", stream, 1)
        stream.seek(0)
        self.assertEqual(b"a", stream.read())

        stream = BytesIO()
        self.ra.get_file("/bar", stream, 1)
        stream.seek(0)
        self.assertEqual(b"a", stream.read())

    def test_get_locations_root(self):
        self.assertEqual({0: "/"}, self.ra.get_locations("", 0, [0]))

    def test_check_path(self):
        cb = self.commit_editor()
        cb.add_dir("bar")
        cb.close()

        self.assertEqual(NODE_DIR, self.ra.check_path("bar", 1))
        self.assertEqual(NODE_DIR, self.ra.check_path("bar/", 1))
        self.assertEqual(NODE_NONE, self.ra.check_path("blaaaa", 1))

    def test_stat(self):
        cb = self.commit_editor()
        cb.add_dir("bar")
        cb.close()

        ret = self.ra.stat("bar", 1)
        self.assertEqual(
            set(['last_author', 'kind', 'created_rev', 'has_props', 'time',
                 'size']),
            set(ret.keys()))

    def test_get_locations_dir(self):
        cb = self.commit_editor()
        cb.add_dir("bar")
        cb.close()

        cb = self.commit_editor()
        cb.add_dir("bla", "bar", 1)
        cb.close()

        cb = self.commit_editor()
        cb.delete("bar")
        cb.close()

        self.assertEqual(
                {1: "/bar", 2: "/bla"},
                self.ra.get_locations("bla", 2, [1, 2]))

        self.assertEqual(
                {1: "/bar", 2: "/bar"},
                self.ra.get_locations("bar", 1, [1, 2]))

        self.assertEqual(
                {1: "/bar", 2: "/bar"},
                self.ra.get_locations("bar", 2, [1, 2]))

        self.assertEqual(
                {1: "/bar", 2: "/bla", 3: "/bla"},
                self.ra.get_locations("bla", 3, [1, 2, 3]))


class AuthTests(TestCase):

    def test_not_list(self):
        self.assertRaises(TypeError, ra.Auth, ra.get_simple_provider())

    def test_not_registered(self):
        auth = ra.Auth([])
        self.assertRaises(
            SubversionException, auth.credentials, "svn.simple", "MyRealm")

    def test_simple(self):
        auth = ra.Auth([ra.get_simple_prompt_provider(
            lambda realm, uname, may_save: ("foo", "geheim", False), 0)])
        creds = auth.credentials("svn.simple", "MyRealm")
        self.assertEqual(("foo", "geheim", 0), next(creds))
        self.assertRaises(StopIteration, next, creds)

    def test_username(self):
        auth = ra.Auth([ra.get_username_prompt_provider(
            lambda realm, may_save: ("somebody", False), 0)])
        creds = auth.credentials("svn.username", "MyRealm")
        self.assertEqual(("somebody", 0), next(creds))
        self.assertRaises(StopIteration, next, creds)

    def test_client_cert(self):
        auth = ra.Auth([ra.get_ssl_client_cert_prompt_provider(
            lambda realm, may_save: ("filename", False), 0)])
        creds = auth.credentials("svn.ssl.client-cert", "MyRealm")
        self.assertEqual(("filename", False), next(creds))
        self.assertRaises(StopIteration, next, creds)

    def test_client_cert_pw(self):
        auth = ra.Auth([ra.get_ssl_client_cert_pw_prompt_provider(
            lambda realm, may_save: ("supergeheim", False), 0)])
        creds = auth.credentials("svn.ssl.client-passphrase", "MyRealm")
        self.assertEqual(("supergeheim", False), next(creds))
        self.assertRaises(StopIteration, next, creds)

    def test_server_trust(self):
        auth = ra.Auth([ra.get_ssl_server_trust_prompt_provider(
            lambda realm, failures, certinfo, may_save: (42, False))])
        auth.set_parameter("svn:auth:ssl:failures", 23)
        creds = auth.credentials("svn.ssl.server", "MyRealm")
        self.assertEqual((42, 0), next(creds))
        self.assertRaises(StopIteration, next, creds)

    def test_server_untrust(self):
        auth = ra.Auth([ra.get_ssl_server_trust_prompt_provider(
            lambda realm, failures, certinfo, may_save: None)])
        auth.set_parameter("svn:auth:ssl:failures", 23)
        creds = auth.credentials("svn.ssl.server", "MyRealm")
        self.assertRaises(StopIteration, next, creds)

    def test_retry(self):
        self.i = 0

        def inc_foo(realm, may_save):
            self.i += 1
            return ("somebody%d" % self.i, False)
        auth = ra.Auth([ra.get_username_prompt_provider(inc_foo, 2)])
        creds = auth.credentials("svn.username", "MyRealm")
        self.assertEqual(("somebody1", 0), next(creds))
        self.assertEqual(("somebody2", 0), next(creds))
        self.assertEqual(("somebody3", 0), next(creds))
        self.assertRaises(StopIteration, next, creds)

    def test_set_default_username(self):
        a = ra.Auth([])
        a.set_parameter("svn:auth:username", "foo")
        self.assertEqual("foo", a.get_parameter("svn:auth:username"))

    def test_set_default_password(self):
        a = ra.Auth([])
        a.set_parameter("svn:auth:password", "bar")
        self.assertEqual("bar", a.get_parameter("svn:auth:password"))

    def test_platform_auth_providers(self):
        ra.Auth(ra.get_platform_specific_client_providers())
