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
    NODE_DIR,
    NODE_NONE,
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

    def test_unknown_url_bytes(self):
        self.assertRaises(SubversionException, ra.RemoteAccess, b"bla://")

    def test_url_handlers_populated(self):
        self.assertIn("svn", ra.url_handlers)
        self.assertIn("svn+ssh", ra.url_handlers)
        self.assertIn("http", ra.url_handlers)
        self.assertIn("https", ra.url_handlers)
        self.assertIn("file", ra.url_handlers)


class TestRemoteAccess(SubversionTestCase):
    def setUp(self):
        super(TestRemoteAccess, self).setUp()
        self.repos_url = self.make_repository("d")
        self.ra = ra.RemoteAccess(
            self.repos_url, auth=ra.Auth([ra.get_username_provider()])
        )

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
        self.assertEqual('RemoteAccess("%s")' % self.repos_url, repr(self.ra))

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
        self.assertEqual(self.repos_url, self.ra.get_session_url())

    def test_reparent(self):
        self.ra.reparent(self.repos_url)

    def test_has_capability(self):
        self.assertRaises(SubversionException, self.ra.has_capability, "FOO")

    def test_get_dir(self):
        ret = self.ra.get_dir("", 0)
        self.assertIsInstance(ret, tuple)

    def test_get_dir_leading_slash(self):
        ret = self.ra.get_dir("/", 0)
        self.assertIsInstance(ret, tuple)

    def test_get_dir_kind(self):
        self.do_commit()
        (dirents, fetch_rev, props) = self.ra.get_dir("/", 1, fields=ra.DIRENT_KIND)
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
            def change_prop(self, name, val):
                pass

            def close(self, checksum=None):
                pass

        class MyDirEditor:
            def change_prop(self, name, val):
                pass

            def add_directory(self, *args):
                return MyDirEditor()

            def add_file(self, *args):
                return MyFileEditor()

            def close(self):
                pass

        class MyEditor:
            def set_target_revision(self, rev):
                pass

            def open_root(self, base_rev):
                return MyDirEditor()

            def close(self):
                pass

        reporter = self.ra.do_diff(1, "", self.ra.get_repos_root(), MyEditor())
        reporter.set_path("", 0, True)
        reporter.finish()
        self.assertRaises(RuntimeError, reporter.finish)
        self.assertRaises(RuntimeError, reporter.set_path, "", 0, True)

    def test_iter_log_invalid(self):
        self.assertRaises(
            SubversionException,
            list,
            self.ra.iter_log(
                ["idontexist"], 0, 0, revprops=["svn:date", "svn:author", "svn:log"]
            ),
        )
        self.assertRaises(
            SubversionException,
            list,
            self.ra.iter_log(
                [""], 0, 1000, revprops=["svn:date", "svn:author", "svn:log"]
            ),
        )

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
            self.assertEqual({"/foo": ("A", None, -1, NODE_DIR)}, paths)
            self.assertEqual(revnum, 1)
            self.assertEqual(
                set(["svn:date", "svn:author", "svn:log"]), set(props.keys())
            )

        returned = list(
            self.ra.iter_log([""], 0, 0, revprops=["svn:date", "svn:author", "svn:log"])
        )
        self.assertEqual(1, len(returned))
        self.do_commit()
        returned = list(
            self.ra.iter_log(
                None,
                0,
                1,
                discover_changed_paths=True,
                strict_node_history=False,
                revprops=["svn:date", "svn:author", "svn:log"],
            )
        )
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
            self.assertEqual({"/foo": ("A", None, -1)}, paths)
            self.assertEqual(revnum, 1)
            self.assertEqual(
                set(["svn:date", "svn:author", "svn:log"]), set(props.keys())
            )

        self.ra.get_log(cb, [""], 0, 0, revprops=["svn:date", "svn:author", "svn:log"])
        self.assertEqual(1, len(returned))
        self.do_commit()
        returned = []
        self.ra.get_log(
            cb,
            None,
            0,
            1,
            discover_changed_paths=True,
            strict_node_history=False,
            revprops=["svn:date", "svn:author", "svn:log"],
        )
        check_results(returned)

    def test_get_log_cancel(self):

        def cb(*args):
            raise KeyError

        self.do_commit()
        self.assertRaises(
            KeyError,
            self.ra.get_log,
            cb,
            [""],
            0,
            0,
            revprops=["svn:date", "svn:author", "svn:log"],
        )

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
            ra.BusyException, self.ra.get_commit_editor, {"svn:log": "foo"}, mycb
        )
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
            {"svn:log": "foo", "bar:foo": "bla", "svn:custom:blie": "bloe"}, mycb
        )
        root = editor.open_root()
        root.add_directory("somedir").close()
        root.close()
        editor.close()

        revprops = self.ra.rev_proplist(1)
        self.assertEqual(
            set(["bar:foo", "svn:author", "svn:custom:blie", "svn:date", "svn:log"]),
            set(revprops.keys()),
            "result: %r" % revprops,
        )

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

    def test_get_commit_editor_with_lock_tokens(self):
        def mycb(paths, rev, revprops):
            pass

        editor = self.ra.get_commit_editor(
            {"svn:log": "with locks"}, mycb, lock_tokens={}, keep_locks=True
        )
        root = editor.open_root()
        root.close()
        editor.close()

    def test_get_log_with_limit(self):
        self.do_commit()
        returned = []

        def cb(*args):
            returned.append(args)

        self.ra.get_log(cb, [""], 0, 1, limit=1, include_merged_revisions=False)
        self.assertEqual(1, len(returned))

    def test_change_rev_prop_old_value(self):
        self.do_commit()
        old = self.ra.rev_proplist(1).get("foo")
        self.ra.change_rev_prop(1, "foo", "bar", old_value=old)
        self.assertEqual(b"bar", self.ra.rev_proplist(1)["foo"])

    def test_do_diff_with_options(self):
        self.do_commit()

        class MyFileEditor:
            def change_prop(self, name, val):
                pass

            def close(self, checksum=None):
                pass

        class MyDirEditor:
            def change_prop(self, name, val):
                pass

            def add_directory(self, *args):
                return MyDirEditor()

            def add_file(self, *args):
                return MyFileEditor()

            def close(self):
                pass

        class MyEditor:
            def set_target_revision(self, rev):
                pass

            def open_root(self, base_rev):
                return MyDirEditor()

            def close(self):
                pass

        reporter = self.ra.do_diff(
            1,
            "",
            self.ra.get_repos_root(),
            MyEditor(),
            recurse=True,
            ignore_ancestry=True,
            text_deltas=True,
        )
        reporter.set_path("", 0, True)
        reporter.finish()

    def test_replay_send_deltas(self):
        self.do_commit()

        class MyFileEditor:
            def change_prop(self, name, val):
                pass

            def apply_textdelta(self, base_checksum):
                pass

            def close(self, checksum=None):
                pass

        class MyDirEditor:
            def change_prop(self, name, val):
                pass

            def add_directory(self, *args):
                return MyDirEditor()

            def add_file(self, *args):
                return MyFileEditor()

            def close(self):
                pass

        class MyEditor:
            def set_target_revision(self, rev):
                pass

            def open_root(self, base_rev):
                return MyDirEditor()

            def close(self):
                pass

        self.ra.replay(1, 0, MyEditor(), send_deltas=False)

    def test_replay_range_send_deltas(self):
        self.do_commit()

        class MyFileEditor:
            def change_prop(self, name, val):
                pass

            def apply_textdelta(self, base_checksum):
                pass

            def close(self, checksum=None):
                pass

        class MyDirEditor:
            def change_prop(self, name, val):
                pass

            def add_directory(self, *args):
                return MyDirEditor()

            def add_file(self, *args):
                return MyFileEditor()

            def close(self):
                pass

        class MyEditor:
            def set_target_revision(self, rev):
                pass

            def open_root(self, base_rev):
                return MyDirEditor()

            def close(self):
                pass

        editors = []

        def revstart_cb(rev, revprops):
            e = MyEditor()
            editors.append(e)
            return e

        def revfinish_cb(rev, revprops, editor):
            pass

        self.ra.replay_range(1, 1, 0, (revstart_cb, revfinish_cb), send_deltas=False)
        self.assertEqual(1, len(editors))

    def test_do_update_with_options(self):
        self.do_commit()

        class MyFileEditor:
            def change_prop(self, name, val):
                pass

            def close(self, checksum=None):
                pass

        class MyDirEditor:
            def change_prop(self, name, val):
                pass

            def add_directory(self, *args):
                return MyDirEditor()

            def add_file(self, *args):
                return MyFileEditor()

            def close(self):
                pass

        class MyEditor:
            def set_target_revision(self, rev):
                pass

            def open_root(self, base_rev):
                return MyDirEditor()

            def close(self):
                pass

        reporter = self.ra.do_update(
            1, "", True, MyEditor(), send_copyfrom_args=True, ignore_ancestry=True
        )
        reporter.set_path("", 0, True)
        reporter.finish()

    def test_do_switch_with_options(self):
        self.do_commit()

        class MyFileEditor:
            def change_prop(self, name, val):
                pass

            def close(self, checksum=None):
                pass

        class MyDirEditor:
            def change_prop(self, name, val):
                pass

            def add_directory(self, *args):
                return MyDirEditor()

            def add_file(self, *args):
                return MyFileEditor()

            def close(self):
                pass

        class MyEditor:
            def set_target_revision(self, rev):
                pass

            def open_root(self, base_rev):
                return MyDirEditor()

            def close(self):
                pass

        reporter = self.ra.do_switch(
            1,
            "",
            True,
            self.repos_url,
            MyEditor(),
            send_copyfrom_args=True,
            ignore_ancestry=True,
        )
        reporter.set_path("", 0, True)
        reporter.finish()

    def test_get_file_revs_include_merged(self):
        dc = self.commit_editor()
        f = dc.add_file("filerevs")
        f.modify(b"v1")
        dc.close()
        revs = []

        def handler(path, rev, rev_props, prop_diffs=None):
            revs.append(rev)

        self.ra.get_file_revs("filerevs", 0, 1, handler, include_merged_revisions=True)
        self.assertTrue(len(revs) > 0)

    def test_mergeinfo_with_options(self):
        self.do_commit()
        result = self.ra.mergeinfo(
            [""], revision=1, inherit=ra.MERGEINFO_INHERITED, include_descendants=True
        )
        if result is not None:
            self.assertIsInstance(result, dict)

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
            set(["last_author", "kind", "created_rev", "has_props", "time", "size"]),
            set(ret.keys()),
        )

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
            {1: "/bar", 2: "/bla"}, self.ra.get_locations("bla", 2, [1, 2])
        )

        self.assertEqual(
            {1: "/bar", 2: "/bar"}, self.ra.get_locations("bar", 1, [1, 2])
        )

        self.assertEqual(
            {1: "/bar", 2: "/bar"}, self.ra.get_locations("bar", 2, [1, 2])
        )

        self.assertEqual(
            {1: "/bar", 2: "/bla", 3: "/bla"},
            self.ra.get_locations("bla", 3, [1, 2, 3]),
        )


class TestEditorOperations(SubversionTestCase):
    """Tests for editor operations: delete_entry, open_directory, etc."""

    def setUp(self):
        super(TestEditorOperations, self).setUp()
        self.repos_url = self.make_repository("d")

    def commit_editor(self):
        return self.get_commit_editor(self.repos_url)

    def test_delete_entry(self):
        dc = self.commit_editor()
        dc.add_file("todelete").modify(b"bye")
        dc.close()

        dc = self.commit_editor()
        dc.delete("todelete")
        dc.close()

        r = ra.RemoteAccess(self.repos_url, auth=ra.Auth([ra.get_username_provider()]))
        self.assertEqual(NODE_NONE, r.check_path("todelete", 2))

    def test_open_directory(self):
        dc = self.commit_editor()
        subdir = dc.add_dir("mydir")
        subdir.add_file("mydir/inner").modify(b"data")
        dc.close()

        dc = self.commit_editor()
        subdir = dc.open_dir("mydir")
        subdir.add_file("mydir/another").modify(b"more")
        dc.close()

        r = ra.RemoteAccess(self.repos_url, auth=ra.Auth([ra.get_username_provider()]))
        stream = BytesIO()
        r.get_file("mydir/another", stream, 2)
        stream.seek(0)
        self.assertEqual(b"more", stream.read())

    def test_dir_change_prop(self):
        dc = self.commit_editor()
        subdir = dc.add_dir("propdir")
        subdir.change_prop("myprop", "myval")
        dc.close()

        r = ra.RemoteAccess(self.repos_url, auth=ra.Auth([ra.get_username_provider()]))
        (dirents, rev, props) = r.get_dir("propdir", 1)
        self.assertIn("myprop", props)
        self.assertEqual(b"myval", props["myprop"])

    def test_absent_file(self):
        # absent_file is used by editors to signal a file is not present
        # We test it via the low-level commit editor
        r = ra.RemoteAccess(self.repos_url, auth=ra.Auth([ra.get_username_provider()]))
        editor = r.get_commit_editor({"svn:log": "absent test"})
        root = editor.open_root()
        root.absent_file("ghost")
        root.close()
        editor.close()

    def test_absent_directory(self):
        r = ra.RemoteAccess(self.repos_url, auth=ra.Auth([ra.get_username_provider()]))
        editor = r.get_commit_editor({"svn:log": "absent dir test"})
        root = editor.open_root()
        root.absent_directory("ghostdir")
        root.close()
        editor.close()


class AuthTests(TestCase):
    def test_not_list(self):
        self.assertRaises(TypeError, ra.Auth, ra.get_simple_provider())

    def test_not_registered(self):
        auth = ra.Auth([])
        self.assertRaises(
            SubversionException, auth.credentials, "svn.simple", "MyRealm"
        )

    def test_simple(self):
        auth = ra.Auth(
            [
                ra.get_simple_prompt_provider(
                    lambda realm, uname, may_save: ("foo", "geheim", False), 0
                )
            ]
        )
        creds = auth.credentials("svn.simple", "MyRealm")
        self.assertEqual(("foo", "geheim", 0), next(creds))
        self.assertRaises(StopIteration, next, creds)

    def test_username(self):
        auth = ra.Auth(
            [
                ra.get_username_prompt_provider(
                    lambda realm, may_save: ("somebody", False), 0
                )
            ]
        )
        creds = auth.credentials("svn.username", "MyRealm")
        self.assertEqual(("somebody", 0), next(creds))
        self.assertRaises(StopIteration, next, creds)

    def test_client_cert(self):
        auth = ra.Auth(
            [
                ra.get_ssl_client_cert_prompt_provider(
                    lambda realm, may_save: ("filename", False), 0
                )
            ]
        )
        creds = auth.credentials("svn.ssl.client-cert", "MyRealm")
        self.assertEqual(("filename", False), next(creds))
        self.assertRaises(StopIteration, next, creds)

    def test_client_cert_pw(self):
        auth = ra.Auth(
            [
                ra.get_ssl_client_cert_pw_prompt_provider(
                    lambda realm, may_save: ("supergeheim", False), 0
                )
            ]
        )
        creds = auth.credentials("svn.ssl.client-passphrase", "MyRealm")
        self.assertEqual(("supergeheim", False), next(creds))
        self.assertRaises(StopIteration, next, creds)

    def test_server_trust(self):
        auth = ra.Auth(
            [
                ra.get_ssl_server_trust_prompt_provider(
                    lambda realm, failures, certinfo, may_save: (42, False)
                )
            ]
        )
        auth.set_parameter("svn:auth:ssl:failures", 23)
        creds = auth.credentials("svn.ssl.server", "MyRealm")
        self.assertEqual((42, 0), next(creds))
        self.assertRaises(StopIteration, next, creds)

    def test_server_untrust(self):
        auth = ra.Auth(
            [
                ra.get_ssl_server_trust_prompt_provider(
                    lambda realm, failures, certinfo, may_save: None
                )
            ]
        )
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


class TestProviders(TestCase):
    def test_get_simple_provider(self):
        provider = ra.get_simple_provider()
        self.assertIsNotNone(provider)

    def test_get_username_provider(self):
        provider = ra.get_username_provider()
        self.assertIsNotNone(provider)

    def test_get_ssl_client_cert_file_provider(self):
        provider = ra.get_ssl_client_cert_file_provider()
        self.assertIsNotNone(provider)

    def test_get_ssl_client_cert_pw_file_provider(self):
        provider = ra.get_ssl_client_cert_pw_file_provider()
        self.assertIsNotNone(provider)

    def test_get_ssl_server_trust_file_provider(self):
        provider = ra.get_ssl_server_trust_file_provider()
        self.assertIsNotNone(provider)

    def test_print_modules(self):
        result = ra.print_modules()
        self.assertIsInstance(result, bytes)
        self.assertIn(b"ra_local", result)


class TestRemoteAccessProperties(SubversionTestCase):
    def setUp(self):
        super(TestRemoteAccessProperties, self).setUp()
        self.repos_url = self.make_repository("d")
        self.ra_ctx = ra.RemoteAccess(
            self.repos_url, auth=ra.Auth([ra.get_username_provider()])
        )

    def tearDown(self):
        del self.ra_ctx
        super(TestRemoteAccessProperties, self).tearDown()

    def test_url_property(self):
        self.assertEqual(self.repos_url, self.ra_ctx.url)

    def test_busy_property(self):
        self.assertFalse(self.ra_ctx.busy)

    def test_get_lock_nonexistent(self):
        self.do_commit()
        lock = self.ra_ctx.get_lock("/nonexistent")
        self.assertIsNone(lock)

    def test_has_capability_mergeinfo(self):
        result = self.ra_ctx.has_capability("mergeinfo")
        self.assertIsInstance(result, bool)

    def test_has_capability_unknown(self):
        self.assertRaises(SubversionException, self.ra_ctx.has_capability, "bogus")

    def do_commit(self):
        dc = self.get_commit_editor(self.repos_url)
        dc.add_dir("foo")
        dc.close()

    def test_do_update(self):
        self.do_commit()

        class MyFileEditor:
            def change_prop(self, name, val):
                pass

            def close(self, checksum=None):
                pass

        class MyDirEditor:
            def change_prop(self, name, val):
                pass

            def add_directory(self, *args):
                return MyDirEditor()

            def add_file(self, *args):
                return MyFileEditor()

            def close(self):
                pass

        class MyEditor:
            def set_target_revision(self, rev):
                pass

            def open_root(self, base_rev):
                return MyDirEditor()

            def close(self):
                pass

        reporter = self.ra_ctx.do_update(1, "", True, MyEditor())
        reporter.set_path("", 0, True)
        reporter.finish()

    def test_replay(self):
        self.do_commit()

        class MyFileEditor:
            def change_prop(self, name, val):
                pass

            def close(self, checksum=None):
                pass

        class MyDirEditor:
            def change_prop(self, name, val):
                pass

            def add_directory(self, *args):
                return MyDirEditor()

            def add_file(self, *args):
                return MyFileEditor()

            def close(self):
                pass

        class MyEditor:
            def set_target_revision(self, rev):
                pass

            def open_root(self, base_rev):
                return MyDirEditor()

            def close(self):
                pass

        self.ra_ctx.replay(1, 0, MyEditor())

    def test_get_location_segments(self):
        self.do_commit()
        segments = []

        def rcvr(range_start, range_end, path):
            segments.append((range_start, range_end, path))

        self.ra_ctx.get_location_segments("foo", 1, 1, 0, rcvr)
        self.assertEqual(1, len(segments))
        self.assertEqual("foo", segments[0][2])

    def test_get_commit_editor_abort(self):
        def mycb(*args):
            pass

        editor = self.ra_ctx.get_commit_editor({"svn:log": "test"}, mycb)
        editor.abort()

    def test_editor_dir_context_manager(self):
        def mycb(*args):
            pass

        editor = self.ra_ctx.get_commit_editor({"svn:log": "test"}, mycb)
        with editor:
            root = editor.open_root()
            with root:
                subdir = root.add_directory("mydir")
                with subdir:
                    pass

    def test_get_locks_empty(self):
        self.do_commit()
        locks = self.ra_ctx.get_locks("")
        self.assertIsInstance(locks, dict)
        self.assertEqual({}, locks)

    def test_lock_unlock(self):
        # Create a file to lock
        dc = self.get_commit_editor(self.repos_url)
        f = dc.add_file("lockme")
        f.modify(b"content")
        dc.close()

        lock_results = []

        def lock_cb(path, do_lock, lock, ra_err):
            lock_results.append((path, do_lock, lock, ra_err))

        self.ra_ctx.lock({b"lockme": 1}, "locking", False, lock_cb)
        self.assertEqual(1, len(lock_results))

        # Verify lock exists
        locks = self.ra_ctx.get_locks("")
        self.assertIn("/lockme", locks)

        # Lock is a tuple: (path, token, owner, comment, is_dav_comment,
        #                    creation_date, expiration_date)
        lock_tuple = locks["/lockme"]
        token = lock_tuple[1]

        # Now unlock
        unlock_results = []

        def unlock_cb(path, do_lock, lock, ra_err):
            unlock_results.append((path, do_lock, lock, ra_err))

        self.ra_ctx.unlock({b"lockme": token}, False, unlock_cb)
        self.assertEqual(1, len(unlock_results))

        # Verify lock is gone
        locks = self.ra_ctx.get_locks("")
        self.assertEqual({}, locks)

    def test_get_locks_with_lock(self):
        dc = self.get_commit_editor(self.repos_url)
        f = dc.add_file("myfile")
        f.modify(b"data")
        dc.close()

        def lock_cb(path, do_lock, lock, ra_err):
            pass

        self.ra_ctx.lock({b"myfile": 1}, "test lock", False, lock_cb)
        locks = self.ra_ctx.get_locks("")
        self.assertIn("/myfile", locks)
        # Lock is a tuple: (path, token, owner, comment, ...)
        lock_tuple = locks["/myfile"]
        self.assertIsInstance(lock_tuple, tuple)
        self.assertEqual("/myfile", lock_tuple[0])  # path
        self.assertIsNotNone(lock_tuple[1])  # token
        self.assertEqual("test lock", lock_tuple[3])  # comment

        # cleanup
        self.ra_ctx.unlock({b"myfile": lock_tuple[1]}, False, lock_cb)

    def test_get_locks_with_depth(self):
        dc = self.get_commit_editor(self.repos_url)
        f = dc.add_file("lockdepth")
        f.modify(b"data")
        dc.close()

        def lock_cb(path, do_lock, lock, ra_err):
            pass

        self.ra_ctx.lock({b"lockdepth": 1}, "depth lock", False, lock_cb)
        locks = self.ra_ctx.get_locks("", ra.DEPTH_INFINITY)
        self.assertIn("/lockdepth", locks)

        # cleanup
        lock_tuple = locks["/lockdepth"]
        self.ra_ctx.unlock({b"lockdepth": lock_tuple[1]}, False, lock_cb)

    def test_do_switch(self):
        self.do_commit()

        class MyFileEditor:
            def change_prop(self, name, val):
                pass

            def close(self, checksum=None):
                pass

        class MyDirEditor:
            def change_prop(self, name, val):
                pass

            def add_directory(self, *args):
                return MyDirEditor()

            def add_file(self, *args):
                return MyFileEditor()

            def open_directory(self, *args):
                return MyDirEditor()

            def open_file(self, *args):
                return MyFileEditor()

            def delete_entry(self, *args):
                pass

            def close(self):
                pass

        class MyEditor:
            def set_target_revision(self, rev):
                pass

            def open_root(self, base_rev):
                return MyDirEditor()

            def close(self):
                pass

        reporter = self.ra_ctx.do_switch(1, "", True, self.repos_url, MyEditor())
        reporter.set_path("", 0, True)
        reporter.finish()

    def test_replay_range(self):
        self.do_commit()
        # Create another commit
        dc = self.get_commit_editor(self.repos_url)
        dc.add_file("bar").modify(b"content")
        dc.close()

        class MyFileEditor:
            def change_prop(self, name, val):
                pass

            def close(self, checksum=None):
                pass

            def apply_textdelta(self, base_checksum=None):
                return None

        class MyDirEditor:
            def change_prop(self, name, val):
                pass

            def add_directory(self, *args):
                return MyDirEditor()

            def add_file(self, *args):
                return MyFileEditor()

            def close(self):
                pass

        class MyEditor:
            def set_target_revision(self, rev):
                pass

            def open_root(self, base_rev):
                return MyDirEditor()

            def close(self):
                pass

        editors = []

        def revstart_cb(rev, revprops):
            e = MyEditor()
            editors.append(e)
            return e

        def revfinish_cb(rev, revprops, editor):
            pass

        self.ra_ctx.replay_range(1, 2, 0, (revstart_cb, revfinish_cb))
        self.assertEqual(2, len(editors))

    def test_constructor_client_string_func(self):
        def client_string_func():
            return "test-client/1.0"

        ra_ctx = ra.RemoteAccess(
            self.repos_url,
            auth=ra.Auth([ra.get_username_provider()]),
            client_string_func=client_string_func,
        )
        self.assertIsNotNone(ra_ctx)
        ra_ctx.get_latest_revnum()
        del ra_ctx

    def test_constructor_uuid(self):
        ra_ctx = ra.RemoteAccess(
            self.repos_url,
            auth=ra.Auth([ra.get_username_provider()]),
            uuid=self.ra_ctx.get_uuid(),
        )
        self.assertIsNotNone(ra_ctx)
        del ra_ctx

    def test_constructor_progress_cb(self):
        progress_calls = []

        def progress_cb(progress, total):
            progress_calls.append((progress, total))

        ra_ctx = ra.RemoteAccess(
            self.repos_url,
            auth=ra.Auth([ra.get_username_provider()]),
            progress_cb=progress_cb,
        )
        ra_ctx.get_latest_revnum()
        del ra_ctx

    def test_get_simple_provider_callback(self):
        def simple_cb(realm, username, may_save):
            return ("user", "pass", False)

        provider = ra.get_simple_provider(simple_cb)
        self.assertIsNotNone(provider)

    def test_constructor_open_tmp_file_func(self):
        import tempfile

        def open_tmp_file():
            return tempfile.mktemp()

        ra_ctx = ra.RemoteAccess(
            self.repos_url,
            auth=ra.Auth([ra.get_username_provider()]),
            open_tmp_file_func=open_tmp_file,
        )
        self.assertIsNotNone(ra_ctx)
        ra_ctx.get_latest_revnum()
        del ra_ctx

    def test_progress_func(self):
        progress_calls = []

        def progress_cb(progress, total):
            progress_calls.append((progress, total))

        ra_ctx = ra.RemoteAccess(
            self.repos_url, auth=ra.Auth([ra.get_username_provider()])
        )
        ra_ctx.progress_func = progress_cb
        ra_ctx.get_latest_revnum()
        del ra_ctx

    def test_constructor_config(self):
        from subvertpy import client

        config = client.get_config()
        ra_ctx = ra.RemoteAccess(
            self.repos_url, auth=ra.Auth([ra.get_username_provider()]), config=config
        )
        self.assertIsNotNone(ra_ctx)
        ra_ctx.get_latest_revnum()
        del ra_ctx

    def test_reporter_set_path_with_depth(self):
        self.do_commit()

        class MyFileEditor:
            def change_prop(self, name, val):
                pass

            def close(self, checksum=None):
                pass

        class MyDirEditor:
            def change_prop(self, name, val):
                pass

            def add_directory(self, *args):
                return MyDirEditor()

            def add_file(self, *args):
                return MyFileEditor()

            def delete_entry(self, *args):
                pass

            def close(self):
                pass

        class MyEditor:
            def set_target_revision(self, rev):
                pass

            def open_root(self, base_rev):
                return MyDirEditor()

            def close(self):
                pass

        reporter = self.ra_ctx.do_update(1, "", True, MyEditor())
        reporter.set_path("", 0, True, None, ra.DEPTH_INFINITY)
        reporter.finish()

    def test_reporter_link_path_with_options(self):
        self.do_commit()

        class MyFileEditor:
            def change_prop(self, name, val):
                pass

            def close(self, checksum=None):
                pass

        class MyDirEditor:
            def change_prop(self, name, val):
                pass

            def add_directory(self, *args):
                return MyDirEditor()

            def add_file(self, *args):
                return MyFileEditor()

            def open_directory(self, *args):
                return MyDirEditor()

            def open_file(self, *args):
                return MyFileEditor()

            def delete_entry(self, *args):
                pass

            def close(self):
                pass

        class MyEditor:
            def set_target_revision(self, rev):
                pass

            def open_root(self, base_rev):
                return MyDirEditor()

            def close(self):
                pass

        reporter = self.ra_ctx.do_update(1, "", True, MyEditor())
        reporter.set_path("", 0, True)
        reporter.link_path(
            "foo", self.repos_url + "/foo", 1, True, None, ra.DEPTH_INFINITY
        )
        reporter.finish()

    def test_reporter_delete_path(self):
        self.do_commit()

        class MyFileEditor:
            def change_prop(self, name, val):
                pass

            def close(self, checksum=None):
                pass

        class MyDirEditor:
            def change_prop(self, name, val):
                pass

            def add_directory(self, *args):
                return MyDirEditor()

            def add_file(self, *args):
                return MyFileEditor()

            def delete_entry(self, *args):
                pass

            def close(self):
                pass

        class MyEditor:
            def set_target_revision(self, rev):
                pass

            def open_root(self, base_rev):
                return MyDirEditor()

            def close(self):
                pass

        reporter = self.ra_ctx.do_update(1, "", True, MyEditor())
        reporter.set_path("", 0, True)
        reporter.delete_path("foo")
        reporter.finish()

    def test_mergeinfo_empty(self):
        self.do_commit()
        result = self.ra_ctx.mergeinfo(["foo"])
        # No mergeinfo set, so result should be None or empty
        if result is not None:
            self.assertIsInstance(result, dict)

    def test_reporter_link_path(self):
        self.do_commit()

        class MyFileEditor:
            def change_prop(self, name, val):
                pass

            def close(self, checksum=None):
                pass

        class MyDirEditor:
            def change_prop(self, name, val):
                pass

            def add_directory(self, *args):
                return MyDirEditor()

            def open_directory(self, *args):
                return MyDirEditor()

            def add_file(self, *args):
                return MyFileEditor()

            def open_file(self, *args):
                return MyFileEditor()

            def delete_entry(self, *args):
                pass

            def close(self):
                pass

        class MyEditor:
            def set_target_revision(self, rev):
                pass

            def open_root(self, base_rev):
                return MyDirEditor()

            def close(self):
                pass

        reporter = self.ra_ctx.do_update(1, "", True, MyEditor())
        reporter.set_path("", 0, True)
        # link_path(path, url, revision, start_empty)
        reporter.link_path("foo", self.repos_url + "/foo", 1, True)
        reporter.finish()


class ConstantsTests(TestCase):
    def test_depth_constants(self):
        self.assertIsInstance(ra.DEPTH_UNKNOWN, int)
        self.assertIsInstance(ra.DEPTH_EXCLUDE, int)
        self.assertIsInstance(ra.DEPTH_EMPTY, int)
        self.assertIsInstance(ra.DEPTH_FILES, int)
        self.assertIsInstance(ra.DEPTH_IMMEDIATES, int)
        self.assertIsInstance(ra.DEPTH_INFINITY, int)

    def test_dirent_constants(self):
        self.assertIsInstance(ra.DIRENT_KIND, int)
        self.assertIsInstance(ra.DIRENT_SIZE, int)
        self.assertIsInstance(ra.DIRENT_HAS_PROPS, int)
        self.assertIsInstance(ra.DIRENT_CREATED_REV, int)
        self.assertIsInstance(ra.DIRENT_TIME, int)
        self.assertIsInstance(ra.DIRENT_LAST_AUTHOR, int)
        self.assertIsInstance(ra.DIRENT_ALL, int)

    def test_mergeinfo_constants(self):
        self.assertIsInstance(ra.MERGEINFO_EXPLICIT, int)
        self.assertIsInstance(ra.MERGEINFO_INHERITED, int)
        self.assertIsInstance(ra.MERGEINFO_NEAREST_ANCESTOR, int)

    def test_svn_revision(self):
        self.assertIsInstance(ra.SVN_REVISION, int)
