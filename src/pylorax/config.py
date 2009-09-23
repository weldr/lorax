#
# config.py
# lorax configuration
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

from misc import seq


class Container(object):

    def __init__(self, attrs=None):
        self.__dict__["__internal"] = {}
        self.__dict__["__internal"]["attrs"] = set()

        if attrs:
            self.addAttr(attrs)

    def __str__(self):
        return str(self.__makeDict())

    def __iter__(self):
        return iter(self.__makeDict())

    def __getitem__(self, attr):
        self.__checkInternal(attr)

        if attr not in self.__dict__:
            raise AttributeError, "object has no attribute '%s'" % attr

        return self.__dict__[attr]

    def __setattr__(self, attr, value):
        raise AttributeError, "you can't do that, use addAttr() and/or set() instead"

    def __delattr__(self, attr):
        raise AttributeError, "you can't do that, use delAttr() instead"

    def addAttr(self, attrs):
        for attr in filter(lambda attr: attr not in self.__dict__, seq(attrs)):
            self.__checkInternal(attr)

            self.__dict__[attr] = None
            self.__dict__["__internal"]["attrs"].add(attr)

    def delAttr(self, attrs):
        for attr in filter(lambda attr: attr in self.__dict__, seq(attrs)):
            self.__checkInternal(attr)

            del self.__dict__[attr]
            self.__dict__["__internal"]["attrs"].discard(attr)

    def set(self, **kwargs):
        unknown = set()
        for attr, value in kwargs.items():
            self.__checkInternal(attr)

            if attr in self.__dict__:
                self.__dict__[attr] = value
            else:
                unknown.add(attr)

        return unknown

    def __makeDict(self):
        d = {}
        for attr in self.__dict__["__internal"]["attrs"]:
            d[attr] = self.__dict__[attr]

        return d

    def __checkInternal(self, attr):
        if attr.startswith("__"):
            raise AttributeError, "do not mess with internal objects"
