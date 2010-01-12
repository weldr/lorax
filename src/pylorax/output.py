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
import singleton


### color codes
C_DEFAULT       = "\x1b[39m"
C_RESET         = "\x1b[0m"

C_BLACK         = "\x1b[0;30m"
C_WHITE         = "\x1b[1;37m"
C_RED           = "\x1b[0;31m"
C_GREEN         = "\x1b[0;32m"
C_BLUE          = "\x1b[0;34m"
C_LIGHTRED      = "\x1b[1;31m"
C_LIGHTGREEN    = "\x1b[1;32m"
C_LIGHTBLUE     = "\x1b[1;34m"

C_BOLD          = "\x1b[1m"
C_UNDERLINE     = "\x1b[4m"

### font types
BOLD            = 0b01
UNDERLINE       = 0b10

### output levels
CRITICAL        = 50
ERROR           = 40
WARNING         = 30
INFO            = 20
DEBUG           = 10
NOTSET          = 0


class Terminal(singleton.Singleton):

    def __init__(self):
        self.__colors           = True
        self.__encoding         = "utf-8"
        self.__output_level     = INFO
        self.__indent_level     = 0

    def basic_config(self, colors=None, encoding=None, level=None):
        if colors is not None:
            self.__colors = colors

        if encoding is not None:
            self.__encoding = encoding

        if level is not None:
            self.__output_level = level

    def indent(self):
        self.__indent_level += 1

    def unindent(self):
        if self.__indent_level > 0:
            self.__indent_level -= 1

    def write(self, s, color=C_RESET, type=None, file=sys.stdout):
        s = self.format(s, color=color, type=type)
        file.write(s)
        file.flush()

    def format(self, s, color=C_RESET, type=None):
        s = s.encode(self.__encoding)

        if self.__colors:
            if type is not None and (type & BOLD):
                s = "%s%s" % (C_BOLD, s)
            if type is not None and (type & UNDERLINE):
                s = "%s%s" % (C_UNDERLINE, s)
            s = "%s%s%s" % (color, s, C_RESET)

        return s

    def writeline(self, s, color=C_RESET, type=None, file=sys.stdout):
        s = "%s%s" % ("    " * self.__indent_level, s)
        self.write(s + "\n", color=color, type=type, file=file)

    def critical(self, s, file=sys.stdout):
        if self.__output_level <= CRITICAL:
            self.writeline("** critical: %s" % s, file=file)

    def error(self, s, file=sys.stdout):
        if self.__output_level <= ERROR:
            self.writeline("** error: %s" % s, file=file)

    def warning(self, s, file=sys.stdout):
        if self.__output_level <= WARNING:
            self.writeline("** warning: %s" % s, file=file)

    def info(self, s, file=sys.stdout):
        if self.__output_level <= INFO:
            self.writeline(s, file=file)

    def debug(self, s, file=sys.stdout):
        if self.__output_level <= DEBUG:
            self.writeline(s, file=file)
