# Copyright (C) 2005-2006 Jelmer Vernooij <jelmer@samba.org>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""Subversion delta operations."""

import md5

TXDELTA_SOURCE = 0
TXDELTA_TARGET = 1
TXDELTA_NEW = 2
TXDELTA_INVALID = 3

def apply_txdelta_handler(sbuf, target_stream):
    def apply_window(window):
        if window is None:
            return # Last call
        (sview_offset, sview_len, tview_len, src_ops, ops, new_data) = window
        sview = sbuf[sview_offset:sview_offset+sview_len]
        tview = txdelta_apply_ops(src_ops, ops, new_data, sview)
        assert len(tview) == tview_len
        target_stream.write(tview)
    return apply_window


def txdelta_apply_ops(src_ops, ops, new_data, sview):
    tview = ""
    for (action, offset, length) in ops:
        if action == TXDELTA_SOURCE:
            # Copy from source area.
            tview += sview[offset:offset+length]
        elif action == TXDELTA_TARGET:
            for i in xrange(length):
                tview += tview[offset+i]
        elif action == TXDELTA_NEW:
            tview += new_data[offset:offset+length]
        else:
            raise Exception("Invalid delta instruction code")

    return tview


SEND_STREAM_BLOCK_SIZE = 1024 * 1024 # 1 Mb


def send_stream(stream, handler, block_size=SEND_STREAM_BLOCK_SIZE):
    hash = md5.new()
    text = stream.read(block_size)
    while text != "":
        hash.update(text)
        window = (0, 0, len(text), 0, [(TXDELTA_NEW, 0, len(text))], text)
        handler(window)
        text = stream.read(block_size)
    handler(None)
    return hash.digest()


def encode_length(len):
    # Based on encode_int() in subversion/libsvn_delta/svndiff.c
    assert len >= 0
    assert isinstance(len, int), "expected int, got %r" % (len,)

    # Count number of required bytes
    v = len >> 7
    n = 1;
    while v > 0:
        v = v >> 7
        n+=1

    ret = ""
    # Encode the remaining bytes; n is always the number of bytes
    # coming after the one we're encoding.  */
    while n > 0:
        n-=1
        if n > 0:
            cont = 1
        else:
            cont = 0
        ret += chr(((len >> (n * 7)) & 0x7f) | (cont << 7))

    return ret


def decode_length(text):
    # Decode bytes until we're done.  */
    ret = 0
    next = True
    while next:
        ret = ((ret << 7) | (ord(text[0]) & 0x7f))
        next = ((ord(text[0]) >> 7) & 0x1)
        text = text[1:]
    return ret, text


def pack_svndiff_instruction((action, offset, length)):
    if length < 0x3f:
        text = chr((action << 6) + length)
    else:
        text = chr((action << 6)) + encode_length(length)
    if action != TXDELTA_NEW:
        text += encode_length(offset)
    return text


def unpack_svndiff_instruction(text):
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
    (sview_offset, sview_len, tview_len, src_ops, ops, new_data) = window
    ret = encode_length(sview_offset) + \
          encode_length(sview_len) + \
          encode_length(tview_len)

    instrdata = ""
    for op in ops:
        instrdata += pack_svndiff_instruction(op)

    ret += encode_length(len(instrdata))
    ret += encode_length(len(new_data))
    ret += instrdata
    ret += new_data
    return ret

def pack_svndiff0(windows):
    ret = SVNDIFF0_HEADER

    for window in windows:
        ret += pack_svndiff0_window(window)

    return ret


def unpack_svndiff0(text):
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

