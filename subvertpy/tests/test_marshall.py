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
    literal,
    marshall,
    unmarshall,
    )
from subvertpy.tests import TestCase


class TestMarshalling(TestCase):

    def test_literal_txt(self):
        l = literal("foo")
        self.assertEqual("foo", l.txt)

    def test_literal_str(self):
        l = literal("foo bar")
        self.assertEqual("foo bar", l.__str__())

    def test_literal_rep(self):
        l = literal("foo bar")
        self.assertEqual("foo bar", l.__repr__())

    def test_marshall_error(self):
        e = MarshallError("bla bla")
        self.assertEqual("bla bla", e.__str__())

    def test_marshall_int(self):
        self.assertEqual(b"1 ", marshall(1))

    def test_marshall_list(self):
        self.assertEqual(b"( 1 2 3 4 ) ", marshall([1, 2, 3, 4]))

    def test_marshall_list_mixed(self):
        self.assertEqual(b"( 1 3 4 3:str ) ", marshall([1, 3, 4, "str"]))

    def test_marshall_literal(self):
        self.assertEqual(b"foo ", marshall(literal("foo")))

    def test_marshall_string(self):
        self.assertEqual(b"3:foo ", marshall("foo"))

    def test_marshall_raises(self):
        self.assertRaises(MarshallError, marshall, dict())

    def test_marshall_list_nested(self):
        self.assertEqual(b"( ( ( 3 ) 4 ) ) ", marshall([[[3], 4]]))

    def test_marshall_string_space(self):
        self.assertEqual(b"5:bla l ", marshall("bla l"))

    def test_unmarshall_string(self):
        self.assertEqual((b'', b"bla l"), unmarshall(b"5:bla l"))

    def test_unmarshall_list(self):
        self.assertEqual((b'', [4, 5]), unmarshall(b"( 4 5 ) "))

    def test_unmarshall_int(self):
        self.assertEqual((b'', 2), unmarshall(b"2 "))

    def test_unmarshall_literal(self):
        self.assertEqual((b'', literal("x")), unmarshall(b"x "))

    def test_unmarshall_empty(self):
        self.assertRaises(MarshallError, unmarshall, b"")

    def test_unmarshall_nospace(self):
        self.assertRaises(MarshallError, unmarshall, b"nospace")

    def test_unmarshall_toolong(self):
        self.assertRaises(MarshallError, unmarshall, b"43432432:bla")

    def test_unmarshall_literal_negative(self):
        self.assertRaises(MarshallError, unmarshall, b":-3213")

    def test_unmarshall_open_list(self):
        self.assertRaises(MarshallError, unmarshall, b"( 3 4 ")
