# Copyright (C) 2005-2007 Jelmer Vernooij <jelmer@samba.org>
 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from bzrlib import osutils, urlutils
from bzrlib.trace import warning
from bzrlib.versionedfile import FulltextContentFactory, VersionedFiles, VirtualVersionedFiles

from bzrlib.plugins.svn.subvertpy import SubversionException
from bzrlib.plugins.svn.errors import ERR_FS_NOT_FILE
from bzrlib.plugins.svn.foreign.versionedfiles import VirtualSignatureTexts, VirtualRevisionTexts, VirtualInventoryTexts

from cStringIO import StringIO

_warned_experimental = False

class SvnTexts(VersionedFiles):
    """Subversion texts backend."""

    def __init__(self, repository):
        self.repository = repository

    def check(self, progressbar=None):
        return True

    def add_mpdiffs(self, records):
        raise NotImplementedError(self.add_mpdiffs)

    def get_record_stream(self, keys, ordering, include_delta_closure):
        global _warned_experimental
        if not _warned_experimental:
            warning("stacking support in bzr-svn is experimental.")
            _warned_experimental = True
        # TODO: there may be valid text revisions that only exist as 
        # ghosts in the repository itself. This function will 
        # not be able to report them.
        # TODO: Sort keys by file id and issue just one get_file_revs() call 
        # per file-id ?
        for (fileid, revid) in list(keys):
            revmeta = self.repository._get_revmeta(revid)
            map = self.repository.get_fileid_map(revmeta, mapping)
            # Unfortunately, the map is the other way around
            lines = None
            for k, (v, ck) in map.items():
                if v == fileid:
                    try:
                        stream = StringIO()
                        self.repository.transport.get_file(urlutils.join(revmeta.branch_path, k), stream, revmeta.revnum)
                        stream.seek(0)
                        lines = stream.readlines()
                    except SubversionException, (_, num):
                        if num == ERR_FS_NOT_FILE:
                            lines = []
                        else:
                            raise
                    break
            if lines is None:
                raise Exception("Inconsistent key specified: (%r,%r)" % (fileid, revid))
            yield FulltextContentFactory((fileid, revid), None, 
                        sha1=osutils.sha_strings(lines),
                        text=''.join(lines))

    def _get_parent(self, fileid, revid):
        revmeta, mapping = self.repository._get_revmeta(revid)
        fileidmap = self.repository.get_fileid_map(revmeta, mapping)
        path = None
        for k, (v_fileid, v_revid) in fileidmap.items():
            if v_fileid == fileid:
                path = k
        if path is None:
            return

        text_parents = mapping.import_text_parents(revmeta.get_revprops(), revmeta.get_changed_fileprops())
        if path in text_parents:
            return text_parents[path]

        # Not explicitly record - so find the last place where this file was modified
        # and report that.

        return 

    def get_parent_map(self, keys):
        invs = {}

        # First, figure out the revision number/path
        ret = {}
        for (fileid, revid) in keys:
            ret[(fileid, revid)] = self._get_parent(fileid, revid)
        return ret

    # TODO: annotate, get_sha1s, iter_lines_added_or_present_in_keys, keys



