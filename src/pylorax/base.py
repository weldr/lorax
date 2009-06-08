# pylorax/base.py

import commands


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
