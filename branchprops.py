# Copyright (C) 2006-2007 Jelmer Vernooij <jelmer@samba.org>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""Branch property access and caching."""

from bzrlib.errors import NoSuchRevision

from bzrlib.plugins.svn import logwalker, properties
from bzrlib.plugins.svn.core import SubversionException
from bzrlib.plugins.svn.errors import ERR_FS_NO_SUCH_REVISION


class PathPropertyProvider(object):
    def __init__(self, log):
        self.log = log
        self._props_cache = {}

    def get_properties(self, path, revnum):
        """Obtain all the directory properties set on a path/revnum pair.

        :param path: Subversion path
        :param revnum: Subversion revision number
        :return: Dictionary with properties
        """
        assert isinstance(path, str)
        path = path.lstrip("/")

        if not (path, revnum) in self._props_cache:
            self._props_cache[(path, revnum)] = logwalker.lazy_dict({}, self._real_get_properties, path, revnum)
        return self._props_cache[path, revnum]

    def _real_get_properties(self, path, revnum):
        try:
            (_, _, props) = self.log._transport.get_dir(path, 
                revnum)
        except SubversionException, (_, num):
            if num == ERR_FS_NO_SUCH_REVISION:
                raise NoSuchRevision(self, revnum)
            raise

        return props
