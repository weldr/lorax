# pylorax/config.py

import sys

from base import seq
import re

from exceptions import TemplateError


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
        raise AttributeError, 'you cannot do that, use addAttr() and set() instead'

    def __delattr__(self, attr):
        raise AttributeError, 'you cannot do that, use delAttr() instead'

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
            raise AttributeError, 'do not mess with internal stuff'


class Template(object):
    def __init__(self):
        self._actions = []

    def parse(self, filename, supported_actions):
        try:
            f = open(filename, 'r')
        except IOError:
            sys.stdout.write('ERROR: Unable to open the template file\n')
            return False
        else:
            lines = f.readlines()
            f.close()

        active_action = ''
        in_action = False
        for lineno, line in enumerate(lines, start=1):
            line = line.strip()

            if not line or line.startswith('#'):
                continue

            if in_action and not line.startswith(':'):
                # create the action object
                regex = supported_actions[active_action].REGEX
                m = re.match(regex, line)
                if m:
                    new_action = supported_actions[active_action](**m.groupdict())
                    self._actions.append(new_action)
                else:
                    # didn't match the regex
                    raise TemplateError, 'invalid action format "%s" on line %d' % (line, lineno)

            if in_action and line.startswith(':'):
                in_action = False

            if not in_action and line.startswith(':'):
                active_action = line[1:]

                if active_action not in supported_actions:
                    raise TemplateError, 'unknown action "%s" on line %d' % (active_action, lineno)
                else:
                    in_action = True
                    continue
        
        return True

    @property
    def actions(self):
        return self._actions
