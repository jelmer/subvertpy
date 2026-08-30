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

"""Marshalling for the svn_ra protocol."""

from subvertpy._typing import MarshallValue, UnmarshalledValue


class literal:
    """A protocol literal."""

    def __init__(self, txt: str) -> None:
        self.txt = txt

    def __str__(self) -> str:
        return self.txt

    def __repr__(self) -> str:
        return self.txt

    def __eq__(self, other: object) -> bool:
        return isinstance(self, type(other)) and self.txt == other.txt  # type: ignore[attr-defined]


# 1. Syntactic structure
# ----------------------
#
# The Subversion protocol is specified in terms of the following
# syntactic elements, specified using ABNF [RFC 2234]:
#
#   item   = word / number / string / list
#   word   = ALPHA *(ALPHA / DIGIT / "-") space
#   number = 1*DIGIT space
#   string = 1*DIGIT ":" *OCTET space
#          ; digits give the byte count of the *OCTET portion
#   list   = "(" space *item ")" space
#   space  = 1*(SP / LF)
#


class MarshallError(Exception):
    """A Marshall error."""


class NeedMoreData(MarshallError):
    """More data needed."""


def marshall(x: MarshallValue) -> bytes:
    """Marshall a Python data item.

    :param x: Data item
    :return: encoded byte string
    """
    if isinstance(x, bool):
        return b"true " if x else b"false "
    elif isinstance(x, int):
        return f"{x} ".encode("ascii")
    elif isinstance(x, (list, tuple)):
        return b"( " + b"".join(map(marshall, x)) + b") "
    elif isinstance(x, literal):
        return (f"{x} ").encode("ascii")
    elif isinstance(x, (bytes, bytearray)):
        return f"{len(x)}:".encode("ascii") + bytes(x) + b" "
    elif isinstance(x, str):
        x_enc = x.encode("utf-8")
        return f"{len(x_enc)}:".encode("ascii") + x_enc + b" "
    raise MarshallError(f"Unable to marshall type {x}")


def unmarshall(x: bytes) -> tuple[bytes, UnmarshalledValue]:
    """Unmarshall the next item from a buffer.

    :param x: Bytes to parse
    :return: tuple with unpacked item and remaining bytes
    """
    whitespace = frozenset(b"\n ")
    if len(x) == 0:
        raise NeedMoreData("Not enough data")
    if x[0:1] == b"(":  # list follows
        if len(x) <= 1:
            raise NeedMoreData("Missing whitespace")
        if x[1:2] != b" ":
            raise MarshallError("missing whitespace after list start")
        x = x[2:]
        ret: list[UnmarshalledValue] = []
        try:
            while x[0:1] != b")":
                (x, n) = unmarshall(x)
                ret.append(n)
        except IndexError:
            raise NeedMoreData("List not terminated")

        if len(x) <= 1:
            raise NeedMoreData("Missing whitespace")

        if x[1] not in whitespace:
            raise MarshallError(f"Expected space, got '{chr(x[1])}'")

        return (x[2:], ret)
    elif x[0:1].isdigit():
        num_buf = bytearray()
        # Check if this is a string or a number
        while x[:1].isdigit():
            num_buf.append(x[0])
            x = x[1:]
        num = int(num_buf)

        if x[0] in whitespace:
            return (x[1:], num)
        elif x[0:1] == b":":
            if len(x) < num:
                raise NeedMoreData(f"Expected string of length {num!r}")
            return (x[num + 2 :], x[1 : num + 1])
        elif not x:
            raise MarshallError("Expected whitespace, got end of string.")
        else:
            raise MarshallError(f"Expected whitespace or ':', got '{chr(x[0])}'")
    elif x[:1].isalpha():
        lit_buf = bytearray()
        # Parse literal
        try:
            while x[:1].isalpha() or x[:1].isdigit() or x[0:1] == b"-":
                lit_buf.append(x[0])
                x = x[1:]
        except IndexError:
            raise NeedMoreData("Expected literal")

        if not x:
            raise MarshallError("Expected whitespace, got end of string.")

        if x[0] not in whitespace:
            raise MarshallError(f"Expected whitespace, got '{chr(x[0])}'")

        return (x[1:], literal(lit_buf.decode("ascii")))
    else:
        raise MarshallError(f"Unexpected character '{chr(x[0])}'")
