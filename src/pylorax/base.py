#
# base.py
#
# Copyright (C) 2009-2015 Red Hat, Inc.
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

import pylorax.output as output


class BaseLoraxClass(object, metaclass=ABCMeta):
    @abstractmethod
    def __init__(self):
        self.output = output.LoraxOutput()

    def pcritical(self, msg, fobj=sys.stdout):
        self.output.critical(msg, fobj)

    def perror(self, msg, fobj=sys.stdout):
        self.output.error(msg, fobj)

    def pwarning(self, msg, fobj=sys.stdout):
        self.output.warning(msg, fobj)

    def pinfo(self, msg, fobj=sys.stdout):
        self.output.info(msg, fobj)

    def pdebug(self, msg, fobj=sys.stdout):
        self.output.debug(msg, fobj)


class DataHolder(dict):

    def __init__(self, **kwargs):
        dict.__init__(self)

        for attr, value in kwargs.items():
            self[attr] = value

    def __getattr__(self, attr):
        if attr in self:
            return self[attr]
        else:
            raise AttributeError

    def __setattr__(self, attr, value):
        self[attr] = value

    def copy(self):
        return DataHolder(**dict.copy(self))
