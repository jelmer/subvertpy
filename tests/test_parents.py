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

from bzrlib import graph as _mod_graph
from bzrlib.tests import TestCaseWithMemoryTransport
from bzrlib.tests.test_graph import InstrumentedParentsProvider

from bzrlib.plugins.svn.parents import ParentsCache, DiskCachingParentsProvider

class ParentsCacheTests(TestCaseWithMemoryTransport):

    def setUp(self):
        super(ParentsCacheTests, self).setUp()
        self.cache = ParentsCache(self.get_transport())
    
    def test_noparents(self):
        self.cache.insert_parents("myrevid", ())
        self.assertEquals((), self.cache.lookup_parents("myrevid"))

    def test_single(self):
        self.cache.insert_parents("myrevid", ("single",))
        self.assertEquals(("single",), self.cache.lookup_parents("myrevid"))

    def test_multiple(self):
        self.cache.insert_parents("myrevid", ("one", "two"))
        self.assertEquals(("one", "two"), self.cache.lookup_parents("myrevid"))

    def test_nonexistant(self):
        self.assertEquals(None, self.cache.lookup_parents("myrevid"))

    def test_insert_twice(self):
        self.cache.insert_parents("myrevid", ("single",))
        self.cache.insert_parents("myrevid", ("second",))
        self.assertEquals(("second",), self.cache.lookup_parents("myrevid"))
        

class TestCachingParentsProvider(TestCaseWithMemoryTransport):

    def setUp(self):
        super(TestCachingParentsProvider, self).setUp()
        dict_pp = _mod_graph.DictParentsProvider({'a':('b',)})
        self.inst_pp = InstrumentedParentsProvider(dict_pp)
        self.caching_pp = DiskCachingParentsProvider(self.inst_pp, self.get_transport())

    def test_get_parent_map(self):
        """Requesting the same revision should be returned from cache"""
        self.assertEqual({'a':('b',)}, self.caching_pp.get_parent_map(['a']))
        self.assertEqual(['a'], self.inst_pp.calls)
        self.assertEqual({'a':('b',)}, self.caching_pp.get_parent_map(['a']))
        # No new call, as it should have been returned from the cache
        self.assertEqual(['a'], self.inst_pp.calls)

    def test_get_parent_map_not_present(self):
        """The cache should also track when a revision doesn't exist"""
        self.assertEqual({}, self.caching_pp.get_parent_map(['b']))
        self.assertEqual(['b'], self.inst_pp.calls)
        self.assertEqual({}, self.caching_pp.get_parent_map(['b']))
        # No new calls
        self.assertEqual(['b', 'b'], self.inst_pp.calls)

    def test_get_parent_map_mixed(self):
        """Anything that can be returned from cache, should be"""
        self.assertEqual({}, self.caching_pp.get_parent_map(['b']))
        self.assertEqual(['b'], self.inst_pp.calls)
        self.assertEqual({'a':('b',)},
                         self.caching_pp.get_parent_map(['a', 'b']))
        self.assertEqual(['b', 'a', 'b'], self.inst_pp.calls)

    def test_get_parent_map_repeated(self):
        """Asking for the same parent 2x will only forward 1 request."""
        self.assertEqual({'a':('b',)},
                         self.caching_pp.get_parent_map(['b', 'a', 'b']))
        # Use sorted because we don't care about the order, just that each is
        # only present 1 time.
        self.assertEqual(['a', 'b'], sorted(self.inst_pp.calls))


