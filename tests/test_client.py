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
        self.assertTrue(client.api_version() <= client.version())


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
            log_msg_func=lambda c: "Bmessage",
        )
        self.client.add("dc/foo")
        self.client.commit(["dc"])
        r = ra.RemoteAccess(self.repos_url)
        revprops = r.rev_proplist(1)
        self.assertEqual(b"Bmessage", revprops["svn:log"])

    def test_mkdir(self):
        self.client.mkdir(["dc/foo"])
        self.client.mkdir("dc/bar")
        self.client.mkdir("dc/bla", revprops={"svn:log": "foo"})

    def test_export(self):
        self.build_tree({"dc/foo": b"bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.client.export(self.repos_url, "de")
        self.assertEqual(["foo"], os.listdir("de"))

    def test_export_new_option(self):
        self.build_tree({"dc/foo": b"bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.client.export(
            self.repos_url, "de", ignore_externals=True, ignore_keywords=True
        )
        self.assertEqual(["foo"], os.listdir("de"))

    def test_set_config(self):
        config = client.get_config()
        self.client.config = config

    def test_set_config_none(self):
        self.client.config = None

    def test_get_config(self):
        self.assertIsInstance(client.get_config(), client.Config)
        try:
            base_dir = tempfile.mkdtemp()
            base_dir_basename = os.path.basename(base_dir)
            svn_cfg_dir = os.path.join(base_dir, ".subversion")
            os.mkdir(svn_cfg_dir)
            with open(os.path.join(svn_cfg_dir, "config"), "w") as svn_cfg:
                svn_cfg.write("[miscellany]\n")
                svn_cfg.write(f"global-ignores = {base_dir_basename}")
            config = client.get_config(svn_cfg_dir)
            self.assertIsInstance(config, client.Config)
            ignores = config.get_default_ignores()
            self.assertTrue(
                base_dir_basename.encode("utf-8") in ignores,
                f"no {base_dir_basename!r} in {ignores!r}",
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
        self.assertEqual(
            b"""Index: foo
===================================================================
--- foo\t(revision 1)
+++ foo\t(revision 2)
@@ -1 +1 @@
-foo1
\\ No newline at end of file
+foo2
\\ No newline at end of file
""".splitlines(),
            outf.read().splitlines(),
        )
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
            entry["revprops"]["svn:date"].decode("utf-8"), "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        self.assertTrue((actual - expected) < delta)

    def test_log(self):
        log_entries = []
        commit_msg_1 = b"Commit"
        commit_msg_2 = b"Commit 2"
        delta = timedelta(hours=1)

        def cb(changed_paths, revision, revprops, has_children=False):
            log_entries.append(
                {
                    "changed_paths": changed_paths,
                    "revision": revision,
                    "revprops": revprops,
                    "has_children": has_children,
                }
            )

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
        self.build_tree(
            {
                "dc/foo": b"blabla",
                "dc/bar": b"blablabla",
            }
        )
        self.client.add("dc/bar")
        self.client.log_msg_func = lambda c: commit_msg_2
        self.client.commit(["dc"])
        commit_2_dt = datetime.utcnow()
        log_entries = []
        self.client.log(
            cb, "dc/foo", start_rev="HEAD", end_rev=1, discover_changed_paths=True
        )
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
        self.client.log(
            cb, "dc/foo", start_rev=2, end_rev=2, discover_changed_paths=True
        )
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

    def test_set_get_prop_with_path(self):
        self.build_tree({"dc/foo": b"bla"})
        self.client_add("dc/foo")
        self.client_set_prop("dc/foo", "svn:eol-style", "native")
        self.client_commit("dc", message="Commit")
        self.assertEqual(
            self.client_get_prop("dc/foo", "svn:eol-style", "HEAD"), b"native"
        )

    def test_set_get_prop_with_url(self):
        self.build_tree({"dc/foo": b"bla"})
        self.client_add("dc/foo")
        self.client_set_prop("dc/foo", "svn:eol-style", "native")
        self.client_commit("dc", message="Commit")
        self.assertEqual(
            self.client_get_prop(self.repos_url + "/foo", "svn:eol-style", "HEAD"),
            b"native",
        )

    def test_checkout(self):
        self.build_tree({"dc/foo": b"bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        checkout_dir = os.path.join(self.test_dir, "checkout2")
        self.client.checkout(self.repos_url, checkout_dir, "HEAD")
        self.assertTrue(os.path.exists(os.path.join(checkout_dir, "foo")))

    def test_delete(self):
        self.build_tree({"dc/foo": b"bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.client.delete(["dc/foo"])
        self.assertFalse(os.path.exists("dc/foo"))

    def test_copy(self):
        self.build_tree({"dc/foo": b"bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.client.copy("dc/foo", "dc/bar")
        self.assertTrue(os.path.exists("dc/bar"))

    def test_propset_propget(self):
        self.build_tree({"dc/foo": b"bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.client.propset("myprop", "myval", "dc/foo", False, True)
        ret = self.client.propget("myprop", "dc/foo", "WORKING", "WORKING")
        self.assertIsInstance(ret, dict)
        self.assertIn(b"myval", ret.values())

    def test_propget_url(self):
        self.build_tree({"dc/foo": b"bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.client.propset("myprop", "myval", "dc/foo", False, True)
        self.client.commit(["dc"])
        url = self.repos_url + "/foo"
        ret = self.client.propget("myprop", url, 2, 2)
        self.assertIsInstance(ret, dict)
        self.assertIn(b"myval", ret.values())

    def test_propget_abspath(self):
        self.build_tree({"dc/foo": b"bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.client.propset("myprop", "myval", "dc/foo", False, True)
        abspath = os.path.abspath("dc/foo")
        ret = self.client.propget("myprop", abspath, "WORKING", "WORKING")
        self.assertIsInstance(ret, dict)
        self.assertIn(b"myval", ret.values())

    def test_proplist(self):
        self.build_tree({"dc/foo": b"bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.client.propset("myprop", "myval", "dc/foo", False, True)
        self.client.commit(["dc"])
        result = self.client.proplist("dc/foo", "WORKING", 0)
        self.assertIsInstance(result, list)

    def test_update(self):
        self.build_tree({"dc/foo": b"bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.client.update(["dc"], "HEAD")

    def test_list(self):
        self.build_tree({"dc/foo": b"bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        entries = self.client.list(self.repos_url, "HEAD", 0)
        self.assertIsInstance(entries, dict)

    def test_config(self):
        config = client.get_config()
        self.assertIsInstance(config, client.Config)

    def test_config_default_ignores(self):
        config = client.get_config()
        ignores = config.get_default_ignores()
        self.assertIsInstance(ignores, list)

    def test_lock_unlock(self):
        self.build_tree({"dc/foo": b"bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.client.lock(["dc/foo"], "test lock comment")
        self.client.unlock(["dc/foo"])

    def test_resolve(self):
        self.build_tree({"dc/resolveme": b"content"})
        self.client.add("dc/resolveme")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        # resolve on a non-conflicted path should succeed without error
        self.client.resolve("dc/resolveme", 0, 0)

    def test_add_with_options(self):
        self.build_tree({"dc/addopts": b"data"})
        self.client.add(
            "dc/addopts",
            recursive=True,
            force=False,
            no_ignore=True,
            add_parents=False,
            no_autoprops=True,
        )

    def test_commit_with_options(self):
        self.build_tree({"dc/commitopt": b"data"})
        self.client.add("dc/commitopt")
        self.client.log_msg_func = lambda c: "Commit with opts"
        callbacks = []
        self.client.commit(
            ["dc"],
            recurse=True,
            keep_locks=False,
            keep_changelist=False,
            commit_as_operations=True,
            include_file_externals=False,
            include_dir_externals=False,
            callback=lambda *args: callbacks.append(args),
        )
        self.assertEqual(1, len(callbacks))

    def test_commit_revprops(self):
        self.build_tree({"dc/rptest": b"data"})
        self.client.add("dc/rptest")
        self.client.log_msg_func = lambda c: "revprop commit"
        self.client.commit(["dc"], revprops={"custom:testprop": "testval"})

    def test_update_with_options(self):
        self.build_tree({"dc/updopt": b"data"})
        self.client.add("dc/updopt")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.client.update(
            ["dc"],
            "HEAD",
            recurse=True,
            ignore_externals=True,
            depth_is_sticky=False,
            allow_unver_obstructions=False,
            adds_as_modification=True,
            make_parents=False,
        )

    def test_checkout_with_options(self):
        self.build_tree({"dc/chkopt": b"data"})
        self.client.add("dc/chkopt")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        checkout_dir = os.path.join(self.test_dir, "checkout3")
        self.client.checkout(
            self.repos_url,
            checkout_dir,
            "HEAD",
            peg_rev="HEAD",
            recurse=True,
            allow_unver_obstructions=False,
        )
        self.assertTrue(os.path.exists(os.path.join(checkout_dir, "chkopt")))

    def test_export_with_options(self):
        self.build_tree({"dc/expopt": b"data"})
        self.client.add("dc/expopt")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        export_dir = os.path.join(self.test_dir, "export_opts")
        self.client.export(
            self.repos_url,
            export_dir,
            rev="HEAD",
            peg_rev="HEAD",
            recurse=True,
            overwrite=False,
        )
        self.assertTrue(os.path.exists(os.path.join(export_dir, "expopt")))

    def test_diff_with_options(self):
        dc = self.get_commit_editor(self.repos_url)
        f = dc.add_file("diffopt")
        f.modify(b"v1")
        dc.close()
        dc = self.get_commit_editor(self.repos_url)
        f = dc.open_file("diffopt")
        f.modify(b"v2")
        dc.close()
        (outf, errf) = self.client.diff(
            1,
            2,
            self.repos_url,
            self.repos_url,
            ignore_ancestry=True,
            no_diff_deleted=False,
            ignore_content_type=False,
        )
        self.addCleanup(outf.close)
        self.addCleanup(errf.close)
        out = outf.read()
        self.assertIn(b"diffopt", out)

    def test_log_with_options(self):
        entries = []

        def cb(changed_paths, revision, revprops, has_children=False):
            entries.append(revision)

        self.build_tree({"dc/logopt": b"data"})
        self.client.add("dc/logopt")
        self.client.log_msg_func = lambda c: "Commit 1"
        self.client.commit(["dc"])
        self.build_tree({"dc/logopt": b"data2"})
        self.client.commit(["dc"])
        self.client.log(
            cb,
            "dc/logopt",
            start_rev="HEAD",
            end_rev=1,
            limit=1,
            discover_changed_paths=True,
            strict_node_history=True,
            include_merged_revisions=False,
        )
        self.assertEqual(1, len(entries))

    def test_cat_with_peg_revision(self):
        self.build_tree({"dc/pegcat": b"original"})
        self.client.add("dc/pegcat")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        io = BytesIO()
        self.client.cat("dc/pegcat", io, revision=1, peg_revision=1)
        self.assertEqual(b"original", io.getvalue())

    def test_delete_keep_local(self):
        self.build_tree({"dc/keepme": b"data"})
        self.client.add("dc/keepme")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.client.delete(["dc/keepme"], keep_local=True)
        # File should still exist on disk
        self.assertTrue(os.path.exists("dc/keepme"))

    def test_copy_with_options(self):
        self.build_tree({"dc/cpsrc": b"data"})
        self.client.add("dc/cpsrc")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.client.copy(
            "dc/cpsrc",
            "dc/cpdst",
            copy_as_child=False,
            make_parents=False,
            metadata_only=False,
        )
        self.assertTrue(os.path.exists("dc/cpdst"))

    def test_info_with_options(self):
        self.build_tree({"dc/infoopt": b"data"})
        self.client.add("dc/infoopt")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        info = self.client.info(
            "dc/infoopt",
            revision=1,
            peg_revision=1,
            depth=0,
            fetch_excluded=False,
            fetch_actual_only=False,
        )
        self.assertIn("infoopt", info)

    def test_lock_steal(self):
        self.build_tree({"dc/locksteal": b"data"})
        self.client.add("dc/locksteal")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.client.lock(["dc/locksteal"], "lock comment", steal_lock=True)
        self.client.unlock(["dc/locksteal"], break_lock=True)

    def test_mkdir_make_parents(self):
        self.client.mkdir("dc/parent/child", make_parents=True)
        self.assertTrue(os.path.exists("dc/parent/child"))

    def test_mkdir_with_callback(self):
        commits = []
        self.client.mkdir(
            [self.repos_url + "/remotedir"], callback=lambda *args: commits.append(args)
        )

    def test_propset_skip_checks(self):
        self.build_tree({"dc/propskip": b"data"})
        self.client.add("dc/propskip")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.client.propset("custom:myprop", b"value", "dc/propskip", skip_checks=True)

    def test_propset_with_options(self):
        self.build_tree({"dc/propopt": b"data"})
        self.client.add("dc/propopt")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.client.propset("myprop", "myval", "dc/propopt", False, True)
        ret = self.client.propget("myprop", "dc/propopt", "WORKING", "WORKING", True)
        self.assertIsInstance(ret, dict)

    def test_cat_expand_keywords(self):
        self.build_tree({"dc/kwcat": b"$Id$"})
        self.client.add("dc/kwcat")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        io = BytesIO()
        self.client.cat("dc/kwcat", io, revision=1, expand_keywords=False)
        self.assertEqual(b"$Id$", io.getvalue())

    def test_export_native_eol(self):
        self.build_tree({"dc/eolfile": b"line\n"})
        self.client.add("dc/eolfile")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        export_dir = os.path.join(self.test_dir, "export_eol")
        self.client.export(self.repos_url, export_dir, native_eol="LF")
        self.assertTrue(os.path.exists(os.path.join(export_dir, "eolfile")))

    def test_list_include_externals(self):
        self.build_tree({"dc/listfile": b"data"})
        self.client.add("dc/listfile")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        entries = self.client.list(self.repos_url, "HEAD", 0, include_externals=False)
        self.assertIsInstance(entries, dict)

    def test_delete_with_callback(self):
        self.build_tree({"dc/delcb": b"data"})
        self.client.add("dc/delcb")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        commits = []
        self.client.delete(
            [self.repos_url + "/delcb"],
            force=True,
            callback=lambda *args: commits.append(args),
        )

    def test_copy_with_src_rev(self):
        self.build_tree({"dc/cprev": b"data"})
        self.client.add("dc/cprev")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.client.copy("dc/cprev", "dc/cprev2", src_rev=1)
        self.assertTrue(os.path.exists("dc/cprev2"))

    def test_get_config_with_dir(self):
        import tempfile

        cfg_dir = tempfile.mkdtemp()
        try:
            config = client.get_config(cfg_dir)
            self.assertIsInstance(config, client.Config)
        finally:
            import shutil

            shutil.rmtree(cfg_dir)

    def test_copy_pin_externals(self):
        self.build_tree({"dc/cppin": b"data"})
        self.client.add("dc/cppin")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.client.copy("dc/cppin", "dc/cppin2", pin_externals=False)
        self.assertTrue(os.path.exists("dc/cppin2"))

    def test_copy_metadata_only(self):
        self.build_tree({"dc/cpmeta": b"data"})
        self.client.add("dc/cpmeta")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.client.copy("dc/cpmeta", "dc/cpmeta2", metadata_only=False)
        self.assertTrue(os.path.exists("dc/cpmeta2"))

    def test_copy_with_callback(self):
        self.build_tree({"dc/cpcb": b"data"})
        self.client.add("dc/cpcb")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.client.copy(
            self.repos_url + "/cpcb",
            self.repos_url + "/cpcb2",
            callback=lambda *args: None,
        )

    def test_diff_relative_to_dir(self):
        self.build_tree({"dc/diffrel": b"line1\n"})
        self.client.add("dc/diffrel")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.build_tree({"dc/diffrel": b"line1\nline2\n"})
        (outfile, _errfile) = self.client.diff(
            1, "WORKING", "dc", "dc", relative_to_dir="dc"
        )
        out = outfile.read()
        self.assertIn(b"line2", out)

    def test_diff_encoding(self):
        self.build_tree({"dc/diffenc": b"hello\n"})
        self.client.add("dc/diffenc")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.build_tree({"dc/diffenc": b"hello\nworld\n"})
        (outfile, _errfile) = self.client.diff(
            1, "WORKING", "dc", "dc", encoding="utf-8"
        )
        out = outfile.read()
        self.assertIn(b"world", out)

    def test_diff_ignore_content_type(self):
        self.build_tree({"dc/diffict": b"hello\n"})
        self.client.add("dc/diffict")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.build_tree({"dc/diffict": b"hello\nworld\n"})
        (outfile, _errfile) = self.client.diff(
            1, "WORKING", "dc", "dc", ignore_content_type=True
        )
        out = outfile.read()
        self.assertIn(b"world", out)

    def test_diff_diffopts(self):
        self.build_tree({"dc/diffopt": b"hello\n"})
        self.client.add("dc/diffopt")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])
        self.build_tree({"dc/diffopt": b"hello\nworld\n"})
        (outfile, _errfile) = self.client.diff(1, "WORKING", "dc", "dc", diffopts=["-u"])
        out = outfile.read()
        self.assertIn(b"world", out)

    def test_notify_func_set_get(self):
        def notify_cb(info):
            pass

        self.assertIsNone(self.client.notify_func)
        self.client.notify_func = notify_cb
        self.assertIs(notify_cb, self.client.notify_func)
        self.client.notify_func = None
        self.assertIsNone(self.client.notify_func)

    def test_propset(self):
        self.client.mkdir(["dc/foo"])
        self.client.propset("someprop", "lala", "dc/foo")
        result = self.client.propget("someprop", "dc/foo")
        # SVN returns canonical paths with forward slashes; normalize for comparison
        normalized = {os.path.normpath(k): v for k, v in result.items()}
        self.assertEqual(
            {os.path.normpath(os.path.abspath("dc/foo")): b"lala"},
            normalized,
        )

    def test_iter_log(self):
        commit_msg_1 = b"Commit"
        commit_msg_2 = b"Commit 2"

        self.build_tree({"dc/foo": b"bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: commit_msg_1
        self.client.commit(["dc"])

        # iter_log without changed paths
        entries = list(self.client.iter_log("dc/foo", start_rev="HEAD", end_rev=1))
        self.assertEqual(1, len(entries))
        changed_paths, revision, revprops, has_children = entries[0]
        self.assertIsNone(changed_paths)
        self.assertEqual(1, revision)
        self.assertEqual(commit_msg_1, revprops["svn:log"])

        # Add a second commit
        self.build_tree({"dc/foo": b"blabla", "dc/bar": b"blablabla"})
        self.client.add("dc/bar")
        self.client.log_msg_func = lambda c: commit_msg_2
        self.client.commit(["dc"])

        # iter_log with changed paths
        entries = list(
            self.client.iter_log(
                "dc/foo", start_rev="HEAD", end_rev=1, discover_changed_paths=True
            )
        )
        self.assertEqual(2, len(entries))
        changed_paths, revision, revprops, has_children = entries[0]
        self.assertEqual(sorted(["/foo", "/bar"]), sorted(changed_paths.keys()))
        self.assertEqual(2, revision)
        self.assertEqual(commit_msg_2, revprops["svn:log"])

        changed_paths, revision, revprops, _has_children = entries[1]
        self.assertEqual(["/foo"], sorted(changed_paths.keys()))
        self.assertEqual(1, revision)
        self.assertEqual(commit_msg_1, revprops["svn:log"])

        # iter_log with limit
        entries = list(
            self.client.iter_log("dc/foo", start_rev="HEAD", end_rev=1, limit=1)
        )
        self.assertEqual(1, len(entries))
        self.assertEqual(2, entries[0][1])

    def test_iter_log_invalid(self):
        self.build_tree({"dc/foo": b"bla"})
        self.client.add("dc/foo")
        self.client.log_msg_func = lambda c: "Commit"
        self.client.commit(["dc"])

        # Non-existent revision should raise
        self.assertRaises(
            SubversionException,
            list,
            self.client.iter_log("dc/foo", start_rev=1000, end_rev=1000),
        )
