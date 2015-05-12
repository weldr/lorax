import sys
import os
import magic
import difflib
import yum          # pylint: disable=import-error
import operator


def main(args):
    try:
        sourcedir, targetdir = args[1], args[2]
    except IndexError:
        print("invalid argument count")
        print("usage: python {0} sourcetree targettree".format(args[0]))
        sys.exit(2)

    if sourcedir.endswith("/"):
        sourcedir = sourcedir[:-1]
    if targetdir.endswith("/"):
        targetdir = targetdir[:-1]

    # parse sourcedir and targetdir
    sourcetree, targettree = {}, {}
    for tree, d in [[sourcetree, sourcedir], [targettree, targetdir]]:
        for root, _dnames, fnames in os.walk(d):
            for fname in fnames:
                fpath = os.path.join(root, fname)
                rpath = fpath.replace(d, "", 1)
                tree[rpath] = fpath

    # set up magic
    m = magic.open(magic.MAGIC_NONE)
    m.load()

    # get files missing in source
    sys.stderr.write("getting files missing in source\n")
    for rpath in sorted(targettree.keys()):
        fpath = targettree[rpath]

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

        # diff only text files
        ftype = m.file(fpath)
        if ftype not in ["ASCII text"]:
            continue

        with open(targetfile, "r") as fobj:
            target = fobj.readlines()
        with open(sourcefile) as fobj:
            source = fobj.readlines()

        # do the file diff
        for line in difflib.unified_diff(source, target,
                                         fromfile=sourcefile,
                                         tofile=targetfile):

            sys.stdout.write(line)

    # set up yum

    # XXX HACK
    # we don't want yum's stuff in the output
    # so we redirect stdout to /dev/null for a while...
    stdout = os.dup(1)
    null = open("/dev/null", "w")
    os.dup2(null.fileno(), 1)

    # here yum prints out some stuff we really don't care about
    yb = yum.YumBase()
    yb.doSackSetup()

    # give the stdout back
    os.dup2(stdout, 1)
    null.close()

    # get excessive files in source
    sys.stderr.write("getting excessive files in source\n")
    sizedict, pkgdict = {}, {}
    for rpath, fpath in sourcetree.items():
        # if file in target, skip it
        if rpath in targettree:
            continue

        # get file size
        try:
            sizeinbytes = os.path.getsize(fpath)
        except OSError:
            sizeinbytes = 0

        # set link size to 0
        islink = os.path.islink(fpath)
        if islink:
            sizeinbytes = 0

        pkglist = yb.whatProvides(rpath, None, None)
        pkglist = set(map(lambda pkgobj: pkgobj.name, pkglist))

        for pkg in pkglist:
            sizedict[pkg] = sizedict.get(pkg, 0) + sizeinbytes
            pkgdict[pkg] = pkgdict.get(pkg, []) + \
                           [(rpath, sizeinbytes, islink)]

    # sort by size
    for pkg, _size in sorted(sizedict.items(), key=operator.itemgetter(1),
                            reverse=True):

        for item in sorted(pkgdict[pkg]):
            sys.stdout.write("%s\t%s\n" % (pkg, item))


if __name__ == "__main__":
    main(sys.argv)
