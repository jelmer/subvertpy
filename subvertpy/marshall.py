# Copyright (C) 2006-2007 Jelmer Vernooij <jelmer@samba.org>
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

from subvertpy import six

class literal:
    """A protocol literal."""

    def __init__(self, txt):
        self.txt = txt

    def __str__(self):
        return self.txt

    def __repr__(self):
        return self.txt

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


def marshall(x):
    """Marshall a Python data item.
    
    :param x: Data item
    :return: encoded string
    """
    if isinstance(x, six.integer_types):
        return "%d " % x
    elif type(x) is list or type(x) is tuple:
        return "( " + "".join(map(marshall, x)) + ") "
    elif isinstance(x, literal):
        return "%s " % x
    elif isinstance(x, six.string_types):
        if six.PY3:
            if isinstance(x, six.binary_type):
                x = x.decode()
        else: #Python 2
            if isinstance(x, six.text_type):
                x = x.encode("utf-8")
        return "%d:%s " % (len(x), x)
    elif type(x) is bool:
        if x == True:
            return "true "
        elif x == False:
            return "false "
    raise MarshallError("Unable to marshall type %s" % x)


def unmarshall(x):
    """Unmarshall the next item from a text.

    :param x: Text to parse
    :return: tuple with unpacked item and remaining text
    """
    whitespace = ['\n', ' ']
    if len(x) == 0:
        raise NeedMoreData("Not enough data")
    if x[0] == "(": # list follows
        if len(x) <= 1:
            raise NeedMoreData("Missing whitespace")
        if x[1] != " ": 
            raise MarshallError("missing whitespace after list start")
        x = x[2:]
        ret = []
        try:
            while x[0] != ")":
                (x, n) = unmarshall(x)
                ret.append(n)
        except IndexError:
            raise NeedMoreData("List not terminated")

        if len(x) <= 1:
            raise NeedMoreData("Missing whitespace")
        
        if not x[1] in whitespace:
            raise MarshallError("Expected space, got %c" % x[1])

        return (x[2:], ret)
    elif x[0].isdigit():
        num = ""
        # Check if this is a string or a number
        while x[0].isdigit():
            num += x[0]
            x = x[1:]
        num = int(num)

        if x[0] in whitespace:
            return (x[1:], num)
        elif x[0] == ":":
            if len(x) < num:
                raise NeedMoreData("Expected string of length %r" % num)
            return (x[num+2:], x[1:num+1])
        else:
            raise MarshallError("Expected whitespace or ':', got '%c" % x[0])
    elif x[0].isalpha():
        ret = ""
        # Parse literal
        try:
            while x[0].isalpha() or x[0].isdigit() or x[0] == '-':
                ret += x[0]
                x = x[1:]
        except IndexError:
            raise NeedMoreData("Expected literal")

        if not x[0] in whitespace:
            raise MarshallError("Expected whitespace, got %c" % x[0])

        return (x[1:], ret)
    else:
        raise MarshallError("Unexpected character '%c'" % x[0])

