import sys
import os
import commands
import re
import socket

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('pylorax')


def genmodinfo(path, output):
    mods = {}
    for root, dirs, files in os.walk(path):
        for file in files:
            mods[file] = os.path.join(root, file)

    modules = { 'scsi_hostadapter': ['block'], 'eth': ['networking'] }
    blacklist = ('floppy', 'scsi_mod', 'libiscsi')

    list = {}
    for modtype in modules:
        list[modtype] = {}
        for file in modules[modtype]:
            try:
                filename = os.path.join(path, 'modules.%s' % file)
                f = open(filename, 'r')
            except IOError:
                logger.error('cannot open file %s', filename)
                continue
            else:
                lines = f.readlines()
                f.close()

            for line in lines:
                line = line.strip()
                if line in mods:
                    modname, ext = os.path.splitext(line)
                    if modname in blacklist:
                        logger.info('skipping %s', modname)
                        continue

                    outtext = commands.getoutput('modinfo -F description %s' % mods[line])
                    desc = outtext.split('\n')[0]
                    desc = desc.strip()

                    # XXX why we need to do this?
                    desc = desc[:65]

                    if not desc:
                        desc = '%s driver' % modname
                        modinfo = '%s\n\t%s\n\t"%s"\n' % (modname, modtype, desc)
                        list[modtype][modname] = modinfo

    f = open(output, 'a')
    f.write('Version 0\n')
    for type in list:
        modlist = list[type].keys()
        modlist.sort()
        for m in modlist:
            f.write('%s\n' %list[type][m])
    f.close()


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


# XXX what are the inputs for this thing?
def trimpciids(pciids, *paths):
    vendors = []
    devices = []

    for file in paths:
        try:
            f = open(file, 'r')
        except IOError:
            logger.error('cannot open file %s', file)
            continue
        else:
            pcitable = f.readlines()
            f.close()

        for line in pcitable:
            if line.startswith('alias pci:'):
                vend = '0x%s' % line[15:19]
                dev = '0x%s' % line[24:28]
            elif line.startswith('alias pcivideo:'):
                vend = '0x%s' % line[20:24]
                dev = '0x%s' % line[29:33]
            else:
                continue

        vend = vend.upper()
        dev = dev.upper()
        if vend not in vendors:
            vendors.append(vend)
        if (vend, dev) not in devices:
            devices.append((vend, dev))

    current_vend = 0
    for line in pciids:
        if line.startswith('#') or line.startswith('\t\t') or line == '\n':
            continue

        # XXX print or return?
        if not line.startswith('\t'):
            current_vend = '0x%s' % line.split()[0]
            current_vend = current_vend.upper()
            if current_vend in vendors:
                print line,
            continue

        # XXX print or return?
        dev = '0x%s' % line.split()[0]
        dev = dev.upper()
        if (current_vend, dev) in devices:
            print line,


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
