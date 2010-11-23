#
# base.py
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

from abc import ABCMeta, abstractmethod
import sys

import output


class BaseLoraxClass(object):

    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self):
        self.output = output.LoraxOutput()

    def pcritical(self, msg, file=sys.stdout):
        self.output.critical(msg, file)

    def perror(self, msg, file=sys.stdout):
        self.output.error(msg, file)

    def pwarning(self, msg, file=sys.stdout):
        self.output.warning(msg, file)

    def pinfo(self, msg, file=sys.stdout):
        self.output.info(msg, file)

    def pdebug(self, msg, file=sys.stdout):
        self.output.debug(msg, file)


class DataHolder(dict):

    def __getattr__(self, attr):
        return self[attr]

    def __setattr__(self, attr, value):
        self[attr] = value
