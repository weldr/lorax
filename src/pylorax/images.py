#
# images.py
#
# Copyright (C) 2011  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Red Hat Author(s):  Martin Gracik <mgracik@redhat.com>
#

import logging
logger = logging.getLogger("pylorax.images")

import os
import subprocess
import shutil
import glob
import collections

from base import DataHolder
from sysutils import joinpaths, cpfile, replace

import constants


##### constants #####

ANABOOTDIR = "usr/share/anaconda/boot"

# ppc
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
WRAPPER = "usr/sbin/wrapper"

ISOPATHDIR = "isopath"

MKISOFS = "mkisofs"
MAPPING = joinpaths(ANABOOTDIR, "mapping")
MAGIC = joinpaths(ANABOOTDIR, "magic")
IMPLANTISOMD5 = "implantisomd5"

# x86
ISOLINUXDIR = "isolinux"
PXEBOOTDIR = "images/pxeboot"

ISOLINUX_BIN = "usr/share/syslinux/isolinux.bin"
ISOLINUX_CFG = "usr/share/anaconda/boot/isolinux.cfg"

ISOHYBRID = "isohybrid"

# s390
INITRD_ADDRESS = "0x02000000"

# sparc
SPARCDIR = "boot"


class PPC(object):

    def __init__(self, kernellist, installtree, outputroot, product, version,
                 treeinfo, basearch, ctype, cargs):

        self.kernellist = kernellist
        self.installtree = installtree
        self.outputroot = outputroot
        self.product = product
        self.version = version
        self.treeinfo = treeinfo
        self.basearch = basearch
        self.ctype = ctype
        self.cargs = cargs
        self.kernels, self.initrds = [], []

        self.reqs = collections.defaultdict(str)

    def backup_required(self, workdir):
        # yaboot.conf
        yabootconf = joinpaths(self.installtree.root, ANABOOTDIR,
                               "yaboot.conf.in")

        self.reqs["yabootconf"] = cpfile(yabootconf, workdir)

        # bootinfo.txt
        bootinfo_txt = joinpaths(self.installtree.root, ANABOOTDIR,
                                 "bootinfo.txt")

        self.reqs["bootinfo_txt"] = cpfile(bootinfo_txt, workdir)

        # efika.forth
        efika_forth = joinpaths(self.installtree.root, "boot",
                                "efika.forth")

        self.reqs["efika_forth"] = cpfile(efika_forth, workdir)

        # yaboot
        yaboot = joinpaths(self.installtree.root, "usr/lib/yaboot/yaboot")
        self.reqs["yaboot"] = cpfile(yaboot, workdir)

        # ofboot.b
        ofboot_b = joinpaths(self.installtree.root, ANABOOTDIR, "ofboot.b")
        self.reqs["ofboot_b"] = cpfile(ofboot_b, workdir)

        # yaboot.conf.3264
        yabootconf3264 = joinpaths(self.installtree.root, ANABOOTDIR,
                                   "yaboot.conf.3264")

        self.reqs["yabootconf3264"] = cpfile(yabootconf3264, workdir)

    def create_initrd(self, libdir):
        # create directories
        logger.info("creating required directories")
        os.makedirs(joinpaths(self.outputroot, ETCDIR))
        os.makedirs(joinpaths(self.outputroot, PPCPARENT))
        os.makedirs(joinpaths(self.outputroot, CHRPDIR))
        os.makedirs(joinpaths(self.outputroot, IMAGESDIR))

        # set up biarch test
        ppc32dir = joinpaths(self.outputroot, PPC32DIR)
        ppc64dir = joinpaths(self.outputroot, PPC64DIR)
        biarch = lambda: (os.path.exists(ppc32dir) and
                          os.path.exists(ppc64dir))

        # create images
        for kernel in self.kernellist:
            # set up bits
            kernel_arch = kernel.version.split(".")[-1]
            if (kernel_arch == "ppc"):
                bits = 32
                ppcdir = PPC32DIR
                fakearch = "ppc"
            elif (kernel_arch == "ppc64"):
                bits = 64
                ppcdir = PPC64DIR
                fakearch = ""
            else:
                raise Exception("unknown kernel arch {0}".format(kernel_arch))

            # create ppc dir
            os.makedirs(joinpaths(self.outputroot, ppcdir))

            # create mac dir
            os.makedirs(joinpaths(self.outputroot, MACDIR))

            # create netboot dir
            os.makedirs(joinpaths(self.outputroot, NETBOOTDIR))

            # copy kernel
            logger.info("copying kernel image")
            kernel.fname = "vmlinuz"
            dst = joinpaths(self.outputroot, ppcdir, kernel.fname)
            kernel.fpath = cpfile(kernel.fpath, dst)

            # create and copy initrd
            initrd = DataHolder()
            initrd.fname = "ramdisk.image.gz"
            initrd.fpath = joinpaths(self.outputroot, ppcdir, initrd.fname)
            initrd.itype = kernel.ktype

            logger.info("compressing the install tree")
            self.installtree.compress(initrd, kernel, self.ctype, self.cargs)

            # add kernel and initrd to the list
            self.kernels.append(kernel)
            self.initrds.append(initrd)

            # add kernel and initrd to .treeinfo
            section = "images-{0}".format(kernel_arch)
            data = {"kernel": joinpaths(ppcdir, kernel.fname)}
            self.treeinfo.add_section(section, data)
            data = {"initrd": joinpaths(ppcdir, initrd.fname)}
            self.treeinfo.add_section(section, data)

            # copy yaboot.conf
            dst = joinpaths(self.outputroot, ppcdir, "yaboot.conf")
            yabootconf = cpfile(self.reqs["yabootconf"], dst)

            replace(yabootconf, r"%BITS%", str(bits))
            replace(yabootconf, r"%PRODUCT%", self.product)
            replace(yabootconf, r"%VERSION%", self.version)

            mkzimage = joinpaths(self.installtree.root, MKZIMAGE)
            zimage_stub = joinpaths(self.installtree.root, ZIMAGE_STUB)
            wrapper = joinpaths(self.installtree.root, WRAPPER)

            # XXX
            wrapper_a = joinpaths(self.installtree.root,
                                  "usr/%s/kernel-wrapper/wrapper.a" % libdir)

            ppc_img_fname = "ppc{0}.img".format(bits)
            ppc_img_fpath = joinpaths(self.outputroot, NETBOOTDIR,
                                      ppc_img_fname)

            if (os.path.exists(mkzimage) and os.path.exists(zimage_stub)):
                logger.info("creating the z image")

                # XXX copy zImage.lds
                zimage_lds = joinpaths(self.installtree.root,
                                   "usr/%s/kernel-wrapper/zImage.lds" % libdir)
                zimage_lds = cpfile(zimage_lds,
                                    joinpaths(self.outputroot, ppcdir))

                # change current working directory
                cwd = os.getcwd()
                os.chdir(joinpaths(self.outputroot, ppcdir))

                # run mkzimage
                cmd = [mkzimage, kernel.fpath, "no", "no", initrd.fpath,
                       zimage_stub, ppc_img_fpath]
                p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE)
                p.wait()

                # remove zImage.lds
                os.unlink(zimage_lds)

                # return to former working directory
                os.chdir(cwd)

            elif (os.path.exists(wrapper) and os.path.exists(wrapper_a)):
                logger.info("running kernel wrapper")
                # run wrapper
                cmd = [wrapper, "-o", ppc_img_fpath, "-i", initrd.fpath,
                       "-D", os.path.dirname(wrapper_a), kernel.fpath]
                p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE)
                p.wait()

            if os.path.exists(ppc_img_fpath):
                # add ppc image to .treeinfo
                section = "images-{0}".format(kernel_arch)
                data = {"zimage": joinpaths(NETBOOTDIR, ppc_img_fname)}
                self.treeinfo.add_section(section, data)

                if (bits == 32):
                    # set up prepboot
                    p = joinpaths(NETBOOTDIR, ppc_img_fname)
                    prepboot = ["-prep-boot {0}".format(p)]

            # remove netboot dir if empty
            try:
                os.rmdir(joinpaths(self.outputroot, NETBOOTDIR))
            except OSError:
                pass

        # copy bootinfo.txt
        cpfile(self.reqs["bootinfo_txt"],
               joinpaths(self.outputroot, PPCPARENT))

        # copy efika.forth
        cpfile(self.reqs["efika_forth"],
               joinpaths(self.outputroot, PPCPARENT))

        # copy yaboot to chrp dir
        yaboot = cpfile(self.reqs["yaboot"],
                        joinpaths(self.outputroot, CHRPDIR))

        if (os.path.exists(joinpaths(self.outputroot, MACDIR))):
            # copy yaboot and ofboot.b to mac dir
            cpfile(yaboot, joinpaths(self.outputroot, MACDIR))
            cpfile(self.reqs["ofboot_b"], joinpaths(self.outputroot, MACDIR))

            # set up macboot
            p = joinpaths(self.outputroot, ISOPATHDIR, MACDIR)
            macboot = ["-hfs-volid {0}".format(self.version),
                       "-hfs-bless {0}".format(p)]

        # add note to yaboot
        cmd = [joinpaths(self.installtree.root, "usr/lib/yaboot/addnote"),
               yaboot]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE)
        p.wait()

        # copy yaboot.conf to etc dir
        if biarch():
            yabootconf = cpfile(self.reqs["yabootconf3264"],
                                joinpaths(self.outputroot, ETCDIR,
                                          "yaboot.conf"))

            replace(yabootconf, r"%BITS%", "32")
            replace(yabootconf, r"%PRODUCT%", self.product)
            replace(yabootconf, r"%VERSION%", self.version)

        else:
            cpfile(joinpaths(self.outputroot, ppcdir, "yaboot.conf"),
                   joinpaths(self.outputroot, ETCDIR))

    def create_boot(self, efiboot=None):
        # create isopath dir
        isopathdir = joinpaths(self.outputroot, ISOPATHDIR)
        os.makedirs(isopathdir)

        # copy etc dir and ppc dir to isopath dir
        shutil.copytree(joinpaths(self.outputroot, ETCDIR),
                        joinpaths(isopathdir, ETCDIR))
        shutil.copytree(joinpaths(self.outputroot, PPCPARENT),
                        joinpaths(isopathdir, PPCPARENT))

        if (os.path.exists(joinpaths(self.outputroot, NETBOOTDIR))):
            # create images dir in isopath dir if we have ppc images
            imagesdir = joinpaths(isopathdir, IMAGESDIR)
            os.makedirs(imagesdir)

            # copy netboot dir to images dir
            shutil.copytree(joinpaths(self.outputroot, NETBOOTDIR),
                            joinpaths(imagesdir, os.path.basename(NETBOOTDIR)))

        # define prepboot and macboot
        prepboot = [] if "prepboot" not in locals() else locals()["prepboot"]
        macboot = [] if "macboot" not in locals() else locals()["macboot"]

        # create boot image
        boot_fpath = joinpaths(self.outputroot, IMAGESDIR, "boot.iso")

        # run mkisofs
        cmd = [MKISOFS, "-o", boot_fpath, "-chrp-boot", "-U"] + prepboot + \
              ["-part", "-hfs", "-T", "-r", "-l", "-J", "-A",
               '"%s %s"' % (self.product, self.version),
               "-sysid", "PPC", "-V", '"PBOOT"',
               "-volset", '"%s"' % self.version, "-volset-size", "1",
               "-volset-seqno", "1"] + macboot + \
              ["-map", joinpaths(self.installtree.root, MAPPING),
               "-magic", joinpaths(self.installtree.root, MAGIC),
               "-no-desktop", "-allow-multidot", "-graft-points", isopathdir]

        p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE)
        p.wait()

        # run implantisomd5
        cmd = [IMPLANTISOMD5, boot_fpath]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE)
        p.wait()

        # remove isopath dir
        shutil.rmtree(isopathdir)


class X86(object):

    def __init__(self, kernellist, installtree, outputroot, product, version,
                 treeinfo, basearch, ctype, cargs):

        self.kernellist = kernellist
        self.installtree = installtree
        self.outputroot = outputroot
        self.product = product
        self.version = version
        self.treeinfo = treeinfo
        self.basearch = basearch
        self.ctype = ctype
        self.cargs = cargs
        self.kernels, self.initrds = [], []

        self.reqs = collections.defaultdict(str)

    def backup_required(self, workdir):
        # isolinux.bin
        isolinux_bin = joinpaths(self.installtree.root, ISOLINUX_BIN)
        if not os.path.exists(isolinux_bin):
            raise Exception("isolinux.bin not present")

        self.reqs["isolinux_bin"] = cpfile(isolinux_bin, workdir)

        # isolinux.cfg
        isolinux_cfg = joinpaths(self.installtree.root, ISOLINUX_CFG)
        self.reqs["isolinux_cfg"] = cpfile(isolinux_cfg, workdir)

        # memtest
        memtest = glob.glob(joinpaths(self.installtree.root, "boot",
                                      "memtest*"))

        if memtest:
            self.reqs["memtest"] = cpfile(memtest[-1],
                                          joinpaths(workdir, "memtest"))

        # *.msg files
        msgfiles = glob.glob(joinpaths(self.installtree.root, ANABOOTDIR,
                                       "*.msg"))

        if not msgfiles:
            raise Exception("message files not present")

        self.reqs["msgfiles"] = []
        for src in msgfiles:
            self.reqs["msgfiles"].append(cpfile(src, workdir))

        # splash
        splash = joinpaths(self.installtree.root, ANABOOTDIR,
                           "syslinux-splash.png")

        if not splash:
            raise Exception("syslinux-splash.png not present")

        self.reqs["splash"] = cpfile(splash, workdir)

        # vesamenu.c32
        vesamenu = joinpaths(self.installtree.root,
                             "usr/share/syslinux/vesamenu.c32")

        self.reqs["vesamenu"] = cpfile(vesamenu, workdir)

        # grub.conf
        grubconf = joinpaths(self.installtree.root, ANABOOTDIR, "grub.conf")
        self.reqs["grubconf"] = cpfile(grubconf, workdir)

    def create_initrd(self, libdir):
        # create directories
        logger.info("creating required directories")
        os.makedirs(joinpaths(self.outputroot, ISOLINUXDIR))
        os.makedirs(joinpaths(self.outputroot, PXEBOOTDIR))

        # copy isolinux.bin to isolinux dir
        cpfile(self.reqs["isolinux_bin"],
               joinpaths(self.outputroot, ISOLINUXDIR))

        # copy isolinux.cfg to isolinux dir
        isolinux_cfg = cpfile(self.reqs["isolinux_cfg"],
                              joinpaths(self.outputroot, ISOLINUXDIR))

        replace(isolinux_cfg, r"@PRODUCT@", self.product)
        replace(isolinux_cfg, r"@VERSION@", self.version)

        # copy memtest
        if self.reqs["memtest"]:
            cpfile(self.reqs["memtest"],
                   joinpaths(self.outputroot, ISOLINUXDIR))

            #with open(isolinux_cfg, "a") as f:
            #    f.write("label memtest86\n")
            #    f.write("  menu label ^Memory test\n")
            #    f.write("  kernel memtest\n")
            #    f.write("  append -\n")

        # copy *.msg files
        for src in self.reqs["msgfiles"]:
            dst = cpfile(src, joinpaths(self.outputroot, ISOLINUXDIR))
            replace(dst, r"@VERSION@", self.version)

        splash = cpfile(self.reqs["splash"],
                        joinpaths(self.outputroot, ISOLINUXDIR, "splash.png"))

        # copy vesamenu.c32
        cpfile(self.reqs["vesamenu"],
               joinpaths(self.outputroot, ISOLINUXDIR))

        # copy grub.conf
        grubconf = cpfile(self.reqs["grubconf"],
                          joinpaths(self.outputroot, ISOLINUXDIR))

        replace(grubconf, r"@PRODUCT@", self.product)
        replace(grubconf, r"@VERSION@", self.version)

        # create images
        for kernel in self.kernellist:
            # set up file names
            suffix = ""
            if (kernel.ktype == constants.K_PAE):
                suffix = "-PAE"
            elif (kernel.ktype == constants.K_XEN):
                suffix = "-XEN"

            logger.info("copying kernel image")
            kernel.fname = "vmlinuz{0}".format(suffix)
            if not suffix:
                # copy kernel to isolinux dir
                kernel.fpath = cpfile(kernel.fpath,
                                      joinpaths(self.outputroot, ISOLINUXDIR,
                                                kernel.fname))

                # create link in pxeboot dir
                os.link(kernel.fpath,
                        joinpaths(self.outputroot, PXEBOOTDIR, kernel.fname))
            else:
                # copy kernel to pxeboot dir
                kernel.fpath = cpfile(kernel.fpath,
                                      joinpaths(self.outputroot, PXEBOOTDIR,
                                                kernel.fname))

            # create and copy initrd to pxeboot dir
            initrd = DataHolder()
            initrd.fname = "initrd{0}.img".format(suffix)
            initrd.fpath = joinpaths(self.outputroot, PXEBOOTDIR, initrd.fname)
            initrd.itype = kernel.ktype

            logger.info("compressing the install tree")
            self.installtree.compress(initrd, kernel, self.ctype, self.cargs)

            # add kernel and initrd to the list
            self.kernels.append(kernel)
            self.initrds.append(initrd)

            if not suffix:
                # create link in isolinux dir
                os.link(initrd.fpath,
                        joinpaths(self.outputroot, ISOLINUXDIR, initrd.fname))

            # add kernel and initrd to .treeinfo
            section = "images-{0}".format("xen" if suffix else self.basearch)
            data = {"kernel": joinpaths(PXEBOOTDIR, kernel.fname)}
            self.treeinfo.add_section(section, data)
            data = {"initrd": joinpaths(PXEBOOTDIR, initrd.fname)}
            self.treeinfo.add_section(section, data)

            if not suffix:
                # add boot.iso to .treeinfo
                data = {"boot.iso": joinpaths(IMAGESDIR, "boot.iso")}
                self.treeinfo.add_section(section, data)

            # create images-xen section on x86_64
            if self.basearch == "x86_64":
                section = "images-xen"
                data = {"kernel": joinpaths(PXEBOOTDIR, kernel.fname)}
                self.treeinfo.add_section(section, data)
                data = {"initrd": joinpaths(PXEBOOTDIR, initrd.fname)}
                self.treeinfo.add_section(section, data)

    def create_boot(self, efiboot=None):
        # define efiargs and efigraft
        efiargs, efigraft = [], []
        if efiboot:
            efiargs = ["-eltorito-alt-boot", "-e",
                       joinpaths(IMAGESDIR, "efiboot.img"), "-no-emul-boot"]
            efigraft = ["EFI/BOOT={0}/EFI/BOOT".format(self.outputroot)]

        # create boot image
        boot_fpath = joinpaths(self.outputroot, IMAGESDIR, "boot.iso")

        # run mkisofs
        cmd = [MKISOFS, "-v", "-o", boot_fpath, "-b",
               "{0}/isolinux.bin".format(ISOLINUXDIR), "-c",
               "{0}/boot.cat".format(ISOLINUXDIR), "-no-emul-boot",
               "-boot-load-size", "4", "-boot-info-table"] + efiargs + \
              ["-R", "-J", "-V", "'{0}'".format(self.product), "-T",
               "-graft-points",
               "isolinux={0}".format(joinpaths(self.outputroot, ISOLINUXDIR)),
               "images={0}".format(joinpaths(self.outputroot, IMAGESDIR))] + \
              efigraft

        p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE)
        p.wait()

        try:
            # run isohybrid
            cmd = [ISOHYBRID, boot_fpath]
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE)
        except OSError as e:
            raise Exception("cannot run isohybrid: %s" % e)
        else:
            p.wait()

        # run implantisomd5
        cmd = [IMPLANTISOMD5, boot_fpath]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE)
        p.wait()


class S390(object):

    def __init__(self, kernellist, installtree, outputroot, product, version,
                 treeinfo, basearch, ctype, cargs):

        self.kernellist = kernellist
        self.installtree = installtree
        self.outputroot = outputroot
        self.product = product
        self.version = version
        self.treeinfo = treeinfo
        self.basearch = basearch
        self.ctype = ctype
        self.cargs = cargs
        self.kernels, self.initrds = [], []

        self.reqs = collections.defaultdict(str)

    def backup_required(self, workdir):
        pass

    def create_initrd(self, libdir):
        # create directories
        os.makedirs(joinpaths(self.outputroot, IMAGESDIR))

        # copy redhat.exec
        cpfile(joinpaths(self.installtree.root, ANABOOTDIR, "redhat.exec"),
               joinpaths(self.outputroot, IMAGESDIR))

        # copy generic.prm
        generic_prm = cpfile(joinpaths(self.installtree.root, ANABOOTDIR,
                                       "generic.prm"),
                             joinpaths(self.outputroot, IMAGESDIR))

        # copy generic.ins
        generic_ins = cpfile(joinpaths(self.installtree.root, ANABOOTDIR,
                                       "generic.ins"), self.outputroot)

        replace(generic_ins, r"@INITRD_LOAD_ADDRESS@", INITRD_ADDRESS)

        for kernel in self.kernellist:
            # copy kernel
            kernel.fname = "kernel.img"
            kernel.fpath = cpfile(kernel.fpath,
                                  joinpaths(self.outputroot, IMAGESDIR,
                                            kernel.fname))

            # create and copy initrd
            initrd = DataHolder()
            initrd.fname = "initrd.img"
            initrd.fpath = joinpaths(self.outputroot, IMAGESDIR, initrd.fname)

            logger.info("compressing the install tree")
            self.installtree.compress(initrd, kernel, self.ctype, self.cargs)

            # run addrsize
            addrsize = joinpaths(self.installtree.root, "usr/libexec",
                                 "anaconda", "addrsize")

            cmd = [addrsize, INITRD_ADDRESS, initrd.fpath,
                   joinpaths(self.outputroot, IMAGESDIR, "initrd.addrsize")]

            p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE)
            p.wait()

            # add kernel and initrd to .treeinfo
            kernel_arch = kernel.version.split(".")[-1]
            section = "images-{0}".format(kernel_arch)
            data = {"kernel": joinpaths(IMAGESDIR, kernel.fname),
                    "initrd": joinpaths(IMAGESDIR, initrd.fname),
                    "initrd.addrsize": joinpaths(IMAGESDIR, "initrd.addrsize"),
                    "generic.prm": joinpaths(IMAGESDIR,
                                             os.path.basename(generic_prm)),
                    "generic.ins": os.path.basename(generic_ins)}
            self.treeinfo.add_section(section, data)

        # create cdboot.img
        bootiso_fpath = joinpaths(self.outputroot, IMAGESDIR, "cdboot.img")

        # run mks390cdboot
        mks390cdboot = joinpaths(self.installtree.root, "usr/libexec",
                                 "anaconda", "mk-s390-cdboot")

        cmd = [mks390cdboot, "-i", kernel.fpath, "-r", initrd.fpath,
               "-p", generic_prm, "-o", bootiso_fpath]

        p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE)
        p.wait()

        # add cdboot.img to treeinfo
        data = {"cdboot.img": joinpaths(IMAGESDIR, "cdboot.img")}
        self.treeinfo.add_section(section, data)

    def create_boot(self, efiboot=None):
        pass


class SPARC(object):

    def __init__(self, kernellist, installtree, outputroot, product, version,
                 treeinfo, basearch, ctype, cargs):

        self.kernellist = kernellist
        self.installtree = installtree
        self.outputroot = outputroot
        self.product = product
        self.version = version
        self.treeinfo = treeinfo
        self.basearch = basearch
        self.ctype = ctype
        self.cargs = cargs
        self.kernels, self.initrds = [], []

        self.reqs = collections.defaultdict(str)

    def backup_required(self, workdir):
        os.makedirs(joinpaths(workdir, "bfiles"))

        for fname in glob.glob(joinpaths(self.installtree.root, "boot/*.b")):
            cpfile(fname, joinpaths(workdir, "bfiles"))

        self.reqs["bfiles"] = glob.glob(joinpaths(workdir, "bfiles/*.b"))

    def create_initrd(self, libdir):
        # create directories
        os.makedirs(joinpaths(self.outputroot, IMAGESDIR))
        os.makedirs(joinpaths(self.outputroot, SPARCDIR))

        # copy silo.conf
        siloconf = cpfile(joinpaths(self.installtree.root, ANABOOTDIR,
                                    "silo.conf"),
                          joinpaths(self.outputroot, SPARCDIR))

        # copy boot.msg
        bootmsg = cpfile(joinpaths(self.installtree.root, ANABOOTDIR,
                                   "boot.msg"),
                         joinpaths(self.outputroot, SPARCDIR))

        replace(bootmsg, r"%PRODUCT%", self.product)
        replace(bootmsg, r"%VERSION%", self.version)

        # copy  *.b to sparc dir
        for fname in self.reqs["bfiles"]:
            cpfile(fname, joinpaths(self.outputroot, SPARCDIR))

        # create images
        for kernel in self.kernellist:
            # copy kernel
            kernel.fname = "vmlinuz"
            kernel.fpath = cpfile(kernel.fpath,
                                  joinpaths(self.outputroot, SPARCDIR,
                                            kernel.fname))

            # create and copy initrd
            initrd = DataHolder()
            initrd.fname = "initrd.img"
            initrd.fpath = joinpaths(self.outputroot, SPARCDIR,  initrd.fname)

            logger.info("compressing the install tree")
            self.installtree.compress(initrd, kernel, self.ctype, self.cargs)

            # add kernel and initrd to .treeinfo
            kernel_arch = kernel.version.split(".")[-1]
            section = "images-{0}".format(kernel_arch)
            data = {"kernel": joinpaths(SPARCDIR, kernel.fname),
                    "initrd":joinpaths(SPARCDIR, initrd.fname)}
            self.treeinfo.add_section(section, data)

    def create_boot(self, efiboot=None):
        # create isopath dir
        isopathdir = joinpaths(self.outputroot, ISOPATHDIR)
        os.makedirs(isopathdir)

        # copy sparc dir to isopath dir
        shutil.copytree(joinpaths(self.outputroot, SPARCDIR),
                        joinpaths(isopathdir, SPARCDIR))

        # create boot.iso
        bootiso_fpath = joinpaths(self.outputroot, IMAGESDIR, "boot.iso")

        # run mkisofs (XXX what's with the "Fedora" exclude?)
        cmd = [MKISOFS, "-R", "-J", "-T",
               "-G", "/%s" % joinpaths(SPARCDIR, "isofs.b"),
               "-B",  "...",
               "-s",  "/%s" % joinpaths(SPARCDIR, "silo.conf"),
               "-r", "-V", '"PBOOT"', "-A",
               '"%s %s"' % (self.product, self.version),
               "-x", "Fedora", "-x", "repodata", "-sparc-label",
               '"%s %s Boot Disc"' % (self.product, self.version),
               "-o", bootiso_fpath, "-graft-points",
               "boot=%s" % joinpaths(self.outputroot, SPARCDIR)]

        p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE)

        p.wait()

        # run implantisomd5
        cmd = [IMPLANTISOMD5, bootiso_fpath]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE)

        p.wait()

        # remove isopath dir
        shutil.rmtree(isopathdir)


class Factory(object):

    DISPATCH_MAP = {"ppc": PPC,
                    "i386": X86,
                    "x86_64": X86,
                    "s390": S390,
                    "s390x": S390,
                    "sparc": SPARC}

    def __init__(self):
        pass

    def get_class(self, arch):
        if arch in self.DISPATCH_MAP:
            return self.DISPATCH_MAP[arch]
        else:
            raise Exception("no support for {0}".format(arch))
