# pylorax/config.py

import sys
import re
from errors import TemplateError

from utils.rpmutils import seq


class Container(object):
    def __init__(self, attrs=None):
        self.__dict__['__internal'] = {}
        self.__dict__['__internal']['attrs'] = set()

        if attrs:
            self.addAttr(attrs)

    def __str__(self):
        return str(self.__makeDict())

    def __iter__(self):
        return iter(self.__makeDict())

    def __getitem__(self, attr):
        self.__checkInternal(attr)

        if attr not in self.__dict__:
            raise AttributeError, "'Container' object has no attribute '%s'" % attr

        return self.__dict__[attr]

    def __setattr__(self, attr, value):
        raise AttributeError, "you can't do that, use addAttr() and/or set()"

    def __delattr__(self, attr):
        raise AttributeError, "you can't do that, use delAttr()"

    def addAttr(self, attrs):
        for attr in filter(lambda attr: attr not in self.__dict__, seq(attrs)):
            self.__checkInternal(attr)

            self.__dict__[attr] = None
            self.__dict__['__internal']['attrs'].add(attr)

    def delAttr(self, attrs):
        for attr in filter(lambda attr: attr in self.__dict__, seq(attrs)):
            self.__checkInternal(attr)

            del self.__dict__[attr]
            self.__dict__['__internal']['attrs'].discard(attr)

    def set(self, **kwargs):
        unknown = set()
        for attr, value in kwargs.items():
            self.__checkInternal(attr)

            if attr in self.__dict__:
                self.__dict__[attr] = value
            else:
                unknown.add(attr)

        return unknown

    def __makeDict(self):
        d = {}
        for attr in self.__dict__['__internal']['attrs']:
            d[attr] = self.__dict__[attr]

        return d

    def __checkInternal(self, attr):
        if attr.startswith('__'):
            raise AttributeError, "do not mess with internal objects"


class Template(object):
    def __init__(self):
        self._actions = []

    def parse(self, filename, supported_actions, variables):
        try:
            f = open(filename, 'r')
        except IOError as why:
            sys.stderr.write("ERROR: Unable to open template file '%s': %s\n" % (filename, why))
            return False
        else:
            lines = f.readlines()
            f.close()

        # check template variables
        for lineno, line in enumerate(lines, start=1):
            for var in filter(lambda var: var not in variables, re.findall(r'@(.*?)@', line)):
                raise TemplateError, "unknown variable '%s' on line %d" % (var, lineno)

        # parse the template
        for lineno, line in enumerate(lines, start=1):
            line = line.strip()

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
