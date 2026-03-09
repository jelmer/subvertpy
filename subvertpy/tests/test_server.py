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

"""Subversion server tests."""

import re

from subvertpy.server import (
    ServerBackend,
    ServerRepositoryBackend,
    generate_random_id,
    )
from subvertpy.tests import TestCase


class GenerateRandomIdTests(TestCase):

    def test_returns_string(self):
        result = generate_random_id()
        self.assertIsInstance(result, str)

    def test_is_uuid_format(self):
        result = generate_random_id()
        uuid_re = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-'
            r'[0-9a-f]{4}-[0-9a-f]{12}$')
        self.assertRegex(result, uuid_re)

    def test_unique(self):
        id1 = generate_random_id()
        id2 = generate_random_id()
        self.assertNotEqual(id1, id2)


class ServerBackendTests(TestCase):

    def test_open_repository_raises(self):
        backend = ServerBackend()
        self.assertRaises(NotImplementedError,
                          backend.open_repository, "/test")


class ServerRepositoryBackendTests(TestCase):

    def setUp(self):
        super(ServerRepositoryBackendTests, self).setUp()
        self.backend = ServerRepositoryBackend()

    def test_get_uuid_raises(self):
        self.assertRaises(NotImplementedError, self.backend.get_uuid)

    def test_get_latest_revnum_raises(self):
        self.assertRaises(NotImplementedError,
                          self.backend.get_latest_revnum)

    def test_log_raises(self):
        self.assertRaises(NotImplementedError,
                          self.backend.log, None, "/", 0, 1, True, True, 0)

    def test_update_raises(self):
        self.assertRaises(NotImplementedError,
                          self.backend.update, None, 1, "/", True)

    def test_check_path_raises(self):
        self.assertRaises(NotImplementedError,
                          self.backend.check_path, "/", 0)

    def test_stat_raises(self):
        self.assertRaises(NotImplementedError,
                          self.backend.stat, "/", 0)

    def test_rev_proplist_raises(self):
        self.assertRaises(NotImplementedError,
                          self.backend.rev_proplist, 0)

    def test_get_locations_raises(self):
        self.assertRaises(NotImplementedError,
                          self.backend.get_locations, "/", 0, [0])
