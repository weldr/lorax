# pylorax/utils/fileutil.py

import sys
import os
import shutil
import glob
import fileinput
import re


def cp(src, dst, mode=None, verbose=False):
    for name in glob.iglob(src):
        __copy(name, dst, verbose=verbose)
        if mode:
            os.chmod(dst, mode)

def mv(src, dst, mode=None, verbose=False):
    for name in glob.iglob(src):
        __copy(name, dst, verbose=verbose, remove=True)
        if mode:
            os.chmod(dst, mode)

def rm(target, verbose=False):
    if os.path.isdir(target):
        if verbose:
            print('removing directory "%s"' % target)
        shutil.rmtree(target, ignore_errors=True)
    else:
        if verbose:
            print('removing file "%s"' % target)
        os.unlink(target)

def __copy(src, dst, verbose=False, remove=False):
    if not os.path.exists(src):
        sys.stderr.write('cannot stat "%s": No such file or directory\n' % src)
        return

    if os.path.isdir(dst):
        basename = os.path.basename(src)
        dst = os.path.join(dst, basename)

    if os.path.isdir(src):
        if os.path.isfile(dst):
            sys.stderr.write('omitting directory "%s"\n' % src)
            return

        if not os.path.isdir(dst):
            os.makedirs(dst)

        names = map(lambda name: os.path.join(src, name), os.listdir(src))
        for name in names:
            __copy(name, dst, verbose=verbose, remove=remove)
    else:
        if os.path.isdir(dst):
            sys.stderr.write('cannot overwrite directory "%s" with non-directory\n' % dst)
            return

        try:
            if verbose:
                print('copying "%s" to "%s"' % (src, dst))
            shutil.copy2(src, dst)
        except (shutil.Error, IOError) as why:
            sys.stderr.write('cannot copy "%s" to "%s": %s\n' % (src, dst, why))
        else:
            if remove:
                if verbose:
                    print('removing "%s"' % src)
                os.unlink(src)


def touch(filename, verbose=False):
    if os.path.exists(filename):
        os.utime(filename, None)
        return True

    try:
        f = open(filename, 'w')
    except IOError:
        return False
    else:
        f.close()
        return True

def edit(filename, text, append=False, verbose=False):
    mode = 'w'
    if append:
        mode = 'a'

    try:
        f = open(filename, mode)
    except IOError:
        return False
    else:
        f.write(text)
        f.close()
        return True

def replace(filename, find, replace, verbose=False):
    fin = fileinput.input(filename, inplace=1)
    for line in fin:
        line = re.sub(find, replace, line)
        sys.stdout.write(line)
    fin.close()
    return True
