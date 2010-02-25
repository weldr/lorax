#
# __init__.py
#
# Copyright (C) 2009  Red Hat, Inc.
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
#                     David Cantrell <dcantrell@redhat.com>
#

import sys
import os
import ConfigParser
import glob
import time
import datetime
import shutil

import yum
import yum.callbacks
import yum.rpmtrans

from base import BaseLoraxClass
import output

import insttree
import images
from sysutils import *


#                        basearch   efiarch     64bit
ARCHMAP = {"i386":      ["i386",    "IA32",     False],
           "i586":      ["i386",    "IA32",     False],
           "i686":      ["i386",    "IA32",     False],
           "x86_64":    ["x86_64",  "X64",      True],
           "ppc":       ["ppc",     "",         False],
           "ppc64":     ["ppc",     "",         True],
           "s390":      ["s390",    "",         False],
           "s390x":     ["s390x",   "",         True],
           "sparc":     ["sparc",   "",         False],
           "sparc64":   ["sparc",   "",         True],
           "ia64":      ["ia64",    "IA64",     True]}

LIB32 = "lib"
LIB64 = "lib64"


class Lorax(BaseLoraxClass):

    def __init__(self, yb, installtree, outputdir,
                 product, version, release,
                 workdir="/tmp", variant="", bugurl="", updatesdir=None):

        BaseLoraxClass.__init__(self)

        # XXX check if we have root privileges
        assert os.geteuid() == self.const.ROOT_UID, "no root privileges"

        # XXX check if we have a yumbase object
        assert isinstance(yb, yum.YumBase), "not an yum base object"

        # setup yum and the install tree
        self.yum = YumHelper(yb)
        self.installtree = insttree.InstallTree(yum=self.yum,
                                                rootdir=installtree,
                                                updatesdir=updatesdir)

        # create the output directory
        self.outputdir = outputdir
        makedirs_(self.outputdir)

        # required parameters
        self.product = product
        self.version = version
        self.release = release

        # create the working director
        self.workdir = workdir
        makedirs_(self.workdir)

        # optional parameters
        self.variant = variant
        self.bugurl = bugurl

        # setup the output
        output_level = output.INFO
        if self.conf.debug:
            output_level = output.DEBUG

        self.output.basic_config(colors=self.conf.colors,
                                 encoding=self.conf.encoding,
                                 output_level=output_level)

        ignore_errors = set()
        if os.path.isfile(self.conf.ignore_errors):
            with open(self.conf.ignore_errors, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        ignore_errors.add(line)

        self.output.ignore = ignore_errors

    def run(self):
        # check if we have all required commands
        for cmd in self.cmd.values():
            if not os.path.isfile(cmd):
                err = "required command <b>{0}</b> does not exist"
                self.pwarning(err.format(cmd))

        # set the build architecture
        self.pinfo(":: setting the build architecture")
        self.conf.buildarch = self.get_buildarch()
        basearch, efiarch, is64 = ARCHMAP[self.conf.buildarch]

        self.conf.basearch = basearch
        self.conf.efiarch = efiarch

        # set the libdir
        self.conf.libdir = LIB32
        if is64:
            self.conf.libdir = LIB64

        # read the configuration files
        self.pinfo(":: reading the configuration files")
        c = self.get_config()
        packages, modules, initrd_template, install_template = c

        # add the branding
        packages.add("{0}-logos".format(self.product.lower()))
        packages.add("{0}-release".format(self.product.lower()))

        # prepare the install tree
        self.pinfo(":: preparing the install tree")
        self.installtree.install_packages(packages=packages)
        self.installtree.run_ldconfig()
        self.installtree.copy_updates()
        self.installtree.fix_problems()

        # check the anaconda runtime directory
        anarun = os.path.join(self.installtree.rootdir,
                              self.const.ANACONDA_RUNTIME)

        if not os.path.isdir(anarun):
            self.pcritical("no anaconda runtime directory found")
            sys.exit(1)

        # prepare the output directory
        self.pinfo(":: preparing the output directory")
        ok = self.prepare_outputdir()
        if not ok:
            self.pcritical("unable to prepare the output directory")
            sys.exit(1)

        # write the treeinfo, discinfo and buildstamp
        self.pinfo(":: creating the treeinfo, discinfo and buildstamp")
        self.conf.treeinfo = self.write_treeinfo()
        self.conf.discinfo = self.write_discinfo()
        self.conf.buildstamp = self.write_buildstamp()

        # create the initrd images for all kernels in install tree
        initrd = images.InitRD(self.installtree, modules, initrd_template,
                               self.workdir)

        # get all kernels and initrds
        kernel_normal, kernel_pae, kernel_xen = [], [], []
        for kernel, initrd in initrd.create():
            if kernel.is_pae:
                kernel_pae.append((kernel, initrd))
            elif kernel.is_xen:
                kernel_xen.append((kernel, initrd))
            else:
                kernel_normal.append((kernel, initrd))

        # if we have a normal kernel, set it as the main kernel
        kernels = []
        try:
            kernels.append(kernel_normal.pop(0))
        except IndexError:
            pass

        # add pae and xen kernels to the list of kernels
        kernels.extend(kernel_pae)
        kernels.extend(kernel_xen)

        # check if we have at least one kernel
        if not kernels:
            self.pcritical("no kernel images found")
            sys.exit(1)

        # main kernel
        kernel, initrd = kernels.pop(0)
        kernelfile = "vmlinuz"
        initrdfile = "initrd.img"

        # add images section to treeinfo
        section = "images-{0}".format(self.conf.basearch)
        data = {"kernel": "images/pxeboot/{0}".format(kernelfile),
                "initrd": "images/pxeboot/{0}".format(initrdfile)}
        self.treeinfo_add_section(self.conf.treeinfo, section, data)

        # copy the kernel and initrd image to the isolinux directory
        kdst = os.path.join(self.conf.isodir, kernelfile)
        idst = os.path.join(self.conf.isodir, initrdfile)
        shutil.copy2(kernel.path, kdst)
        shutil.copy2(initrd, idst)

        # copy the kernel and initrd image to the pxe directory
        kdst = os.path.join(self.conf.pxedir, kernelfile)
        idst = os.path.join(self.conf.pxedir, initrdfile)
        shutil.copy2(kernel.path, kdst)
        shutil.copy2(initrd, idst)

        # create the efi images
        if self.installtree.do_efi:
            efi = images.EFI(self.installtree, kernel, initrd,
                             self.product, self.version, self.workdir)

            efiboot, efidisk = efi.create()

            # copy the efi images to the images directory
            shutil.copy2(efiboot, self.conf.imgdir)
            shutil.copy2(efidisk, self.conf.imgdir)

        # other kernels
        for kernel, initrd in kernels:
            if kernel.is_pae:
                kernelfile = "vmlinuz-PAE"
                initrdfile = "initrd-PAE.img"
                # XXX add images section to treeinfo
                section = "images-xen"
                data = {"kernel": "images/pxeboot/{0}".format(kernelfile),
                        "initrd": "images/pxeboot/{0}".format(initrdfile)}
                self.treeinfo_add_section(self.conf.treeinfo, section, data)
            elif kernel.is_xen:
                kernelfile = "vmlinuz-xen"
                initrdfile = "initrd-xen.img"
                # XXX add images section to treeinfo
                section = "images-xen"
                data = {"kernel": "images/pxeboot/{0}".format(kernelfile),
                        "initrd": "images/pxeboot/{0}".format(initrdfile)}
                self.treeinfo_add_section(self.conf.treeinfo, section, data)

            # copy the kernel and initrd image to the pxe directory
            kdst = os.path.join(self.conf.pxedir, kernelfile)
            idst = os.path.join(self.conf.pxedir, initrdfile)
            shutil.copy2(kernel.path, kdst)
            shutil.copy2(initrd, idst)

        # create the install image
        install = images.Install(self.installtree, install_template,
                                 self.workdir)

        installimg = install.create()
        if not installimg:
            self.perror("unable to create the install image")
            sys.exit(1)

        # add stage2 section to the treeinfo
        section = "stage2"
        data = {"mainimage": "images/install.img"}
        self.treeinfo_add_section(self.conf.treeinfo, section, data)

        # move the install image to the images directory
        shutil.move(installimg, self.conf.imgdir)

        # create the boot iso image
        boot = images.Boot(self.product, self.workdir)
        bootiso = boot.create()

        # add boot iso to the images section in treeinfo
        section = "images-{0}".format(self.conf.basearch)
        data = {"boot.iso": "images/boot.iso"}
        self.treeinfo_add_section(self.conf.treeinfo, section, data)

        # move the boot iso to the images directory
        shutil.move(bootiso, self.conf.imgdir)

        # copy the treeinfo and discinfo to the output directory
        shutil.copy2(self.conf.treeinfo, self.outputdir)
        shutil.copy2(self.conf.discinfo, self.outputdir)

        # cleanup
        self.cleanup()

    def get_buildarch(self):
        # get the architecture of the anaconda package
        installed, available = self.yum.search(self.const.ANACONDA_PACKAGE)

        if installed:
            anaconda = installed[0]
        if available:
            anaconda = available[0]

        try:
            buildarch = anaconda.arch
        except:
            # fallback to the system architecture
            self.pwarning("using system architecture")
            buildarch = os.uname()[4]

        return buildarch

    def get_config(self):
        generic = os.path.join(self.conf.confdir, "config.noarch")
        specific = os.path.join(self.conf.confdir,
                                "config.{0}".format(self.conf.basearch))

        packages, modules = set(), set()
        initrd_template, install_template = None, None

        for f in (generic, specific):
            if not os.path.isfile(f):
                continue

            c = ConfigParser.ConfigParser()
            c.read(f)

            if c.has_option("lorax", "packages"):
                list = c.get("lorax", "packages").split()
                for name in list:
                    if name.startswith("-"):
                        packages.discard(name)
                    else:
                        packages.add(name)

            if c.has_option("lorax", "modules"):
                list = c.get("lorax", "modules").split()
                for name in list:
                    if name.startswith("-"):
                        modules.discard(name)
                    else:
                        modules.add(name)

            if c.has_option("lorax", "initrd_template"):
                initrd_template = c.get("lorax", "initrd_template")
                initrd_template = os.path.join(self.conf.confdir,
                                               initrd_template)

            if c.has_option("lorax", "install_template"):
                install_template = c.get("lorax", "install_template")
                install_template = os.path.join(self.conf.confdir,
                                                install_template)

        return packages, modules, initrd_template, install_template

    def prepare_outputdir(self):
        imgdir = os.path.join(self.outputdir, "images")
        makedirs_(imgdir)

        # write the images/README file
        text = """
This directory contains image files that can be used to create media
capable of starting the {0} installation process.

The boot.iso file is an ISO 9660 image of a bootable CD-ROM. It is useful
in cases where the CD-ROM installation method is not desired, but the
CD-ROM's boot speed would be an advantage.

To use this image file, burn the file onto CD-R (or CD-RW) media as you
normally would.
"""

        text = text.format(self.product)
        with open(os.path.join(imgdir, "README"), "w") as f:
            f.write(text)

        pxedir = os.path.join(imgdir, "pxeboot")
        makedirs_(pxedir)

        # write the images/pxeboot/README file
        text = """
The files in this directory are useful for booting a machine via PXE.

The following files are available:
vmlinuz - the kernel used for the installer
initrd.img - an initrd with support for all install methods and
             drivers supported for installation of {0}
"""

        text = text.format(self.product)
        with open(os.path.join(pxedir, "README"), "w") as f:
            f.write(text)

        efidir = os.path.join(self.outputdir, "EFI/BOOT")
        makedirs_(efidir)

        isodir = os.path.join(self.outputdir, "isolinux")
        makedirs_(isodir)

        self.conf.imgdir = imgdir
        self.conf.pxedir = pxedir
        self.conf.efidir = efidir
        self.conf.isodir = isodir

        isolinuxbin = os.path.join(self.installtree.rootdir,
                                   self.const.ISOLINUXBIN)
        syslinuxcfg = os.path.join(self.installtree.rootdir,
                                   self.const.SYSLINUXCFG)

        if not os.path.isfile(isolinuxbin):
            self.perror("no isolinux binary found")
            return False

        # copy the isolinux.bin file
        shutil.copy2(isolinuxbin, self.conf.isodir)

        # copy the syslinux.cfg
        isolinuxcfg = os.path.join(self.conf.isodir, "isolinux.cfg")
        shutil.copy2(syslinuxcfg, isolinuxcfg)

        # set the product and version in isolinux.cfg
        replace_(isolinuxcfg, r"@PRODUCT@", self.product)
        replace_(isolinuxcfg, r"@VERSION@", self.version)

        # set up the label for finding stage2 with a hybrid iso
        replace_(isolinuxcfg, r"initrd=initrd.img",
                 'initrd=initrd.img stage2=hd:LABEL="{0}"'.format(self.product))

        # copy the .msg files
        msgfiles = os.path.join(self.const.ANACONDA_BOOTDIR, "*.msg")
        msgfiles = os.path.join(self.installtree.rootdir, msgfiles)
        for fname in glob.iglob(msgfiles):
            shutil.copy2(fname, self.conf.isodir)
            path = os.path.join(self.conf.isodir, os.path.basename(fname))
            replace_(path, r"@VERSION@", self.version)

        # copy the memtest
        memtest = os.path.join(self.const.BOOTDIR, "memtest*")
        memtest = os.path.join(self.installtree.rootdir, memtest)
        for fname in glob.iglob(memtest):
            shutil.copy2(fname, os.path.join(self.conf.isodir, "memtest"))

            text = """label memtest86
  menu label ^Memory test
  kernel memtest
  append -

"""

            with open(isolinuxcfg, "a") as f:
                f.write(text)

            break

        # copy the grub.conf
        grubconf = os.path.join(self.installtree.rootdir,
                                self.const.ANACONDA_BOOTDIR, "grub.conf")
        shutil.copy2(grubconf, isodir)

        # copy the splash files
        vesasplash = os.path.join(self.installtree.rootdir,
                                  self.const.VESASPLASH)
        vesamenu = os.path.join(self.installtree.rootdir,
                                self.const.VESAMENU)

        splashtools = os.path.join(self.installtree.rootdir,
                                   self.const.SPLASHTOOLS)
        syslinuxsplash = os.path.join(self.installtree.rootdir,
                                      self.const.SYSLINUXSPLASH)
        splashlss = os.path.join(self.installtree.rootdir,
                                 self.const.SPLASHLSS)

        if os.path.isfile(vesasplash):
            shutil.copy2(vesasplash, os.path.join(isodir, "splash.jpg"))
            shutil.copy2(vesamenu, isodir)
            replace_(isolinuxcfg, r"default linux", "default vesamenu.c32")
            replace_(isolinuxcfg, r"prompt 1", "#prompt 1")
        else:
            if os.path.isfile(splashtools):
                cmd = "{0} {1} {2}".format(splashtools,
                                           syslinuxsplash,
                                           splashlss)

                err, stdout = commands.getstatusoutput(cmd)
                if err:
                    self.pwarning(stdout)

            if os.path.isfile(splashlss):
                shutil.copy2(splashlss, isodir)

        return True

    def write_treeinfo(self, discnum=1, totaldiscs=1, packagedir=""):
        outfile = os.path.join(self.workdir, ".treeinfo")

        c = ConfigParser.ConfigParser()

        variant = self.variant
        if variant is None:
            variant = ""

        section = "general"
        data = {"timestamp": time.time(),
                "family": self.product,
                "version": self.version,
                "variant": variant,
                "arch": self.conf.basearch,
                "discnum": discnum,
                "totaldiscs": totaldiscs,
                "packagedir": packagedir}

        c.add_section(section)
        map(lambda (key, value): c.set(section, key, value), data.items())

        with open(outfile, "w") as f:
            c.write(f)

        return outfile

    def treeinfo_add_section(self, treeinfo, section, data):
        c = ConfigParser.ConfigParser()
        c.read(treeinfo)

        if not c.has_section(section):
            c.add_section(section)

        map(lambda (key, value): c.set(section, key, value), data.items())

        with open(treeinfo, "w") as f:
            c.write(f)

    def write_discinfo(self, discnum="ALL"):
        outfile = os.path.join(self.workdir, ".discinfo")

        with open(outfile, "w") as f:
            f.write("{0:f}\n".format(time.time()))
            f.write("{0}\n".format(self.release))
            f.write("{0}\n".format(self.conf.basearch))
            f.write("{0}\n".format(discnum))

        return outfile

    def write_buildstamp(self):
        outfile = os.path.join(self.workdir, ".buildstamp")

        now = datetime.datetime.now()
        uuid = "{0}.{1}"
        uuid = uuid.format(now.strftime("%Y%m%d%H%M"), self.conf.buildarch)

        with open(outfile, "w") as f:
            f.write("{0}\n".format(uuid))
            f.write("{0}\n".format(self.product))
            f.write("{0}\n".format(self.version))
            f.write("{0}\n".format(self.bugurl))

        return outfile

    def cleanup(self):
        # TODO
        pass


class YumHelper(object):

    def __init__(self, yb):
        self.yb = yb

    def install(self, pattern):
        try:
            self.yb.install(name=pattern)
        except yum.Errors.InstallError:
            try:
                self.yb.install(pattern=pattern)
            except yum.Errors.InstallError:
                return False

        return True

    def process_transaction(self):
        self.yb.resolveDeps()
        self.yb.buildTransaction()

        cb = yum.callbacks.ProcessTransBaseCallback()
        rpmcb = RpmCallback()

        self.yb.processTransaction(callback=cb, rpmDisplay=rpmcb)

        self.yb.closeRpmDB()
        self.yb.close()

    def search(self, pattern):
        pl = self.yb.doPackageLists(patterns=[pattern])
        return pl.installed, pl.available


class RpmCallback(yum.rpmtrans.SimpleCliCallBack):

    def __init__(self):
        yum.rpmtrans.SimpleCliCallBack.__init__(self)
        self.output = output.LoraxOutput()

        self.termwidth = 79

    def event(self, package, action, te_current, te_total,
              ts_current, ts_total):

        info = "({0:3d}/{1:3d}) [{2:3.0f}%] {3} "
        info = info.format(ts_current, ts_total,
                           float(te_current) / float(te_total) * 100,
                           self.action[action])

        pkg = "{0}".format(package)

        infolen = len(info)
        pkglen = len(pkg)
        if (infolen + pkglen) > self.termwidth:
            pkg = "{0}...".format(pkg[:self.termwidth-infolen-3])

        msg = "{0}<b>{1}</b>\r".format(info, pkg)
        self.output.write(msg)
        if te_current == te_total:
            self.output.write("\n")
