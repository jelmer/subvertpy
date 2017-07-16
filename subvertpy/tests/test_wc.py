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
import os
from unittest import SkipTest

import subvertpy
from subvertpy import (
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


class WorkingCopyTests(TestCase):

    def test_get_adm_dir(self):
        self.assertEqual(b".svn", wc.get_adm_dir())

    def test_set_adm_dir(self):
        old_dir_name = wc.get_adm_dir()
        try:
            wc.set_adm_dir(b"_svn")
            self.assertEqual(b"_svn", wc.get_adm_dir())
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
            return  # Skip test
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


class AdmTests(SubversionTestCase):

    def setUp(self):
        super(AdmTests, self).setUp()
        if getattr(wc, "WorkingCopy", None) is None:
            raise SkipTest(
                "Subversion 1.7 API for WorkingCopy not yet supported")

    def test_has_binary_prop(self):
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"\x00 \x01"})
        self.client_add('checkout/bar')
        adm = wc.WorkingCopy(None, "checkout")
        path = os.path.join(self.test_dir, "checkout/bar")
        self.assertFalse(adm.has_binary_prop(path))
        adm.close()

    def test_get_ancestry(self):
        repos_url = self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"\x00 \x01"})
        self.client_add('checkout/bar')
        adm = wc.WorkingCopy(None, "checkout")
        self.assertEqual(("%s/bar" % repos_url, 0),
                         adm.get_ancestry("checkout/bar"))
        adm.close()

    def test_maybe_set_repos_root(self):
        repos_url = self.make_client("repos", "checkout")
        adm = wc.WorkingCopy(None, "checkout")
        adm.maybe_set_repos_root(
            os.path.join(self.test_dir, "checkout"), repos_url)
        adm.close()

    def test_add_repos_file(self):
        self.make_client("repos", "checkout")
        adm = wc.WorkingCopy(None, "checkout", True)
        adm.add_repos_file("checkout/bar", BytesIO(b"basecontents"),
                           BytesIO(b"contents"), {}, {})
        self.assertEqual(b"basecontents",
                         wc.get_pristine_contents("checkout/bar").read())

    def test_mark_missing_deleted(self):
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"\x00 \x01"})
        self.client_add('checkout/bar')
        adm = wc.WorkingCopy(None, "checkout", True)
        os.remove("checkout/bar")
        adm.mark_missing_deleted("checkout/bar")
        self.assertFalse(os.path.exists("checkout/bar"))

    def test_remove_from_revision_control(self):
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"\x00 \x01"})
        self.client_add('checkout/bar')
        adm = wc.WorkingCopy(None, "checkout", True)
        adm.remove_from_revision_control("bar")
        self.assertTrue(os.path.exists("checkout/bar"))

    def test_relocate(self):
        self.make_client("repos", "checkout")
        adm = wc.WorkingCopy(None, "checkout", True)
        adm.relocate("checkout", "file://", "http://")

    def test_translated_stream(self):
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"My id: $Id$"})
        self.client_add('checkout/bar')
        self.client_set_prop("checkout/bar", "svn:keywords", "Id\n")
        self.client_commit("checkout", "foo")
        adm = wc.WorkingCopy(None, "checkout", True)
        path = os.path.join(self.test_dir, "checkout/bar")
        stream = adm.translated_stream(path, path, wc.TRANSLATE_TO_NF)
        self.assertTrue(stream.read().startswith(b"My id: $Id: "))

    def test_text_modified(self):
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"My id: $Id$"})
        self.client_add('checkout/bar')
        self.client_set_prop("checkout/bar", "svn:keywords", "Id\n")
        self.client_commit("checkout", "foo")
        adm = wc.WorkingCopy(None, "checkout")
        self.assertFalse(adm.text_modified("checkout/bar"))
        self.build_tree({"checkout/bar": b"gambon"})
        self.assertTrue(adm.text_modified("checkout/bar", True))

    def test_props_modified(self):
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"My id: $Id$"})
        self.client_add('checkout/bar')
        self.client_set_prop("checkout/bar", "svn:keywords", "Id\n")
        self.client_commit("checkout", "foo")
        adm = wc.WorkingCopy(None, "checkout", True)
        self.assertFalse(adm.props_modified("checkout/bar"))
        adm.prop_set("aprop", "avalue", "checkout/bar")
        self.assertTrue(adm.props_modified("checkout/bar"))

    def test_prop_set(self):
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"file"})
        self.client_add('checkout/bar')
        adm = wc.WorkingCopy(None, "checkout", True)
        adm.prop_set("aprop", "avalue", "checkout/bar")
        self.assertEqual(adm.prop_get("aprop", "checkout/bar"), "avalue")
        adm.prop_set("aprop", None, "checkout/bar")
        self.assertEqual(adm.prop_get("aprop", "checkout/bar"), None)

    def test_committed_queue(self):
        if getattr(wc, "CommittedQueue", None) is None:
            raise SkipTest("CommittedQueue not available")
        cq = wc.CommittedQueue()
        self.make_client("repos", "checkout")
        adm = wc.WorkingCopy(None, "checkout", True)
        adm.process_committed_queue(cq, 1, "2010-05-31T08:49:22.430000Z",
                                    "jelmer")

    def test_entry_not_found(self):
        self.make_client("repos", "checkout")
        adm = wc.WorkingCopy(None, "checkout")
        self.assertRaises(KeyError, adm.entry, "bar")

    def test_entry(self):
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"\x00 \x01"})
        self.client_add('checkout/bar')
        adm = wc.WorkingCopy(None, "checkout")
        entry = adm.entry("checkout/bar")
        self.assertEqual("bar", entry.name)
        self.assertEqual(NODE_FILE, entry.kind)
        self.assertEqual(0, entry.revision)
        self.client_commit("checkout", "msg")
        adm = wc.WorkingCopy(None, "checkout")
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
        adm = wc.WorkingCopy(None, ".")
        self.assertTrue(adm.is_wc_root(self.test_dir))
        self.assertFalse(adm.is_wc_root(os.path.join(self.test_dir, "bar")))

    def test_status(self):
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"text"})
        self.client_add('checkout/bar')
        adm = wc.WorkingCopy(None, "checkout")
        self.assertEqual(wc.STATUS_ADDED, adm.status('bar').status)
        self.client_commit("checkout", "foo")
        adm = wc.WorkingCopy(None, "checkout")
        self.assertEqual(wc.STATUS_NORMAL, adm.status('bar').status)

    def test_transmit_text_deltas(self):
        self.make_client("repos", ".")
        self.build_tree({"bar": b"blala"})
        self.client_add('bar')
        adm = wc.WorkingCopy(None, ".", True)

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
        self.assertIs(None, bar.checksum)
        self.assertEqual(1, bar.cmt_rev)
        self.assertEqual(1, bar.revision)

    def test_process_committed_queue(self):
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"la"})
        self.client_add('checkout/bar')
        adm = wc.WorkingCopy(None, "checkout", True)
        cq = wc.CommittedQueue()
        cq.queue(os.path.join(self.test_dir, "checkout/bar"), adm)
        adm.process_committed_queue(cq, 1, "2010-05-31T08:49:22.430000Z",
                                    "jelmer")
        bar = adm.entry("checkout/bar")
        self.assertEqual("bar", bar.name)
        self.assertEqual(NODE_FILE, bar.kind)
        self.assertEqual(wc.SCHEDULE_ADD, bar.schedule)

    def test_probe_try(self):
        self.make_client("repos", "checkout")
        self.build_tree({"checkout/bar": b"la"})
        self.client_add('checkout/bar')
        adm = wc.WorkingCopy(None, "checkout", True)
        try:
            self.assertIs(None, adm.probe_try(self.test_dir))
        except subvertpy.SubversionException as e:
            (msg, num) = e.args
            if num != subvertpy.ERR_WC_NOT_WORKING_COPY:
                raise
        self.assertEqual(
            "checkout",
            adm.probe_try(os.path.join("checkout", "bar")).access_path())
