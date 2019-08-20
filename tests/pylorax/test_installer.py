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
import unittest

from ..lib import get_file_magic
from pylorax.installer import make_ks_disk

class InstallerTest(unittest.TestCase):
    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def ks_disk_test(self):
        """Test creating a kickstart disk image"""
        ks_disk = make_ks_disk(["./tests/pylorax/repos/server-1.repo"], "KS_DISK_IMG")
        self.assertTrue(os.path.exists(ks_disk))
        file_details = get_file_magic(ks_disk)
        self.assertTrue("ext2 filesystem" in file_details, file_details)
