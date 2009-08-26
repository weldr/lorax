import sys
import os
import shutil
import glob
import fileinput
import re


def cp(src, dst, mode=None, verbose=False):
    errors = []
    for name in glob.iglob(src):
        rc = __copy(name, dst, verbose=verbose)
        if not rc:
            errors.append("unable to copy '%s' to '%s'" % (name, dst))
        else:
            if mode:
                os.chmod(dst, int(mode))

    return errors

def mv(src, dst, mode=None, verbose=False):
    errors = []
    for name in glob.iglob(src):
        rc = __copy(name, dst, verbose=verbose, remove=True)
        if not rc:
            errors.append("unable to move '%s' to '%s'" % (name, dst))
        else:
            if mode:
                os.chmod(dst, int(mode))

    return errors

def rm(target, verbose=False):
    for name in glob.iglob(target):
        if os.path.islink(name):
            os.unlink(name)
        else:
            if os.path.isdir(name):
                if verbose:
                    print("removing directory '%s'" % name)
                shutil.rmtree(name, ignore_errors=True)
            else:
                if verbose:
                    print("removing file '%s'" % name)
                os.unlink(name)

    return True


def __copy(src, dst, verbose=False, remove=False):
    if not os.path.exists(src):
        sys.stderr.write("cannot stat '%s': No such file or directory\n" % src)
        return False

    if os.path.isdir(dst):
        basename = os.path.basename(src)
        dst = os.path.join(dst, basename)
    
    if os.path.islink(src):
        print('Got link %s' % src)
        target = os.readlink(src)

        if os.path.exists(dst):
            os.unlink(dst)
        os.symlink(target, dst)

        if remove:
            if verbose:
                print("removing '%s'" % src)
            os.unlink(src)

        return True

    if os.path.isdir(src):
        if os.path.isfile(dst):
            sys.stderr.write("omitting directory '%s'\n" % src)
            return False

        if not os.path.isdir(dst):
            os.makedirs(dst)

        names = map(lambda name: os.path.join(src, name), os.listdir(src))
        for name in names:
            __copy(name, dst, verbose=verbose, remove=remove)
    else:
        if os.path.isdir(dst):
            sys.stderr.write("cannot overwrite directory '%s' with non-directory\n" % dst)
            return False

        try:
            if verbose:
                print("copying '%s' to '%s'" % (src, dst))
            
            if os.path.exists(dst):
                os.unlink(dst)

            shutil.copy2(src, dst)
        except (shutil.Error, IOError) as why:
            sys.stderr.write("cannot copy '%s' to '%s': %s\n" % (src, dst, why))
            return False
        else:
            if remove:
                if verbose:
                    print("removing '%s'" % src)
                os.unlink(src)
    
    return True


def touch(filename, verbose=False):
    if os.path.exists(filename):
        if verbose:
            print("touching file '%s'" % filename)
        os.utime(filename, None)
        return True

    try:
        if verbose:
            print("creating file '%s'" % filename)
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
        if verbose:
            print("editing file '%s'" % filename)
        f = open(filename, mode)
    except IOError:
        return False
    else:
        f.write(text)
        f.close()
        return True

def replace(filename, find, replace, verbose=False):
    if verbose:
        print("replacing '%s' for '%s' in file '%s'" % (find, replace, filename))
    fin = fileinput.input(filename, inplace=1)
    for line in fin:
        line = re.sub(find, replace, line)
        sys.stdout.write(line)
    fin.close()
    return True
