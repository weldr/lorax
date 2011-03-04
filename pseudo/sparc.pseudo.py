# sparc.pseudo.py


##### constants #####

ANABOOTDIR = "usr/share/anaconda/boot"

IMAGESDIR = "images"

SPARCDIR = "boot"

ISOPATHDIR = "isopath"

MKISOFS = "mkisofs"
IMPLANTISOMD5 = "implantisomd5"


##### main() #####

""" kernellist, installroot, outputroot, product, version, treeinfo, bootiso

"""

# create directories
makedirs(joinpaths(outputroot, IMAGESDIR))
makedirs(joinpaths(outputroot, SPARCDIR))

# copy silo.conf
siloconf = copy(joinpaths(installroot, ANABOOTDIR, "silo.conf"),
                joinpaths(outputroot, SPARCDIR))

# copy boot.msg
bootmsg = copy(joinpaths(installroot, ANABOOTDIR, "boot.msg"),
               joinpaths(outputroot, SPARCDIR))

replace(bootmsg, "%PRODUCT%", product)
replace(bootmsg, "%VERSION%", version)

# copy  *.b to sparc dir
copy(joinpaths(installroot, ANABOOTDIR, "*.b"),
     joinpaths(outputroot, SPARCDIR))

# create images
for kernel in kernellist:
    # copy kernel
    kernel.fname = "vmlinuz"
    kernel.fpath = copy(kernel.fpath,
                        joinpaths(outputroot, SPARCDIR,  kernel.fname))

    # create and copy initrd
    initrd_fname = "initrd.img"
    initrd_fpath = copy(create_initrd(kernel),
                        joinpaths(outputroot, SPARCDIR,  initrd_fname))

    # add kernel and initrd to .treeinfo
    with open(treeinfo, "a") as f:
        f.write("[images-%s]\n" % kernel.arch)
        f.write("kernel = %s\n" % joinpaths(SPARCDIR, kernel.fname))
        f.write("initrd = %s\n" % joinpaths(SPARCDIR, initrd_fname))

if (bootiso):
    # create isopath dir
    isopathdir = joinpaths(outputroot, ISOPATHDIR)
    makedirs(isopathdir)

    # copy sparc dir to isopath dir
    copytree(joinpaths(outputroot, SPARCDIR), isopathdir)

    # create boot.iso
    bootiso_fpath = joinpaths(outputroot, IMAGESDIR, bootiso)

    # run mkisofs (XXX what's with the "Fedora" exclude?)
    rc = exec([MKISOFS, "-R", "-J", "-T",
               "-G", "/%s" % joinpaths(SPARCDIR, "isofs.b"),
               "-B",  "...",
               "-s",  "/%s" % joinpaths(SPARCDIR, "silo.conf"),
               "-r", "-V", '"PBOOT"', "-A", '"%s %s"' % (product, version),
               "-x", "Fedora", "-x", "repodata",
               "-sparc-label", '"%s %s Boot Disc"' % (product, version),
               "-o", bootiso_fpath, "-graft-points",
               "boot=%s" % joinpaths(outputroot, SPARCDIR)])

    # run implantisomd5
    rc = exec([IMPLANTISOMD5, bootiso_fpath])

    # remove isopath dir
    remove(isopathdir)
