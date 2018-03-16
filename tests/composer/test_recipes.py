#
# Copyright (C) 2018  Red Hat, Inc.
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import unittest

from composer.cli.recipes import prettyDiffEntry

diff_entries = [{'new': {'Description': 'Shiny new description'}, 'old': {'Description': 'Old reliable description'}},
                {'new': {'Version': '0.3.1'}, 'old': {'Version': '0.1.1'}},
                {'new': {'Module': {'name': 'openssh', 'version': '2.8.1'}}, 'old': None},
                {'new': None, 'old': {'Module': {'name': 'bash', 'version': '4.*'}}},
                {'new': {'Module': {'name': 'httpd', 'version': '3.8.*'}},
                 'old': {'Module': {'name': 'httpd', 'version': '3.7.*'}}},
                {'new': {'Package': {'name': 'git', 'version': '2.13.*'}}, 'old': None}]

diff_result = [
    'Changed Description "Old reliable description" -> "Shiny new description"',
    'Changed Version 0.1.1 -> 0.3.1',
    'Added Module openssh 2.8.1',
    'Removed Module bash 4.*',
    'Changed Module httpd 3.7.* -> 3.8.*',
    'Added Package git 2.13.*']

class RecipesTest(unittest.TestCase):
    def test_prettyDiffEntry(self):
        """Return a nice representation of a diff entry"""
        self.assertEqual([prettyDiffEntry(entry) for entry in diff_entries], diff_result)
