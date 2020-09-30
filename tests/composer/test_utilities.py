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
from composer.cli.utilities import handle_api_result, get_arg

INVALID_CHARS = "InvalidChars"

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
        self.assertTrue(handle_api_result(result, show_json=False)[0] == 0)

    def test_api_result_2(self):
        """Test a result with errors=[{"id": INVALID_CHARS, "msg": "some error"}], and no status field"""
        result = {"foo": "bar", "errors": [{"id": INVALID_CHARS, "msg": "some error"}]}
        self.assertEqual(handle_api_result(result, show_json=False), (1, False))
        self.assertTrue(handle_api_result(result, show_json=False)[0] == 1)

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

    def test_get_arg_empty(self):
        """Test get_arg with no arguments"""
        self.assertEqual(get_arg([], "--size"), ([], None))

    def test_get_arg_no_arg(self):
        """Test get_arg with no argument in the list"""
        self.assertEqual(get_arg(["first", "second"], "--size"), (["first", "second"], None))

    def test_get_arg_notype(self):
        """Test get_arg with no argtype set"""
        self.assertEqual(get_arg(["first", "--size", "100", "second"], "--size"), (["first", "second"], "100"))

    def test_get_arg_string(self):
        """Test get_arg with a string argument"""
        self.assertEqual(get_arg(["first", "--size", "100", "second"], "--size", str), (["first", "second"], "100"))

    def test_get_arg_int(self):
        """Test get_arg with an int argument"""
        self.assertEqual(get_arg(["first", "--size", "100", "second"], "--size", int), (["first", "second"], 100))

    def test_get_arg_short(self):
        """Test get_arg error handling with a short list"""
        with self.assertRaises(RuntimeError):
            get_arg(["first", "--size", ], "--size", int)

    def test_get_arg_start(self):
        """Test get_arg with the argument at the start of the list"""
        self.assertEqual(get_arg(["--size", "100", "first", "second"], "--size", int), (["first", "second"], 100))

    def test_get_arg_wrong_type(self):
        """Test get_arg with the wrong type"""
        with self.assertRaises(ValueError):
            get_arg(["first", "--size", "abc", "second"], "--size", int)
