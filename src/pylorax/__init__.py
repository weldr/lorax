#
# __init__.py
# main lorax class
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
# Red Hat Author(s):  David Cantrell <dcantrell@redhat.com>
#                     Martin Gracik <mgracik@redhat.com>
#

__VERSION__ = "0.1"

import sys
import os
import ConfigParser
import re
import glob
import time
import datetime
import shutil
import commands

import yum
import yum.callbacks
import yum.rpmtrans

import config
import output
import ramdisk
import efi
import install
import lcs


ARCHS64         = ( "x86_64",
                    "s390x",
                    "sparc64" )

BASEARCH_MAP    = { "i586" : "i386",
                    "i686" : "i386",
                    "sparc64" : "sparc" }

EFIARCH_MAP     = { "i386" : "IA32",
                    "i586" : "IA32",
                    "i686" : "IA32",
                    "x86_64" : "X64",
                    "ia64" : "IA64" }

LIB32 = "lib"
LIB64 = "lib64"


class LoraxError(Exception):
    pass


class Lorax(object):

    SETTINGS   = ( "colors",
                   "encoding",
                   "debug",
                   "cleanup" )

    REQ_PARAMS = ( "product",
                   "version",
                   "release",
                   "outputdir",
                   "tempdir",
                   "installtree" )

    OPT_PARAMS = ( "variant",
                   "bugurl",
                   "updates" )

    def __init__(self, yb, *args, **kwargs):
        # check if we have root privileges
        if not os.geteuid() == 0:
            raise LoraxError("no root privileges")

        # check the yumbase object
        if not isinstance(yb, yum.YumBase):
            raise LoraxError("not an yumbase object")

        # create the yum object
        self.yum = YumHelper(yb)

        # get the config object
        self.conf = config.LoraxConfig.get()

        # get the settings first
        for key in self.SETTINGS:
            value = kwargs.get(key, None)
            if value is not None:
                setattr(self.conf, key, value)

        # set up the output
        self.output = output.Terminal.get()

        output_level = output.INFO
        if self.conf.debug:
            output_level = output.DEBUG

        self.output.basic_config(colors=self.conf.colors,
                                 encoding=self.conf.encoding,
                                 level=output_level)

        # check and set up the required parameters
        for key in self.REQ_PARAMS:
            value = kwargs.get(key, None)

            if value is None:
                raise LoraxError("missing required parameter '%s'" % key)

            setattr(self.conf, key, value)

        # set up the optional parameters
        for key in self.OPT_PARAMS:
            setattr(self.conf, key, kwargs.get(key, ""))

        # check if the required directories exist
        if os.path.isdir(self.conf.outputdir):
            raise LoraxError("output directory '%s' already exist" % \
                             self.conf.outputdir)

        if not os.path.isdir(self.conf.tempdir):
            raise LoraxError("temporary directory '%s' does not exist" % \
                             self.conf.tempdir)

        if not os.path.isdir(self.conf.installtree):
            raise LoraxError("install tree directory '%s' does not exist" % \
                             self.conf.installtree)

        # get the paths
        self.paths = config.LoraxPaths.get()

    def run(self):
        # set the target architecture
        self.output.info(":: setting the build architecture")
        self.conf.arch = self.get_arch()
        self.conf.basearch = BASEARCH_MAP.get(self.conf.arch, self.conf.arch)
        self.conf.efiarch = EFIARCH_MAP.get(self.conf.arch, "")

        # set the libdir
        self.conf.libdir = LIB32
        if self.conf.arch in ARCHS64:
            self.conf.libdir = LIB64

        # read the config files
        self.output.info(":: reading the configuration files")
        packages, modules, initrd_template, scrubs_template = self.get_config()

        # add the branding
        packages.add("%s-logos" % self.conf.product.lower())
        packages.add("%s-release" % self.conf.product.lower())

        self.conf.packages = packages
        self.conf.modules = modules
        self.conf.initrd_template = initrd_template
        self.conf.scrubs_template = scrubs_template

        # install packages into the install tree
        self.output.info(":: installing required packages")
        for name in packages:
            if not self.yum.install(name):
                self.output.warning("no package %s found" % \
                                    self.output.format(name, type=output.BOLD))

        self.yum.process_transaction()

        # copy the updates
        if self.conf.updates and os.path.isdir(self.conf.updates):
            self.output.info(":: copying updates")
            utils.scopy(src_root=self.conf.updates, src_path="*",
                        dst_root=self.conf.installtree, dst_path="")

        # get the anaconda runtime directory
        if os.path.isdir(self.paths.ANACONDA_RUNTIME):
            self.conf.anaconda_runtime = self.paths.ANACONDA_RUNTIME
            self.conf.anaconda_boot = self.paths.ANACONDA_BOOT
        else:
            self.output.critical("no anaconda runtime directory found")
            sys.exit(1)

        # get list of the installed kernel files
        kerneldir = self.paths.BOOTDIR
        if self.conf.arch == "ia64":
            kerneldir = self.paths.BOOTDIR_IA64

        kernelfiles = glob.glob(os.path.join(kerneldir, "vmlinuz-*"))

        if not kernelfiles:
            self.output.critical("no kernel image found")
            sys.exit(1)

        # create treeinfo, discinfo, and buildstamp
        self.conf.treeinfo = self.write_treeinfo()
        self.conf.discinfo = self.write_discinfo()
        self.conf.buildstamp = self.write_buildstamp()

        # prepare the output directory
        self.output.info(":: preparing the output directory")
        ok = self.prepare_output_directory()

        if not ok:
            self.output.critical("unable to prepare the output directory")
            sys.exit(1)

        for kernelfile in kernelfiles:
            kfilename = os.path.basename(kernelfile)
            m = re.match(r"vmlinuz-(?P<ver>.*)", kfilename)
            if m:
                self.conf.kernelfile = kernelfile
                self.conf.kernelver = m.group("ver")
            else:
                continue

            self.output.info(":: creating initrd for '%s'" % kfilename)

            # create a temporary directory for the ramdisk tree
            self.conf.ramdisktree = os.path.join(self.conf.tempdir,
                                                 "ramdisk-%s" % \
                                                 self.conf.kernelver)

            utils.makedirs(self.conf.ramdisktree)

            initrd = ramdisk.Ramdisk()
            kernel_path, initrd_path = initrd.create()

            # copy the kernel and initrd images to the pxeboot directory
            if kernel_path is not None:
                shutil.copy2(kernel_path, self.conf.pxebootdir)
            if kernel_path is not None:
                shutil.copy2(initrd_path, self.conf.pxebootdir)

            # if this is a PAE kernel, skip the EFI part
            if kernel_path.endswith("PAE"):
                continue

            # copy the kernel and initrd images to the isolinux directory
            shutil.copy2(kernel_path, self.conf.isolinuxdir)
            shutil.copy2(initrd_path, self.conf.isolinuxdir)

            # create the efi images
            self.output.info(":: creating efi images for '%s'" % kfilename)

            efiimages = efi.EFI()
            eb, ed = efiimages.create(kernel=kernel_path,
                                      initrd=initrd_path,
                                      kernelpath="/images/pxeboot/vmlinuz",
                                      initrdpath="/images/pxeboot/initrd.img")

            self.conf.efiboot = eb
            self.conf.efidisk = ed

            # copy the efi images to the images directory
            shutil.copy2(self.conf.efiboot, self.conf.imagesdir)
            shutil.copy2(self.conf.efidisk, self.conf.imagesdir)

        # create the install image
        self.output.info(":: creating the install image")
        i = install.InstallImage()
        installimg = i.create()

        if installimg is None:
            self.output.critical("unable to create install image")
            sys.exit(1)

        shutil.copy2(installimg, self.conf.imagesdir)

        # create the boot iso
        if self.conf.arch in ("i386", "i586", "i686", "x86_64"):
            self.output.info(":: creating the boot iso")
            bootiso = self.create_boot_iso_x86()
        elif self.conf.arch in ("ppc", "ppc64"):
            self.output.info(":: creating the boot iso")
            bootiso = self.create_boot_iso_ppc()

        if bootiso is None:
            self.output.critical("unable to create boot iso")
            sys.exit(1)

        shutil.copy2(bootiso, self.conf.imagesdir)

        # copy the treeinfo and discinfo to the output directory
        shutil.copy2(self.conf.treeinfo, self.conf.outputdir)
        shutil.copy2(self.conf.discinfo, self.conf.outputdir)

        # cleanup
        self.cleanup()

    def get_arch(self):
        # get the architecture of the anaconda package
        installed, available = self.yum.search(self.paths.ANACONDA_PACKAGE)
        try:
            arch = available[0].arch
        except:
            # fallback to the system architecture
            arch = os.uname()[4]

        return arch

    def get_config(self):
        generic = os.path.join(self.conf.confdir, "config.noarch")
        specific = os.path.join(self.conf.confdir,
                                "config.%s" % self.conf.arch)

        packages, modules = set(), set()
        initrd_template, scrubs_template = None, None

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

            if c.has_option("lorax", "scrubs_template"):
                scrubs_template = c.get("lorax", "scrubs_template")
                scrubs_template = os.path.join(self.conf.confdir,
                                               scrubs_template)

        return packages, modules, initrd_template, scrubs_template

    def write_treeinfo(self, discnum=1, totaldiscs=1, packagedir=""):
        outfile = os.path.join(self.conf.tempdir, ".treeinfo")

        variant = self.conf.variant
        if variant is None:
            variant = ""

        c = ConfigParser.ConfigParser()

        section = "general"
        data = { "timestamp" : time.time(),
                 "family" : self.conf.product,
                 "version" : self.conf.version,
                 "arch" : self.conf.basearch,
                 "variant" : variant,
                 "discnum" : discnum,
                 "totaldiscs" : totaldiscs,
                 "packagedir" : packagedir }

        c.add_section(section)
        map(lambda (key, value): c.set(section, key, value), data.items())

        section = "images-%s" % self.conf.basearch
        data = { "kernel" : "images/pxeboot/vmlinuz",
                 "initrd" : "images/pxeboot/initrd.img",
                 "boot.iso" : "images/boot.iso" }

        c.add_section(section)
        map(lambda (key, value): c.set(section, key, value), data.items())

        with open(outfile, "w") as f:
            c.write(f)

        return outfile

    def write_discinfo(self, discnum="ALL"):
        outfile = os.path.join(self.conf.tempdir, ".discinfo")

        with open(outfile, "w") as f:
            f.write("%f\n" % time.time())
            f.write("%s\n" % self.conf.release)
            f.write("%s\n" % self.conf.basearch)
            f.write("%s\n" % discnum)

        return outfile

    def write_buildstamp(self):
        outfile = os.path.join(self.conf.tempdir, ".buildstamp")

        now = datetime.datetime.now()
        uuid = "%s.%s" % (now.strftime("%Y%m%d%H%M"), self.conf.arch)

        with open(outfile, "w") as f:
            f.write("%s\n" % uuid)
            f.write("%s\n" % self.conf.product)
            f.write("%s\n" % self.conf.version)
            f.write("%s\n" % self.conf.bugurl)

        return outfile

    def prepare_output_directory(self):
        # create the output directory
        os.mkdir(self.conf.outputdir)

        # create the images directory
        imagesdir = os.path.join(self.conf.outputdir, "images")
        utils.mkdir(imagesdir)
        self.conf.imagesdir = imagesdir

        # write the images/README file
        src = os.path.join(self.paths.OUTPUTDIR_DATADIR, "images", "README")
        dst = os.path.join(imagesdir, "README")
        shutil.copy2(src, dst)
        utils.replace(dst, r"@PRODUCT@", self.conf.product)

        # create the pxeboot directory
        pxebootdir = os.path.join(imagesdir, "pxeboot")
        utils.mkdir(pxebootdir)
        self.conf.pxebootdir = pxebootdir

        # write the images/pxeboot/README file
        src = os.path.join(self.paths.OUTPUTDIR_DATADIR, "images", "pxeboot",
                           "README")
        dst = os.path.join(pxebootdir, "README")
        shutil.copy2(src, dst)
        utils.replace(dst, r"@PRODUCT@", self.conf.product)

        # create the efiboot directory
        efibootdir = os.path.join(self.conf.outputdir, "EFI", "BOOT")
        utils.makedirs(efibootdir)
        self.conf.efibootdir = efibootdir

        # create the isolinux directory
        isolinuxdir = os.path.join(self.conf.outputdir, "isolinux")
        utils.mkdir(isolinuxdir)
        self.conf.isolinuxdir = isolinuxdir

        syslinuxdir = self.paths.SYSLINUXDIR
        isolinuxbin = self.paths.ISOLINUXBIN

        if not os.path.isfile(isolinuxbin):
            self.output.error("no isolinux binary found")
            return False

        # copy the isolinux.bin
        shutil.copy2(isolinuxbin, isolinuxdir)

        # copy the syslinux.cfg to isolinux/isolinux.cfg
        isolinuxcfg = os.path.join(isolinuxdir, "isolinux.cfg")
        shutil.copy2(self.paths.SYSLINUXCFG, isolinuxcfg)

        # set the product and version in isolinux.cfg
        utils.replace(isolinuxcfg, r"@PRODUCT@", self.conf.product)
        utils.replace(isolinuxcfg, r"@VERSION@", self.conf.version)

        # set up the label for finding stage2 with a hybrid iso
        utils.replace(isolinuxcfg, r"initrd=initrd.img",
                      'initrd=initrd.img stage2=hd:LABEL="%s"' % \
                      self.conf.product)

        # copy the grub.conf
        dst = os.path.join(isolinuxdir, "grub.conf")
        shutil.copy2(self.paths.GRUBCONF, dst)

        # copy the splash files
        if os.path.isfile(self.paths.VESASPLASH):
            shutil.copy2(self.paths.VESASPLASH,
                         os.path.join(isolinuxdir, "splash.jpg"))

            shutil.copy2(self.paths.VESAMENU, isolinuxdir)

            utils.replace(isolinuxcfg, r"default linux", "default vesamenu.c32")
            utils.replace(isolinuxcfg, r"prompt 1", "#prompt 1")

        else:
            if os.path.isfile(self.paths.SPLASHTOOLS):
                cmd = "%s %s %s" % (self.paths.SPLASHTOOLS,
                                    self.paths.SYSLINUXSPLASH,
                                    self.paths.SPLASHLSS)
                err, output = commands.getstatusoutput(cmd)
                if err:
                    self.output.warning(output)

            if os.path.isfile(self.paths.SPLASHLSS):
                shutil.copy2(self.paths.SPLASHLSS, isolinuxdir)

        # copy the .msg files
        msgfiles = os.path.join(self.conf.anaconda_boot, "*.msg")
        for fname in glob.glob(msgfiles):
            shutil.copy2(fname, isolinuxdir)
            utils.replace(os.path.join(isolinuxdir, os.path.basename(fname)),
                          r"@VERSION@", self.conf.version)

        # copy the memtest
        memtest = os.path.join(self.paths.BOOTDIR, "memtest*")
        for fname in glob.glob(memtest):
            shutil.copy2(fname, os.path.join(isolinuxdir, "memtest"))

            text = """label memtest86
  menu label ^Memory test
  kernel memtest
  append -

"""

            utils.edit(isolinuxcfg, append=True, text=text)
            break

        return True

    def create_boot_iso_x86(self):
        bootiso = os.path.join(self.conf.tempdir, "boot.iso")

        if os.path.exists(bootiso):
            os.unlink(bootiso)

        if os.path.exists(self.conf.efiboot):
            self.output.info(":: creating efi capable boot iso")
            efiargs = "-eltorito-alt-boot -e images/efiboot.img -no-emul-boot"
            efigraft = "EFI/BOOT=%s" % self.conf.efibootdir
        else:
            efiargs = ""
            efigraft = ""

        #biosargs = "-b isolinux/isolinux.bin -c isolinux/boot.cat" \
        #           " -no-emul-boot -boot-load-size 4 -boot-info-table"

        #cmd = "%s -v -o %s %s %s -R -J -V %s -T -graft-points" \
        #      " isolinux=%s images=%s %s" % (self.paths.MKISOFS, bootiso,
        #                                     biosargs, efiargs,
        #                                     self.conf.product,
        #                                     self.conf.isolinuxdir,
        #                                     self.conf.imagesdir, efigraft)

        cmd = "%s -U -A %s -V %s -volset %s -J -joliet-long -r -v -T -o %s" \
              " -b isolinux/isolinux.bin -c isolinux/boot.cat" \
              " -no-emul-boot -boot-load-size 4 -boot-info-table" \
              " %s -graft-points isolinux=%s images=%s %s" \
              % (self.paths.MKISOFS, self.conf.product, self.conf.product,
                 self.conf.product, bootiso, efiargs,
                 self.conf.isolinuxdir, self.conf.imagesdir, efigraft)

        err, output = commands.getstatusoutput(cmd)
        if err:
            self.output.error(output)
            return None

        if os.path.isfile(self.paths.ISOHYBRID):
            cmd = "%s %s" % (self.paths.ISOHYBRID, bootiso)
            err, output = commands.getstatusoutput(cmd)
            if err:
                self.output.warning(output)

        return bootiso

    def create_boot_iso_ppc(self):
        bootiso = os.path.join(self.conf.tempdir, "boot.iso")

        if os.path.exists(bootiso):
            os.unlink(bootiso)

        etcdir = os.path.join(self.conf.outputdir, "etc")
        ppcdir = os.path.join(self.conf.outputdir, "ppc")
        macdir = os.path.join(ppcdir, "mac")
        chrpdir = os.path.join(ppcdir, "chrp")

        utils.makedirs(etcdir)
        utils.makedirs(chrpdir)

        shutil.copy2(self.paths.BOOTINFO, ppcdir)
        shutil.copy2(self.paths.EFIKA_FORTH, ppcdir)

        if os.path.isdir(macdir):
            shutil.copy2(self.paths.OFBOOT, macdir)
            shutil.copy2(self.paths.YABOOT, macdir)

        if os.path.isdir(chrpdir):
            shutil.copy2(self.paths.YABOOT, chrpdir)
            cmd = "%s %s" % (self.paths.ADD_NOTE,
                             os.path.join(chrpdir, "yaboot"))

        # IBM firmware can't handle boot scripts properly,
        # so for biarch installs we use a yaboot.conf,
        # which asks the user to select 32-bit or 64-bit kernel
        yaboot32 = os.path.join(ppcdir, "ppc32", "yaboot.conf")
        yaboot64 = os.path.join(ppcdir, "ppc64", "yaboot.conf")
        if os.path.isfile(yaboot32) and os.path.isfile(yaboot64):
            # both kernels exist, copy the biarch yaboot.conf into place
            yaboot = os.path.join(etcdir, "yaboot.conf")
            shutil.copy2(self.paths.BIARCH_YABOOT, yaboot)
            utils.replace(yaboot, "%BITS%", "32")
            utils.replace(yaboot, "%PRODUCT%", self.conf.product)
            utils.replace(yaboot, "%VERSION%", self.conf.version)
        else:
            if os.path.isfile(yaboot32):
                shutil.copy2(yaboot32, etcdir)
            if os.path.isfile(yaboot64):
                shutil.copy2(yaboot64, etcdir)

        isopath = os.path.join(self.conf.outputdir, "isopath")
        utils.mkdir(isopath)

        utils.scopy(ppcdir, isopath)
        utils.scopy(etcdir, isopath)

        netbootdir = os.path.join(self.conf.outputdir, "images", "netboot")
        if os.path.isdir(netbootdir):
            imagesdir = os.path.join(isopath, "images")
            utils.mkdir(imagesdir)

            utils.scopy(netbootdir, imagesdir)
            utils.remove(os.path.join(imagesdir, "ppc64.img"))

        ppc32img = os.path.join(netbootdir, "ppc32.img")
        if os.path.isfile(pcp32img):
            prepboot = "-prep-boot images/netboot/ppc32.img"

        isomacdir = os.path.join(isopath, "ppc", "mac")
        if os.path.isdir(isomacdir):
            macboot = "-hfs-volid %s -hfs-bless %s" % (self.conf.version,
                                                       isomacdir)

        installimg = os.path.join(self.conf.imagesdir, "install.img")
        cmd = '%s -o %s -chrp-boot -U %s -part -hfs -T -r -l -J -A "%s %s"' \
              ' -sysid PPC -V "PBOOT" -volset %s -volset-size 1' \
              ' -volset-seqno 1 %s -map %s/mapping -magic %s/magic' \
              ' -no-desktop' \
              ' -allow-multidot -graft-points %s images/install.img=%s' % \
              (self.paths.MKISOFS, bootiso, prepboot, self.conf.product,
               self.conf.version, self.conf.version, macboot,
               self.paths.ANACONDA_BOOT, self.paths.ANACONDA_BOOT,
               isopath, installimg)

        err, output = commands.getstatusoutput(cmd)
        if err:
            self.output.warning(output)
            return None

        cmd = "%s %s" % (self.paths.IMPLANTISO, bootiso)
        err, output = commands.getstatusoutput(cmd)
        if err:
            self.output.warning(output)
            return None

        utils.remove(isopath)

        return bootiso

    def cleanup(self):
        if self.conf.cleanup:
            shutil.rmtree(self.conf.tempdir)


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
        self.output = output.Terminal.get()

    def event(self, package, action, te_current, te_total,
            ts_current, ts_total):

        msg = "(%3d/%3d) [%3d%%] %s %s\r" % (ts_current, ts_total,
                float(te_current) / float(te_total) * 100,
                self.action[action],
                self.output.format("%s" % package, type=output.BOLD))

        self.output.write(msg)
        if te_current == te_total:
            self.output.write("\n")
