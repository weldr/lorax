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

from mako.template import Template
from mako.lookup import TemplateLookup
from mako.exceptions import RichTraceback


class LoraxTemplate(object):

    def parse(self, template_file, variables):
        # we have to set the template lookup directories to ["/"],
        # otherwise the file includes will not work properly
        lookup = TemplateLookup(directories=["/"])
        template = Template(filename=template_file, lookup=lookup)

        try:
            s = template.render(**variables)
        except:
            traceback = RichTraceback()
            for (filename, lineno, function, line) in traceback.traceback:
                print "File %s, line %s, in %s" % (filename, lineno, function)
                print line

            sys.exit(2)

        # split, strip and remove empty lines
        lines = s.splitlines()
        lines = map(lambda line: line.strip(), lines)
        lines = filter(lambda line: line, lines)

        # split with shlex
        lines = map(lambda line: shlex.split(line), lines)

        return lines
