# Copyright (C) 2005-2007 Jelmer Vernooij <jelmer@samba.org>
 
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

"""Subversion client library tests."""

import os

from subvertpy import (
    NODE_DIR, NODE_FILE,
    client,
    ra,
    wc,
    )
from subvertpy.tests import (
    SubversionTestCase,
    )

class TestClient(SubversionTestCase):

    def setUp(self):

        super(TestClient, self).setUp()
        self.repos_url = self.make_client("d", "dc")
        self.client = client.Client(auth=ra.Auth([ra.get_username_provider()]))

    def test_add(self):
        self.build_tree({"dc/foo": None})
        self.client.add("dc/foo")

    def test_add_recursive(self):
        self.build_tree({"dc/trunk/foo": 'bla', "dc/trunk": None})
        self.client.add("dc/trunk")
        adm = wc.WorkingCopy(None, os.path.join(os.getcwd(), "dc"))
        e = adm.entry(os.path.join(os.getcwd(), "dc", "trunk"))
        self.assertEquals(e.kind, NODE_DIR)
        adm2 = wc.WorkingCopy(None, os.path.join(os.getcwd(), "dc", "trunk"))
        e = adm2.entry(os.path.join(os.getcwd(), "dc", "trunk", "foo"))
        self.assertEquals(e.kind, NODE_FILE)

    def test_get_config(self):
        self.assertIsInstance(client.get_config().__dict__, dict)

    def test_diff(self):
        r = ra.RemoteAccess(self.repos_url,
                auth=ra.Auth([ra.get_username_provider()]))
        dc = self.get_commit_editor(self.repos_url) 
        f = dc.add_file("foo")
        f.modify("foo1")
        dc.close()

        dc = self.get_commit_editor(self.repos_url) 
        f = dc.open_file("foo")
        f.modify("foo2")
        dc.close()

        if wc.api_version() < (1, 5):
            self.assertRaises(NotImplementedError, self.client.diff, 1, 2,
                self.repos_url, self.repos_url)
            return # Skip test

        (outf, errf) = self.client.diff(1, 2, self.repos_url, self.repos_url)
        outf.seek(0)
        errf.seek(0)
        self.assertEquals("""Index: foo
===================================================================
--- foo\t(revision 1)
+++ foo\t(revision 2)
@@ -1 +1 @@
-foo1
\\ No newline at end of file
+foo2
\\ No newline at end of file
""", outf.read())
        self.assertEquals("", errf.read())

