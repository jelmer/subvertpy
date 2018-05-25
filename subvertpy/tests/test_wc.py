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

import hashlib
from io import BytesIO
import os

import subvertpy
from subvertpy import (
    NODE_DIR,
    NODE_FILE,
    wc,
    )
from subvertpy.tests import (
    SubversionTestCase,
    TestCase,
    )


class VersionTest(TestCase):

    def test_version_length(self):
        self.assertEqual(4, len(wc.version()))

    def test_api_version_length(self):
        self.assertEqual(4, len(wc.api_version()))

    def test_api_version_later_same(self):
        self.assertTrue(wc.api_version() <= wc.version())


class AdmTests(TestCase):

    def test_get_adm_dir(self):
        self.assertEqual(".svn", wc.get_adm_dir())

    def test_set_adm_dir(self):
        old_dir_name = wc.get_adm_dir()
        try:
            wc.set_adm_dir(b"_svn")
            self.assertEqual("_svn", wc.get_adm_dir())
        finally:
            wc.set_adm_dir(old_dir_name)

    def test_is_normal_prop(self):
        self.assertTrue(wc.is_normal_prop("svn:ignore"))

    def test_is_entry_prop(self):
        self.assertTrue(wc.is_entry_prop("svn:entry:foo"))

    def test_is_wc_prop(self):
        self.assertTrue(wc.is_wc_prop("svn:wc:foo"))

    def test_match_ignore_list(self):
        if wc.api_version() < (1, 5):
            self.assertRaises(
                NotImplementedError, wc.match_ignore_list, "foo", [])
            self.skipTest("match_ignore_list not supported with svn < 1.5")
        self.assertTrue(wc.match_ignore_list("foo", ["f*"]))
        self.assertTrue(wc.match_ignore_list("foo", ["foo"]))
        self.assertFalse(wc.match_ignore_list("foo", []))
        self.assertFalse(wc.match_ignore_list("foo", ["bar"]))


class WcTests(SubversionTestCase):

    def test_revision_status(self):
        self.make_client("repos", "checkout")
        ret = wc.revision_status("checkout")
        self.assertEqual((0, 0, 0, 0), ret)

    def test_revision_status_trailing(self):
        self.make_client("repos", "checkout")
        ret = wc.revision_status("checkout/")
        self.assertEqual((0, 0, 0, 0), ret)


class AdmObjTests(SubversionTestCase):

    def test_has_binary_prop(self):
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"\x00 \x01"})
        self.client_add('checkout/bar')
        self.client_set_prop('checkout/bar', 'svn:mime-type', 'text/bar')
        adm = wc.Adm(None, "checkout")
        self.assertFalse(adm.has_binary_prop("checkout/bar"))
        adm.close()

    def test_get_ancestry(self):
        repos_url = self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"\x00 \x01"})
        self.client_add('checkout/bar')
        adm = wc.Adm(None, "checkout")
        self.assertEqual(("%s/bar" % repos_url, 0),
                         adm.get_ancestry("checkout/bar"))
        adm.close()

    def test_maybe_set_repos_root(self):
        repos_url = self.make_client("repos", "checkout")
        adm = wc.Adm(None, "checkout")
        adm.maybe_set_repos_root(
            os.path.join(self.test_dir, "checkout"), repos_url)
        adm.close()

    def test_add_repos_file(self):
        if wc.api_version() >= (1, 7):
            self.skipTest("TODO: doesn't yet work with svn >= 1.7")
        if wc.api_version() < (1, 6):
            self.skipTest("doesn't work with svn < 1.6")
        self.make_client("repos", "checkout")
        adm = wc.Adm(None, "checkout", True)
        adm.add_repos_file("checkout/bar", BytesIO(b"basecontents"),
                           BytesIO(b"contents"), {}, {})
        self.assertEqual(b"basecontents",
                         wc.get_pristine_contents("checkout/bar").read())

    def test_mark_missing_deleted(self):
        if wc.api_version() >= (1, 7):
            self.skipTest("TODO: doesn't yet work with svn >= 1.7")
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"\x00 \x01"})
        self.client_add('checkout/bar')
        adm = wc.Adm(None, "checkout", True)
        os.remove("checkout/bar")
        adm.mark_missing_deleted("checkout/bar")
        self.assertFalse(os.path.exists("checkout/bar"))

    def test_remove_from_revision_control(self):
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"\x00 \x01"})
        self.client_add('checkout/bar')
        adm = wc.Adm(None, "checkout", True)
        adm.remove_from_revision_control("bar")
        self.assertTrue(os.path.exists("checkout/bar"))

    def test_relocate(self):
        self.make_client("repos", "checkout")
        adm = wc.Adm(None, "checkout", True)
        adm.relocate("checkout", "file://", "http://")

    def test_translated_stream(self):
        self.skipTest("TODO: doesn't yet work")
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"My id: $Id$"})
        self.client_add('checkout/bar')
        self.client_set_prop("checkout/bar", "svn:keywords", "Id\n")
        self.client_commit("checkout", "foo")
        adm = wc.Adm(None, "checkout", True)
        stream = adm.translated_stream(
                'checkout/bar', 'checkout/bar', wc.TRANSLATE_TO_NF)
        body = stream.read()
        self.assertTrue(body.startswith(b"My id: $Id: "), body)

    def test_text_modified(self):
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"My id: $Id$"})
        self.client_add('checkout/bar')
        self.client_set_prop("checkout/bar", "svn:keywords", "Id\n")
        self.client_commit("checkout", "foo")
        adm = wc.Adm(None, "checkout")
        self.assertFalse(adm.text_modified("checkout/bar"))
        self.build_tree({"checkout/bar": b"gambon"})
        self.assertTrue(adm.text_modified("checkout/bar", True))

    def test_props_modified(self):
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"My id: $Id$"})
        self.client_add('checkout/bar')
        self.client_set_prop("checkout/bar", "svn:keywords", "Id\n")
        self.client_commit("checkout", "foo")
        adm = wc.Adm(None, "checkout", True)
        self.assertFalse(adm.props_modified("checkout/bar"))
        adm.prop_set("aprop", "avalue", "checkout/bar")
        self.assertTrue(adm.props_modified("checkout/bar"))

    def test_prop_set(self):
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"file"})
        self.client_add('checkout/bar')
        adm = wc.Adm(None, "checkout", True)
        adm.prop_set("aprop", "avalue", "checkout/bar")
        self.assertEqual(adm.prop_get("aprop", "checkout/bar"), b"avalue")
        adm.prop_set("aprop", None, "checkout/bar")
        self.assertEqual(adm.prop_get("aprop", "checkout/bar"), None)

    def test_committed_queue(self):
        cq = wc.CommittedQueue()
        self.make_client("repos", "checkout")
        adm = wc.Adm(None, "checkout", True)
        adm.process_committed_queue(cq, 1, "2010-05-31T08:49:22.430000Z",
                                    "jelmer")

    def test_entry_not_found(self):
        self.make_client("repos", "checkout")
        adm = wc.Adm(None, "checkout")
        self.assertRaises(KeyError, adm.entry, "bar")

    def test_entry(self):
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"\x00 \x01"})
        self.client_add('checkout/bar')
        adm = wc.Adm(None, "checkout")
        entry = adm.entry("checkout/bar")
        self.assertEqual("bar", entry.name)
        self.assertEqual(NODE_FILE, entry.kind)
        self.assertEqual(0, entry.revision)
        self.client_commit("checkout", "msg")
        adm = wc.Adm(None, "checkout")
        entry = adm.entry("checkout/bar")
        self.assertEqual("bar", entry.name)
        self.assertEqual(NODE_FILE, entry.kind)
        self.assertEqual(1, entry.revision)

    def test_get_actual_target(self):
        self.make_client("repos", ".")
        self.assertEqual((self.test_dir, "bla"),
                         wc.get_actual_target("%s/bla" % self.test_dir))

    def test_is_wc_root(self):
        self.make_client("repos", ".")
        self.build_tree({"bar": None})
        self.client_add('bar')
        adm = wc.Adm(None, ".")
        self.assertTrue(adm.is_wc_root(self.test_dir))
        self.assertFalse(adm.is_wc_root(os.path.join(self.test_dir, "bar")))

    def test_status(self):
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"text"})
        self.client_add('checkout/bar')
        adm = wc.Adm(None, "checkout")
        self.assertEqual(
                wc.STATUS_ADDED,
                adm.status('checkout/bar').status)
        self.client_commit("checkout", "foo")
        adm = wc.Adm(None, "checkout")
        self.assertEqual(
                wc.STATUS_NORMAL,
                adm.status('checkout/bar').status)

    def test_transmit_text_deltas(self):
        if wc.api_version() >= (1, 7):
            self.skipTest("TODO: doesn't yet work with svn >= 1.7")
        self.make_client("repos", ".")
        self.build_tree({"bar": b"blala"})
        self.client_add('bar')
        adm = wc.Adm(None, ".", True)

        class Editor(object):
            """Editor"""

            def __init__(self):
                self._windows = []

            def apply_textdelta(self, checksum):
                def window_handler(window):
                    self._windows.append(window)
                return window_handler

            def close(self):
                pass
        editor = Editor()
        (tmpfile, digest) = adm.transmit_text_deltas("bar", True, editor)
        self.assertEqual(editor._windows,
                         [(0, 0, 5, 0, [(2, 0, 5)], b'blala'), None])
        self.assertIsInstance(tmpfile, str)
        self.assertEqual(16, len(digest))

        bar = adm.entry("bar")
        self.assertEqual(-1, bar.cmt_rev)
        self.assertEqual(0, bar.revision)

        cq = wc.CommittedQueue()
        cq.queue("bar", adm)
        adm.process_committed_queue(cq, 1, "2010-05-31T08:49:22.430000Z",
                                    "jelmer")
        bar = adm.entry("bar")
        self.assertEqual("bar", bar.name)
        self.assertEqual(NODE_FILE, bar.kind)
        self.assertEqual(wc.SCHEDULE_NORMAL, bar.schedule)
        self.assertIn(bar.checksum, (None, hashlib.md5(b'blala').hexdigest()))
        self.assertEqual(1, bar.cmt_rev)
        self.assertEqual(1, bar.revision)

    def test_process_committed_queue(self):
        if wc.api_version() >= (1, 7):
            self.skipTest("TODO: doesn't yet work with svn >= 1.7")
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"blala"})
        self.client_add('checkout/bar')
        adm = wc.Adm(None, "checkout", True)

        class Editor(object):
            """Editor"""

            def __init__(self):
                self._windows = []

            def apply_textdelta(self, checksum):
                def window_handler(window):
                    self._windows.append(window)
                return window_handler

            def close(self):
                pass

        editor = Editor()
        (tmpfile, digest) = adm.transmit_text_deltas(
                "checkout/bar", True, editor)
        self.assertEqual(editor._windows,
                         [(0, 0, 5, 0, [(2, 0, 5)], b'blala'), None])
        self.assertIsInstance(tmpfile, str)
        self.assertEqual(16, len(digest))

        cq = wc.CommittedQueue()
        cq.queue("checkout/bar", adm)
        adm.process_committed_queue(cq, 1, "2010-05-31T08:49:22.430000Z",
                                    "jelmer")
        bar = adm.entry("checkout/bar")
        self.assertEqual("bar", bar.name)
        self.assertEqual(NODE_FILE, bar.kind)
        self.assertEqual(wc.SCHEDULE_NORMAL, bar.schedule)

    def test_process_committed(self):
        if wc.api_version() >= (1, 7):
            self.skipTest("TODO: doesn't yet work with svn >= 1.7")
        self.make_client("repos", ".")
        self.build_tree({"bar": b"la"})
        self.client_add('bar')
        adm = wc.Adm(None, ".", True)

        class Editor(object):
            """Editor"""

            def __init__(self):
                self._windows = []

            def apply_textdelta(self, checksum):
                def window_handler(window):
                    self._windows.append(window)
                return window_handler

            def close(self):
                pass
        editor = Editor()
        (tmpfile, digest) = adm.transmit_text_deltas("bar", True, editor)
        self.assertEqual(editor._windows,
                         [(0, 0, 2, 0, [(2, 0, 2)], b'la'), None])
        self.assertIsInstance(tmpfile, str)
        self.assertEqual(16, len(digest))
        bar = adm.entry("bar")
        self.assertEqual(-1, bar.cmt_rev)
        self.assertEqual(0, bar.revision)

        adm.process_committed(
            "bar", False, 1, "2010-05-31T08:49:22.430000Z", "jelmer")
        bar = adm.entry("bar")
        self.assertEqual("bar", bar.name)
        self.assertEqual(NODE_FILE, bar.kind)
        self.assertEqual(wc.SCHEDULE_NORMAL, bar.schedule)

    def test_probe_try(self):
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"la"})
        self.client_add('checkout/bar')
        adm = wc.Adm(None, "checkout", True)
        try:
            self.assertIs(None, adm.probe_try(self.test_dir))
        except subvertpy.SubversionException as e:
            (msg, num) = e.args
            if num != subvertpy.ERR_WC_NOT_WORKING_COPY:
                raise
        self.assertEqual(
            os.path.abspath("checkout"),
            adm.probe_try(os.path.join("checkout", "bar")).access_path())


class ContextTests(SubversionTestCase):

    def setUp(self):
        super(ContextTests, self).setUp()
        if wc.api_version() < (1, 7):
            self.skipTest("context API not available on Subversion < 1.7")

    def test_create(self):
        context = wc.Context()
        self.assertIsInstance(context, wc.Context)

    def test_locked(self):
        context = wc.Context()
        self.make_client("repos", "checkout")
        self.assertEqual((False, False), context.locked("checkout"))

    def test_check_wc(self):
        context = wc.Context()
        self.make_client("repos", "checkout")
        self.assertIsInstance(context.check_wc("checkout"), int)

    def test_text_modified(self):
        context = wc.Context()
        self.make_client("repos", "checkout")
        with open('checkout/bla.txt', 'w') as f:
            f.write("modified")
        self.client_add("checkout/bla.txt")
        self.assertTrue(context.text_modified("checkout/bla.txt"))

    def test_props_modified(self):
        context = wc.Context()
        self.make_client("repos", "checkout")
        with open('checkout/bla.txt', 'w') as f:
            f.write("modified")
        self.client_add("checkout/bla.txt")
        self.assertFalse(context.props_modified("checkout/bla.txt"))

    def test_conflicted(self):
        context = wc.Context()
        self.make_client("repos", "checkout")
        with open('checkout/bla.txt', 'w') as f:
            f.write("modified")
        self.client_add("checkout/bla.txt")
        self.assertEqual(
            (False, False, False),
            context.conflicted("checkout/bla.txt"))

    def test_crawl_revisions(self):
        context = wc.Context()
        self.make_client("repos", "checkout")
        with open('checkout/bla.txt', 'w') as f:
            f.write("modified")
        self.client_add("checkout/bla.txt")
        ret = []

        class Reporter(object):
            def set_path(self, *args):
                ret.append(args)

            def finish(self):
                pass
        context.crawl_revisions("checkout", Reporter())

        self.assertEqual(ret, [('', 0, 0, None, 3)])

    def test_get_update_editor(self):
        self.make_client("repos", "checkout")
        context = wc.Context()
        editor = context.get_update_editor("checkout", "")
        editor.close()

    def test_status(self):
        self.make_client("repos", "checkout")
        context = wc.Context()
        status = context.status("checkout")
        self.assertEqual(NODE_DIR, status.kind)

    def test_walk_status(self):
        self.make_client("repos", "checkout")
        with open('checkout/bla.txt', 'w') as f:
            f.write("modified")
        self.client_add("checkout/bla.txt")
        context = wc.Context()
        result = {}
        context.walk_status("checkout", result.__setitem__)
        self.assertEqual(
                set(result.keys()),
                {os.path.abspath("checkout"),
                 os.path.abspath("checkout/bla.txt")})

    def test_locking(self):
        self.make_client("repos", "checkout")
        with open('checkout/bla.txt', 'w') as f:
            f.write("modified")
        self.client_add("checkout/bla.txt")
        context = wc.Context()
        lock = wc.Lock()
        self.assertEqual((False, False), context.locked("checkout"))
        context.add_lock("checkout/", lock)
        self.assertEqual((True, True), context.locked("checkout"))
        context.remove_lock("checkout/", lock)

    def test_add_from_disk(self):
        self.make_client("repos", "checkout")
        with open('checkout/bla.txt', 'w') as f:
            f.write("modified")
        context = wc.Context()
        lock = wc.Lock()
        context.add_lock("checkout/", lock)
        context.add_from_disk('checkout/bla.txt')
        context.remove_lock("checkout/", lock)

    def test_get_prop_diffs(self):
        self.make_client("repos", "checkout")
        context = wc.Context()
        (orig_props, propdelta) = context.get_prop_diffs("checkout")
        self.assertEqual({}, orig_props)
        self.assertEqual([], propdelta)
