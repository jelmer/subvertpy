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

"""Subversion core library tests."""

import os
import time
from unittest import SkipTest
from subvertpy import properties
from subvertpy.tests import (
    TestCase,
)


class TestProperties(TestCase):
    def setUp(self):
        super(TestProperties, self).setUp()

    def test_time_from_cstring(self):
        self.assertEqual(
            1225704780716938,
            properties.time_from_cstring("2008-11-03T09:33:00.716938Z"),
        )

    def test_time_from_cstring_independent_from_dst(self):
        old_tz = os.environ.get("TZ", None)
        # On Windows, there is no tzset function, so skip this test.
        if getattr(time, "tzset", None) is None:
            raise SkipTest("tzset not available on Windows")

        try:
            # First specify a fixed timezone with known DST (late March to late
            # October)
            os.environ["TZ"] = "Europe/London"
            time.tzset()
            # Now test a time within that DST
            self.assertEqual(
                1275295762430000,
                properties.time_from_cstring("2010-05-31T08:49:22.430000Z"),
            )
        finally:
            if old_tz is None:
                del os.environ["TZ"]
            else:
                os.environ["TZ"] = old_tz
            time.tzset()

    def test_time_to_cstring(self):
        self.assertEqual(
            "2008-11-03T09:33:00.716938Z", properties.time_to_cstring(1225704780716938)
        )


class TestExternalsParser(TestCase):
    def test_parse_root_relative_externals(self):
        self.assertRaises(
            NotImplementedError,
            properties.parse_externals_description,
            "http://example.com",
            "third-party/skins              ^/foo",
        )

    def test_parse_scheme_relative_externals(self):
        self.assertRaises(
            NotImplementedError,
            properties.parse_externals_description,
            "http://example.com",
            "third-party/skins              //foo",
        )

    def test_parse_externals(self):
        self.assertEqual(
            {
                "third-party/sounds": (None, "http://sounds.red-bean.com/repos"),
                "third-party/skins": (
                    None,
                    "http://skins.red-bean.com/repositories/skinproj",
                ),
                "third-party/skins/toolkit": (
                    21,
                    "http://svn.red-bean.com/repos/skin-maker",
                ),
            },
            properties.parse_externals_description(
                "http://example.com",
                """\
third-party/sounds            http://sounds.red-bean.com/repos
third-party/skins          http://skins.red-bean.com/repositories/skinproj
third-party/skins/toolkit -r21 http://svn.red-bean.com/repos/skin-maker""",
            ),
        )

    def test_parse_externals_space_revno(self):
        self.assertEqual(
            {
                "third-party/skins/toolkit": (
                    21,
                    "http://svn.red-bean.com/repos/skin-maker",
                )
            },
            properties.parse_externals_description(
                "http://example.com",
                """\
third-party/skins/toolkit -r 21 http://svn.red-bean.com/repos/skin-maker""",
            ),
        )

    def test_parse_externals_swapped(self):
        self.assertEqual(
            {"third-party/sounds": (None, "http://sounds.red-bean.com/repos")},
            properties.parse_externals_description(
                "http://example.com",
                """\
http://sounds.red-bean.com/repos         third-party/sounds
""",
            ),
        )

    def test_parse_comment(self):
        self.assertEqual(
            {"third-party/sounds": (None, "http://sounds.red-bean.com/repos")},
            properties.parse_externals_description(
                "http://example.com/",
                """\

third-party/sounds             http://sounds.red-bean.com/repos
#third-party/skins              http://skins.red-bean.com/repositories/skinproj
#third-party/skins/toolkit -r21 http://svn.red-bean.com/repos/skin-maker""",
            ),
        )

    def test_parse_relative(self):
        self.assertEqual(
            {
                "third-party/sounds": (None, "http://example.com/branches/other"),
            },
            properties.parse_externals_description(
                "http://example.com/trunk",
                "third-party/sounds             ../branches/other",
            ),
        )

    def test_parse_repos_root_relative(self):
        self.assertEqual(
            {
                "third-party/sounds": (
                    None,
                    "http://example.com/bar/bla/branches/other",
                ),
            },
            properties.parse_externals_description(
                "http://example.com/trunk",
                "third-party/sounds             /bar/bla/branches/other",
            ),
        )

    def test_parse_invalid_missing_url(self):
        """No URL specified."""
        self.assertRaises(
            properties.InvalidExternalsDescription,
            lambda: properties.parse_externals_description(
                "http://example.com/", "bla"
            ),
        )

    def test_parse_invalid_too_much_data(self):
        """No URL specified."""
        self.assertRaises(
            properties.InvalidExternalsDescription,
            lambda: properties.parse_externals_description(
                None, "bla -R40 http://bla/"
            ),
        )


class MergeInfoPropertyParserTests(TestCase):
    def test_simple_range(self):
        self.assertEqual(
            {"/trunk": [(1, 2, True)]},
            properties.parse_mergeinfo_property("/trunk:1-2\n"),
        )

    def test_simple_range_uninheritable(self):
        self.assertEqual(
            {"/trunk": [(1, 2, False)]},
            properties.parse_mergeinfo_property("/trunk:1-2*\n"),
        )

    def test_simple_individual(self):
        self.assertEqual(
            {"/trunk": [(1, 1, True)]},
            properties.parse_mergeinfo_property("/trunk:1\n"),
        )

    def test_empty(self):
        self.assertEqual({}, properties.parse_mergeinfo_property(""))


class MergeInfoPropertyCreatorTests(TestCase):
    def test_simple_range(self):
        self.assertEqual(
            "/trunk:1-2\n",
            properties.generate_mergeinfo_property({"/trunk": [(1, 2, True)]}),
        )

    def test_simple_individual(self):
        self.assertEqual(
            "/trunk:1\n",
            properties.generate_mergeinfo_property({"/trunk": [(1, 1, True)]}),
        )

    def test_empty(self):
        self.assertEqual("", properties.generate_mergeinfo_property({}))


class RevnumRangeTests(TestCase):
    def test_add_revnum_empty(self):
        self.assertEqual([(1, 1, True)], properties.range_add_revnum([], 1))

    def test_add_revnum_before(self):
        self.assertEqual(
            [(2, 2, True), (8, 8, True)], properties.range_add_revnum([(2, 2, True)], 8)
        )

    def test_add_revnum_included(self):
        self.assertEqual([(1, 3, True)], properties.range_add_revnum([(1, 3, True)], 2))

    def test_add_revnum_after(self):
        self.assertEqual(
            [(1, 3, True), (5, 5, True)], properties.range_add_revnum([(1, 3, True)], 5)
        )

    def test_add_revnum_extend_before(self):
        self.assertEqual([(1, 3, True)], properties.range_add_revnum([(2, 3, True)], 1))

    def test_add_revnum_extend_after(self):
        self.assertEqual([(1, 3, True)], properties.range_add_revnum([(1, 2, True)], 3))

    def test_revnum_includes_empty(self):
        self.assertFalse(properties.range_includes_revnum([], 2))

    def test_revnum_includes_oor(self):
        self.assertFalse(
            properties.range_includes_revnum([(1, 3, True), (4, 5, True)], 10)
        )

    def test_revnum_includes_in(self):
        self.assertTrue(
            properties.range_includes_revnum([(1, 3, True), (4, 5, True)], 2)
        )


class MergeInfoIncludeTests(TestCase):
    def test_includes_individual(self):
        self.assertTrue(
            properties.mergeinfo_includes_revision(
                {"/trunk": [(1, 1, True)]}, "/trunk", 1
            )
        )

    def test_includes_range(self):
        self.assertTrue(
            properties.mergeinfo_includes_revision(
                {"/trunk": [(1, 5, True)]}, "/trunk", 3
            )
        )

    def test_includes_invalid_path(self):
        self.assertFalse(
            properties.mergeinfo_includes_revision(
                {"/somepath": [(1, 5, True)]}, "/trunk", 3
            )
        )

    def test_includes_invalid_revnum(self):
        self.assertFalse(
            properties.mergeinfo_includes_revision(
                {"/trunk": [(1, 5, True)]}, "/trunk", 30
            )
        )


class MergeInfoAddRevisionTests(TestCase):
    def test_add_new_path(self):
        mergeinfo = {}
        result = properties.mergeinfo_add_revision(mergeinfo, "/trunk", 5)
        self.assertEqual({"/trunk": [(5, 5, True)]}, result)

    def test_add_to_existing_path(self):
        mergeinfo = {"/trunk": [(1, 3, True)]}
        result = properties.mergeinfo_add_revision(mergeinfo, "/trunk", 5)
        self.assertEqual({"/trunk": [(1, 3, True), (5, 5, True)]}, result)

    def test_add_extends_range(self):
        mergeinfo = {"/trunk": [(1, 3, True)]}
        result = properties.mergeinfo_add_revision(mergeinfo, "/trunk", 4)
        self.assertEqual({"/trunk": [(1, 4, True)]}, result)

    def test_add_already_included(self):
        mergeinfo = {"/trunk": [(1, 5, True)]}
        result = properties.mergeinfo_add_revision(mergeinfo, "/trunk", 3)
        self.assertEqual({"/trunk": [(1, 5, True)]}, result)


class IsValidPropertyNameTests(TestCase):
    def test_simple_name(self):
        self.assertTrue(properties.is_valid_property_name("svn:log"))

    def test_name_with_colon(self):
        self.assertTrue(properties.is_valid_property_name(":foo"))

    def test_name_with_underscore_start(self):
        self.assertTrue(properties.is_valid_property_name("_foo"))

    def test_alphanumeric(self):
        self.assertTrue(properties.is_valid_property_name("abc123"))

    def test_with_dash(self):
        self.assertTrue(properties.is_valid_property_name("my-prop"))

    def test_with_dot(self):
        self.assertTrue(properties.is_valid_property_name("my.prop"))

    def test_invalid_start(self):
        self.assertFalse(properties.is_valid_property_name("-foo"))

    def test_invalid_char(self):
        self.assertFalse(properties.is_valid_property_name("foo bar"))

    def test_svn_prefix(self):
        self.assertTrue(properties.is_valid_property_name("svn:externals"))


class PropertyDiffTests(TestCase):
    def test_diff_empty(self):
        self.assertEqual({}, properties.diff({}, {}))

    def test_diff_added(self):
        self.assertEqual({"key": (None, "val")}, properties.diff({"key": "val"}, {}))

    def test_diff_changed(self):
        self.assertEqual(
            {"key": ("old", "new")}, properties.diff({"key": "new"}, {"key": "old"})
        )

    def test_diff_unchanged(self):
        self.assertEqual({}, properties.diff({"key": "same"}, {"key": "same"}))

    def test_diff_multiple_changes(self):
        result = properties.diff(
            {"a": "1", "b": "changed", "c": "3"}, {"a": "1", "b": "original"}
        )
        self.assertEqual({"b": ("original", "changed"), "c": (None, "3")}, result)

    def test_diff_only_reports_current_keys(self):
        # diff() only iterates over current.items(), so properties
        # that were deleted (in previous but not current) are not reported
        result = properties.diff({}, {"deleted": "val"})
        self.assertEqual({}, result)


class PropertyConstantsTests(TestCase):
    def test_prop_executable(self):
        self.assertEqual(properties.PROP_EXECUTABLE, "svn:executable")

    def test_prop_externals(self):
        self.assertEqual(properties.PROP_EXTERNALS, "svn:externals")

    def test_prop_mergeinfo(self):
        self.assertEqual(properties.PROP_MERGEINFO, "svn:mergeinfo")

    def test_prop_revision_log(self):
        self.assertEqual(properties.PROP_REVISION_LOG, "svn:log")

    def test_prop_revision_author(self):
        self.assertEqual(properties.PROP_REVISION_AUTHOR, "svn:author")

    def test_prop_revision_date(self):
        self.assertEqual(properties.PROP_REVISION_DATE, "svn:date")

    def test_prop_special(self):
        self.assertEqual(properties.PROP_SPECIAL, "svn:special")

    def test_prop_prefix(self):
        self.assertEqual(properties.PROP_PREFIX, "svn:")


class ExternalsParserAdditionalTests(TestCase):
    def test_parse_swapped_with_revision_dash_r_x(self):
        self.assertEqual(
            {"ext": (10, "http://example.com/foo")},
            properties.parse_externals_description(
                "http://example.com", "-r10 http://example.com/foo ext"
            ),
        )

    def test_parse_dir_dash_r_x_url(self):
        self.assertEqual(
            {"ext": (10, "http://example.com/foo")},
            properties.parse_externals_description(
                "http://example.com", "ext -r10 http://example.com/foo"
            ),
        )

    def test_parse_empty(self):
        self.assertEqual(
            {}, properties.parse_externals_description("http://example.com", "")
        )

    def test_parse_comment_only(self):
        self.assertEqual(
            {},
            properties.parse_externals_description(
                "http://example.com", "# just a comment"
            ),
        )


class MergeInfoPropertyCreatorAdditionalTests(TestCase):
    def test_uninheritable_range(self):
        self.assertEqual(
            "/trunk:1-2*\n",
            properties.generate_mergeinfo_property({"/trunk": [(1, 2, False)]}),
        )

    def test_uninheritable_individual(self):
        self.assertEqual(
            "/trunk:1*\n",
            properties.generate_mergeinfo_property({"/trunk": [(1, 1, False)]}),
        )

    def test_multiple_ranges(self):
        result = properties.generate_mergeinfo_property(
            {"/trunk": [(1, 3, True), (5, 8, True)]}
        )
        self.assertEqual("/trunk:1-3,5-8\n", result)
