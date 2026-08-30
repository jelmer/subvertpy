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

"""Handling of Subversion properties."""

__author__ = "Jelmer Vernooij <jelmer@jelmer.uk>"
__docformat__ = "restructuredText"


import bisect
import calendar
import time

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse


class InvalidExternalsDescription(Exception):
    _fmt = """Unable to parse externals description."""


class InvalidMergeinfoProperty(Exception):
    _fmt = """Unable to parse mergeinfo property."""


def is_valid_property_name(prop: str) -> bool:
    """Check the validity of a property name.

    :param prop: Property name
    :return: Whether prop is a valid property name
    """
    if not prop[0].isalnum() and prop[0] not in ":_":
        return False
    for c in prop[1:]:
        if not c.isalnum() and c not in "-:._":
            return False
    return True


def time_to_cstring(timestamp: int) -> str:
    """Determine string representation of a time.

    :param timestamp: Number of microseconds since the start of 1970
    :return: string with date
    """
    tm_usec = timestamp % 1000000
    (
        tm_year,
        tm_mon,
        tm_mday,
        tm_hour,
        tm_min,
        tm_sec,
        _tm_wday,
        _tm_yday,
        _tm_isdst,
    ) = time.gmtime(timestamp / 1000000)
    return f"{tm_year:04d}-{tm_mon:02d}-{tm_mday:02d}T{tm_hour:02d}:{tm_min:02d}:{tm_sec:02d}.{tm_usec:06d}Z"


def time_from_cstring(text: str) -> int:
    """Parse a time from a cstring.

    :param text: Parse text
    :return: number of microseconds since the start of 1970
    """
    (basestr, usecstr) = text.split(".", 1)
    assert usecstr[-1] == "Z"
    tm_usec = int(usecstr[:-1])
    tm = time.strptime(basestr, "%Y-%m-%dT%H:%M:%S")
    return int(calendar.timegm(tm)) * 1000000 + tm_usec


def parse_externals_description(
    base_url: str, val: str
) -> dict[str, tuple[int | None, str]]:
    """Parse an svn:externals property value.

    :param base_url: URL on which the property is set. Used for
        relative externals.

    :returns: dictionary with local names as keys, (revnum, url)
              as value. revnum is the revision number and is
              set to None if not applicable.
    """

    def is_url(u: str) -> bool:
        return "://" in u

    ret: dict[str, tuple[int | None, str]] = {}
    for line in val.splitlines():
        if line == "" or line[0] == "#":
            continue
        pts = line.rsplit(None, 3)
        if len(pts) == 4:
            if pts[0] == "-r":  # -r X URL DIR
                revno = int(pts[1])
                path = pts[3]
                relurl = pts[2]
            elif pts[1] == "-r":  # DIR -r X URL
                revno = int(pts[2])
                path = pts[0]
                relurl = pts[3]
            else:
                raise InvalidExternalsDescription
        elif len(pts) == 3:
            if pts[1].startswith("-r"):  # DIR -rX URL
                revno = int(pts[1][2:])
                path = pts[0]
                relurl = pts[2]
            elif pts[0].startswith("-r"):  # -rX URL DIR
                revno = int(pts[0][2:])
                path = pts[2]
                relurl = pts[1]
            else:
                raise InvalidExternalsDescription
        elif len(pts) == 2:
            if not is_url(pts[0]):
                relurl = pts[1]
                path = pts[0]
            else:
                relurl = pts[0]
                path = pts[1]
            revno = None
        else:
            raise InvalidExternalsDescription
        if relurl.startswith("//"):
            raise NotImplementedError(
                "Relative to the scheme externals not yet supported"
            )
        if relurl.startswith("^/"):
            raise NotImplementedError(
                "Relative to the repository root externals not yet supported"
            )
        ret[path] = (revno, urlparse.urljoin(base_url + "/", relurl))
    return ret


def canonicalize_mergeinfo_path(path: str) -> str:
    """Canonicalize a merge source path.

    Merge source paths are absolute from the repository root, but relative
    paths are tolerated in the property text and converted to absolute ones.
    This mirrors svn_fspath__canonicalize().

    :param path: Merge source path
    :return: Canonical path, starting with a slash
    """
    segments = [s for s in path.split("/") if s not in ("", ".")]
    return "/" + "/".join(segments)


def parse_mergeinfo_property(
    text: str,
) -> dict[str, list[tuple[int, int, bool]]]:
    """Parse a mergeinfo property.

    Relative merge source paths are converted to absolute paths. A path that
    occurs both with and without a leading slash ends up under a single key,
    with the ranges combined.

    :param text: Property contents
    :return: Dictionary mapping paths to lists of ranges
    :raise InvalidMergeinfoProperty: If the property can not be parsed
    """
    ret: dict[str, list[tuple[int, int, bool]]] = {}
    for line in text.splitlines():
        try:
            (path, ranges) = line.rsplit(":", 1)
        except ValueError:
            raise InvalidMergeinfoProperty(f"missing ':' in line {line!r}") from None
        path = canonicalize_mergeinfo_path(path)
        parsed = ret.setdefault(path, [])
        for range in ranges.split(","):
            if range.endswith("*"):
                inheritable = False
                range = range[:-1]
            else:
                inheritable = True
            (start, sep, end) = range.partition("-")
            if not sep:
                end = start
            if not start.isdigit() or not end.isdigit():
                raise InvalidMergeinfoProperty(
                    f"invalid revision range {range!r} for {path!r}"
                )
            parsed.append((int(start), int(end), inheritable))

    return ret


def generate_mergeinfo_property(
    merges: dict[str, list[tuple[int, int, bool]]],
) -> str:
    """Generate the contents of the svn:mergeinfo property.

    :param merges: dictionary mapping paths to lists of ranges; relative
        paths are written out as absolute ones
    :return: Property contents
    """

    def formatrange(range_params: tuple[int, int, bool]) -> str:
        (start, end, inheritable) = range_params
        suffix = ""
        if not inheritable:
            suffix = "*"
        if start == end:
            return f"{start}{suffix}"
        else:
            return f"{start}-{end}{suffix}"

    text = ""
    for path, ranges in merges.items():
        path = canonicalize_mergeinfo_path(path)
        text += "{}:{}\n".format(path, ",".join(map(formatrange, ranges)))
    return text


def range_includes_revnum(ranges: list[tuple[int, int, bool]], revnum: int) -> bool:
    """Check if the specified range contains the mentioned revision number.

    :param ranges: list of ranges
    :param revnum: revision number
    :return: Whether or not the revision number is included
    """
    i = bisect.bisect(ranges, (revnum, revnum, True))
    if i == 0:
        return False
    (start, end, _inheritable) = ranges[i - 1]
    return start <= revnum <= end


def range_add_revnum(
    ranges: list[tuple[int, int, bool]],
    revnum: int,
    inheritable: bool = True,
) -> list[tuple[int, int, bool]]:
    """Add revision number to a list of ranges.

    :param ranges: List of ranges
    :param revnum: Revision number to add
    :param inheritable: TODO
    :return: New list of ranges
    """
    # TODO: Deal with inheritable
    item = (revnum, revnum, inheritable)
    if len(ranges) == 0:
        ranges.append(item)
        return ranges
    i = bisect.bisect(ranges, item)
    if i > 0:
        (start, end, inh) = ranges[i - 1]
        if start <= revnum <= end:
            # already there
            return ranges
        if end == revnum - 1:
            # Extend previous range
            ranges[i - 1] = (start, end + 1, inh)
            return ranges
    if i < len(ranges):
        (start, end, inh) = ranges[i]
        if start - 1 == revnum:
            # Extend next range
            ranges[i] = (start - 1, end, inh)
            return ranges
    ranges.insert(i, item)
    return ranges


def mergeinfo_includes_revision(
    merges: dict[str, list[tuple[int, int, bool]]], path: str, revnum: int
) -> bool:
    """Check if the specified mergeinfo contains a path in revnum.

    :param merges: Dictionary with merges, keyed by absolute path
    :param path: Merged path; relative paths are treated as absolute
    :param revnum: Revision number
    :return: Whether the revision is included
    """
    try:
        ranges = merges[canonicalize_mergeinfo_path(path)]
    except KeyError:
        return False

    return range_includes_revnum(ranges, revnum)


def mergeinfo_add_revision(
    mergeinfo: dict[str, list[tuple[int, int, bool]]], path: str, revnum: int
) -> dict[str, list[tuple[int, int, bool]]]:
    """Add a revision to a mergeinfo dictionary.

    :param mergeinfo: Merginfo dictionary, keyed by absolute path
    :param path: Merged path to add; relative paths are treated as absolute
    :param revnum: Merged revision to add
    :return: Updated dictionary
    """
    path = canonicalize_mergeinfo_path(path)
    mergeinfo[path] = range_add_revnum(mergeinfo.get(path, []), revnum)
    return mergeinfo


PROP_EXECUTABLE = "svn:executable"
PROP_EXECUTABLE_VALUE = b"*"
PROP_EXTERNALS = "svn:externals"
PROP_IGNORE = "svn:ignore"
PROP_KEYWORDS = "svn:keywords"
PROP_MIME_TYPE = "svn:mime-type"
PROP_MERGEINFO = "svn:mergeinfo"
PROP_NEEDS_LOCK = "svn:needs-lock"
PROP_NEEDS_LOCK_VALUE = b"*"
PROP_PREFIX = "svn:"
PROP_SPECIAL = "svn:special"
PROP_SPECIAL_VALUE = b"*"
PROP_WC_PREFIX = "svn:wc:"
PROP_ENTRY_PREFIX = "svn:entry"
PROP_ENTRY_COMMITTED_DATE = "svn:entry:committed-date"
PROP_ENTRY_COMMITTED_REV = "svn:entry:committed-rev"
PROP_ENTRY_LAST_AUTHOR = "svn:entry:last-author"
PROP_ENTRY_LOCK_TOKEN = "svn:entry:lock-token"
PROP_ENTRY_UUID = "svn:entry:uuid"

PROP_REVISION_LOG = "svn:log"
PROP_REVISION_AUTHOR = "svn:author"
PROP_REVISION_DATE = "svn:date"
PROP_REVISION_ORIGINAL_DATE = "svn:original-date"


def diff(
    current: dict[str, bytes], previous: dict[str, bytes]
) -> dict[str, tuple[bytes | None, bytes]]:
    """Find the differences between two property dictionaries.

    :param current: Dictionary with current (new) properties
    :param previous: Dictionary with previous (old) properties
    :return: Dictionary that contains an entry for
             each property that was changed. Value is a tuple
             with the old and the new property value.
    """
    ret: dict[str, tuple[bytes | None, bytes]] = {}
    for key, newval in current.items():
        oldval = previous.get(key)
        if oldval != newval:
            ret[key] = (oldval, newval)
    return ret
