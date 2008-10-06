# Copyright (C) 2006-2007 Jelmer Vernooij <jelmer@samba.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from bzrlib.tests import TestCase
from marshall import literal, MarshallError, marshall, unmarshall

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
        self.assertEqual("1 ", marshall(1))

    def test_marshall_list(self):
        self.assertEqual("( 1 2 3 4 ) ", marshall([1,2,3,4]))
    
    def test_marshall_list_mixed(self):
        self.assertEqual("( 1 3 4 3:str ) ", marshall([1,3,4,"str"]))

    def test_marshall_literal(self):
        self.assertEqual("foo ", marshall(literal("foo")))

    def test_marshall_string(self):
        self.assertEqual("3:foo ", marshall("foo"))

    def test_marshall_raises(self):
        self.assertRaises(MarshallError, marshall, dict())

    def test_marshall_list_nested(self):
        self.assertEqual("( ( ( 3 ) 4 ) ) ", marshall([[[3], 4]]))

    def test_marshall_string_space(self):
        self.assertEqual("5:bla l ", marshall("bla l"))

    def test_unmarshall_string(self):
        self.assertEqual(('', "bla l"), unmarshall("5:bla l"))

    def test_unmarshall_list(self):
        self.assertEqual(('', [4,5]), unmarshall("( 4 5 ) "))

    def test_unmarshall_int(self):
        self.assertEqual(('', 2), unmarshall("2 "))

    def test_unmarshall_literal(self):
        self.assertEqual(('', literal("x")), unmarshall("x "))

    def test_unmarshall_empty(self):
        self.assertRaises(MarshallError, unmarshall, "")

    def test_unmarshall_nospace(self):
        self.assertRaises(MarshallError, unmarshall, "nospace")

    def test_unmarshall_toolong(self):
        self.assertRaises(MarshallError, unmarshall, "43432432:bla")

    def test_unmarshall_literal(self):
        self.assertRaises(MarshallError, unmarshall, ":-3213")

    def test_unmarshall_open_list(self):
        self.assertRaises(MarshallError, unmarshall, "( 3 4 ")

