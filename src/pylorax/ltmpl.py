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

from mako.template import Template as MakoTemplate
from mako.lookup import TemplateLookup as MakoTemplateLookup


class Template(object):

    def parse(self, template_file, variables):
        # we have to set the template lookup directories to ["/"],
        # otherwise the file includes will not work properly
        lookup = MakoTemplateLookup(directories=["/"])
        template = MakoTemplate(filename=template_file, lookup=lookup)
        s = template.render(**variables)

        # enumerate, strip and remove empty lines
        lines = enumerate(s.splitlines(), start=1)
        lines = map(lambda (n, line): (n, line.strip()), lines)
        lines = filter(lambda (n, line): line, lines)
        return lines
