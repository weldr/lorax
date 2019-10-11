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
from lifted.providers import load_profiles, validate_settings, load_settings, delete_profile
from lifted.providers import _get_profile_path
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

    def test_get_profile_path(self):
        """Make sure that _get_profile_path strips path elements from the input"""
        path = _get_profile_path(self.config["upload"], "aws", "staging-settings", exists=False)
        self.assertEqual(path, os.path.abspath(joinpaths(self.config["upload"]["settings_dir"], "aws/staging-settings.toml")))

        path = _get_profile_path(self.config["upload"], "../../../../foo/bar/aws", "/not/my/path/staging-settings", exists=False)
        self.assertEqual(path, os.path.abspath(joinpaths(self.config["upload"]["settings_dir"], "aws/staging-settings.toml")))

    def test_list_providers(self):
        p = list_providers(self.config["upload"])
        self.assertEqual(p, ['aws', 'dummy', 'openstack', 'vsphere'])

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
            validate_settings(self.config["upload"], "aws", {"wrong-key": "wrong value"})

        with self.assertRaises(ValueError):
            validate_settings(self.config["upload"], "aws", {"secret": False})

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

    # This *must* run after test_save_settings, _zz_ ensures that happens
    def test_zz_load_settings_errors(self):
        """Test returning the correct errors for missing profiles and providers"""
        with self.assertRaises(ValueError):
            load_settings(self.config["upload"], "", "")

        with self.assertRaises(ValueError):
            load_settings(self.config["upload"], "", "default")

        with self.assertRaises(ValueError):
            load_settings(self.config["upload"], "aws", "")

        with self.assertRaises(RuntimeError):
            load_settings(self.config["upload"], "foo", "default")

        with self.assertRaises(RuntimeError):
            load_settings(self.config["upload"], "aws", "missing-test")

    # This *must* run after test_save_settings, _zz_ ensures that happens
    def test_zz_load_settings(self):
        """Test loading settings"""
        for p in list_providers(self.config["upload"]):
            settings = load_settings(self.config["upload"], p, test_profiles[p][0])
            self.assertEqual(settings, test_profiles[p][1])

    # This *must* run after all the save and load tests, but *before* the actual delete test
    # _zz_ ensures this happens
    def test_zz_delete_settings_errors(self):
        """Test raising the correct errors when deleting"""
        with self.assertRaises(ValueError):
            delete_profile(self.config["upload"], "", "")

        with self.assertRaises(ValueError):
            delete_profile(self.config["upload"], "", "default")

        with self.assertRaises(ValueError):
            delete_profile(self.config["upload"], "aws", "")

        with self.assertRaises(RuntimeError):
            delete_profile(self.config["upload"], "aws", "missing-test")

    # This *must* run after all the save and load tests, _zzz_ ensures this happens
    def test_zzz_delete_settings(self):
        """Test raising the correct errors when deleting"""
        # Ensure the profile is really there
        settings = load_settings(self.config["upload"], "aws", test_profiles["aws"][0])
        self.assertEqual(settings, test_profiles["aws"][1])

        delete_profile(self.config["upload"], "aws", test_profiles["aws"][0])

        with self.assertRaises(RuntimeError):
            load_settings(self.config["upload"], "aws", test_profiles["aws"][0])
