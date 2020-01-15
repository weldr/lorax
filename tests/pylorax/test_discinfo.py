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

from pylorax.discinfo import DiscInfo

class DiscInfoTest(unittest.TestCase):
    def test_discinfo(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as f:
            di = DiscInfo("1.0", "x86_64")
            di.write(f.name)
            f.seek(0)
            self.assertTrue(f.readline().strip() not in ["", None])
            self.assertEqual(f.readline().strip(), "1.0")
            self.assertEqual(f.readline().strip(), "x86_64")
