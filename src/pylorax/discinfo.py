#
# discinfo.py
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
logger = logging.getLogger("pylorax.discinfo")

import time
from sysutils import *


class DiscInfo(object):

    def __init__(self, workdir, release, basearch, discnum="ALL"):
        self.path = joinpaths(workdir, ".discinfo")

        self.release = release
        self.basearch = basearch
        self.discnum = discnum

    def write(self):
        logger.info("writing .discinfo file")
        with open(self.path, "w") as fobj:
            fobj.write("{0:f}\n".format(time.time()))
            fobj.write("{0}\n".format(self.release))
            fobj.write("{0}\n".format(self.basearch))
            fobj.write("{0}\n".format(self.discnum))
