#
# genmodinfo.py
# generation of modinfo
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

import sys
import os
import commands


def genmodinfo(path, output):
    mods = {}
    for root, dirs, files in os.walk(path):
        for file in files:
            mods[file] = os.path.join(root, file)

    modules = { 'scsi_hostadapter': ['block'], 'eth': ['networking'] }
    blacklist = ('floppy', 'scsi_mod', 'libiscsi')

    list = {}
    for modtype in modules:
        list[modtype] = {}
        for file in modules[modtype]:
            try:
                filename = os.path.join(path, 'modules.%s' % file)
                f = open(filename, 'r')
            except IOError:
                sys.stderr.write('cannot open file %s\n', filename)
                continue
            else:
                lines = f.readlines()
                f.close()

            for line in lines:
                line = line.strip()
                if line in mods:
                    modname, ext = os.path.splitext(line)
                    if modname in blacklist:
                        continue

                    outtext = commands.getoutput('modinfo -F description %s' % mods[line])
                    desc = outtext.split('\n')[0]
                    desc = desc.strip()
                    desc = desc[:65]

                    if not desc:
                        desc = '%s driver' % modname
                        modinfo = '%s\n\t%s\n\t"%s"\n' % (modname, modtype, desc)
                        list[modtype][modname] = modinfo

    f = open(output, 'a')
    f.write('Version 0\n')
    for type in list:
        modlist = list[type].keys()
        modlist.sort()
        for m in modlist:
            f.write('%s\n' %list[type][m])
    f.close()
