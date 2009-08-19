import sys
import os
import commands
import re
import socket

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('pylorax')

# XXX is the input a path to a file?
def filtermoddeps(input):
    try:
        f = open(input, 'r')
    except IOError:
        logger.error('cannot open file %s', input)
        return
   
    # concatenate lines ending with \
    lines = []
    for line in f.readlines():
        if line.endswith('\\\n'):
            line = line[:-2]
        lines.append(line)

    f.close()

    lines = ''.join(lines).split('\n')

    # XXX what's the purpose of these gentlemen?
    lines = filter(lambda line: re.search(':.*ko', line), lines)
    lines = map(lambda line: re.sub('\.ko', '', line), lines)
    lines = map(lambda line: re.sub('/[^:  ]*/', '', line), lines)
    lines = map(lambda line: re.sub('\t+', ' ', line), lines)
    
    return lines

# XXX what is this whole thing for?
def geninitrdsz(size, filename):
    size = socket.htonl(size)
    
    try:
        f = open(filename, 'w')
    except IOError:
        logger.error('cannot open file %s', filename)
    else:
        f.write(str(size))
        f.close()

        # XXX is this needed? default mode is 0664
        os.chmod(filename, 0644)
