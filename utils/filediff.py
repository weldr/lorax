import sys
import os
import magic
import difflib


def main(args):
    try:
        sourcedir, targetdir = args[1], args[2]
    except IndexError:
        print("invalid argument count")
        print("usage: python {0} sourcetree targettree > output.diff".format(
              args[0]))

        sys.exit(2)

    if sourcedir.endswith("/"):
        sourcedir = sourcedir[:-1]
    if targetdir.endswith("/"):
        targetdir = targetdir[:-1]

    sourcetree = {}
    for root, dnames, fnames in os.walk(sourcedir):
        for fname in fnames:
            fpath = os.path.join(root, fname)
            rpath = fpath.replace(sourcedir, "", 1)
            sourcetree[rpath] = fpath

    m = magic.open(magic.MAGIC_NONE)
    m.load()

    for root, dnames, fnames in os.walk(targetdir):
        for fname in fnames:
            fpath = os.path.join(root, fname)
            rpath = fpath.replace(targetdir, "", 1)

            sys.stderr.write('processing "%s"\n' % rpath)

            targetfile = fpath
            try:
                sourcefile = sourcetree[rpath]
            except KeyError:
                sys.stdout.write('Missing: %s\n' % rpath)
                continue

            # skip broken links
            if os.path.islink(targetfile) and not os.path.exists(targetfile):
                continue

            # check stat
            #sourcemode = os.stat(sourcefile).st_mode
            #targetmode = os.stat(targetfile).st_mode
            #if sourcemode != targetmode:
            #    sys.stdout.write('Stat differ: %s\n' % rpath)

            ftype = m.file(fpath)

            # diff only text files
            if ftype not in ["ASCII text"]:
                continue

            with open(targetfile, "r") as fobj:
                target = fobj.readlines()
            with open(sourcefile) as fobj:
                source = fobj.readlines()

            # do a file diff
            for line in difflib.unified_diff(source, target,
                                             fromfile=sourcefile,
                                             tofile=targetfile):

                sys.stdout.write(line)


if __name__ == "__main__":
    main(sys.argv)
