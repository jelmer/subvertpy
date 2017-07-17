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

"""Tests for subvertpy.delta."""

from io import BytesIO

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
        stream = BytesIO(b"foo")
        send_stream(stream, self.storing_window_handler)
        self.assertEqual([(0, 0, 3, 0, [(2, 0, 3)], b'foo'), None],
                         self.windows)

    def test_apply_delta(self):
        stream = BytesIO()
        source = b"(source)"
        handler = apply_txdelta_handler(source, stream)

        new = b"(new)"
        ops = (  # (action, offset, length)
            (TXDELTA_NEW, 0, len(new)),
            (TXDELTA_SOURCE, 0, len(source)),
            (TXDELTA_TARGET, len(new), len(b"(s")),  # Copy "(s"
            (TXDELTA_TARGET, len(b"(n"), len(b"ew)")),  # Copy "ew)"

            # Copy as target is generated
            (TXDELTA_TARGET, len(new + source), len(b"(sew)") * 2),
        )
        result = b"(new)(source)(sew)(sew)(sew)"

        # (source offset, source length, result length, src_ops, ops, new)
        handler((0, len(source), len(result), 0, ops, new))
        handler(None)
        self.assertEqual(result, stream.getvalue())


class MarshallTests(TestCase):

    def test_encode_length(self):
        self.assertEqual(bytearray(b"\x81\x02"), encode_length(130))

    def test_roundtrip_length(self):
        self.assertEqual((42, bytes()), decode_length(encode_length(42)))

    def test_roundtrip_window(self):
        mywindow = (0, 0, 3, 1, [(2, 0, 3)], b'foo')
        self.assertEqual(
            [mywindow],
            list(unpack_svndiff0(pack_svndiff0([mywindow]))))
