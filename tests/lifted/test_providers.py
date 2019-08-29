#
# Copyright (C) 2019 Red Hat, Inc.
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
import shutil
import tempfile
import unittest

import lifted.config
from lifted.providers import list_providers, resolve_provider, resolve_playbook_path, save_settings
from lifted.providers import load_profiles, validate_settings
import pylorax.api.config
from pylorax.sysutils import joinpaths

from tests.lifted.profiles import test_profiles

class ProvidersTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.root_dir = tempfile.mkdtemp(prefix="lifted.test.")
        self.config = pylorax.api.config.configure(root_dir=self.root_dir, test_config=True)
        self.config.set("composer", "share_dir", os.path.realpath("./share/"))
        lifted.config.configure(self.config)

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.root_dir)

    def test_list_providers(self):
        p = list_providers(self.config["upload"])
        self.assertEqual(p, ['azure', 'dummy', 'openstack', 'vsphere'])

    def test_resolve_provider(self):
        for p in list_providers(self.config["upload"]):
            print(p)
            info = resolve_provider(self.config["upload"], p)
            self.assertTrue("display" in info)
            self.assertTrue("supported_types" in info)
            self.assertTrue("settings-info" in info)

    def test_resolve_playbook_path(self):
        for p in list_providers(self.config["upload"]):
            print(p)
            self.assertTrue(len(resolve_playbook_path(self.config["upload"], p)) > 0)

    def test_resolve_playbook_path_error(self):
        with self.assertRaises(RuntimeError):
            resolve_playbook_path(self.config["upload"], "foobar")

    def test_validate_settings(self):
        for p in list_providers(self.config["upload"]):
            print(p)
            validate_settings(self.config["upload"], p, test_profiles[p][1])

    def test_validate_settings_errors(self):
        with self.assertRaises(ValueError):
            validate_settings(self.config["upload"], "dummy", test_profiles["dummy"][1], image_name="")

        with self.assertRaises(ValueError):
            validate_settings(self.config["upload"], "azure", {"wrong-key": "wrong value"})

        with self.assertRaises(ValueError):
            validate_settings(self.config["upload"], "azure", {"secret": False})

        # TODO - test regex, needs a provider with a regex

    def test_save_settings(self):
        """Test saving profiles"""
        for p in list_providers(self.config["upload"]):
            print(p)
            save_settings(self.config["upload"], p, test_profiles[p][0], test_profiles[p][1])

            profile_dir = joinpaths(self.config.get("upload", "settings_dir"), p, test_profiles[p][0]+".toml")
            self.assertTrue(os.path.exists(profile_dir))

    # This *must* run after test_save_settings, _zz_ ensures that happens
    def test_zz_load_profiles(self):
        """Test loading profiles"""
        for p in list_providers(self.config["upload"]):
            print(p)
            profile = load_profiles(self.config["upload"], p)
            self.assertTrue(test_profiles[p][0] in profile)
