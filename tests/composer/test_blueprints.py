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
import os
import unittest

from ..lib import captured_output

from composer.cli.blueprints import prettyDiffEntry, blueprints_list, blueprints_show, blueprints_changes
from composer.cli.blueprints import blueprints_diff, blueprints_save, blueprints_delete, blueprints_depsolve
from composer.cli.blueprints import blueprints_push, blueprints_freeze, blueprints_undo, blueprints_tag

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

class BlueprintsTest(unittest.TestCase):
    def test_prettyDiffEntry(self):
        """Return a nice representation of a diff entry"""
        self.assertEqual([prettyDiffEntry(entry) for entry in diff_entries], diff_result)

    @unittest.skipUnless(os.path.exists("/run/weldr/api.socket"), "Test requires a running API server")
    def test_list(self):
        """blueprints list"""
        with captured_output() as (out, _):
            rc = blueprints_list("/run/weldr/api.socket", 0, [], show_json=False)
        output = out.getvalue().strip()
        self.assertTrue(rc == 0)
        self.assertTrue("example-http-server" in output)

    @unittest.skipUnless(os.path.exists("/run/weldr/api.socket"), "Test requires a running API server")
    def test_show(self):
        """blueprints show"""
        with captured_output() as (out, _):
            blueprints_show("/run/weldr/api.socket", 0, ["example-http-server"], show_json=False)
        output = out.getvalue().strip()
        self.assertTrue("example-http-server" in output)
        self.assertTrue("[[packages]]" in output)
        self.assertTrue("[[modules]]" in output)

    @unittest.skipUnless(os.path.exists("/run/weldr/api.socket"), "Test requires a running API server")
    def test_changes(self):
        """blueprints changes"""
        with captured_output() as (out, _):
            rc = blueprints_changes("/run/weldr/api.socket", 0, ["example-http-server"], show_json=False)
        output = out.getvalue().strip()
        self.assertTrue(rc == 0)
        self.assertTrue("example-http-server" in output)
        self.assertTrue("Recipe example-http-server, version 0.0.1 saved." in output)

    # NOTE: Order of these 3 is important, delete needs to come after save, before push and these 3
    @unittest.skipUnless(os.path.exists("/run/weldr/api.socket"), "Test requires a running API server")
    def test_save_0(self):
        """blueprints save example-development"""
        blueprints_save("/run/weldr/api.socket", 0, ["example-development"], show_json=False)
        self.assertTrue(os.path.exists("example-http-server.toml"))

    @unittest.skipUnless(os.path.exists("/run/weldr/api.socket"), "Test requires a running API server")
    def test_save_1(self):
        """blueprints delete example-development"""
        rc = blueprints_delete("/run/weldr/api.socket", 0, ["example-development"], show_json=False)
        self.assertTrue(rc == 0)

    @unittest.skipUnless(os.path.exists("/run/weldr/api.socket"), "Test requires a running API server")
    def test_save_2(self):
        """blueprints push example-development"""
        rc = blueprints_push("/run/weldr/api.socket", 0, ["example-development.toml"], show_json=False)
        self.assertTrue(rc == 0)

    @unittest.skipUnless(os.path.exists("/run/weldr/api.socket"), "Test requires a running API server")
    def test_depsolve(self):
        """blueprints depsolve"""
        with captured_output() as (out, _):
            rc = blueprints_depsolve("/run/weldr/api.socket", 0, ["example-http-server"], show_json=False)
        output = out.getvalue().strip()
        self.assertTrue(rc == 0)
        self.assertTrue("blueprint: example-http-server v" in output)
        self.assertTrue("httpd" in output)

    @unittest.skipUnless(os.path.exists("/run/weldr/api.socket"), "Test requires a running API server")
    def test_freeze_show(self):
        """blueprints freeze show"""
        with captured_output() as (out, _):
            rc = blueprints_freeze("/run/weldr/api.socket", 0, ["show", "example-http-server"], show_json=False)
        output = out.getvalue().strip()
        self.assertTrue(rc == 0)
        self.assertTrue("version" in output)
        self.assertTrue("example-http-server" in output)
        self.assertTrue("x86_64" in output)
        self.assertTrue("[[packages]]" in output)
        self.assertTrue("[[modules]]" in output)

    @unittest.skipUnless(os.path.exists("/run/weldr/api.socket"), "Test requires a running API server")
    def test_freeze_save(self):
        """blueprints freeze save"""
        rc = blueprints_freeze("/run/weldr/api.socket", 0, ["save", "example-http-server"], show_json=False)
        self.assertTrue(rc == 0)
        self.assertTrue(os.path.exists("example-http-server.frozen.toml"))

    @unittest.skipUnless(os.path.exists("/run/weldr/api.socket"), "Test requires a running API server")
    def test_freeze(self):
        """blueprints freeze"""
        with captured_output() as (out, _):
            rc = blueprints_freeze("/run/weldr/api.socket", 0, ["example-http-server"], show_json=False)
        output = out.getvalue().strip()
        self.assertTrue(rc == 0)
        self.assertTrue("blueprint: example-http-server v" in output)
        self.assertTrue("httpd" in output)
        self.assertTrue("x86_64" in output)

    @unittest.skipUnless(os.path.exists("/run/weldr/api.socket"), "Test requires a running API server")
    def test_tag(self):
        """blueprints tag"""
        rc = blueprints_tag("/run/weldr/api.socket", 0, ["glusterfs"], show_json=False)
        self.assertTrue(rc == 0)

    @unittest.skipUnless(os.path.exists("/run/weldr/api.socket"), "Test requires a running API server")
    def test_undo(self):
        """blueprints undo"""
        # Get the oldest commit, it should be 2nd to last line
        with captured_output() as (out, _):
            rc = blueprints_changes("/run/weldr/api.socket", 0, ["example-http-server"], show_json=False)
        output = out.getvalue().strip().splitlines()
        first_commit = output[-2].split()[1]

        with captured_output() as (out, _):
            rc = blueprints_undo("/run/weldr/api.socket", 0, ["example-http-server", first_commit, "HEAD"], show_json=False)
        output = out.getvalue().strip()
        self.assertTrue(rc == 0)

    @unittest.skipUnless(os.path.exists("/run/weldr/api.socket"), "Test requires a running API server")
    def test_workspace(self):
        """blueprints workspace"""
        rc = blueprints_push("/run/weldr/api.socket", 0, ["example-http-server.toml"], show_json=False)
        self.assertTrue(rc == 0)

    # XXX MUST COME LAST
    # XXX which is what _z_ ensures
    @unittest.skipUnless(os.path.exists("/run/weldr/api.socket"), "Test requires a running API server")
    def test_z_diff(self):
        """blueprints diff"""
        # Get the oldest commit, it should be 2nd to last line
        with captured_output() as (out, _):
            rc = blueprints_changes("/run/weldr/api.socket", 0, ["example-http-server"], show_json=False)
        output = out.getvalue().strip().splitlines()
        first_commit = output[-2].split()[1]

        with captured_output() as (out, _):
            rc = blueprints_diff("/run/weldr/api.socket", 0, ["example-http-server", first_commit, "HEAD"], show_json=False)
        output = out.getvalue().strip()
        self.assertTrue(rc == 0)
        self.assertTrue("Changed Version" in output)
