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

from pylorax.api.errors import INVALID_CHARS
from composer.cli.utilities import argify, toml_filename, frozen_toml_filename, packageNEVRA
from composer.cli.utilities import handle_api_result

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

    def test_api_result_1(self):
        """Test a result with no status and no error fields"""
        result = {"foo": "bar"}
        self.assertEqual(handle_api_result(result, show_json=False), (0, False))

    def test_api_result_2(self):
        """Test a result with errors=[{"id": INVALID_CHARS, "msg": "some error"}], and no status field"""
        result = {"foo": "bar", "errors": [{"id": INVALID_CHARS, "msg": "some error"}]}
        self.assertEqual(handle_api_result(result, show_json=False), (1, False))

    def test_api_result_3(self):
        """Test a result with status=True, and errors=[]"""
        result = {"status": True, "errors": []}
        self.assertEqual(handle_api_result(result, show_json=False), (0, False))

    def test_api_result_4(self):
        """Test a result with status=False, and errors=[]"""
        result = {"status": False, "errors": []}
        self.assertEqual(handle_api_result(result, show_json=False), (1, True))

    def test_api_result_5(self):
        """Test a result with status=False, and errors=[{"id": INVALID_CHARS, "msg": "some error"}]"""
        result = {"status": False, "errors": [{"id": INVALID_CHARS, "msg": "some error"}]}
        self.assertEqual(handle_api_result(result, show_json=False), (1, True))

    def test_api_result_6(self):
        """Test a result with show_json=True, and no status or errors fields"""
        result = {"foo": "bar"}
        self.assertEqual(handle_api_result(result, show_json=True), (0, True))

    def test_api_result_7(self):
        """Test a result with show_json=True, status=False, and errors=[{"id": INVALID_CHARS, "msg": "some error"}]"""
        result = {"status": False, "errors": [{"id": INVALID_CHARS, "msg": "some error"}]}
        self.assertEqual(handle_api_result(result, show_json=True), (1, True))

    def test_api_result_8(self):
        """Test a result with show_json=True, errors=[{"id": INVALID_CHARS, "msg": "some error"}], and no status field"""
        result = {"foo": "bar", "errors": [{"id": INVALID_CHARS, "msg": "some error"}]}
        self.assertEqual(handle_api_result(result, show_json=True), (1, True))

    def test_api_result_9(self):
        """Test a result with show_json=True, errors=[], and no status field"""
        result = {"foo": "bar", "errors": []}
        self.assertEqual(handle_api_result(result, show_json=True), (0, True))
