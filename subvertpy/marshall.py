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

class literal:
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
    if isinstance(x, int):
        return "%d " % x
    elif isinstance(x, list) or isinstance(x, tuple):
        return "( " + "".join(map(marshall, x)) + ") "
    elif isinstance(x, literal):
        return "%s " % x
    elif isinstance(x, str):
        return "%d:%s " % (len(x), x)
    elif isinstance(x, unicode):
        return "%d:%s " % (len(x), x.encode("utf-8"))
    raise MarshallError("Unable to marshall type %s" % x)


def unmarshall(x):
    whitespace = ['\n', ' ']
    if len(x) == 0:
        raise NeedMoreData("Not enough data")
    if x[0] == "(" and x[1] == " ": # list follows
        x = x[2:]
        ret = []
        try:
            while x[0] != ")":
                (x, n) = unmarshall(x)
                ret.append(n)
        except IndexError:
            raise NeedMoreData("List not terminated")
        
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
            raise MarshallError("Expected literal")

        if not x[0] in whitespace:
            raise MarshallError("Expected whitespace, got %c" % x[0])

        return (x[1:], ret)
    else:
        raise MarshallError("Unexpected character '%c'" % x[0])
