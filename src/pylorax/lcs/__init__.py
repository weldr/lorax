#
# __init__.py
# lorax control system classes
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
import re

from mako.template import Template as MakoTemplate
from mako.lookup import TemplateLookup as MakoTemplateLookup

import actions


class TemplateParserError(Exception):
    pass


class TemplateParser(object):

    def __init__(self, variables):
        self.variables = variables
        self.actions_map = actions.get_map()

    def get_actions(self, file):
        template_actions = []

        # we have to set the template lookup directories to ["/"],
        # otherwise the relative and absolute includes don't work properly
        lookup = MakoTemplateLookup(directories=["/"])
        template = MakoTemplate(filename=file, lookup=lookup)
        s = template.render(**self.variables)

        # concatenate lines ending with "\"
        #s = re.sub(r"\s*\\\s*\n", " ", s)

        for lineno, line in enumerate(s.splitlines(), start=1):
            # remove multiple whitespaces
            line = re.sub(r"\s+", " ", line.strip())
            if not line:
                continue

            # get the command
            command, line = line.split(None, 1)
            if command not in self.actions_map:
                raise TemplateParserError("%s: %d: invalid command" % \
                                          (file, lineno))

            # create the action object
            m = re.match(self.actions_map[command].REGEX, line)
            if m:
                new_action = self.actions_map[command](**m.groupdict())
                template_actions.append(new_action)
            else:
                raise TemplateParserError("%s: %d: invalid command format" % \
                                          (file, lineno))

        return template_actions
