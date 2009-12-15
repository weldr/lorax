#
# __init__.py
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
