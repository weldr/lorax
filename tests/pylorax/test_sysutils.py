#
# Copyright (C) 2017  Red Hat, Inc.
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

from pylorax.sysutils import safe_write

class SysutilsTest(unittest.TestCase):
    def test_safe_write(self):
        test_filename = "/tmp/composer-safe-test"
        with safe_write(test_filename, 0o600) as f:
            f.write("This text is only readable by the user")

        self.assertEqual(os.stat(test_filename).st_mode & 0o777, 0o600)

        os.unlink(test_filename)
