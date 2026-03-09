# Copyright (C) 2006-2007 Jelmer Vernooij <jelmer@jelmer.uk>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA

"""Tests for subvertpy.marshall."""

from subvertpy.marshall import (
    MarshallError,
    NeedMoreData,
    literal,
    marshall,
    unmarshall,
)
from subvertpy.tests import TestCase


class TestMarshalling(TestCase):
    def test_literal_txt(self):
        line = literal("foo")
        self.assertEqual("foo", line.txt)

    def test_literal_str(self):
        line = literal("foo bar")
        self.assertEqual("foo bar", line.__str__())

    def test_literal_rep(self):
        line = literal("foo bar")
        self.assertEqual("foo bar", line.__repr__())

    def test_literal_eq_same(self):
        self.assertEqual(literal("foo"), literal("foo"))

    def test_literal_eq_different(self):
        self.assertNotEqual(literal("foo"), literal("bar"))

    def test_literal_eq_non_literal(self):
        self.assertNotEqual(literal("foo"), "foo")

    def test_marshall_error(self):
        err = MarshallError("bla bla")
        self.assertEqual("bla bla", err.__str__())

    def test_need_more_data_is_marshall_error(self):
        self.assertTrue(issubclass(NeedMoreData, MarshallError))

    def test_need_more_data(self):
        err = NeedMoreData("need more")
        self.assertIsInstance(err, MarshallError)
        self.assertEqual("need more", str(err))

    def test_marshall_int(self):
        self.assertEqual(b"1 ", marshall(1))

    def test_marshall_int_zero(self):
        self.assertEqual(b"0 ", marshall(0))

    def test_marshall_int_large(self):
        self.assertEqual(b"999999 ", marshall(999999))

    def test_marshall_list(self):
        self.assertEqual(b"( 1 2 3 4 ) ", marshall([1, 2, 3, 4]))

    def test_marshall_list_mixed(self):
        self.assertEqual(b"( 1 3 4 3:str ) ", marshall([1, 3, 4, "str"]))

    def test_marshall_literal(self):
        self.assertEqual(b"foo ", marshall(literal("foo")))

    def test_marshall_string(self):
        self.assertEqual(b"3:foo ", marshall("foo"))

    def test_marshall_bytes(self):
        self.assertEqual(b"3:foo ", marshall(b"foo"))

    def test_marshall_bytes_binary(self):
        data = b"\x00\x01\x02"
        self.assertEqual(b"3:\x00\x01\x02 ", marshall(data))

    def test_marshall_string_utf8(self):
        # UTF-8 multi-byte characters
        result = marshall("\u00e9")  # é
        self.assertEqual(b"2:\xc3\xa9 ", result)

    def test_marshall_raises(self):
        self.assertRaises(MarshallError, marshall, dict())

    def test_marshall_list_nested(self):
        self.assertEqual(b"( ( ( 3 ) 4 ) ) ", marshall([[[3], 4]]))

    def test_marshall_list_empty(self):
        self.assertEqual(b"( ) ", marshall([]))

    def test_marshall_tuple(self):
        self.assertEqual(b"( 1 2 ) ", marshall((1, 2)))

    def test_marshall_string_space(self):
        self.assertEqual(b"5:bla l ", marshall("bla l"))

    def test_marshall_string_empty(self):
        self.assertEqual(b"0: ", marshall(""))

    def test_unmarshall_string(self):
        self.assertEqual((b"", b"bla l"), unmarshall(b"5:bla l"))

    def test_unmarshall_list(self):
        self.assertEqual((b"", [4, 5]), unmarshall(b"( 4 5 ) "))

    def test_unmarshall_list_empty(self):
        self.assertEqual((b'', []), unmarshall(b"( ) "))

    def test_unmarshall_list_nested(self):
        self.assertEqual(
            (b'', [[1, 2], 3]),
            unmarshall(b"( ( 1 2 ) 3 ) "))

    def test_unmarshall_int(self):
        self.assertEqual((b"", 2), unmarshall(b"2 "))

    def test_unmarshall_int_zero(self):
        self.assertEqual((b'', 0), unmarshall(b"0 "))

    def test_unmarshall_int_large(self):
        self.assertEqual((b'', 123456), unmarshall(b"123456 "))

    def test_unmarshall_literal(self):
        self.assertEqual((b"", literal("x")), unmarshall(b"x "))

    def test_unmarshall_literal_with_digits(self):
        self.assertEqual((b'', literal("foo2")), unmarshall(b"foo2 "))

    def test_unmarshall_literal_with_dash(self):
        self.assertEqual(
            (b'', literal("foo-bar")), unmarshall(b"foo-bar "))

    def test_unmarshall_empty(self):
        self.assertRaises(NeedMoreData, unmarshall, b"")

    def test_unmarshall_nospace(self):
        self.assertRaises(MarshallError, unmarshall, b"nospace")

    def test_unmarshall_toolong(self):
        self.assertRaises(NeedMoreData, unmarshall, b"43432432:bla")

    def test_unmarshall_literal_negative(self):
        self.assertRaises(MarshallError, unmarshall, b":-3213")

    def test_unmarshall_open_list(self):
        self.assertRaises(NeedMoreData, unmarshall, b"( 3 4 ")

    def test_unmarshall_remaining_data(self):
        # Two marshalled items concatenated
        data = marshall(b"foo") + marshall(b"bar")
        remainder, value = unmarshall(data)
        self.assertEqual(b"foo", value)
        _, value2 = unmarshall(remainder)
        self.assertEqual(b"bar", value2)

    def test_unmarshall_list_missing_space_after_open(self):
        self.assertRaises(MarshallError, unmarshall, b"(x")

    def test_unmarshall_need_more_data_list_start(self):
        self.assertRaises(NeedMoreData, unmarshall, b"(")

    def test_roundtrip_int(self):
        _, val = unmarshall(marshall(42))
        self.assertEqual(42, val)

    def test_roundtrip_string(self):
        _, val = unmarshall(marshall(b"hello"))
        self.assertEqual(b"hello", val)

    def test_roundtrip_list(self):
        _, val = unmarshall(marshall([1, 2, 3]))
        self.assertEqual([1, 2, 3], val)

    def test_roundtrip_literal(self):
        _, val = unmarshall(marshall(literal("success")))
        self.assertEqual(literal("success"), val)

    def test_roundtrip_nested(self):
        _, val = unmarshall(marshall([literal("cmd"), [1, b"data"]]))
        self.assertEqual([literal("cmd"), [1, b"data"]], val)

    def test_marshall_bool_true(self):
        # In Python 3, bool is a subclass of int, so True marshalls as 1
        self.assertEqual(b"1 ", marshall(True))

    def test_marshall_bool_false(self):
        # In Python 3, bool is a subclass of int, so False marshalls as 0
        self.assertEqual(b"0 ", marshall(False))

    def test_marshall_none_raises(self):
        self.assertRaises(MarshallError, marshall, None)

    def test_marshall_float_raises(self):
        self.assertRaises(MarshallError, marshall, 3.14)

    def test_unmarshall_literal_newline_separator(self):
        # newline is also valid whitespace
        self.assertEqual((b'', literal("x")), unmarshall(b"x\n"))

    def test_unmarshall_int_newline_separator(self):
        self.assertEqual((b'', 5), unmarshall(b"5\n"))

    def test_unmarshall_list_newline_separator(self):
        self.assertEqual((b'', [1]), unmarshall(b"( 1 )\n"))
