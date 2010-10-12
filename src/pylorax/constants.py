#
# constants.py
#
# Copyright (C) 2009  Red Hat, Inc.
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
# Red Hat Author(s):  Martin Gracik <mgracik@redhat.com>
#

import os

from sysutils import joinpaths


class LoraxRequiredCommands(dict):

    def __init__(self):
        self.__path = os.environ["PATH"].split(":")

        self["AWK"] = "awk"
        self["BUILD_LOCALE_ARCHIVE"] = "build-locale-archive"
        self["CPIO"] = "cpio"
        self["DEPMOD"] = "depmod"
        self["DMSETUP"] = "dmsetup"
        self["FIND"] = "find"
        self["ISOHYBRID"] = "isohybrid"
        self["LDCONFIG"] = "ldconfig"
        self["LOCALEDEF"] = "localedef"
        self["LOSETUP"] = "losetup"
        self["MKDOSFS"] = "mkdosfs"
        self["MKISOFS"] = "mkisofs"
        self["MKSQUASHFS"] = "mksquashfs"
        self["MODINFO"] = "modinfo"
        self["MOUNT"] = "mount"
        self["PARTED"] = "parted"
        self["UMOUNT"] = "umount"

    def __getattr__(self, attr):
        return self[attr]

    def get_missing(self):
        missing = []
        for cmd in self.values():
            found = [joinpaths(path, cmd) for path in self.__path
                     if os.path.exists(joinpaths(path, cmd))]

            if not found:
                missing.append(cmd)

        return missing
