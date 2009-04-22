import os
import shutil
import glob


def cp(src, dst, verbose=False):
    for name in glob.iglob(src):
        __copy(name, dst, verbose=verbose)

def mv(src, dst, verbose=False):
    for name in glob.iglob(src):
        __copy(name, dst, verbose=verbose, remove=True)


def __copy(src, dst, verbose=False, remove=False):
    if not os.path.exists(src):
        print('cannot stat "%s": No such file or directory' % (src,))
        return

    if os.path.isdir(dst):
        basename = os.path.basename(src)
        dst = os.path.join(dst, basename)

    if os.path.isdir(src):
        if os.path.isfile(dst):
            print('omitting directory "%s"' % (src,))
            return

        if not os.path.isdir(dst):
            os.makedirs(dst)

        names = map(lambda name: os.path.join(src, name), os.listdir(src))
        for name in names:
            __copy(name, dst, verbose=verbose, remove=remove)
    else:
        if os.path.isdir(dst):
            print('cannot overwrite directory "%s" with non-directory' % (dst,))
            return

        try:
            if verbose:
                print('copying "%s" to "%s"' % (src, dst))
            shutil.copy2(src, dst)
        except shutil.Error, IOError:
            print('cannot copy "%s" to "%s"' % (src, dst))
        else:
            if remove:
                if verbose:
                    print('removing "%s"' % (src,))
                os.unlink(src)
