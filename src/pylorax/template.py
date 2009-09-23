#
# template.py
# initrd template class
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


class TemplateError(Exception):
    pass

class Template(object):
    def __init__(self):
        self._actions = []

        self.lines = []
        self.included_files = []

    def preparse(self, filename):
        try:
            f = open(filename, 'r')
        except IOError as why:
            sys.stderr.write("ERROR: Unable to open template file '%s': %s\n" % (filename, why))
            return False
        else:
            lines = f.readlines()
            f.close()

        self.included_files.append(filename)
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('#include'):
                file_to_include = line.split()[1]
                path = os.path.join(os.path.dirname(filename), file_to_include)
                if path not in self.included_files:
                    self.preparse(path)
            else:
                self.lines.append(line)

    def parse(self, supported_actions, variables):
        lines = self.lines

        # append next line if line ends with '\'
        temp = []
        for line in lines:
            line = line.strip()
            if line.endswith('\\'):
                line = line[:-1]
                line = line.rstrip()
                line = line + ' '
            else:
                line = line + '\n'
            temp.append(line)
        temp = ''.join(temp)
        lines = temp.splitlines()

        # check template variables
        for lineno, line in enumerate(lines, start=1):
            for var in filter(lambda var: var not in variables, re.findall(r'@(.*?)@', line)):
                raise TemplateError, "unknown variable '%s' on line %d" % (var, lineno)

        # parse the template
        for lineno, line in enumerate(lines, start=1):
            line, sep, comment = line.partition('#')
            if not line:
                continue

            # expand variables
            for var, value in variables.items():
                line = re.sub(r'@%s@' % var, value, line)

            # get the command
            command, line = line.split(None, 1)
            if command not in supported_actions:
                raise TemplateError, "unknown command '%s' on line %d" % (command, lineno)

            # create the action object
            regex = supported_actions[command].REGEX
            m = re.match(regex, line)
            if m:
                new_action = supported_actions[command](**m.groupdict())
                self._actions.append(new_action)
            else:
                # didn't match the regex
                raise TemplateError, "invalid command format '%s' on line %d" % (line, lineno)

        return True

    @property
    def actions(self):
        return self._actions

