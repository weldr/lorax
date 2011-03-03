# x86.pseudo.py


##### constants #####

ANABOOTDIR = "usr/share/anaconda/boot"

ISOLINUXDIR = "isolinux"
IMAGESDIR = "images"
PXEBOOTDIR = "images/pxeboot"

ISOLINUX_BIN = "usr/share/syslinux/isolinux.bin"
SYSLINUX_CFG = "usr/share/anaconda/boot/syslinux.cfg"

ISOHYBRID = "isohybrid"
IMPLANTISOMD5 = "implantisomd5"


##### main() #####

""" kernellist, installroot, outputroot, product, version, treeinfo, bootiso,
    basearch, uefi_boot_iso

"""

# create directories
makedirs(joinpaths(outputroot, ISOLINUXDIR))
makedirs(joinpaths(outputroot, PXEBOOTDIR))

# check for isolinux.bin
isolinux_bin = joinpaths(installroot, ISOLINUX_BIN)
if (not exists(isolinux_bin)):
    # XXX fatal?
    raise Exception("isolinux.bin not present")

# copy isolinux.bin to isolinux dir
copy(isolinux_bin, joinpaths(outputroot, ISOLINUXDIR))

# copy syslinux.cfg to isolinux dir (XXX rename to isolinux.cfg)
isolinux_cfg = copy(joinpaths(installroot, SYSLINUX_CFG),
                    joinpaths(outputroot, ISOLINUXDIR, "isolinux.cfg"))

replace(isolinux_cfg, "@PRODUCT@", product)
replace(isolinux_cfg, "@VERSION@", version)

# copy memtest (XXX not from installroot/boot ?
memtest = glob(joinpaths(installroot, ANABOOTDIR, "memtest*"))
if memtest:
    copy(memtest[-1], joinpaths(outputroot, ISOLINUXDIR, "memtest"))
    with open(isolinux_cfg, "a") as f:
        f.write("label memtest86\n")
        f.write("  menu label ^Memory test\n")
        f.write("  kernel memtest\n")
        f.write("  append -\n")

# copy *.msg files
msgfiles = glob(joinpaths(installroot, ANABOOTDIR, "*.msg"))
if (not msgfiles):
    raise Exception("message files not present")

for source_path in msgfiles:
    target_path = copy(source_path, joinpaths(outputroot, ISOLINUXDIR))
    replace(target_path, "@VERSION@", version)

# copy syslinux vesa splash and vesamenu.c32
splash = joinpaths(installroot, ANABOOTDIR, "syslinux-vesa-splash.jpg")
if (not exists(splash)):
    raise Exception("syslinux-vesa-splash.jpg not present")

splash = copy(splash, joinpaths(outputroot, ISOLINUXDIR, "splash.jpg"))
copy(joinpaths(installroot, "usr/share/syslinux/vesamenu.c32"),
     joinpaths(outputroot, ISOLINUXDIR))

# set up isolinux.cfg
replace(isolinux_cfg, "default linux", "default vesamenu.c32")
replace(isolinux_cfg, "prompt 1", "#prompt 1")

# copy grub.conf
grubconf = copy(joinpaths(installroot, ANABOOTDIR, "grub.conf"),
                joinpaths(outputroot, ISOLINUXDIR))

replace(grubconf, "@PRODUCT@", product)
replace(grubconf, "@VERSION@", version)

# create images
for kernel in kernellist:

    # set up file names
    suffix = ""
    if (kernel.type == K_PAE):
        suffix = "-PAE"
    elif (kernel.type == K_XEN):
        suffix = "-XEN"

    kernel.fname = "vmlinuz%s" % suffix
    if (not suffix):
        # copy kernel to isolinux dir
        kernel.fpath = copy(kernel.fpath,
                            joinpaths(outputroot, ISOLINUXDIR, kernel.fname))

        # create link in pxeboot dir
        os.link(kernel.fpath, joinpaths(outputroot, PXEBOOTDIR, kernel.fname))
    else:
        # copy kernel to pxeboot dir
        kernel.fpath = copy(kernel.fpath,
                            joinpaths(outputroot, PXEBOOTDIR, kernel.fname))

    # create and copy initrd to pxeboot dir
    initrd_fname = "initrd%s.img" % suffix
    initrd_fpath = copy(create_initrd(kernel),
                        joinpaths(outputroot, PXEBOOTDIR, initrd_fname))

    if (not suffix):
        # create link in isolinux dir
        os.link(initrd_fpath, joinpaths(outputroot, ISOLINUXDIR, initrd_fname))

    # add kernel and initrd to .treeinfo
    with open(treeinfo, "a") as f:
        f.write("[images-%s]\n" % "xen" if suffix else basearch)
        f.write("kernel = %s\n" % joinpaths(PXEBOOTDIR, kernel.fname))
        f.write("initrd = %s\n" % joinpaths(PXEBOOTDIR, initrd_fname))

    if (not suffix):
        # add boot.iso to .treeinfo
        with open(treeinfo, "a") as f:
            f.write("boot.iso = %s\n" % joinpaths(IMAGESDIR, bootiso))

if (bootiso):
    # define efiargs and efigraft
    efiargs, efigraft = [], []
    if (uefi_boot_iso and
        exists(joinpaths(outputroot, IMAGESDIR, "efiboot.img"))):

        efiargs = ["-eltorito-alt-boot", "-e",
                   joinpaths(IMAGESDIR, "efiboot.img"), "-no-emul-boot"]
        efigraft = ["EFI/BOOT=%s/EFI/BOOT" % outputroot]

    # create boot.iso
    bootiso_fpath = joinpaths(outputroot, IMAGESDIR, bootiso)

    # run mkisofs
    rc = exec([MKISOFS, "-v", "-o", bootiso_fpath, "-b",
               "%s/isolinux.bin" % ISOLINUXDIR, "-c",
               "%s/boot.cat" % ISOLINUXDIR, "-no-emul-boot", "-boot-load-size",
               "4", "-boot-info-table"] + EFIARGS + ["-R", "-J", "-V",
               "'%s'" % product, "-T", "-graft-points",
               "isolinux=%s" % joinpaths(outputroot, ISOLINUXDIR),
               "images=%s" % joinpaths(outputroot, IMAGESDIR)] + EFIGRAFT)

    if (exists(ISOHYBRID)):
        # run isohybrid
        rc = exec([ISOHYBRID, bootiso_fpath])

    # run implantisomd5
    rc = exec([IMPLANTISOMD5, bootiso_fpath])
