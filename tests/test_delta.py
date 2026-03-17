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
    DELTA_WINDOW_SIZE,
    MAX_ENCODED_INT_LEN,
    SVNDIFF0_HEADER,
    TXDELTA_INVALID,
    TXDELTA_NEW,
    TXDELTA_SOURCE,
    TXDELTA_TARGET,
    apply_txdelta_handler,
    apply_txdelta_handler_chunks,
    apply_txdelta_window,
    decode_length,
    encode_length,
    pack_svndiff0,
    pack_svndiff0_window,
    pack_svndiff_instruction,
    send_stream,
    txdelta_apply_ops,
    unpack_svndiff0,
    unpack_svndiff_instruction,
)
from tests import TestCase


class DeltaTests(TestCase):
    def setUp(self):
        super().setUp()
        self.windows = []

    def storing_window_handler(self, window):
        self.windows.append(window)

    def test_send_stream(self):
        stream = BytesIO(b"foo")
        send_stream(stream, self.storing_window_handler)
        self.assertEqual([(0, 0, 3, 0, [(2, 0, 3)], b"foo"), None], self.windows)

    def test_send_stream_returns_md5(self):
        import hashlib

        data = b"hello world"
        stream = BytesIO(data)
        result = send_stream(stream, self.storing_window_handler)
        self.assertEqual(hashlib.md5(data).digest(), result)

    def test_send_stream_empty(self):
        stream = BytesIO(b"")
        send_stream(stream, self.storing_window_handler)
        self.assertEqual([None], self.windows)

    def test_send_stream_non_bytes_raises(self):
        import io

        stream = io.StringIO("text")
        self.assertRaises(TypeError, send_stream, stream, self.storing_window_handler)

    def test_send_stream_custom_block_size(self):
        data = b"abcdef"
        stream = BytesIO(data)
        send_stream(stream, self.storing_window_handler, block_size=3)
        # Should get two windows plus None
        self.assertEqual(3, len(self.windows))
        self.assertIsNone(self.windows[-1])

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

    def test_apply_txdelta_handler_none_is_noop(self):
        stream = BytesIO()
        handler = apply_txdelta_handler(b"", stream)
        handler(None)
        self.assertEqual(b"", stream.getvalue())

    def test_apply_txdelta_handler_chunks(self):
        source_chunks = [b"hello", b" world"]
        target_chunks = []
        handler = apply_txdelta_handler_chunks(source_chunks, target_chunks)
        new_data = b"replaced"
        ops = [(TXDELTA_NEW, 0, len(new_data))]
        handler((0, 11, len(new_data), 0, ops, new_data))
        handler(None)
        self.assertEqual([bytearray(b"replaced")], target_chunks)

    def test_apply_txdelta_handler_chunks_source_copy(self):
        source_chunks = [b"hello"]
        target_chunks = []
        handler = apply_txdelta_handler_chunks(source_chunks, target_chunks)
        ops = [(TXDELTA_SOURCE, 0, 5)]
        handler((0, 5, 5, 0, ops, b""))
        handler(None)
        self.assertEqual([bytearray(b"hello")], target_chunks)


class TxDeltaApplyOpsTests(TestCase):
    def test_source_copy(self):
        result = txdelta_apply_ops(0, [(TXDELTA_SOURCE, 0, 3)], b"", b"abc")
        self.assertEqual(bytearray(b"abc"), result)

    def test_new_data(self):
        result = txdelta_apply_ops(0, [(TXDELTA_NEW, 0, 3)], b"xyz", b"")
        self.assertEqual(bytearray(b"xyz"), result)

    def test_target_copy(self):
        # First add some new data, then copy from target
        ops = [
            (TXDELTA_NEW, 0, 2),
            (TXDELTA_TARGET, 0, 4),
        ]
        result = txdelta_apply_ops(0, ops, b"ab", b"")
        self.assertEqual(bytearray(b"ababab"), result)

    def test_invalid_action_raises(self):
        self.assertRaises(
            Exception, txdelta_apply_ops, 0, [(TXDELTA_INVALID, 0, 1)], b"", b"x"
        )

    def test_empty_ops(self):
        result = txdelta_apply_ops(0, [], b"", b"source")
        self.assertEqual(bytearray(b""), result)


class ApplyTxDeltaWindowTests(TestCase):
    def test_simple_new(self):
        window = (0, 0, 5, 0, [(TXDELTA_NEW, 0, 5)], b"hello")
        result = apply_txdelta_window(b"", window)
        self.assertEqual(bytearray(b"hello"), result)

    def test_source_copy(self):
        window = (2, 3, 3, 0, [(TXDELTA_SOURCE, 0, 3)], b"")
        result = apply_txdelta_window(b"XXabcXX", window)
        self.assertEqual(bytearray(b"abc"), result)

    def test_tview_len_mismatch_raises(self):
        # tview_len (10) doesn't match actual result length (5)
        window = (0, 0, 10, 0, [(TXDELTA_NEW, 0, 5)], b"hello")
        self.assertRaises(AssertionError, apply_txdelta_window, b"", window)


class MarshallTests(TestCase):
    def test_encode_length(self):
        self.assertEqual(bytearray(b"\x81\x02"), encode_length(130))

    def test_encode_length_zero(self):
        self.assertEqual(bytearray(b"\x00"), encode_length(0))

    def test_encode_length_small(self):
        self.assertEqual(bytearray(b"\x01"), encode_length(1))
        self.assertEqual(bytearray(b"\x7f"), encode_length(127))

    def test_encode_length_large(self):
        encoded = encode_length(16384)
        decoded, _ = decode_length(encoded)
        self.assertEqual(16384, decoded)

    def test_roundtrip_length(self):
        self.assertEqual((42, b""), decode_length(encode_length(42)))

    def test_roundtrip_length_various(self):
        for val in [0, 1, 127, 128, 255, 256, 1000, 65535, 100000]:
            decoded, remainder = decode_length(encode_length(val))
            self.assertEqual(val, decoded)
            self.assertEqual(b"", remainder)

    def test_roundtrip_window(self):
        mywindow = (0, 0, 3, 1, [(2, 0, 3)], b"foo")
        self.assertEqual([mywindow], list(unpack_svndiff0(pack_svndiff0([mywindow]))))

    def test_roundtrip_window_multiple(self):
        w1 = (0, 0, 3, 1, [(TXDELTA_NEW, 0, 3)], b"foo")
        w2 = (0, 0, 3, 1, [(TXDELTA_NEW, 0, 3)], b"bar")
        result = list(unpack_svndiff0(pack_svndiff0([w1, w2])))
        self.assertEqual([w1, w2], result)

    def test_pack_svndiff0_header(self):
        packed = pack_svndiff0([])
        self.assertTrue(packed.startswith(SVNDIFF0_HEADER))

    def test_unpack_svndiff0_empty(self):
        result = list(unpack_svndiff0(SVNDIFF0_HEADER))
        self.assertEqual([], result)


class SvndiffInstructionTests(TestCase):
    def test_pack_unpack_new_short(self):
        instr = (TXDELTA_NEW, 0, 10)
        packed = pack_svndiff_instruction(instr)
        unpacked, remainder = unpack_svndiff_instruction(packed)
        self.assertEqual(instr, unpacked)
        self.assertEqual(b"", remainder)

    def test_pack_unpack_source(self):
        instr = (TXDELTA_SOURCE, 5, 10)
        packed = pack_svndiff_instruction(instr)
        unpacked, remainder = unpack_svndiff_instruction(packed)
        self.assertEqual(instr, unpacked)
        self.assertEqual(b"", remainder)

    def test_pack_unpack_target(self):
        instr = (TXDELTA_TARGET, 3, 7)
        packed = pack_svndiff_instruction(instr)
        unpacked, remainder = unpack_svndiff_instruction(packed)
        self.assertEqual(instr, unpacked)
        self.assertEqual(b"", remainder)

    def test_pack_unpack_long_length(self):
        # Length >= 0x3f triggers the longer encoding path
        instr = (TXDELTA_NEW, 0, 100)
        packed = pack_svndiff_instruction(instr)
        unpacked, remainder = unpack_svndiff_instruction(packed)
        self.assertEqual(instr, unpacked)
        self.assertEqual(b"", remainder)

    def test_pack_unpack_source_long(self):
        instr = (TXDELTA_SOURCE, 200, 100)
        packed = pack_svndiff_instruction(instr)
        unpacked, _ = unpack_svndiff_instruction(packed)
        self.assertEqual(instr, unpacked)

    def test_roundtrip_through_window(self):
        """Pack instructions into a window, then unpack."""
        ops = [
            (TXDELTA_NEW, 0, 5),
            (TXDELTA_SOURCE, 0, 3),
        ]
        new_data = b"hello"
        window = (0, 3, 8, len(ops), ops, new_data)
        packed = pack_svndiff0_window(window)
        # Pack into full svndiff and unpack
        full = SVNDIFF0_HEADER + bytes(packed)
        result = list(unpack_svndiff0(full))
        self.assertEqual(1, len(result))
        self.assertEqual(window, result[0])


class ConstantsTests(TestCase):
    def test_txdelta_constants(self):
        self.assertEqual(TXDELTA_SOURCE, 0)
        self.assertEqual(TXDELTA_TARGET, 1)
        self.assertEqual(TXDELTA_NEW, 2)
        self.assertEqual(TXDELTA_INVALID, 3)

    def test_max_encoded_int_len(self):
        self.assertEqual(MAX_ENCODED_INT_LEN, 10)

    def test_delta_window_size(self):
        self.assertEqual(DELTA_WINDOW_SIZE, 102400)

    def test_svndiff0_header(self):
        self.assertEqual(SVNDIFF0_HEADER, b"SVN\0")
