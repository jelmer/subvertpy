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

"""Tests for subvertpy.delta."""

from cStringIO import StringIO

from subvertpy.delta import (
    decode_length,
    encode_length,
    pack_svndiff0,
    send_stream,
    unpack_svndiff0,
    apply_txdelta_handler,
    TXDELTA_NEW, TXDELTA_SOURCE, TXDELTA_TARGET,
    )
from subvertpy.tests import TestCase

class DeltaTests(TestCase):

    def setUp(self):
        super(DeltaTests, self).setUp()
        self.windows = []

    def storing_window_handler(self, window):
        self.windows.append(window)

    def test_send_stream(self):
        stream = StringIO("foo")
        send_stream(stream, self.storing_window_handler)
        self.assertEqual([(0, 0, 3, 0, [(2, 0, 3)], 'foo'), None], 
                          self.windows)
    
    def test_apply_delta(self):
        stream = StringIO()
        source = "(source)"
        handler = apply_txdelta_handler(source, stream)
        
        new = "(new)"
        ops = (  # (action, offset, length)
            (TXDELTA_NEW, 0, len(new)),
            (TXDELTA_SOURCE, 0, len(source)),
            (TXDELTA_TARGET, len(new), len("(s")),  # Copy "(s"
            (TXDELTA_TARGET, len("(n"), len("ew)")),  # Copy "ew)"
            
            # Copy as target is generated
            (TXDELTA_TARGET, len(new + source), len("(sew)") * 2),
        )
        result = "(new)(source)(sew)(sew)(sew)"
        
        # (source offset, source length, result length, src_ops, ops, new)
        handler((0, len(source), len(result), 0, ops, new))
        handler(None)
        self.assertEqual(result, stream.getvalue())


class MarshallTests(TestCase):

    def test_encode_length(self):
        self.assertEqual("\x81\x02", encode_length(130))

    def test_roundtrip_length(self):
        self.assertEqual((42, ""), decode_length(encode_length(42)))


    def test_roundtrip_window(self):
        mywindow = (0, 0, 3, 1, [(2, 0, 3)], 'foo')
        self.assertEqual([mywindow], list(unpack_svndiff0(pack_svndiff0([mywindow]))))
