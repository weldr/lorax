# ppc.pseudo.py


##### constants #####

ANABOOTDIR = "usr/share/anaconda/boot"

ETCDIR = "etc"
PPCPARENT = "ppc"
CHRPDIR = "ppc/chrp"
IMAGESDIR = "images"

PPC32DIR = "ppc/ppc32"
PPC64DIR = "ppc/ppc64"
MACDIR = "ppc/mac"
NETBOOTDIR = "images/netboot"

MKZIMAGE = "usr/bin/mkzimage"
ZIMAGE_STUB = "usr/share/ppc64-utils/zImage.stub"
ZIMAGE_LDS = "usr/share/ppc64-utils/zImage.lds"
WRAPPER = "usr/sbin/wrapper"
# XXX variable constant :/
WRAPPER_A = "usr/%s/kernel-wrapper/wrapper.a" % libdir

ISOPATHDIR = "isopath"

MKISOFS = "mkisofs"
MAPPING = joinpaths(ANABOOTDIR, "mapping")
MAGIC = joinpaths(ANABOOTDIR, "magic")
IMPLANTISOMD5 = "implantisomd5"


##### main() #####

""" kernellist, installroot, outputroot, product, version, treeinfo, bootiso

"""

# create directories
makedirs(joinpaths(outputroot, ETCDIR))
makedirs(joinpaths(outputroot, PPCPARENT)
makedirs(joinpaths(outputroot, CHRPDIR))
makedirs(joinpaths(outputroot, IMAGESDIR))

# set up biarch test
biarch = lambda: (exists(joinpaths(outputroot, PPC32DIR)) and
                  exists(joinpaths(outputroot, PPC64DIR)))

# create images
for kernel in kernellist:

    # set up bits
    if (kernel.arch == "ppc"):
        bits = 32
        ppcdir = PPC32DIR
        fakearch = "ppc"
    elif (kernel.arch == "ppc64"):
        bits = 64
        ppcdir = PPC64DIR
        fakearch = ""
    else:
        raise Exception("unknown kernel arch %s" % kernel.arch)

    # create ppc dir
    makedirs(joinpaths(outputroot, ppcdir))

    if (kernel.arch == "ppc"):
        # create mac dir
        makedirs(joinpaths(outputroot, MACDIR))

    # create netboot dir
    makedirs(joinpaths(outputroot, NETBOOTDIR))

    # copy kernel
    kernel.fname = "vmlinuz"
    kernel.fpath = copy(kernel.fpath,
                        joinpaths(outputroot, ppcdir, kernel.fname))

    # create and copy initrd
    initrd_fname = "ramdisk.image.gz"
    initrd_fpath = copy(create_initrd(kernel),
                        joinpaths(outputroot, ppcdir, initrd_fname))

    # copy yaboot.conf
    yabootconf = copy(joinpaths(installroot, ANABOOTDIR, "yaboot.conf.in"),
                      joinpaths(outputroot, ppcdir, "yaboot.conf"))

    replace(yabootconf, "%BITS%", "%d" % bits)
    replace(yabootconf, "%PRODUCT%", product)
    replace(yabootconf, "%VERSION%", version)

    # add kernel and initrd to .treeinfo
    with open(treeinfo, "a") as f:
        f.write("[images-%s]\n" % kernel.arch)
        f.write("kernel = %s\n" % joinpaths(ppcdir, kernel.fname))
        f.write("initrd = %s\n" % joinpaths(ppcdir, initrd_fname))

    mkzimage = joinpaths(installroot, MKZIMAGE)
    zimage_stub = joinpaths(installroot, ZIMAGE_STUB)
    wrapper = joinpaths(installroot, WRAPPER)
    wrapper_a = joinpaths(installroot, WRAPPER_A)

    ppc_img_fname = "ppc%d.img" % bits
    ppc_img_fpath = joinpaths(outputroot, NETBOOTDIR, ppc_img_fname)

    if (exists(mkzimage) and exists(zimage_stub)):
        # copy zImage.lds
        zimage_lds = joinpaths(installroot, ZIMAGE_LDS)
        zimage_lds = copy(zimage_lds,
                          joinpaths(outputroot, ppcdir))

        # change current working dir
        cwd = os.getcwd()
        os.chdir(joinpaths(outputroot, ppcdir))

        # run mkzimage
        rc = exec([mkzimage, kernel.fpath, "no", "no", initrd_fpath,
                   zimage_stub, ppc_img_fpath])

        # remove zImage.lds
        remove(zimage_lds)

        # return to former working dir
        os.chdir(cwd)

    elif (exists(wrapper) and exists(wrapper_a)):
        # run wrapper
        rc = exec([wrapper, "-o", ppc_img_fpath, "-i", initrd_fpath,
                   "-D", dirname(wrapper_a), kernel.fpath])

    if (exists(ppc_img_fpath)):
        # add ppc image to .treeinfo
        with open(treeinfo, "a") as f:
            f.write("zimage = %s\n" % joinpaths(NETBOOTDIR, ppc_img_fname))

        if (bits == 32):
            # set up prepboot
            prepboot = "-prep-boot %s" % joinpaths(NETBOOTDIR, ppc_img_fname)

    if (empty(joinpaths(outputroot, NETBOOTDIR))):
        remove(joinpaths(outputroot, NETBOOTDIR))

# copy bootinfo.txt
copy(joinpaths(installroot, ANABOOTDIR, "bootinfo.txt"),
     joinpaths(outputroot, PPCPARENT))

# copy efika.forth
copy(joinpaths(installroot, ANABOOTDIR, "efika.forth"),
     joinpaths(outputroot, PPCPARENT))

# copy yaboot to chrp dir
yaboot = joinpaths(installroot, "usr/lib/yaboot/yaboot")
yaboot = copy(yaboot, joinpaths(outputroot, CHRPDIR))

if (exists(joinpaths(outputroot, MACDIR))):
    # copy yaboot and ofboot.b to mac dir
    copy(yaboot, joinpaths(outputroot, MACDIR))
    copy(joinpaths(installroot, ANABOOTDIR, "ofboot.b"),
         joinpaths(outputroot, MACDIR))

    # set up macboot
    p = joinpaths(outputroot, ISOPATHDIR, MACDIR)
    macboot = "-hfs-volid %s -hfs-bless %s" % (version, p)

# add note to yaboot
rc = exec([joinpaths(installroot, "usr/lib/yaboot/addnote"), yaboot])

# copy yaboot.conf to etc dir
if (biarch):
    yabootconf = copy(joinpaths(installroot, ANABOOTDIR, "yaboot.conf.3264"),
                      joinpaths(outputroot, ETCDIR, "yaboot.conf"))

    replace(yabootconf, "%BITS%", "32")
    replace(yabootconf, "%PRODUCT%", product)
    replace(yabootconf, "%VERSION%", version)

else:
    copy(joinpaths(outputroot, ppcdir, "yaboot.conf"),
         joinpaths(outputroot, ETCDIR))

if (bootiso):
    # create isopath dir
    isopathdir = joinpaths(outputroot, ISOPATHDIR)
    makedirs(isopathdir)

    # copy etc dir and ppc dir to isopath dir
    copytree(joinpaths(outputroot, ETCDIR), isopathdir)
    copytree(joinpaths(outputroot, PPCPARENT), isopathdir)

    if (exists(joinpaths(outputroot, NETBOOTDIR))):
        # if we have ppc images, create images dir in isopath dir
        imagesdir = joinpaths(isopathdir, IMAGESDIR)
        makedirs(imagesdir)

        # copy netboot dir to images dir
        copytree(joinpaths(outputroot, NETBOOTDIR), imagesdir)

    # define prepboot and macboot
    prepboot = "" if "prepboot" not in locals() else locals()["prepboot"]
    macboot = "" if "macboot" not in locals() else locals()["macboot"]

    # create boot.iso
    bootiso_fpath = joinpaths(outputroot, IMAGESDIR, bootiso)

    # run mkisofs
    rc = exec([MKISOFS, "-o", bootiso_fpath, "-chrp-boot", "-U", prepboot,
               "-part", "-hfs", "-T", "-r", "-l", "-J", "-A",
               '"%s %s"' % (product, version), "-sysid", "PPC", "-V", '"PBOOT"',
               "-volset", '"%s"' % version, "-volset-size", "1",
               "-volset-seqno", "1", macboot, "-map", MAPPING, "-magic", MAGIC,
               "-no-desktop", "-allow-multidot", "-graft-points", isopathdir])

    # run implantisomd5
    rc = exec([IMPLANTISOMD5, bootiso_fpath])

    # remove isopath dir
    remove(isopathdir)
