# Copyright (C) 2017 Jelmer Vernooij <jelmer@jelmer.uk>

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

"""Subversion subr library tests."""

import os
from unittest import TestCase

from subvertpy.subr import (
    uri_canonicalize,
    dirent_canonicalize,
    abspath,
    )


class UriCanonicalizeTests(TestCase):

    def test_canonicalize(self):
        self.assertEqual(
                'https://www.example.com',
                uri_canonicalize('https://www.example.com/'))
        self.assertEqual(
                'https://www.example.com(bla)',
                uri_canonicalize('https://www.example.com(bla)'))
        self.assertEqual(
                'https://www.example.com/(bla)',
                uri_canonicalize('https://www.example.com/(bla%29'))


class DirentCanonicalizeTests(TestCase):

    def test_canonicalize(self):
        self.assertEqual(
                '/foo/bar',
                dirent_canonicalize('/foo/bar'))
        self.assertEqual(
                '/foo/bar',
                dirent_canonicalize('/foo//bar'))


class AbspathTests(TestCase):

    def test_abspath(self):
        self.assertEqual(
                '/foo/bar',
                abspath('/foo//bar'))
        self.assertEqual(
                os.path.join(os.getcwd(), 'bar'),
                abspath('bar'))
        self.assertEqual(
                os.path.join(os.getcwd(), 'bar', 'foo'),
                abspath('bar/foo'))
