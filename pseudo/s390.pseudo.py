# s390.pseudo.py


##### constants #####

ANABOOTDIR = "usr/share/anaconda/boot"

IMAGESDIR = "images"

INITRD_ADDRESS = "0x02000000"

ADDRSIZE = "usr/%s/anaconda/addrsize" % libdir
MKS390CDBOOT = "usr/%s/anaconda/mk-s390-cdboot" % libdir


##### main() #####

""" kernellist, installroot, outputroot, product, version, treeinfo, bootiso

"""

# create directories
makedirs(joinpaths(outputroot, IMAGESDIR))

# copy redhat.exec
copy(joinpaths(installroot, ANABOOTDIR, "redhat.exec"),
     joinpaths(outputroot, IMAGESDIR))

# copy generic.prm
generic_prm = copy(joinpaths(installroot, ANABOOTDIR, "generic.prm"),
                   joinpaths(outputroot, IMAGESDIR))

# copy generic.ins
generic_ins = copy(joinpaths(installroot, ANABOOTDIR, "generic.ins"),
                   outputroot)

replace(generic_ins, "@INITRD_LOAD_ADDRESS@", INITRD_ADDRESS)

for kernel in kernellist:

    # copy kernel
    kernel.fname = "kernel.img"
    kernel.fpath = copy(kernel.fpath,
                        joinpaths(outputroot, IMAGESDIR, kernel.fname))

    # create and copy initrd
    initrd_fname = "initrd.img"
    initrd_fpath = copy(create_initrd(kernel),
                        joinpaths(outputroot, IMAGESDIR, initrd_fname))

    # run addrsize
    initrd_addrsize = "initrd_addrsize"
    rc = exec([ADDRSIZE, INITRD_ADDRESS, initrd_fpath,
               joinpaths(outputroot, IMAGESDIR, initrd_addrsize)])

    # add kernel and initrd to .treeinfo
    with open(treeinfo, "a") as f:
        f.write("[images-%s]\n" % kernel.arch)
        f.write("kernel = %s\n" % joinpaths(IMAGESDIR, kernel.fname))
        f.write("initrd = %s\n" % joinpaths(IMAGESDIR, initrd_fname))
        f.write("initrd.addrsize = %s\n" % joinpaths(IMAGESDIR,
                                                     initrd_addrsize))
        f.write("generic.prm = %s\n" % joinpaths(IMAGESDIR,
                                                 basename(generic_prm)))
        f.write("generic.ins = %s\n" % basename(generic_ins))
        f.write("cdboot.img = %s\n" % joinpaths(IMAGESDIR, bootiso))

if (bootiso):
    # create boot.iso
    bootiso_fpath = joinpaths(outputroot, IMAGESDIR, bootiso)

    # run mks390cdboot
    rc = exec([MKS390CDBOOT, "-i", kernel.fpath, "-r", initrd_fpath,
               "-p", generic_prm, "-o", bootiso_fpath])
