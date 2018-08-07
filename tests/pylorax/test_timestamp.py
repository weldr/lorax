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
import shutil
import tempfile
import unittest

from pylorax.api.timestamp import write_timestamp, timestamp_dict
from pylorax.api.timestamp import TS_CREATED, TS_STARTED, TS_FINISHED

class TimestampTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.test_dir = tempfile.mkdtemp(prefix="lorax.timestamp.")

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.test_dir)

    def timestamp_test(self):
        """Test writing and reading compose timestamps"""
        write_timestamp(self.test_dir, TS_CREATED)
        ts = timestamp_dict(self.test_dir)
        self.assertTrue(TS_CREATED in ts)
        self.assertTrue(TS_STARTED not in ts)
        self.assertTrue(TS_FINISHED not in ts)

        write_timestamp(self.test_dir, TS_STARTED)
        ts = timestamp_dict(self.test_dir)
        self.assertTrue(TS_CREATED in ts)
        self.assertTrue(TS_STARTED in ts)
        self.assertTrue(TS_FINISHED not in ts)

        write_timestamp(self.test_dir, TS_FINISHED)
        ts = timestamp_dict(self.test_dir)
        self.assertTrue(TS_CREATED in ts)
        self.assertTrue(TS_STARTED in ts)
        self.assertTrue(TS_FINISHED in ts)
