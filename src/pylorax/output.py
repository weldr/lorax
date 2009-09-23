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

# font types
BOLD            = 0b01
UNDERLINE       = 0b10


class OutputError(Exception):
    pass

class Output(object):

    def __init__(self, output=sys.stdout, colors=True, encoding="utf-8",
            verbose=False):

        self.output = output
        if not hasattr(self.output, "write"):
            raise OutputError, "output does not support write()"
        
        self.is_flushable = hasattr(self.output, "flush")

        self.colors = colors
        self.encoding = encoding
        self.verbose = verbose

        self.__indent_level = 0

    def write(self, s, color=C_RESET, type=None):
        s = self.format(s, color=color, type=type)
        self.output.write(s)

        if self.is_flushable:
            self.output.flush()

    def format(self, s, color=C_RESET, type=None):
        s = s.encode(self.encoding)
        
        if self.colors:
            if type is not None and (type & BOLD):
                s = "%s%s" % (C_BOLD, s)
            if type is not None and (type & UNDERLINE):
                s = "%s%s" % (C_UNDERLINE, s)
            s = "%s%s%s" % (color, s, C_RESET)
        
        return s

    def writeline(self, s, color=C_RESET, type=None):
        s = "%s%s\n" % ("    " * self.__indent_level, s)
        self.write(s, color=color, type=type)

    def indent(self):
        self.__indent_level += 1

    def unindent(self):
        if self.__indent_level > 0:
            self.__indent_level -= 1

    def newline(self):
        self.output.write("\n")

    def banner(self, s, indent_level=0):
        self.writeline(s, color=C_GREEN, type=BOLD)

    def header(self, s, indent_level=0):
        self.writeline(s, type=BOLD)

    def info(self, s, indent_level=0):
        self.writeline(s)

    def error(self, s, indent_level=0):
        self.writeline(s, color=C_RED, type=BOLD)

    def warning(self, s, indent_level=0):
        self.writeline(s, color=C_RED)

    def debug(self, s, indent_level=0):
        if self.verbose:
            self.writeline(s)


def initialize(verbose=False):
    stdout = Output(output=sys.stdout, verbose=verbose)
    stderr = Output(output=sys.stderr, verbose=verbose)
    
    return stdout, stderr
