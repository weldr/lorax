#
# ldd.py
# library dependencies
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
import commands
import re


class LDD(object):
    def __init__(self, libroots=['/lib', '/usr/lib']):
        f = open('/usr/bin/ldd', 'r')
        for line in f.readlines():
            line = line.strip()
            if line.startswith('RTLDLIST='):
                rtldlist, sep, ld_linux = line.partition('=')
                break
        f.close()

        self._ldd = 'LD_LIBRARY_PATH="%s" %s --list' % (':'.join(libroots), ld_linux)
        self._deps = set()

    def getDeps(self, filename):
        rc, output = commands.getstatusoutput('%s %s' % (self._ldd, filename))

        if rc:
            return

        lines = output.splitlines()
        for line in lines:
            line = line.strip()

            m = re.match(r'^[a-zA-Z0-9.]*\s=>\s(?P<lib>[a-zA-Z0-9./]*)\s\(0x[0-9a-f]*\)$', line)
            if m:
                lib = m.group('lib')
                if lib not in self._deps:
                    self._deps.add(lib)
                    self.getDeps(lib)

    def getLinks(self):
        targets = set()
        for lib in self._deps:
            if os.path.islink(lib):
                targets.add(os.path.realpath(lib))

        self._deps.update(targets)

    @property
    def deps(self):
        return self._deps
