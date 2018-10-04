#
# discinfo.py
#
# Copyright (C) 2010-2015  Red Hat, Inc.
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

import os
import time


class DiscInfo(object):

    def __init__(self, release, basearch):
        self.release = release
        self.basearch = basearch

    def write(self, outfile):
        if 'SOURCE_DATE_EPOCH' in os.environ:
            timestamp = int(os.environ['SOURCE_DATE_EPOCH'])
        else:
            timestamp = time.time()

        logger.info("writing .discinfo file")
        with open(outfile, "w") as fobj:
            fobj.write("{0:f}\n".format(timestamp))
            fobj.write("{0.release}\n".format(self))
            fobj.write("{0.basearch}\n".format(self))
