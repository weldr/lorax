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

from composer.cli.utilities import argify, toml_filename, frozen_toml_filename, packageNEVRA

class CliUtilitiesTest(unittest.TestCase):
    def test_argify(self):
        """Convert an optionally comma-separated cmdline into a list of args"""
        self.assertEqual(argify(["one,two", "three", ",four", ",five,"]), ["one", "two", "three", "four", "five"])

    def test_toml_filename(self):
        """Return the recipe's toml filename"""
        self.assertEqual(toml_filename("http server"), "http-server.toml")

    def test_frozen_toml_filename(self):
        """Return the recipe's frozen toml filename"""
        self.assertEqual(frozen_toml_filename("http server"), "http-server.frozen.toml")

    def test_packageNEVRA(self):
        """Return a string with the NVRA or NEVRA"""
        epoch_0 = {"arch": "noarch",
                   "epoch": 0,
                   "name": "basesystem",
                   "release": "7.el7",
                   "version": "10.0"}
        epoch_3 = {"arch": "noarch",
                   "epoch": 3,
                   "name": "basesystem",
                   "release": "7.el7",
                   "version": "10.0"}
        self.assertEqual(packageNEVRA(epoch_0), "basesystem-10.0-7.el7.noarch")
        self.assertEqual(packageNEVRA(epoch_3), "basesystem-3:10.0-7.el7.noarch")
