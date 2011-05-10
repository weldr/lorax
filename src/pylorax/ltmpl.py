#
# ltmpl.py
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
import shlex

from mako.lookup import TemplateLookup
from mako.exceptions import RichTraceback


class LoraxTemplate(object):
    def __init__(self, directories=["/usr/share/lorax"]):
        # we have to add ["/"] to the template lookup directories or the
        # file includes won't work properly for absolute paths
        self.directories = ["/"] + directories

    def parse(self, template_file, variables):
        lookup = TemplateLookup(directories=self.directories)
        template = lookup.get_template(template_file)

        try:
            textbuf = template.render(**variables)
        except:
            traceback = RichTraceback()
            for (filename, lineno, function, line) in traceback.traceback:
                print "File %s, line %s, in %s" % (filename, lineno, function)
                print line

            sys.exit(2)

        # split, strip and remove empty lines
        lines = textbuf.splitlines()
        lines = map(lambda line: line.strip(), lines)
        lines = filter(lambda line: line, lines)

        # mako template now returns unicode strings
        lines = map(lambda line: line.encode("ascii"), lines)

        # split with shlex
        lines = map(shlex.split, lines)

        self.lines = lines
        return lines

    def getdata(self, cmd, mode="tokens"):
        '''returns a generator that yields every token on every line starting
        with 'cmd'. if mode is "lines", you get a list for each line instead.'''
        if mode == "lines":
            return (f[1:] for f in self.lines if f[0]==cmd)
        else:
            return (i for f in self.lines if f[0]==cmd for i in f[1:])
