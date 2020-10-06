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
import tempfile
import unittest

from ..lib import captured_output

from composer.cli.blueprints import pretty_diff_entry, blueprints_list, blueprints_show, blueprints_changes
from composer.cli.blueprints import blueprints_diff, blueprints_save, blueprints_delete, blueprints_depsolve
from composer.cli.blueprints import blueprints_push, blueprints_freeze, blueprints_undo, blueprints_tag
from composer.cli.blueprints import pretty_dict, dict_names

diff_entries = [{'new': {'Description': 'Shiny new description'}, 'old': {'Description': 'Old reliable description'}},
                {'new': {'Version': '0.3.1'}, 'old': {'Version': '0.1.1'}},
                {'new': {'Module': {'name': 'openssh', 'version': '2.8.1'}}, 'old': None},
                {'new': None, 'old': {'Module': {'name': 'bash', 'version': '5.*'}}},
                {'new': {'Module': {'name': 'httpd', 'version': '3.8.*'}},
                 'old': {'Module': {'name': 'httpd', 'version': '3.7.*'}}},
                {'new': {'Package': {'name': 'git', 'version': '2.13.*'}}, 'old': None},
                # New items
                {"new": {"Group": {"name": "core"}}, "old": None},
                {"new": {"Customizations.firewall": {"ports": ["8888:tcp", "22:tcp", "dns:udp", "9090:tcp"], "services": ["smtp"]}}, "old": None},
                {"new": {"Customizations.hostname": "foobar"}, "old": None},
                {"new": {"Customizations.locale": {"keyboard": "US"}}, "old": None},
                {"new": {"Customizations.sshkey": [{"key": "ssh-rsa AAAAB3NzaC1... norm@localhost.localdomain", "user": "norm" }]}, "old": None},
                {"new": {"Customizations.timezone": {"ntpservers": ["ntp.nowhere.com" ], "timezone": "PST8PDT"}}, "old": None},
                {"new": {"Customizations.user": [{"key": "ssh-rsa AAAAB3NzaC1... root@localhost.localdomain", "name": "root", "password": "fobarfobar"}]}, "old": None},
                {"new": {"Repos.git": {"destination": "/opt/server-1/", "ref": "v1.0", "repo": "PATH OF GIT REPO TO CLONE", "rpmname": "server-config", "rpmrelease": "2", "rpmversion": "1.0", "summary": "Setup files for server deployment"}}, "old": None},
                # Removed items (just reversed old/old from above block)
                {"old": {"Group": {"name": "core"}}, "new": None},
                {"old": {"Customizations.firewall": {"ports": ["8888:tcp", "22:tcp", "dns:udp", "9090:tcp"], "services": ["smtp"]}}, "new": None},
                {"old": {"Customizations.hostname": "foobar"}, "new": None},
                {"old": {"Customizations.locale": {"keyboard": "US"}}, "new": None},
                {"old": {"Customizations.sshkey": [{"key": "ssh-rsa AAAAB3NzaC1... norm@localhost.localdomain", "user": "norm" }]}, "new": None},
                {"old": {"Customizations.timezone": {"ntpservers": ["ntp.nowhere.com" ], "timezone": "PST8PDT"}}, "new": None},
                {"old": {"Customizations.user": [{"key": "ssh-rsa AAAAB3NzaC1... root@localhost.localdomain", "name": "root", "password": "fobarfobar"}]}, "new": None},
                {"old": {"Repos.git": {"destination": "/opt/server-1/", "ref": "v1.0", "repo": "PATH OF GIT REPO TO CLONE", "rpmname": "server-config", "rpmrelease": "2", "rpmversion": "1.0", "summary": "Setup files for server deployment"}}, "new": None},
                # Changed items
                {"old": {"Customizations.firewall": {"ports": ["8888:tcp", "22:tcp", "dns:udp", "9090:tcp"], "services": ["smtp"]}}, "new": {"Customizations.firewall": {"ports": ["8888:tcp", "22:tcp", "25:tcp"]}}},
                {"old": {"Customizations.hostname": "foobar"}, "new": {"Customizations.hostname": "grues"}},
                {"old": {"Customizations.locale": {"keyboard": "US"}}, "new": {"Customizations.locale": {"keyboard": "US", "languages": ["en_US.UTF-8"]}}},
                {"old": {"Customizations.sshkey": [{"key": "ssh-rsa AAAAB3NzaC1... norm@localhost.localdomain", "user": "norm" }]}, "new": {"Customizations.sshkey": [{"key": "ssh-rsa ABCDEF01234... norm@localhost.localdomain", "user": "norm" }]}},
                {"old": {"Customizations.timezone": {"ntpservers": ["ntp.nowhere.com" ], "timezone": "PST8PDT"}}, "new": {"Customizations.timezone": {"timezone": "Antarctica/Palmer"}}},
                {"old": {"Customizations.user": [{"key": "ssh-rsa AAAAB3NzaC1... root@localhost.localdomain", "name": "root", "password": "fobarfobar"}]}, "new": {"Customizations.user": [{"key": "ssh-rsa AAAAB3NzaC1... root@localhost.localdomain", "name": "root", "password": "qweqweqwe"}]}},
                {"old": {"Repos.git": {"destination": "/opt/server-1/", "ref": "v1.0", "repo": "PATH OF GIT REPO TO CLONE", "rpmname": "server-config", "rpmrelease": "2", "rpmversion": "1.0", "summary": "Setup files for server deployment"}}, "new": {"Repos.git": {"destination": "/opt/server-1/", "ref": "v1.0", "repo": "PATH OF GIT REPO TO CLONE", "rpmname": "server-config", "rpmrelease": "1", "rpmversion": "1.1", "summary": "Setup files for server deployment"}}}
                ]

diff_result = [
    'Changed Description "Old reliable description" -> "Shiny new description"',
    'Changed Version 0.1.1 -> 0.3.1',
    'Added Module openssh 2.8.1',
    'Removed Module bash 5.*',
    'Changed Module httpd 3.7.* -> 3.8.*',
    'Added Package git 2.13.*',
    'Added Group core',
    'Added Customizations.firewall ports="8888:tcp, 22:tcp, dns:udp, 9090:tcp" services="smtp"',
    'Added Customizations.hostname foobar',
    'Added Customizations.locale keyboard="US"',
    'Added Customizations.sshkey norm',
    'Added Customizations.timezone ntpservers="ntp.nowhere.com" timezone="PST8PDT"',
    'Added Customizations.user root',
    'Added Repos.git destination="/opt/server-1/" ref="v1.0" repo="PATH OF GIT REPO TO CLONE" rpmname="server-config" rpmrelease="2" rpmversion="1.0" summary="Setup files for server deployment"',
    'Removed Group core',
    'Removed Customizations.firewall ports="8888:tcp, 22:tcp, dns:udp, 9090:tcp" services="smtp"',
    'Removed Customizations.hostname foobar',
    'Removed Customizations.locale keyboard="US"',
    'Removed Customizations.sshkey norm',
    'Removed Customizations.timezone ntpservers="ntp.nowhere.com" timezone="PST8PDT"',
    'Removed Customizations.user root',
    'Removed Repos.git destination="/opt/server-1/" ref="v1.0" repo="PATH OF GIT REPO TO CLONE" rpmname="server-config" rpmrelease="2" rpmversion="1.0" summary="Setup files for server deployment"',
    'Changed Customizations.firewall ports="8888:tcp, 22:tcp, dns:udp, 9090:tcp" services="smtp" -> ports="8888:tcp, 22:tcp, 25:tcp"',
    'Changed Customizations.hostname foobar -> grues',
    'Changed Customizations.locale keyboard="US" -> keyboard="US" languages="en_US.UTF-8"',
    'Changed Customizations.sshkey norm -> norm',
    'Changed Customizations.timezone ntpservers="ntp.nowhere.com" timezone="PST8PDT" -> timezone="Antarctica/Palmer"',
    'Changed Customizations.user root -> root',
    'Changed Repos.git destination="/opt/server-1/" ref="v1.0" repo="PATH OF GIT REPO TO CLONE" rpmname="server-config" rpmrelease="2" rpmversion="1.0" summary="Setup files for server deployment" -> destination="/opt/server-1/" ref="v1.0" repo="PATH OF GIT REPO TO CLONE" rpmname="server-config" rpmrelease="1" rpmversion="1.1" summary="Setup files for server deployment"',
    ]

dict_entries = [{"ports": ["8888:tcp", "22:tcp", "dns:udp", "9090:tcp"]},
                {"ports": ["8888:tcp", "22:tcp", "dns:udp", "9090:tcp"], "services": ["smtp"]},
                { "destination": "/opt/server-1/", "ref": "v1.0", "repo": "PATH OF GIT REPO TO CLONE", "rpmname": "server-config", "rpmrelease": "1", "rpmversion": "1.0", "summary": "Setup files for server deployment" },
                {"foo": ["one", "two"], "bar": {"baz": "three"}}]

dict_results = ['ports="8888:tcp, 22:tcp, dns:udp, 9090:tcp"',
                'ports="8888:tcp, 22:tcp, dns:udp, 9090:tcp" services="smtp"',
                'destination="/opt/server-1/" ref="v1.0" repo="PATH OF GIT REPO TO CLONE" rpmname="server-config" rpmrelease="1" rpmversion="1.0" summary="Setup files for server deployment"',
                'foo="one, two"']

dict_name_entry1 = [{"name": "bart", "home": "Springfield"},
                    {"name": "lisa", "instrument": "Saxaphone"},
                    {"name": "homer", "kids": ["bart", "maggie", "lisa"]}]

dict_name_results1 = "bart, lisa, homer"

dict_name_entry2 = [{"user": "root", "password": "qweqweqwe"},
                    {"user": "norm", "password": "b33r"},
                    {"user": "cliff", "password": "POSTMASTER"}]

dict_name_results2 = "root, norm, cliff"

dict_name_entry3 = [{"home": "/root", "key": "skeleton"},
                    {"home": "/home/norm", "key": "SSH KEY"},
                    {"home": "/home/cliff", "key": "lost"}]

dict_name_results3 = "/root, /home/norm, /home/cliff"



HTTP_BLUEPRINT = b"""name = "example-http-server"
description = "An example http server with PHP and MySQL support."
version = "0.0.1"

[[packages]]
name = "httpd"
version = "*"

[[packages]]
name = "tmux"
version = "*"

[[packages]]
name = "openssh-server"
version = "*"

[[packages]]
name = "rsync"
version = "*"

[[modules]]
name = "php"
version = "*"
"""

DEV_BLUEPRINT = b"""name = "example-development"
description = "A general purpose development image"

[[packages]]
name = "cmake"
version = "*"

[[packages]]
name = "curl"
version = "*"

[[packages]]
name = "gcc"
version = "*"

[[packages]]
name = "gdb"
version = "*"
"""


class BlueprintsTest(unittest.TestCase):
    def test_pretty_diff_entry(self):
        """Return a nice representation of a diff entry"""
        self.assertEqual([pretty_diff_entry(entry) for entry in diff_entries], diff_result)

    def test_pretty_dict(self):
        """Return a human readable single line"""
        self.assertEqual([pretty_dict(entry) for entry in dict_entries], dict_results)

    def test_dict_names_users(self):
        """Return a list of the name field of the list of dicts"""
        self.assertEqual(dict_names(dict_name_entry1), dict_name_results1)

    def test_dict_names_sshkey(self):
        """Return a list of the user field of the list of dicts"""
        self.assertEqual(dict_names(dict_name_entry2), dict_name_results2)

    def test_dict_names_other(self):
        """Return a list of the unknown field of the list of dicts"""
        self.assertEqual(dict_names(dict_name_entry3), dict_name_results3)

@unittest.skipUnless(os.path.exists("/run/weldr/api.socket"), "Tests require a running API server")
class ServerBlueprintsTest(unittest.TestCase):
    # MUST come first, tests push and installs required blueprints
    def test_0000(self):
        """initialize server blueprints"""
        for blueprint in [HTTP_BLUEPRINT, DEV_BLUEPRINT]:
            with tempfile.NamedTemporaryFile(prefix="composer.test.") as tf:
                tf.write(blueprint)
                tf.file.close()

                rc = blueprints_push("/run/weldr/api.socket", 0, [tf.name], show_json=False)
                self.assertTrue(rc == 0)

    def test_list(self):
        """blueprints list"""
        with captured_output() as (out, _):
            rc = blueprints_list("/run/weldr/api.socket", 0, [], show_json=False)
        output = out.getvalue().strip()
        self.assertTrue(rc == 0)
        self.assertTrue("example-http-server" in output)

    def test_show(self):
        """blueprints show"""
        with captured_output() as (out, _):
            blueprints_show("/run/weldr/api.socket", 0, ["example-http-server"], show_json=False)
        output = out.getvalue().strip()
        self.assertTrue("example-http-server" in output)
        self.assertTrue("[[packages]]" in output)
        self.assertTrue("[[modules]]" in output)

    def test_changes(self):
        """blueprints changes"""
        with captured_output() as (out, _):
            rc = blueprints_changes("/run/weldr/api.socket", 0, ["example-http-server"], show_json=False)
        output = out.getvalue().strip()
        self.assertTrue(rc == 0)
        self.assertTrue("example-http-server" in output)
        self.assertTrue("Recipe example-http-server, version 0.0.1 saved." in output)

    def test_save_0(self):
        """blueprints save"""
        blueprints_save("/run/weldr/api.socket", 0, ["example-http-server"], show_json=False)
        self.assertTrue(os.path.exists("example-http-server.toml"))

    def test_save_1(self):
        """blueprints push"""
        rc = blueprints_push("/run/weldr/api.socket", 0, ["example-http-server.toml"], show_json=False)
        self.assertTrue(rc == 0)

    def test_delete(self):
        """blueprints delete"""
        rc = blueprints_delete("/run/weldr/api.socket", 0, ["example-development"], show_json=False)
        self.assertTrue(rc == 0)

    def test_depsolve(self):
        """blueprints depsolve"""
        with captured_output() as (out, _):
            rc = blueprints_depsolve("/run/weldr/api.socket", 0, ["example-http-server"], show_json=False)
        output = out.getvalue().strip()
        self.assertTrue(rc == 0)
        self.assertTrue("blueprint: example-http-server v" in output)
        self.assertTrue("httpd" in output)

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

    def test_freeze_save(self):
        """blueprints freeze save"""
        rc = blueprints_freeze("/run/weldr/api.socket", 0, ["save", "example-http-server"], show_json=False)
        self.assertTrue(rc == 0)
        self.assertTrue(os.path.exists("example-http-server.frozen.toml"))

    def test_freeze(self):
        """blueprints freeze"""
        with captured_output() as (out, _):
            rc = blueprints_freeze("/run/weldr/api.socket", 0, ["example-http-server"], show_json=False)
        output = out.getvalue().strip()
        self.assertTrue(rc == 0)
        self.assertTrue("blueprint: example-http-server v" in output)
        self.assertTrue("httpd" in output)
        self.assertTrue("x86_64" in output)

    def test_tag(self):
        """blueprints tag"""
        rc = blueprints_tag("/run/weldr/api.socket", 0, ["example-http-server"], show_json=False)
        self.assertTrue(rc == 0)

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

    def test_workspace(self):
        """blueprints workspace"""
        rc = blueprints_push("/run/weldr/api.socket", 0, ["example-http-server.toml"], show_json=False)
        self.assertTrue(rc == 0)

    # XXX MUST COME LAST
    # XXX which is what _z_ ensures
    @unittest.expectedFailure
    def test_z_diff(self):
        """blueprints diff"""
        # Get the oldest commit, it should be 2nd to last line
        with captured_output() as (out, _):
            rc = blueprints_changes("/run/weldr/api.socket", 0, ["example-http-server"], show_json=False)
        output = out.getvalue().strip().splitlines()
        first_commit = output[-2].split()[1]

        with captured_output() as (out, _):
            rc = blueprints_diff("/run/weldr/api.socket", 0, ["example-http-server", first_commit, "NEWEST"], show_json=False)
        output = out.getvalue().strip()
        self.assertTrue(rc == 0)
        self.assertTrue("Changed Version" in output)
