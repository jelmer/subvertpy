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

"""Subversion client library tests."""

import os
import shutil
import tempfile
from datetime import datetime, timedelta
from io import BytesIO

from subvertpy import (
    SubversionException,
    client,
    ra,
)
from tests import (
    SubversionTestCase,
    TestCase,
)


class VersionTest(TestCase):

    def test_version_length(self):
        self.assertEqual(4, len(client.version()))

    def test_api_version_length(self):
        self.assertEqual(4, len(client.api_version()))

    def test_api_version_later_same(self):
        self.assertLessEqual(client.api_version(), client.version())


class TestClient(SubversionTestCase):

    def setUp(self):

        super().setUp()
        self.repos_url = self.make_client("d", "dc")
        self.client = client.Client(auth=ra.Auth([ra.get_username_provider()]))

    def tearDown(self):
        del self.client
        super().tearDown()

    def test_add(self):
        self.build_tree({"dc/foo": None})
        self.client.add("dc/foo")

    def test_commit(self):
        self.build_tree({"dc/foo": None})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: "Amessage"
        self.client.commit(["dc"])
        r = ra.RemoteAccess(self.repos_url)
        revprops = r.rev_proplist(1)
        self.assertEqual(b"Amessage", revprops["svn:log"])

    def test_commit_start(self):
        self.build_tree({"dc/foo": None})
        self.client = client.Client(
            auth=ra.Auth([ra.get_username_provider()]),
            log_msg_func=lambda c: "Bmessage")
        self.client.add("dc/foo")
        self.client.commit(["dc"])
        r = ra.RemoteAccess(self.repos_url)
        revprops = r.rev_proplist(1)
        self.assertEqual(b"Bmessage", revprops["svn:log"])

    def test_mkdir(self):
        self.client.mkdir(["dc/foo"])
        self.client.mkdir("dc/bar")
        self.client.mkdir("dc/bla", revprops={"svn:log": "foo"})

    def test_propset(self):
        self.client.mkdir(["dc/foo"])
        self.client.propset("someprop", "lala", "dc/foo")
        self.assertEqual(
            {os.path.abspath('dc/foo'): b'lala'},
            self.client.propget("someprop", "dc/foo"))

    def test_export(self):
        self.build_tree({"dc/foo": b"bla"})
        self.client.add("dc/foo")
        self.client.commit(["dc"])
        self.client.export(self.repos_url, "de")
        self.assertEqual(["foo"], os.listdir("de"))

    def test_export_new_option(self):
        self.build_tree({"dc/foo": b"bla"})
        self.client.add("dc/foo")
        self.client.commit(["dc"])
        self.client.export(self.repos_url, "de", ignore_externals=True,
                           ignore_keywords=True)
        self.assertEqual(["foo"], os.listdir("de"))

    def test_get_config(self):
        self.assertIsInstance(client.get_config(), client.Config)
        try:
            base_dir = tempfile.mkdtemp()
            base_dir_basename = os.path.basename(base_dir)
            svn_cfg_dir = os.path.join(base_dir, '.subversion')
            os.mkdir(svn_cfg_dir)
            with open(os.path.join(svn_cfg_dir, 'config'), 'w') as svn_cfg:
                svn_cfg.write('[miscellany]\n')
                svn_cfg.write(f'global-ignores = {base_dir_basename}')
            config = client.get_config(svn_cfg_dir)
            self.assertIsInstance(config, client.Config)
            ignores = config.get_default_ignores()
            self.assertIn(
                base_dir_basename.encode('utf-8'),
                ignores,
                f"no {base_dir_basename!r} in {ignores!r}"
            )
        finally:
            shutil.rmtree(base_dir)

    def test_diff(self):
        dc = self.get_commit_editor(self.repos_url)
        f = dc.add_file("foo")
        f.modify(b"foo1")
        dc.close()

        dc = self.get_commit_editor(self.repos_url)
        f = dc.open_file("foo")
        f.modify(b"foo2")
        dc.close()

        (outf, errf) = self.client.diff(1, 2, self.repos_url, self.repos_url)
        self.addCleanup(outf.close)
        self.addCleanup(errf.close)
        self.assertEqual(b"""Index: foo
===================================================================
--- foo\t(revision 1)
+++ foo\t(revision 2)
@@ -1 +1 @@
-foo1
\\ No newline at end of file
+foo2
\\ No newline at end of file
""".splitlines(), outf.read().splitlines())
        self.assertEqual(b"", errf.read())

    def assertCatEquals(self, value, revision=None):
        io = BytesIO()
        self.client.cat("dc/foo", io, revision)
        self.assertEqual(value, io.getvalue())

    def test_cat(self):
        self.build_tree({"dc/foo": b"bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.assertCatEquals(b"bla")
        self.build_tree({"dc/foo": b"blabla"})
        self.client.commit(["dc"])
        self.assertCatEquals(b"blabla")
        self.assertCatEquals(b"bla", revision=1)
        self.assertCatEquals(b"blabla", revision=2)

    def assertLogEntryChangedPathsEquals(self, expected, entry):
        changed_paths = entry["changed_paths"]
        self.assertIsInstance(changed_paths, dict)
        self.assertEqual(sorted(expected), sorted(changed_paths.keys()))

    def assertLogEntryMessageEquals(self, expected, entry):
        self.assertEqual(expected, entry["revprops"]["svn:log"])

    def assertLogEntryDateAlmostEquals(self, expected, entry, delta):
        actual = datetime.strptime(
            entry["revprops"]["svn:date"].decode('utf-8'),
            "%Y-%m-%dT%H:%M:%S.%fZ")
        self.assertLess(actual - expected, delta)

    def test_log(self):
        log_entries = []
        commit_msg_1 = b"Commit"
        commit_msg_2 = b"Commit 2"
        delta = timedelta(hours=1)

        def cb(changed_paths, revision, revprops, has_children=False):
            log_entries.append({
                'changed_paths': changed_paths,
                'revision': revision,
                'revprops': revprops,
                'has_children': has_children,
            })
        self.build_tree({"dc/foo": b"bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: commit_msg_1
        self.client.commit(["dc"])
        commit_1_dt = datetime.utcnow()
        self.client.log(cb, "dc/foo", start_rev="HEAD", end_rev=1)
        self.assertEqual(1, len(log_entries))
        self.assertEqual(None, log_entries[0]["changed_paths"])
        self.assertEqual(1, log_entries[0]["revision"])
        self.assertLogEntryMessageEquals(commit_msg_1, log_entries[0])
        self.assertLogEntryDateAlmostEquals(commit_1_dt, log_entries[0], delta)
        self.build_tree({
            "dc/foo": b"blabla",
            "dc/bar": b"blablabla",
        })
        self.client.add("dc/bar")
        self.client.log_msg_func = lambda c: commit_msg_2
        self.client.commit(["dc"])
        commit_2_dt = datetime.utcnow()
        log_entries = []
        self.client.log(
                cb, "dc/foo", start_rev="HEAD", end_rev=1,
                discover_changed_paths=True)
        self.assertEqual(2, len(log_entries))
        self.assertLogEntryChangedPathsEquals(["/foo", "/bar"], log_entries[0])
        self.assertEqual(2, log_entries[0]["revision"])
        self.assertLogEntryMessageEquals(commit_msg_2, log_entries[0])
        self.assertLogEntryDateAlmostEquals(commit_2_dt, log_entries[0], delta)
        self.assertLogEntryChangedPathsEquals(["/foo"], log_entries[1])
        self.assertEqual(1, log_entries[1]["revision"])
        self.assertLogEntryMessageEquals(commit_msg_1, log_entries[1])
        self.assertLogEntryDateAlmostEquals(commit_1_dt, log_entries[1], delta)
        log_entries = []
        self.client.log(cb, "dc/foo", start_rev=2, end_rev=2,
                        discover_changed_paths=True)
        self.assertEqual(1, len(log_entries))
        self.assertLogEntryChangedPathsEquals(["/foo", "/bar"], log_entries[0])
        self.assertEqual(2, log_entries[0]["revision"])
        self.assertLogEntryMessageEquals(commit_msg_2, log_entries[0])
        self.assertLogEntryDateAlmostEquals(commit_2_dt, log_entries[0], delta)

    def test_info(self):
        self.build_tree({"dc/foo": b"bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        info = self.client.info("dc/foo")
        self.assertEqual(["foo"], list(info.keys()))
        self.assertEqual(1, info["foo"].revision)
        self.assertEqual(3, info["foo"].size)
        self.build_tree({"dc/bar": b"blablabla"})
        self.client.add(os.path.abspath("dc/bar"))

    def test_info_nonexistant(self):
        self.build_tree({"dc/foo": b"bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.assertRaises(SubversionException, self.client.info, "dc/missing")
