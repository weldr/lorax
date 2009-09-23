#
# misc.py
# miscellaneous functions
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

import commands


def seq(arg):
    if type(arg) not in (type([]), type(())):
        return [arg]
    else:
        return arg

def get_console_size():
    err, output = commands.getstatusoutput("stty size")
    if not err:
        height, width = output.split()
        height, width = int(height), int(width)
    else:
        # set defaults
        height, width = 24, 80
    
    return height, width
