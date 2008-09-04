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

from bzrlib.tests import multiply_tests_from_modules
from bzrlib.plugins.svn.mapping import mapping_registry

def load_tests(basic_tests, module, loader):
    result = loader.suiteClass()
    prefix = "bzrlib.plugins.svn.tests.mapping_implementations"
    modules = ['test_base', 'test_repository']
    module_name_list = ["%s.%s" % (prefix, m) for m in modules]
    format_scenarios = []
    for name in mapping_registry.keys():
        format_scenarios.append((name, {'mapping_name': name}))
    result.addTests(multiply_tests_from_modules(module_name_list,
                                                format_scenarios,
                                                loader))
    return result
