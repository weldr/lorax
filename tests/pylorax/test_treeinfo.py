#
# Copyright (C) 2018 Red Hat, Inc.
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
import tempfile
import configparser
import os

from pylorax.treeinfo import TreeInfo

class TreeInfoTest(unittest.TestCase):
    def test_treeinfo(self):
        with tempfile.NamedTemporaryFile() as f:
            ti = TreeInfo("Lorax-Test", "1.0", "Server", "x86_64", "Packages")
            ti.add_section("images", {"initrd": "images/pxeboot/initrd.img",
                                      "kernel": "images/pxeboot/vmlinuz"})
            ti.write(f.name)

            config = configparser.ConfigParser()
            config.read(f.name)

            self.assertEqual(config.get("general", "family"), "Lorax-Test")
            self.assertEqual(config.get("general", "version"), "1.0")
            self.assertEqual(config.get("general", "name"), "Lorax-Test-1.0")
            self.assertEqual(config.get("general", "variant"), "Server")
            self.assertEqual(config.get("general", "arch"), "x86_64")
            self.assertEqual(config.get("general", "packagedir"), "Packages")
            self.assertTrue(config.get("general", "timestamp") not in ["", None])

            self.assertEqual(config.get("images", "initrd"), "images/pxeboot/initrd.img")
            self.assertEqual(config.get("images", "kernel"), "images/pxeboot/vmlinuz")

    def test_source_time(self):
        """Test treeinfo with SOURCE_DATE_EPOCH environmental variable set"""
        os.environ["SOURCE_DATE_EPOCH"] = str(499137660)
        with tempfile.NamedTemporaryFile() as f:
            ti = TreeInfo("Lorax-Test", "1.0", "Server", "x86_64", "Packages")
            ti.write(f.name)

            config = configparser.ConfigParser()
            config.read(f.name)

            self.assertEqual(config.get("general", "timestamp"), str(499137660))
