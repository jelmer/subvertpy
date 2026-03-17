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

"""Subversion wc library tests."""

import os

from subvertpy import (
    wc,
)
from tests import (
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

    def test_is_normal_prop_false(self):
        self.assertFalse(wc.is_normal_prop("svn:entry:foo"))
        self.assertFalse(wc.is_normal_prop("svn:wc:foo"))

    def test_is_entry_prop(self):
        self.assertTrue(wc.is_entry_prop("svn:entry:foo"))

    def test_is_entry_prop_false(self):
        self.assertFalse(wc.is_entry_prop("svn:ignore"))

    def test_is_wc_prop(self):
        self.assertTrue(wc.is_wc_prop("svn:wc:foo"))

    def test_is_wc_prop_false(self):
        self.assertFalse(wc.is_wc_prop("svn:ignore"))

    def test_is_adm_dir(self):
        self.assertTrue(wc.is_adm_dir(".svn"))
        self.assertFalse(wc.is_adm_dir("foo"))

    def test_match_ignore_list(self):
        self.assertTrue(wc.match_ignore_list("foo", ["f*"]))
        self.assertTrue(wc.match_ignore_list("foo", ["foo"]))
        self.assertFalse(wc.match_ignore_list("foo", []))
        self.assertFalse(wc.match_ignore_list("foo", ["bar"]))

    def test_check_wc_nonexistent(self):
        import tempfile

        tmpdir = tempfile.mkdtemp()
        try:
            result = wc.check_wc(tmpdir)
            self.assertEqual(0, result)
        finally:
            import shutil

            shutil.rmtree(tmpdir)

    def test_get_actual_target(self):
        result = wc.get_actual_target("/foo/bar")
        self.assertIsInstance(result, tuple)
        self.assertEqual(2, len(result))


class WcTests(SubversionTestCase):
    def test_revision_status(self):
        self.make_client("repos", "checkout")
        ret = wc.revision_status("checkout")
        self.assertEqual((0, 0, 0, 0), ret)

    def test_revision_status_trailing(self):
        self.make_client("repos", "checkout")
        ret = wc.revision_status("checkout/")
        self.assertEqual((0, 0, 0, 0), ret)

    def test_revision_status_committed(self):
        self.make_client("repos", "checkout")
        ret = wc.revision_status("checkout", committed=True)
        self.assertEqual((0, 0, 0, 0), ret)

    def test_revision_status_trail_url(self):
        self.make_client("repos", "checkout")
        ret = wc.revision_status("checkout", trail_url=None)
        self.assertEqual((0, 0, 0, 0), ret)


class ContextTests(SubversionTestCase):
    def setUp(self):
        super().setUp()
        self.repos_url = self.make_client("repos", "checkout")

    def test_create_context(self):
        ctx = wc.Context()
        self.assertIsNotNone(ctx)

    def test_locked(self):
        ctx = wc.Context()
        result = ctx.locked(os.path.abspath("checkout"))
        self.assertIsInstance(result, tuple)
        self.assertEqual(2, len(result))

    def test_text_modified(self):
        ctx = wc.Context()
        self.build_tree({"checkout/foo": b"content"})
        self.client_add("checkout/foo")
        self.client_commit("checkout", message="add foo")
        # Unmodified file
        result = ctx.text_modified(os.path.abspath("checkout/foo"))
        self.assertFalse(result)
        # Modify the file
        self.build_tree({"checkout/foo": b"changed"})
        result = ctx.text_modified(os.path.abspath("checkout/foo"))
        self.assertTrue(result)

    def test_props_modified(self):
        ctx = wc.Context()
        self.build_tree({"checkout/bar": b"content"})
        self.client_add("checkout/bar")
        self.client_commit("checkout", message="add bar")
        result = ctx.props_modified(os.path.abspath("checkout/bar"))
        self.assertFalse(result)

    def test_conflicted(self):
        ctx = wc.Context()
        self.build_tree({"checkout/baz": b"content"})
        self.client_add("checkout/baz")
        self.client_commit("checkout", message="add baz")
        result = ctx.conflicted(os.path.abspath("checkout/baz"))
        # Returns a tuple of (text_conflicted, prop_conflicted, tree_conflicted)
        self.assertIsInstance(result, tuple)

    def test_status(self):
        ctx = wc.Context()
        self.build_tree({"checkout/statusfile": b"content"})
        self.client_add("checkout/statusfile")
        result = ctx.status(os.path.abspath("checkout/statusfile"))
        self.assertIsNotNone(result)

    def test_get_prop_diffs(self):
        ctx = wc.Context()
        self.build_tree({"checkout/propfile": b"content"})
        self.client_add("checkout/propfile")
        self.client_commit("checkout", message="add")
        result = ctx.get_prop_diffs(os.path.abspath("checkout/propfile"))
        self.assertIsInstance(result, tuple)
        self.assertEqual(2, len(result))

    def test_walk_status(self):
        ctx = wc.Context()
        self.build_tree({"checkout/walkfile": b"content"})
        self.client_add("checkout/walkfile")
        self.client_commit("checkout", message="add walkfile")
        statuses = []

        def receiver(path, status):
            statuses.append((path, status))

        ctx.walk_status(os.path.abspath("checkout"), receiver)
        self.assertTrue(len(statuses) > 0)

    def test_walk_status_with_options(self):
        from subvertpy import ra

        ctx = wc.Context()
        self.build_tree({"checkout/walkopt": b"content"})
        self.client_add("checkout/walkopt")
        self.client_commit("checkout", message="add walkopt")
        statuses = []

        def receiver(path, status):
            statuses.append((path, status))

        ctx.walk_status(
            os.path.abspath("checkout"),
            receiver,
            depth=ra.DEPTH_INFINITY,
            get_all=True,
            no_ignore=True,
        )
        self.assertTrue(len(statuses) > 0)

    def test_walk_status_ignore_patterns(self):
        ctx = wc.Context()
        self.build_tree({"checkout/walkign": b"content"})
        self.client_add("checkout/walkign")
        self.client_commit("checkout", message="add walkign")
        statuses = []

        def receiver(path, status):
            statuses.append((path, status))

        ctx.walk_status(
            os.path.abspath("checkout"), receiver, ignore_patterns=["*.pyc", "*.o"]
        )
        self.assertTrue(len(statuses) > 0)

    def test_walk_status_ignore_text_mode(self):
        ctx = wc.Context()
        self.build_tree({"checkout/walktxt": b"content"})
        self.client_add("checkout/walktxt")
        self.client_commit("checkout", message="add walktxt")
        statuses = []

        def receiver(path, status):
            statuses.append((path, status))

        ctx.walk_status(os.path.abspath("checkout"), receiver, ignore_text_mode=True)
        self.assertTrue(len(statuses) > 0)

    def test_crawl_revisions_with_options(self):
        ctx = wc.Context()
        self.build_tree({"checkout/crawlopt": b"data"})
        self.client_add("checkout/crawlopt")
        self.client_commit("checkout", message="add crawlopt")

        class MockReporter:
            def __init__(self):
                self.calls = []

            def set_path(self, path, revision, start_empty, lock_token, depth):
                self.calls.append(("set_path", path))

            def finish(self):
                self.calls.append(("finish",))

            def delete_path(self, path):
                pass

            def link_path(self, path, url, revision, start_empty, lock_token, depth):
                pass

            def abort(self):
                pass

        reporter = MockReporter()
        ctx.crawl_revisions(
            os.path.abspath("checkout"),
            reporter,
            restore_files=True,
            honor_depth_exclude=False,
            depth_compatibility_trick=True,
            use_commit_times=True,
        )
        call_types = [c[0] for c in reporter.calls]
        self.assertIn("set_path", call_types)
        self.assertIn("finish", call_types)

    def test_add_from_disk_no_lock(self):
        ctx = wc.Context()
        self.build_tree({"checkout/diskfile": b"disk content"})
        from subvertpy import SubversionException

        # add_from_disk requires a write lock
        self.assertRaises(
            SubversionException, ctx.add_from_disk, os.path.abspath("checkout/diskfile")
        )

    def test_add_lock_requires_write_lock(self):
        ctx = wc.Context()
        self.build_tree({"checkout/lockwc": b"data"})
        self.client_add("checkout/lockwc")
        self.client_commit("checkout", message="add lockwc")
        lock = wc.Lock(token="opaquelocktoken:test-token")
        from subvertpy import SubversionException

        # add_lock requires a write lock on the WC
        self.assertRaises(
            SubversionException, ctx.add_lock, os.path.abspath("checkout/lockwc"), lock
        )

    def test_remove_lock_requires_write_lock(self):
        ctx = wc.Context()
        self.build_tree({"checkout/rmlockwc": b"data"})
        self.client_add("checkout/rmlockwc")
        self.client_commit("checkout", message="add rmlockwc")
        from subvertpy import SubversionException

        self.assertRaises(
            SubversionException, ctx.remove_lock, os.path.abspath("checkout/rmlockwc")
        )

    def test_crawl_revisions(self):
        ctx = wc.Context()
        self.build_tree({"checkout/crawlfile": b"data"})
        self.client_add("checkout/crawlfile")
        self.client_commit("checkout", message="add crawlfile")

        class MockReporter:
            def __init__(self):
                self.calls = []

            def set_path(self, path, revision, start_empty, lock_token, depth):
                self.calls.append(("set_path", path, revision, start_empty))

            def finish(self):
                self.calls.append(("finish",))

            def delete_path(self, path):
                self.calls.append(("delete_path", path))

            def link_path(self, path, url, revision, start_empty, lock_token, depth):
                self.calls.append(("link_path", path, url))

            def abort(self):
                self.calls.append(("abort",))

        reporter = MockReporter()
        ctx.crawl_revisions(os.path.abspath("checkout"), reporter, restore_files=False)
        self.assertTrue(len(reporter.calls) > 0)
        # Should have called set_path at least once and finish
        call_types = [c[0] for c in reporter.calls]
        self.assertIn("set_path", call_types)
        self.assertIn("finish", call_types)

    def test_get_update_editor(self):
        ctx = wc.Context()
        self.build_tree({"checkout/updfile": b"data"})
        self.client_add("checkout/updfile")
        self.client_commit("checkout", message="add updfile")
        editor = ctx.get_update_editor(os.path.abspath("checkout"), "")
        self.assertIsNotNone(editor)
        editor.abort()

    def test_get_update_editor_with_options(self):
        from subvertpy import ra

        ctx = wc.Context()
        self.build_tree({"checkout/upd2": b"data"})
        self.client_add("checkout/upd2")
        self.client_commit("checkout", message="add upd2")
        editor = ctx.get_update_editor(
            os.path.abspath("checkout"),
            "",
            use_commit_times=True,
            depth=ra.DEPTH_INFINITY,
            depth_is_sticky=False,
            allow_unver_obstructions=False,
            adds_as_modification=True,
            server_performs_filtering=False,
            clean_checkout=False,
        )
        self.assertIsNotNone(editor)
        editor.abort()

    def test_get_update_editor_preserved_exts(self):
        ctx = wc.Context()
        self.build_tree({"checkout/upd3": b"data"})
        self.client_add("checkout/upd3")
        self.client_commit("checkout", message="add upd3")
        editor = ctx.get_update_editor(
            os.path.abspath("checkout"), "", preserved_exts=[".mine", ".theirs"]
        )
        self.assertIsNotNone(editor)
        editor.abort()

    def test_get_update_editor_notify_func(self):
        ctx = wc.Context()
        self.build_tree({"checkout/upd4": b"data"})
        self.client_add("checkout/upd4")
        self.client_commit("checkout", message="add upd4")
        notifications = []

        def notify(info):
            notifications.append(info)

        editor = ctx.get_update_editor(
            os.path.abspath("checkout"), "", notify_func=notify
        )
        self.assertIsNotNone(editor)
        editor.abort()

    def test_get_update_editor_conflict_func_not_implemented(self):
        ctx = wc.Context()
        self.build_tree({"checkout/upd5": b"data"})
        self.client_add("checkout/upd5")
        self.client_commit("checkout", message="add upd5")
        self.assertRaises(
            NotImplementedError,
            ctx.get_update_editor,
            os.path.abspath("checkout"),
            "",
            conflict_func=lambda: None,
        )

    def test_get_update_editor_external_func_not_implemented(self):
        ctx = wc.Context()
        self.build_tree({"checkout/upd6": b"data"})
        self.client_add("checkout/upd6")
        self.client_commit("checkout", message="add upd6")
        self.assertRaises(
            NotImplementedError,
            ctx.get_update_editor,
            os.path.abspath("checkout"),
            "",
            external_func=lambda: None,
        )

    def test_get_update_editor_dirents_func_not_implemented(self):
        ctx = wc.Context()
        self.build_tree({"checkout/upd7": b"data"})
        self.client_add("checkout/upd7")
        self.client_commit("checkout", message="add upd7")
        self.assertRaises(
            NotImplementedError,
            ctx.get_update_editor,
            os.path.abspath("checkout"),
            "",
            dirents_func=lambda: None,
        )

    def test_add_from_disk_with_props(self):
        ctx = wc.Context()
        self.build_tree({"checkout/diskprops": b"data"})
        from subvertpy import SubversionException

        # add_from_disk requires a write lock, but we can test that
        # the props parameter is accepted
        self.assertRaises(
            SubversionException,
            ctx.add_from_disk,
            os.path.abspath("checkout/diskprops"),
            props={b"svn:eol-style": b"native"},
        )

    def test_add_from_disk_skip_checks(self):
        ctx = wc.Context()
        self.build_tree({"checkout/diskskip": b"data"})
        from subvertpy import SubversionException

        # add_from_disk requires a write lock
        self.assertRaises(
            SubversionException,
            ctx.add_from_disk,
            os.path.abspath("checkout/diskskip"),
            skip_checks=True,
        )

    def test_add_from_disk_notify(self):
        ctx = wc.Context()
        self.build_tree({"checkout/disknot": b"data"})
        from subvertpy import SubversionException

        notifications = []

        def notify_cb(info):
            notifications.append(info)

        # add_from_disk requires a write lock
        self.assertRaises(
            SubversionException,
            ctx.add_from_disk,
            os.path.abspath("checkout/disknot"),
            notify=notify_cb,
        )

    def test_crawl_revisions_with_notify(self):
        ctx = wc.Context()
        self.build_tree({"checkout/crawlnot": b"data"})
        self.client_add("checkout/crawlnot")
        self.client_commit("checkout", message="add crawlnot")

        class MockReporter:
            def __init__(self):
                self.calls = []

            def set_path(self, path, revision, start_empty, lock_token, depth):
                self.calls.append(("set_path", path))

            def finish(self):
                self.calls.append(("finish",))

            def delete_path(self, path):
                pass

            def link_path(self, path, url, revision, start_empty, lock_token, depth):
                pass

            def abort(self):
                pass

        reporter = MockReporter()
        notifications = []

        def notify_cb(info):
            notifications.append(info)

        ctx.crawl_revisions(
            os.path.abspath("checkout"), reporter, restore_files=True, notify=notify_cb
        )
        call_types = [c[0] for c in reporter.calls]
        self.assertIn("set_path", call_types)
        self.assertIn("finish", call_types)

    def test_ensure_adm(self):
        from subvertpy import repos as svn_repos

        repo = svn_repos.Repository("repos")
        uuid = repo.fs().get_uuid()
        ctx = wc.Context()
        # ensure_adm on an existing checkout should succeed
        ctx.ensure_adm(
            os.path.abspath("checkout"), self.repos_url, self.repos_url, uuid, 0
        )

    def test_ensure_adm_with_depth(self):
        from subvertpy import ra
        from subvertpy import repos as svn_repos

        repo = svn_repos.Repository("repos")
        uuid = repo.fs().get_uuid()
        ctx = wc.Context()
        ctx.ensure_adm(
            os.path.abspath("checkout"),
            self.repos_url,
            self.repos_url,
            uuid,
            0,
            depth=ra.DEPTH_INFINITY,
        )

    def test_committed_queue_create(self):
        queue = wc.CommittedQueue()
        self.assertIsNotNone(queue)

    def test_committed_queue_queue(self):
        ctx = wc.Context()
        self.build_tree({"checkout/qfile": b"queue data"})
        self.client_add("checkout/qfile")
        self.client_commit("checkout", message="add qfile")
        queue = wc.CommittedQueue()
        queue.queue(os.path.abspath("checkout/qfile"), ctx)

    def test_process_committed_queue_requires_write_lock(self):
        from subvertpy import SubversionException

        ctx = wc.Context()
        self.build_tree({"checkout/pcqfile": b"data"})
        self.client_add("checkout/pcqfile")
        self.client_commit("checkout", message="add pcqfile")
        queue = wc.CommittedQueue()
        queue.queue(os.path.abspath("checkout/pcqfile"), ctx)
        self.assertRaises(
            SubversionException,
            ctx.process_committed_queue,
            queue,
            1,
            "2026-01-01T00:00:00.000000Z",
            "testuser",
        )


class LockTests(TestCase):
    def test_create_lock(self):
        lock = wc.Lock()
        self.assertIsNotNone(lock)

    def test_create_lock_with_token(self):
        lock = wc.Lock(token="opaquelocktoken:test")
        self.assertEqual(b"opaquelocktoken:test", lock.token)

    def test_path_default(self):
        lock = wc.Lock()
        self.assertIsNone(lock.path)

    def test_set_path(self):
        lock = wc.Lock()
        lock.path = b"/some/path"
        self.assertEqual("/some/path", lock.path)

    def test_token_default(self):
        lock = wc.Lock()
        self.assertIsNone(lock.token)

    def test_set_token(self):
        lock = wc.Lock()
        lock.token = b"opaquelocktoken:abc"
        self.assertEqual(b"opaquelocktoken:abc", lock.token)


class PristineTests(SubversionTestCase):
    def setUp(self):
        super().setUp()
        self.repos_url = self.make_client("repos", "checkout")

    def test_get_pristine_contents(self):
        self.build_tree({"checkout/pristfile": b"pristine data"})
        self.client_add("checkout/pristfile")
        self.client_commit("checkout", message="add pristfile")
        stream = wc.get_pristine_contents(os.path.abspath("checkout/pristfile"))
        self.assertIsNotNone(stream)

    def test_get_pristine_copy_path(self):
        import warnings

        self.build_tree({"checkout/cpfile": b"data"})
        self.client_add("checkout/cpfile")
        self.client_commit("checkout", message="add cpfile")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = wc.get_pristine_copy_path(os.path.abspath("checkout/cpfile"))
        self.assertIsNotNone(result)


class EnsureAdmTests(SubversionTestCase):
    def test_ensure_adm_bogus_url(self):
        from subvertpy import SubversionException

        self.make_client("repos", "checkout")
        self.assertRaises(
            SubversionException, wc.ensure_adm, "checkout", "fake-uuid", "file:///fake"
        )

    def test_ensure_adm_with_repos_and_rev(self):
        from subvertpy import repos as svn_repos

        repos_url = self.make_client("repos", "checkout")
        repo = svn_repos.Repository("repos")
        uuid = repo.fs().get_uuid()
        wc.ensure_adm("checkout", uuid, repos_url, repos=repos_url, rev=0)

    def test_ensure_adm_with_depth(self):
        from subvertpy import ra
        from subvertpy import repos as svn_repos

        repos_url = self.make_client("repos", "checkout")
        repo = svn_repos.Repository("repos")
        uuid = repo.fs().get_uuid()
        wc.ensure_adm(
            "checkout", uuid, repos_url, repos=repos_url, rev=0, depth=ra.DEPTH_INFINITY
        )


class CleanupTests(SubversionTestCase):
    def test_cleanup(self):
        self.make_client("repos", "checkout")
        # cleanup on a clean working copy should succeed
        wc.cleanup("checkout")

    def test_cleanup_with_diff3_cmd(self):
        self.make_client("repos", "checkout")
        wc.cleanup("checkout", diff3_cmd=None)


class ConstantsTests(TestCase):
    def test_schedule_constants(self):
        self.assertEqual(0, wc.SCHEDULE_NORMAL)
        self.assertEqual(1, wc.SCHEDULE_ADD)
        self.assertEqual(2, wc.SCHEDULE_DELETE)
        self.assertEqual(3, wc.SCHEDULE_REPLACE)

    def test_conflict_choose_constants(self):
        self.assertIsInstance(wc.CONFLICT_CHOOSE_POSTPONE, int)
        self.assertIsInstance(wc.CONFLICT_CHOOSE_BASE, int)
        self.assertIsInstance(wc.CONFLICT_CHOOSE_THEIRS_FULL, int)
        self.assertIsInstance(wc.CONFLICT_CHOOSE_MINE_FULL, int)
        self.assertIsInstance(wc.CONFLICT_CHOOSE_THEIRS_CONFLICT, int)
        self.assertIsInstance(wc.CONFLICT_CHOOSE_MINE_CONFLICT, int)
        self.assertIsInstance(wc.CONFLICT_CHOOSE_MERGED, int)

    def test_status_constants(self):
        self.assertIsInstance(wc.STATUS_NONE, int)
        self.assertIsInstance(wc.STATUS_UNVERSIONED, int)
        self.assertIsInstance(wc.STATUS_NORMAL, int)
        self.assertIsInstance(wc.STATUS_ADDED, int)
        self.assertIsInstance(wc.STATUS_MISSING, int)
        self.assertIsInstance(wc.STATUS_DELETED, int)
        self.assertIsInstance(wc.STATUS_REPLACED, int)
        self.assertIsInstance(wc.STATUS_MODIFIED, int)
        self.assertIsInstance(wc.STATUS_MERGED, int)
        self.assertIsInstance(wc.STATUS_CONFLICTED, int)
        self.assertIsInstance(wc.STATUS_IGNORED, int)
        self.assertIsInstance(wc.STATUS_OBSTRUCTED, int)
        self.assertIsInstance(wc.STATUS_EXTERNAL, int)
        self.assertIsInstance(wc.STATUS_INCOMPLETE, int)

    def test_translate_constants(self):
        self.assertIsInstance(wc.TRANSLATE_FROM_NF, int)
        self.assertIsInstance(wc.TRANSLATE_TO_NF, int)
        self.assertIsInstance(wc.TRANSLATE_FORCE_EOL_REPAIR, int)
        self.assertIsInstance(wc.TRANSLATE_NO_OUTPUT_CLEANUP, int)
        self.assertIsInstance(wc.TRANSLATE_FORCE_COPY, int)
        self.assertIsInstance(wc.TRANSLATE_USE_GLOBAL_TMP, int)
