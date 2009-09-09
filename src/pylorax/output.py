#
# output.py
# output control
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


# color codes
C_DEFAULT       = "\x1b[39m"
C_RESET         = "\x1b[0m"

C_BOLD          = "\x1b[1m"
C_UNDERLINE     = "\x1b[4m"

C_BLACK         = "\x1b[0;30m"
C_WHITE         = "\x1b[1;37m"
C_RED           = "\x1b[0;31m"
C_GREEN         = "\x1b[0;32m"
C_BLUE          = "\x1b[0;34m"
C_LIGHTRED      = "\x1b[1;31m"
C_LIGHTGREEN    = "\x1b[1;32m"
C_LIGHTBLUE     = "\x1b[1;34m"

C_LIGHTGRAY     = "\x1b[0;37m"
C_DARKGRAY      = "\x1b[1;30m"


class Output(object):

    def __init__(self, output=sys.stdout, colors=True, encoding=None, verbose=False):
        self.output = output
        self.is_flushable = hasattr(self.output, "flush")

        self.colors = colors
        if encoding is None:
            encoding = "utf-8"
        self.encoding = encoding

        self.verbose = verbose

    def write(self, s, color=C_RESET, bold=False, underline=False):
        self.output.write(self.compose(s, color=color, bold=bold, underline=underline))

        if self.is_flushable:
            self.output.flush()

    def compose(self, s, color=C_RESET, bold=False, underline=False):
        s = s.encode(self.encoding)
        
        if self.colors:
            if bold:
                s = "%s%s" % (C_BOLD, s)
            if underline:
                s = "%s%s" % (C_UNDERLINE, s)
            s = "%s%s%s" % (color, s, C_RESET)
        
        return s

    def writeline(self, s, color=C_RESET, bold=False, underline=False):
        self.write("%s\n" % (s,), color=color, bold=bold, underline=underline)

    def banner(self, s):
        self.writeline(s, color=C_BLUE, bold=True)

    def header(self, s):
        self.writeline(s, bold=True)

    def info(self, s):
        self.writeline(s)

    def error(self, s):
        self.writeline(s, color=C_RED, bold=True)

    def debug(self, s):
        if self.verbose:
            self.writeline(s)


def initialize(verbose=False):
    stdout = Output(output=sys.stdout, verbose=verbose)
    stderr = Output(output=sys.stderr, verbose=verbose)
    
    return stdout, stderr
