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
import unittest

import lifted.config
import pylorax.api.config

class ConfigTestCase(unittest.TestCase):
    def test_lifted_config(self):
        """Test lifted config setup"""
        config = pylorax.api.config.configure(test_config=True)
        lifted.config.configure(config)

        self.assertTrue(config.get("upload", "providers_dir").startswith(config.get("composer", "share_dir")))
        self.assertTrue(config.get("upload", "queue_dir").startswith(config.get("composer", "lib_dir")))
        self.assertTrue(config.get("upload", "settings_dir").startswith(config.get("composer", "lib_dir")))

    def test_lifted_sharedir_config(self):
        """Test lifted config setup with custom share_dir"""
        config = pylorax.api.config.configure(test_config=True)
        config.set("composer", "share_dir", "/custom/share/path")
        lifted.config.configure(config)

        self.assertEqual(config.get("composer", "share_dir"), "/custom/share/path")
        self.assertTrue(config.get("upload", "providers_dir").startswith(config.get("composer", "share_dir")))
        self.assertTrue(config.get("upload", "queue_dir").startswith(config.get("composer", "lib_dir")))
        self.assertTrue(config.get("upload", "settings_dir").startswith(config.get("composer", "lib_dir")))

    def test_lifted_libdir_config(self):
        """Test lifted config setup with custom lib_dir"""
        config = pylorax.api.config.configure(test_config=True)
        config.set("composer", "lib_dir", "/custom/lib/path")
        lifted.config.configure(config)

        self.assertEqual(config.get("composer", "lib_dir"), "/custom/lib/path")
        self.assertTrue(config.get("upload", "providers_dir").startswith(config.get("composer", "share_dir")))
        self.assertTrue(config.get("upload", "queue_dir").startswith(config.get("composer", "lib_dir")))
        self.assertTrue(config.get("upload", "settings_dir").startswith(config.get("composer", "lib_dir")))
