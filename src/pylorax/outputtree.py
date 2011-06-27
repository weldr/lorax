#
# outputtree.py
#
# Copyright (C) 2010  Red Hat, Inc.
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

import logging
logger = logging.getLogger("pylorax.outputtree")

import sys
import os
import shutil
import glob
import subprocess

from base import BaseLoraxClass, DataHolder
from sysutils import *
import constants


class LoraxOutputTree(BaseLoraxClass):

    def __init__(self, root, installtree, product, version):
        BaseLoraxClass.__init__(self)
        self.root = root
        self.installtree = installtree

        self.product = product
        self.version = version

    def get_kernels(self, workdir):
        self.kernels = []

        for n, kernel in enumerate(self.installtree.kernels):
            suffix = ""
            if kernel.ktype == constants.K_PAE:
                suffix = "-PAE"
            elif kernel.ktype == constants.K_XEN:
                suffix = "-XEN"

            kname = "vmlinuz{0}".format(suffix)

            dst = joinpaths(workdir, kname)
            shutil.copy2(kernel.fpath, dst)

            # change the fname and fpath to new values
            self.kernels.append(DataHolder(fname=kname,
                                           fpath=dst,
                                           version=kernel.version,
                                           ktype=kernel.ktype))
