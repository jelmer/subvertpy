# Copyright (C) 2006-2008 Jelmer Vernooij <jelmer@jelmer.uk>

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

"""Tests for subvertpy.ra_svn."""

from io import StringIO

from subvertpy.marshall import literal, marshall
from subvertpy.ra_svn import (
    CAPABILITIES,
    MAX_VERSION,
    MECHANISMS,
    MIN_VERSION,
    SVN_PORT,
    SVNConnection,
    SVNServer,
    Editor,
    DirectoryEditor,
    FileEditor,
    Reporter,
    SSHSubprocess,
    SSHVendor,
    mark_busy,
    unmarshall_dirent,
)
from tests import TestCase


class MarkBusyTests(TestCase):
    def test_sets_and_clears_busy(self):
        class Obj:
            busy = False

            @mark_busy
            def do_thing(self):
                return self.busy

        obj = Obj()
        self.assertFalse(obj.busy)
        result = obj.do_thing()
        self.assertTrue(result)  # was True during execution
        self.assertFalse(obj.busy)  # cleared after

    def test_clears_busy_on_exception(self):
        class Obj:
            busy = False

            @mark_busy
            def do_fail(self):
                raise ValueError("fail")

        obj = Obj()
        self.assertRaises(ValueError, obj.do_fail)
        self.assertFalse(obj.busy)

    def test_preserves_docstring(self):
        class Obj:
            @mark_busy
            def do_thing(self):
                """My docstring."""
                pass

        self.assertEqual("My docstring.", Obj.do_thing.__doc__)

    def test_preserves_name(self):
        class Obj:
            @mark_busy
            def do_thing(self):
                pass

        self.assertEqual("do_thing", Obj.do_thing.__name__)

    def test_returns_value(self):
        class Obj:
            busy = False

            @mark_busy
            def do_thing(self):
                return 42

        obj = Obj()
        self.assertEqual(42, obj.do_thing())


class UnmarshallDirentTests(TestCase):
    def test_basic(self):
        d = ["file.txt", "file", 1234, True, 5, [], []]
        result = unmarshall_dirent(d)
        self.assertEqual("file.txt", result["name"])
        self.assertEqual("file", result["kind"])
        self.assertEqual(1234, result["size"])
        self.assertTrue(result["has-props"])
        self.assertEqual(5, result["created-rev"])
        self.assertNotIn("created-date", result)
        self.assertNotIn("last-author", result)

    def test_with_date_and_author(self):
        d = ["dir", "dir", 0, False, 3, "2024-01-01T00:00:00.000000Z", "admin"]
        result = unmarshall_dirent(d)
        self.assertEqual("2024-01-01T00:00:00.000000Z", result["created-date"])
        self.assertEqual("admin", result["last-author"])

    def test_has_props_converted_to_bool(self):
        d = ["f", "file", 0, 0, 1, [], []]
        result = unmarshall_dirent(d)
        self.assertFalse(result["has-props"])

        d2 = ["f", "file", 0, 1, 1, [], []]
        result2 = unmarshall_dirent(d2)
        self.assertTrue(result2["has-props"])


class SVNConnectionTests(TestCase):
    def test_send_msg(self):
        sent = []

        def send_fn(data):
            sent.append(data)

        conn = SVNConnection(None, send_fn)
        conn.send_msg([1, 2, 3])
        self.assertEqual(1, len(sent))
        self.assertEqual(marshall([1, 2, 3]), sent[0])

    def test_send_success(self):
        sent = []

        def send_fn(data):
            sent.append(data)

        conn = SVNConnection(None, send_fn)
        conn.send_success(1, 2)
        self.assertEqual(1, len(sent))
        expected = marshall([literal("success"), [1, 2]])
        self.assertEqual(expected, sent[0])

    def test_send_success_no_args(self):
        sent = []

        def send_fn(data):
            sent.append(data)

        conn = SVNConnection(None, send_fn)
        conn.send_success()
        expected = marshall([literal("success"), []])
        self.assertEqual(expected, sent[0])

    def test_inbuffer_initialized(self):
        conn = SVNConnection(None, None)
        self.assertEqual("", conn.inbuffer)


class EditorTests(TestCase):
    def setUp(self):
        super(EditorTests, self).setUp()
        self.sent = []

        class MockConn:
            _open_ids = []

            def send_msg(_, data):
                self.sent.append(data)

        self.conn = MockConn()

    def test_set_target_revision(self):
        editor = Editor(self.conn)
        editor.set_target_revision(5)
        self.assertEqual(1, len(self.sent))
        self.assertEqual(literal("target-rev"), self.sent[0][0])
        self.assertEqual([5], self.sent[0][1])

    def test_close(self):
        editor = Editor(self.conn)
        editor.close()
        self.assertEqual(literal("close-edit"), self.sent[0][0])

    def test_abort(self):
        editor = Editor(self.conn)
        editor.abort()
        self.assertEqual(literal("abort-edit"), self.sent[0][0])

    def test_open_root_returns_directory_editor(self):
        editor = Editor(self.conn)
        de = editor.open_root()
        self.assertIsInstance(de, DirectoryEditor)

    def test_open_root_no_base_revision(self):
        editor = Editor(self.conn)
        editor.open_root()
        # baserev should be empty list when no base_revision
        self.assertEqual(literal("open-root"), self.sent[0][0])
        self.assertEqual([], self.sent[0][1][0])

    def test_open_root_with_base_revision(self):
        editor = Editor(self.conn)
        editor.open_root(base_revision=5)
        self.assertEqual(literal("open-root"), self.sent[0][0])
        self.assertEqual([5], self.sent[0][1][0])


class DirectoryEditorTests(TestCase):
    def setUp(self):
        super(DirectoryEditorTests, self).setUp()
        self.sent = []

        class MockConn:
            _open_ids = []

            def send_msg(_, data):
                self.sent.append(data)

        self.conn = MockConn()
        self.dir_id = "test-id"
        self.conn._open_ids.append(self.dir_id)
        self.de = DirectoryEditor(self.conn, self.dir_id)

    def test_change_prop(self):
        self.de.change_prop("svn:log", "value")
        self.assertEqual(literal("change-dir-prop"), self.sent[0][0])
        self.assertEqual([self.dir_id, "svn:log", ["value"]], self.sent[0][1])

    def test_change_prop_none_value(self):
        self.de.change_prop("svn:log", None)
        self.assertEqual([self.dir_id, "svn:log", []], self.sent[0][1])

    def test_add_file_returns_file_editor(self):
        fe = self.de.add_file("test.txt")
        self.assertIsInstance(fe, FileEditor)
        self.assertEqual(literal("add-file"), self.sent[0][0])

    def test_add_file_with_copyfrom(self):
        self.de.add_file("test.txt", copyfrom_path="/trunk/old.txt", copyfrom_rev=3)
        args = self.sent[0][1]
        self.assertEqual("test.txt", args[0])
        self.assertEqual(["/trunk/old.txt", 3], args[3])

    def test_add_file_no_copyfrom(self):
        self.de.add_file("test.txt")
        args = self.sent[0][1]
        self.assertEqual([], args[3])  # empty copyfrom_data

    def test_add_directory_returns_directory_editor(self):
        de2 = self.de.add_directory("subdir")
        self.assertIsInstance(de2, DirectoryEditor)
        self.assertEqual(literal("add-dir"), self.sent[0][0])

    def test_add_directory_with_copyfrom(self):
        self.de.add_directory("subdir", copyfrom_path="/trunk/old", copyfrom_rev=2)
        args = self.sent[0][1]
        self.assertEqual("subdir", args[0])
        self.assertEqual(["/trunk/old", 2], args[3])

    def test_add_directory_no_copyfrom(self):
        self.de.add_directory("subdir")
        args = self.sent[0][1]
        self.assertEqual([], args[3])

    def test_open_file(self):
        fe = self.de.open_file("file.txt", 3)
        self.assertIsInstance(fe, FileEditor)
        self.assertEqual(literal("open-file"), self.sent[0][0])
        args = self.sent[0][1]
        self.assertEqual("file.txt", args[0])
        self.assertEqual(3, args[3])

    def test_open_directory(self):
        de2 = self.de.open_directory("subdir", 2)
        self.assertIsInstance(de2, DirectoryEditor)
        self.assertEqual(literal("open-dir"), self.sent[0][0])
        args = self.sent[0][1]
        self.assertEqual("subdir", args[0])
        self.assertEqual(2, args[3])

    def test_delete_entry(self):
        self.de.delete_entry("file.txt", 3)
        self.assertEqual(literal("delete-entry"), self.sent[0][0])

    def test_close(self):
        # DirectoryEditor.__init__ appends the id to _open_ids,
        # and close() pops the last one
        initial_count = self.conn._open_ids.count(self.dir_id)
        self.de.close()
        self.assertEqual(literal("close-dir"), self.sent[0][0])
        self.assertEqual(initial_count - 1, self.conn._open_ids.count(self.dir_id))


class FileEditorTests(TestCase):
    def setUp(self):
        super(FileEditorTests, self).setUp()
        self.sent = []

        class MockConn:
            _open_ids = []

            def send_msg(_, data):
                self.sent.append(data)

        self.conn = MockConn()
        self.file_id = "file-id"
        self.conn._open_ids.append(self.file_id)
        self.fe = FileEditor(self.conn, self.file_id)

    def test_change_prop(self):
        self.fe.change_prop("svn:mime-type", "text/plain")
        self.assertEqual(literal("change-file-prop"), self.sent[0][0])
        self.assertEqual(
            [self.file_id, "svn:mime-type", ["text/plain"]], self.sent[0][1]
        )

    def test_change_prop_none(self):
        self.fe.change_prop("svn:mime-type", None)
        self.assertEqual([self.file_id, "svn:mime-type", []], self.sent[0][1])

    def test_close_no_checksum(self):
        self.fe.close()
        self.assertEqual(literal("close-file"), self.sent[0][0])
        self.assertEqual([self.file_id, []], self.sent[0][1])

    def test_close_with_checksum(self):
        self.fe.close(checksum="abc123")
        self.assertEqual([self.file_id, ["abc123"]], self.sent[0][1])

    def test_apply_textdelta(self):
        handler = self.fe.apply_textdelta()
        self.assertTrue(callable(handler))
        # Should have sent apply-textdelta and the SVN header chunk
        self.assertEqual(literal("apply-textdelta"), self.sent[0][0])
        self.assertEqual(literal("textdelta-chunk"), self.sent[1][0])

    def test_apply_textdelta_with_checksum(self):
        self.fe.apply_textdelta(base_checksum="md5sum")
        self.assertEqual([self.file_id, ["md5sum"]], self.sent[0][1])

    def test_apply_textdelta_handler_sends_chunks(self):
        handler = self.fe.apply_textdelta()
        self.sent.clear()
        # Send a delta window (None signals end)
        handler(None)
        self.assertEqual(literal("textdelta-end"), self.sent[0][0])

    def test_apply_textdelta_handler_sends_window(self):
        from subvertpy.delta import TXDELTA_NEW

        handler = self.fe.apply_textdelta()
        self.sent.clear()
        window = (0, 0, 3, 1, [(TXDELTA_NEW, 0, 3)], b"foo")
        handler(window)
        self.assertEqual(literal("textdelta-chunk"), self.sent[0][0])
        # The second element should be the file_id and packed window data
        self.assertEqual(self.file_id, self.sent[0][1][0])


class SSHSubprocessTests(TestCase):
    def test_get_filelike_channels(self):
        class FakeProc:
            stdout = "fake_stdout"
            stdin = "fake_stdin"

        proc = FakeProc()
        ssh = SSHSubprocess(proc)
        stdout, stdin = ssh.get_filelike_channels()
        self.assertEqual("fake_stdout", stdout)
        self.assertEqual("fake_stdin", stdin)


class SSHVendorTests(TestCase):
    def test_is_instantiable(self):
        vendor = SSHVendor()
        self.assertTrue(hasattr(vendor, "connect_ssh"))


class ReporterTests(TestCase):
    def setUp(self):
        super(ReporterTests, self).setUp()
        self.sent = []

        class MockConn:
            busy = True

            def send_msg(_, data):
                self.sent.append(data)

        self.conn = MockConn()

    def test_set_path_basic(self):
        reporter = Reporter(self.conn, None)
        reporter.set_path("path", 5)
        self.assertEqual(literal("set-path"), self.sent[0][0])
        args = self.sent[0][1]
        self.assertEqual("path", args[0])
        self.assertEqual(5, args[1])
        self.assertFalse(args[2])  # start_empty default
        self.assertEqual([], args[3])  # no lock_token

    def test_set_path_start_empty(self):
        reporter = Reporter(self.conn, None)
        reporter.set_path("path", 5, start_empty=True)
        args = self.sent[0][1]
        self.assertTrue(args[2])

    def test_set_path_with_lock_token(self):
        reporter = Reporter(self.conn, None)
        reporter.set_path("path", 5, lock_token="token123")
        args = self.sent[0][1]
        self.assertEqual(["token123"], args[3])

    def test_set_path_with_depth(self):
        reporter = Reporter(self.conn, None)
        reporter.set_path("path", 5, depth="infinity")
        args = self.sent[0][1]
        self.assertEqual("infinity", args[4])

    def test_delete_path(self):
        reporter = Reporter(self.conn, None)
        reporter.delete_path("deleted/path")
        self.assertEqual(literal("delete-path"), self.sent[0][0])
        self.assertEqual(["deleted/path"], self.sent[0][1])

    def test_link_path_basic(self):
        reporter = Reporter(self.conn, None)
        reporter.link_path("path", "svn://example.com/repo", 3)
        self.assertEqual(literal("link-path"), self.sent[0][0])
        args = self.sent[0][1]
        self.assertEqual("path", args[0])
        self.assertEqual("svn://example.com/repo", args[1])
        self.assertEqual(3, args[2])
        self.assertFalse(args[3])  # start_empty default
        self.assertEqual([], args[4])  # no lock_token

    def test_link_path_with_lock_token(self):
        reporter = Reporter(self.conn, None)
        reporter.link_path("path", "svn://example.com", 3, lock_token="tok")
        args = self.sent[0][1]
        self.assertEqual(["tok"], args[4])

    def test_link_path_with_depth(self):
        reporter = Reporter(self.conn, None)
        reporter.link_path("path", "svn://example.com", 3, depth="files")
        args = self.sent[0][1]
        self.assertEqual("files", args[5])

    def test_abort(self):
        reporter = Reporter(self.conn, None)
        reporter.abort()
        self.assertEqual(literal("abort-report"), self.sent[0][0])
        self.assertFalse(self.conn.busy)


class SVNServerMutterTests(TestCase):
    def test_mutter_with_logf(self):
        logf = StringIO()
        sent = []

        def send_fn(data):
            sent.append(data)

        # Create SVNServer without full init (which sends greeting)
        server = SVNServer.__new__(SVNServer)
        server._logf = logf
        server._stop = False
        server.mutter("hello world")
        self.assertEqual("hello world\n", logf.getvalue())

    def test_mutter_without_logf(self):
        server = SVNServer.__new__(SVNServer)
        server._logf = None
        server._stop = False
        # Should not raise
        server.mutter("hello world")

    def test_close_sets_stop(self):
        server = SVNServer.__new__(SVNServer)
        server._stop = False
        server.close()
        self.assertTrue(server._stop)

    def test_send_failure(self):
        sent = []

        def send_fn(data):
            sent.append(data)

        server = SVNServer.__new__(SVNServer)
        server.send_fn = send_fn
        server.inbuffer = ""
        server.recv_fn = None
        server.send_failure([210001, "Unknown command", "file.py", 1])
        self.assertEqual(1, len(sent))

    def test_send_ack(self):
        sent = []

        def send_fn(data):
            sent.append(data)

        server = SVNServer.__new__(SVNServer)
        server.send_fn = send_fn
        server.inbuffer = ""
        server.recv_fn = None
        server.send_ack()
        self.assertEqual(1, len(sent))

    def test_send_unknown(self):
        sent = []

        def send_fn(data):
            sent.append(data)

        server = SVNServer.__new__(SVNServer)
        server.send_fn = send_fn
        server.inbuffer = ""
        server.recv_fn = None
        server.send_unknown("bogus-cmd")
        self.assertEqual(1, len(sent))


class ConstantsTests(TestCase):
    def test_svn_port(self):
        self.assertEqual(3690, SVN_PORT)

    def test_min_version(self):
        self.assertEqual(2, MIN_VERSION)

    def test_max_version(self):
        self.assertEqual(2, MAX_VERSION)

    def test_capabilities(self):
        self.assertIsInstance(CAPABILITIES, list)
        self.assertIn("edit-pipeline", CAPABILITIES)

    def test_mechanisms(self):
        self.assertIsInstance(MECHANISMS, list)
        self.assertIn("ANONYMOUS", MECHANISMS)
