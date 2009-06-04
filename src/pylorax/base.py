# pylorax/base.py

import commands


class LoraxAction(object):

    REGEX = r'.*'

    def __init__(self):
        if self.__class__ is LoraxAction:
            raise TypeError, 'LoraxAction is an abstract class'

        self._attrs = {}
        self._attrs['success'] = None

    def __str__(self):
        return '%s: %s' % (self.__class__.__name__, self._attrs)

    def execute(self, verbose=False):
        raise NotImplementedError, 'execute method not implemented for LoraxAction class'

    @property
    def success(self):
        return self._attrs['success']


def seq(arg):
    if type(arg) not in (type([]), type(())):
        return [arg]
    else:
        return arg


def getConsoleSize():
    err, output = commands.getstatusoutput('stty size')
    if not err:
        height, width = output.split()
    else:
        # set defaults
        height, width = 24, 80
    
    return int(height), int(width)
