# Copyright (C) 2005-2007 Jelmer Vernooij <jelmer@samba.org>
 
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

from datetime import datetime, timedelta
import os
import shutil
import tempfile

from subvertpy.six import iterkeys,itervalues,iteritems
from subvertpy.six import BytesIO,b
from subvertpy import (
    SubversionException,
    NODE_DIR, NODE_FILE,
    client,
    ra,
    wc,
    )
from subvertpy.tests import (
    SubversionTestCase,
    TestCase,
    )


class VersionTest(TestCase):

    def test_version_length(self):
        self.assertEqual(4, len(client.version()))

    def test_api_version_length(self):
        self.assertEqual(4, len(client.api_version()))

    def test_api_version_later_same(self):
        self.assertTrue(client.api_version() <= client.version())


class TestClient(SubversionTestCase):

    def setUp(self):

        super(TestClient, self).setUp()
        self.repos_url = self.make_client("d", "dc")
        self.client = client.Client(auth=ra.Auth([ra.get_username_provider()]))

    def tearDown(self):
        del self.client
        super(TestClient, self).tearDown()

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
        self.assertEqual("Amessage", revprops["svn:log"])

    def test_commit_start(self):
        self.build_tree({"dc/foo": None})
        self.client = client.Client(auth=ra.Auth([ra.get_username_provider()]),
                log_msg_func=lambda c: "Bmessage")
        self.client.add("dc/foo")
        self.client.commit(["dc"])
        r = ra.RemoteAccess(self.repos_url)
        revprops = r.rev_proplist(1)
        self.assertEqual("Bmessage", revprops["svn:log"])

    def test_mkdir(self):
        self.client.mkdir(["dc/foo"])
        self.client.mkdir("dc/bar")
        self.client.mkdir("dc/bla", revprops={"svn:log": "foo"})

    def test_export(self):
        self.build_tree({"dc/foo": "bla"})
        self.client.add("dc/foo")
        self.client.commit(["dc"])
        self.client.export(self.repos_url, "de")
        self.assertEqual(["foo"], os.listdir("de"))

    def test_add_recursive(self):
        self.build_tree({"dc/trunk/foo": 'bla', "dc/trunk": None})
        self.client.add("dc/trunk")
        adm = wc.WorkingCopy(None, os.path.join(os.getcwd(), "dc"))
        e = adm.entry(os.path.join(os.getcwd(), "dc", "trunk"))
        self.assertEqual(e.kind, NODE_DIR)
        adm2 = wc.WorkingCopy(None, os.path.join(os.getcwd(), "dc", "trunk"))
        e = adm2.entry(os.path.join(os.getcwd(), "dc", "trunk", "foo"))
        self.assertEqual(e.kind, NODE_FILE)
        self.assertEqual(e.revision, 0)

    def test_get_config(self):
        self.assertIsInstance(client.get_config(), client.Config)
        try:
            base_dir = tempfile.mkdtemp()
            base_dir_basename = os.path.basename(base_dir)
            svn_cfg_dir = os.path.join(base_dir, '.subversion')
            os.mkdir(svn_cfg_dir)
            svn_cfg = open(os.path.join(svn_cfg_dir, 'config'), 'w')
            try:
                svn_cfg.write('[miscellany]\n')
                svn_cfg.write('global-ignores = %s' % base_dir_basename)
            finally:
                svn_cfg.close()
            config = client.get_config(svn_cfg_dir)
            self.assertIsInstance(config, client.Config)
            ignores = config.get_default_ignores()
            self.assertTrue(base_dir_basename in ignores)
        finally:
            shutil.rmtree(base_dir)

    def test_diff(self):
        r = ra.RemoteAccess(self.repos_url,
                auth=ra.Auth([ra.get_username_provider()]))
        dc = self.get_commit_editor(self.repos_url) 
        f = dc.add_file("foo")
        f.modify("foo1")
        dc.close()

        dc = self.get_commit_editor(self.repos_url) 
        f = dc.open_file("foo")
        f.modify("foo2")
        dc.close()

        if client.api_version() < (1, 5):
            self.assertRaises(NotImplementedError, self.client.diff, 1, 2,
                self.repos_url, self.repos_url)
            return # Skip test

        (outf, errf) = self.client.diff(1, 2, self.repos_url, self.repos_url)
        self.addCleanup(outf.close)
        self.addCleanup(errf.close)
        self.assertEqual(b("""Index: foo
===================================================================
--- foo\t(revision 1)
+++ foo\t(revision 2)
@@ -1 +1 @@
-foo1
\\ No newline at end of file
+foo2
\\ No newline at end of file
""").splitlines(), outf.read().splitlines())
        self.assertEqual(b(""), errf.read())

    def assertCatEquals(self, value, revision=None):
        io = BytesIO()
        self.client.cat("dc/foo", io, revision)
        self.assertEqual(b(value), io.getvalue())

    def test_cat(self):
        self.build_tree({"dc/foo": "bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.assertCatEquals("bla")
        self.build_tree({"dc/foo": "blabla"})
        self.client.commit(["dc"])
        self.assertCatEquals("blabla")
        self.assertCatEquals("bla", revision=1)
        self.assertCatEquals("blabla", revision=2)

    def assertLogEntryChangedPathsEquals(self, expected, entry):
        changed_paths = entry["changed_paths"]
        self.assertIsInstance(changed_paths, dict)
        self.assertEqual(sorted(expected), sorted(list(iterkeys(changed_paths))))

    def assertLogEntryMessageEquals(self, expected, entry):
        self.assertEqual(expected, entry["revprops"]["svn:log"])

    def assertLogEntryDateAlmostEquals(self, expected, entry, delta):
        actual = datetime.strptime(entry["revprops"]["svn:date"], "%Y-%m-%dT%H:%M:%S.%fZ")
        self.assertTrue((actual - expected) < delta)

    def test_log(self):
        log_entries = []
        commit_msg_1 = "Commit"
        commit_msg_2 = "Commit 2"
        delta = timedelta(hours=1)
        def cb(changed_paths, revision, revprops, has_children=False):
            log_entries.append({
                'changed_paths': changed_paths,
                'revision': revision,
                'revprops': revprops,
                'has_children': has_children,
            })
        self.build_tree({"dc/foo": "bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: commit_msg_1
        self.client.commit(["dc"])
        commit_1_dt = datetime.utcnow()
        self.client.log(cb, "dc/foo")
        self.assertEqual(1, len(log_entries))
        self.assertEqual(None, log_entries[0]["changed_paths"])
        self.assertEqual(1, log_entries[0]["revision"])
        self.assertLogEntryMessageEquals(commit_msg_1, log_entries[0])
        self.assertLogEntryDateAlmostEquals(commit_1_dt, log_entries[0], delta)
        self.build_tree({
            "dc/foo": "blabla",
            "dc/bar": "blablabla",
        })
        self.client.add("dc/bar")
        self.client.log_msg_func = lambda c: commit_msg_2
        self.client.commit(["dc"])
        commit_2_dt = datetime.utcnow()
        log_entries = []
        self.client.log(cb, "dc/foo", discover_changed_paths=True)
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
        self.client.log(cb, "dc/foo", start_rev=2, end_rev=2, discover_changed_paths=True)
        self.assertEqual(1, len(log_entries))
        self.assertLogEntryChangedPathsEquals(["/foo", "/bar"], log_entries[0])
        self.assertEqual(2, log_entries[0]["revision"])
        self.assertLogEntryMessageEquals(commit_msg_2, log_entries[0])
        self.assertLogEntryDateAlmostEquals(commit_2_dt, log_entries[0], delta)

    def test_info(self):
        self.build_tree({"dc/foo": "bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        info = self.client.info("dc/foo")
        self.assertEqual(["foo"], list(iterkeys(info)))
        self.assertEqual(1, info["foo"].revision)
        self.assertEqual(3L, info["foo"].size)
        self.assertEqual(wc.SCHEDULE_NORMAL, info["foo"].wc_info.schedule)
        self.build_tree({"dc/bar": "blablabla"})
        self.client.add(os.path.abspath("dc/bar"))

    def test_info_nonexistant(self):
        self.build_tree({"dc/foo": "bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.assertRaises(SubversionException, self.client.info, "dc/missing")
