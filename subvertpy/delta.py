# Copyright (C) 2005-2006 Jelmer Vernooij <jelmer@samba.org>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA
"""Subversion delta operations."""

__author__ = "Jelmer Vernooij <jelmer@samba.org>"
__docformat__ = "restructuredText"

import sys
from subvertpy.six import moves,b,binary_type
if sys.version_info < (2, 5):
    import md5 as _mod_md5
    md5 = _mod_md5.new
else:
    from hashlib import (
        md5,
        )


TXDELTA_SOURCE = 0
TXDELTA_TARGET = 1
TXDELTA_NEW = 2
TXDELTA_INVALID = 3

MAX_ENCODED_INT_LEN = 10

DELTA_WINDOW_SIZE = 102400

def apply_txdelta_window(sbuf,
            (sview_offset, sview_len, tview_len, src_ops, ops, new_data)):
    """Apply a txdelta window to a buffer.

    :param sbuf: Source buffer (as bytestring)
    :param sview_offset: Offset of the source view
    :param sview_len: Length of the source view
    :param tview_len: Target view length
    :param src_ops: Operations to apply to sview
    :param ops: Ops to apply
    :param new_data: Buffer with possible new data
    :return: Target buffer
    """
    sview = sbuf[sview_offset:sview_offset+sview_len]
    tview = txdelta_apply_ops(src_ops, ops, new_data, sview)
    if len(tview) != tview_len:
        raise AssertionError("%d != %d" % (len(tview), tview_len))
    return tview


def apply_txdelta_handler_chunks(source_chunks, target_chunks):
    """Return a function that can be called repeatedly with txdelta windows.

    :param sbuf: Source buffer
    :param target_stream: Target stream
    """
    sbuf = "".join(source_chunks)
    def apply_window(window):
        if window is None:
            return # Last call
        target_chunks.append(apply_txdelta_window(sbuf, window))
    return apply_window


def apply_txdelta_handler(sbuf, target_stream):
    """Return a function that can be called repeatedly with txdelta windows.

    :param sbuf: Source buffer
    :param target_stream: Target stream
    """
    def apply_window(window):
        if window is None:
            return # Last call
        target_stream.write(apply_txdelta_window(sbuf, window))
    return apply_window


def txdelta_apply_ops(src_ops, ops, new_data, sview):
    """Apply txdelta operations to a source view.

    :param src_ops: Source operations, ignored.
    :param ops: List of operations (action, offset, length).
    :param new_data: Buffer to fetch fragments with new data from
    :param sview: Source data
    :return: Result data
    """
    tview = ""
    for (action, offset, length) in ops:
        if action == TXDELTA_SOURCE:
            # Copy from source area.
            tview += sview[offset:offset+length]
        elif action == TXDELTA_TARGET:
            for i in moves.xrange(length):
                tview += tview[offset+i]
        elif action == TXDELTA_NEW:
            tview += new_data[offset:offset+length]
        else:
            raise Exception("Invalid delta instruction code")
    return tview


def send_stream(stream, handler, block_size=DELTA_WINDOW_SIZE):
    """Send txdelta windows that create stream to handler

    :param stream: file-like object to read the file from
    :param handler: txdelta window handler function
    :return: MD5 hash over the stream
    """
    hash = md5()
    text = stream.read(block_size)
    if not isinstance(text,binary_type):
        raise Exception("The stream should read out bytes")
    while text != b(""):
        hash.update(text)
        window = (0, 0, len(text), 0, [(TXDELTA_NEW, 0, len(text))], text)
        handler(window)
        text = stream.read(block_size)
    handler(None)
    return hash.digest()


def encode_length(len):
    """Encode a length variable.

    :param len: Length to encode
    :return: String with encoded length
    """
    # Based on encode_int() in subversion/libsvn_delta/svndiff.c
    assert len >= 0
    assert isinstance(len, int), "expected int, got %r" % (len,)

    # Count number of required bytes
    v = len >> 7
    n = 1;
    while v > 0:
        v = v >> 7
        n+=1

    assert n <= MAX_ENCODED_INT_LEN

    ret = ""
    while n > 0:
        n-=1
        if n > 0:
            cont = 1
        else:
            cont = 0
        ret += chr(((len >> (n * 7)) & 0x7f) | (cont << 7))

    return ret


def decode_length(text):
    """Decode a length variable.

    :param text: Bytestring to decode
    :return: Integer with actual length
    """
    # Decode bytes until we're done.  */
    ret = 0
    next = True
    while next:
        ret = ((ret << 7) | (ord(text[0]) & 0x7f))
        next = ((ord(text[0]) >> 7) & 0x1)
        text = text[1:]
    return ret, text


def pack_svndiff_instruction((action, offset, length)):
    """Pack a SVN diff instruction

    :param action: Action
    :param offset: Offset
    :param length: Length
    :return: encoded text
    """
    if length < 0x3f:
        text = chr((action << 6) + length)
    else:
        text = chr((action << 6)) + encode_length(length)
    if action != TXDELTA_NEW:
        text += encode_length(offset)
    return text


def unpack_svndiff_instruction(text):
    """Unpack a SVN diff instruction

    :param text: Text to parse
    :return: tuple with operation, remaining text
    """
    action = (ord(text[0]) >> 6)
    length = (ord(text[0]) & 0x3f)
    text = text[1:]
    assert action in (TXDELTA_NEW, TXDELTA_SOURCE, TXDELTA_TARGET)
    if length == 0:
        length, text = decode_length(text)
    if action != TXDELTA_NEW:
        offset, text = decode_length(text)
    else:
        offset = 0
    return (action, offset, length), text


SVNDIFF0_HEADER = "SVN\0"

def pack_svndiff0_window(window):
    """Pack an individual window using svndiff0.

    :param window: Window to pack
    :return: Packed diff (as bytestring)
    """
    (sview_offset, sview_len, tview_len, src_ops, ops, new_data) = window
    ret = [encode_length(sview_offset) + \
           encode_length(sview_len) + \
           encode_length(tview_len)]

    instrdata = ""
    for op in ops:
        instrdata += pack_svndiff_instruction(op)

    ret.append(encode_length(len(instrdata)))
    ret.append(encode_length(len(new_data)))
    ret.append(instrdata)
    ret.append(new_data)
    return "".join(ret)


def pack_svndiff0(windows):
    """Pack a SVN diff file.

    :param windows: Iterator over diff windows
    :return: text
    """
    ret = SVNDIFF0_HEADER
    for window in windows:
        ret += pack_svndiff0_window(window)
    return ret


def unpack_svndiff0(text):
    """Unpack a version 0 svndiff text.
    
    :param text: Text to unpack.
    :return: yields tuples with sview_offset, sview_len, tview_len, ops_len, 
        ops, newdata
    """
    assert text.startswith(SVNDIFF0_HEADER)
    text = text[4:]

    while text != "":
        sview_offset, text = decode_length(text)
        sview_len, text = decode_length(text)
        tview_len, text = decode_length(text)
        instr_len, text = decode_length(text)
        newdata_len, text = decode_length(text)

        instrdata = text[:instr_len]
        text = text[instr_len:]

        ops = []
        while instrdata != "":
            op, instrdata = unpack_svndiff_instruction(instrdata)
            ops.append(op)

        newdata = text[:newdata_len]
        text = text[newdata_len:]
        yield (sview_offset, sview_len, tview_len, len(ops), ops, newdata)

