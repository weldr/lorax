#
# __init__.py
#
# Copyright (C) 2010  Red Hat, Inc.
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

# set up logging
import logging
logging.basicConfig(level=logging.DEBUG, filename="pylorax.log", filemode="w")

sh = logging.StreamHandler()
sh.setLevel(logging.INFO)
logging.getLogger("").addHandler(sh)

logger = logging.getLogger("pylorax")


import sys
import os
import ConfigParser
import tempfile
import shutil
import gzip
import shlex
import fnmatch
import re
import itertools
import glob
import time
import datetime
import itertools
import subprocess
import operator
import math

from collections import namedtuple

from base import BaseLoraxClass
import output

import yum
import yumhelper
import ltmpl

import constants
from sysutils import *


ARCHMAPS = {
        "i386":     {"base": "i386",    "efi": "IA32",  "is64": False},
        "i586":     {"base": "i386",    "efi": "IA32",  "is64": False},
        "i686":     {"base": "i386",    "efi": "IA32",  "is64": False},
        "x86_64":   {"base": "x86_64",  "efi": "X64",   "is64": True},
        "ppc":      {"base": "ppc",     "efi": "",      "is64": False},
        "ppc64":    {"base": "ppc",     "efi": "",      "is64": True},
        "s390":     {"base": "s390",    "efi": "",      "is64": False},
        "s390x":    {"base": "s390x",   "efi": "",      "is64": True},
        "sparc":    {"base": "sparc",   "efi": "",      "is64": False},
        "sparc64":  {"base": "sparc",   "efi": "",      "is64": True},
        "ia64":     {"base": "ia64",    "efi": "IA64",  "is64": True}
        }

LIB32 = "lib"
LIB64 = "lib64"


# kernel types
K_NORMAL = 0
K_PAE = 1
K_XEN = 1


# XXX kernel tuple
Kernel = namedtuple("Kernel", "fname fpath version type")


class Lorax(BaseLoraxClass):

    def __init__(self):
        BaseLoraxClass.__init__(self)
        self._configured = False

    def configure(self, conf_file="/etc/lorax/lorax.conf"):
        self.conf = ConfigParser.SafeConfigParser()

        # set defaults
        self.conf.add_section("lorax")
        self.conf.set("lorax", "debug", "1")
        self.conf.set("lorax", "sharedir", "/usr/share/lorax")

        self.conf.add_section("output")
        self.conf.set("output", "colors", "1")
        self.conf.set("output", "encoding", "utf-8")
        self.conf.set("output", "ignorelist", "/usr/share/lorax/ignorelist")

        self.conf.add_section("templates")
        self.conf.set("templates", "ramdisk", "ramdisk.ltmpl")

        # read the config file
        if os.path.isfile(conf_file):
            self.conf.read(conf_file)

        # set up the output
        debug = self.conf.getboolean("lorax", "debug")
        output_level = output.DEBUG if debug else output.INFO

        colors = self.conf.getboolean("output", "colors")
        encoding = self.conf.get("output", "encoding")

        self.output.basic_config(output_level=output_level,
                                 colors=colors, encoding=encoding)

        ignorelist = self.conf.get("output", "ignorelist")
        if os.path.isfile(ignorelist):
            with open(ignorelist, "r") as fobj:
                for line in fobj:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        self.output.ignore(line)

        self._configured = True

    def run(self, yb, product, version, release, variant="", bugurl="",
            is_beta=False, workdir=None, outputdir=None):

        # XXX
        assert self._configured

        # do we have root privileges?
        logger.info("checking for root privileges")
        if not os.geteuid() == 0:
            logger.critical("no root privileges")
            sys.exit(1)

        # XXX do we have all lorax required commands?
        self.lcmds = constants.LoraxRequiredCommands()
        missing = self.lcmds.get_missing()
        if missing:
            logger.critical("missing required command: {0}".format(missing))
            sys.exit(1)

        # do we have a proper yum base object?
        logger.info("checking yum base object")
        if not isinstance(yb, yum.YumBase):
            logger.critical("no yum base object")
            sys.exit(1)

        # set up yum helper
        logger.info("setting up yum helper")
        self.yum = yumhelper.LoraxYumHelper(yb)
        logger.debug("using install root: {0}".format(self.yum.installroot))

        # set up build architecture
        logger.info("setting up build architecture")
        self.buildarch = self.get_buildarch()
        archmap = ARCHMAPS.get(self.buildarch)

        # XXX
        assert archmap is not None

        self.basearch = archmap.get("base")
        self.efiarch = archmap.get("efi")
        self.libdir = LIB64 if archmap.get("is64") else LIB32

        logger.debug("set buildarch = {0.buildarch}".format(self))
        logger.debug("set basearch = {0.basearch}".format(self))
        logger.debug("set efiarch = {0.efiarch}".format(self))
        logger.debug("set libdir = {0.libdir}".format(self))

        # set up install tree
        logger.info("setting up install tree")
        self.installtree = LoraxInstallTree(self.yum, self.basearch,
                                            self.libdir)

        # set up required build parameters
        logger.info("setting up build parameters")
        self.product = product
        self.version = version
        self.release = release
        logger.debug("set product = {0.product}".format(self))
        logger.debug("set version = {0.version}".format(self))
        logger.debug("set release = {0.release}".format(self))

        # set up optional build parameters
        self.variant = variant
        self.bugurl = bugurl
        self.is_beta = is_beta
        logger.debug("set variant = {0.variant}".format(self))
        logger.debug("set bugurl = {0.bugurl}".format(self))
        logger.debug("set is_beta = {0.is_beta}".format(self))

        # XXX set up work directory
        logger.info("setting up work directory")
        self.workdir = workdir or tempfile.mkdtemp(prefix="pylorax.work.")
        if not os.path.isdir(self.workdir):
            os.makedirs(self.workdir)
        logger.debug("using work directory {0.workdir}".format(self))

        # parse the template
        logger.info("parsing the template")
        tfile = joinpaths(self.conf.get("lorax", "sharedir"),
                          self.conf.get("templates", "ramdisk"))

        vars = { "basearch": self.basearch,
                 "libdir" : self.libdir,
                 "product": self.product.lower() }

        template = ltmpl.LoraxTemplate()
        template = template.parse(tfile, vars)

        # get list of required packages
        logger.info("getting list of required packages")
        required = [f[1:] for f in template if f[0] == "install"]
        required = itertools.chain.from_iterable(required)

        # install packages
        for package in required:
            self.installtree.yum.install(package)
        self.installtree.yum.process_transaction()

        # write .buildstamp
        buildstamp = BuildStamp(self.workdir, self.product, self.version,
                                self.bugurl, self.is_beta, self.buildarch)

        buildstamp.write()
        shutil.copy2(buildstamp.path, self.installtree.root)

        # XXX save list of installed packages
        with open(joinpaths(self.workdir, "packages"), "w") as fobj:
            for pkgname in self.installtree.yum.installed_packages:
                fobj.write("{0}\n".format(pkgname))

        # remove locales
        logger.info("removing locales")
        self.installtree.remove_locales()

        # create keymaps
        logger.info("creating keymaps")
        self.installtree.create_keymaps()

        # create screenfont
        logger.info("creating screenfont")
        self.installtree.create_screenfont()

        # move stubs
        logger.info("moving stubs")
        self.installtree.move_stubs()

        # get the list of required modules
        logger.info("getting list of required modules")
        modules = [f[1:] for f in template if f[0] == "module"]
        modules = itertools.chain.from_iterable(modules)

        for kernel in self.installtree.kernels:
            logger.info("cleaning up kernel modules")
            self.installtree.cleanup_kernel_modules(modules, kernel)

            logger.info("compressing modules")
            self.installtree.compress_modules(kernel)

            logger.info("running depmod")
            self.installtree.run_depmod(kernel)

        # create gconf
        logger.info("creating gconf files")
        self.installtree.create_gconf()

        # move repos
        logger.info("moving anaconda repos")
        self.installtree.move_repos()

        # create depmod conf
        logger.info("creating depmod.conf")
        self.installtree.create_depmod_conf()

        # misc tree modifications
        self.installtree.misc_tree_modifications()

        # get config files
        config_dir = joinpaths(self.conf.get("lorax", "sharedir"),
                               "config_files")

        self.installtree.get_config_files(config_dir)
        self.installtree.setup_sshd(config_dir)

        # get anaconda portions
        self.installtree.get_anaconda_portions()

        # set up output tree
        logger.info("setting up output tree")
        self.outputdir = outputdir or tempfile.mkdtemp(prefix="pylorax.out.")
        if not os.path.isdir(self.outputdir):
            os.makedirs(self.outputdir)
        logger.debug("using output directory {0.outputdir}".format(self))

        self.outputtree = LoraxOutputTree(self.outputdir, self.installtree,
                                          self.product, self.version)

        self.outputtree.prepare()
        self.outputtree.get_isolinux()
        self.outputtree.get_msg_files()
        self.outputtree.get_grub_conf()

        # write .discinfo
        discinfo = DiscInfo(self.workdir, self.release, self.basearch)
        discinfo.write()

        shutil.copy2(discinfo.path, self.outputtree.root)

        # XXX
        grubefi = joinpaths(self.installtree.root, "boot/efi/EFI/redhat",
                            "grub.efi")

        if os.path.isfile(grubefi):
            shutil.move(grubefi, self.workdir)
            grubefi = joinpaths(self.workdir, os.path.basename(grubefi))
        else:
            grubefi = None

        splash = joinpaths(self.installtree.root, "boot/grub/",
                           "splash.xpm.gz")

        shutil.move(splash, self.workdir)
        splash = joinpaths(self.workdir, os.path.basename(splash))

        # move kernels to workdir
        kernels = []
        for kernel in self.installtree.kernels:
            type = ""
            if kernel.type == K_PAE:
                type = "-PAE"
            elif kernel.type == K_XEN:
                type = "-XEN"

            kname = "vmlinuz{0}".format(type)

            shutil.move(kernel.fpath, joinpaths(self.workdir, kname))
            kernels.append(Kernel(kname,
                                  joinpaths(self.workdir, kname),
                                  kernel.version,
                                  kernel.type))

        self.outputtree.get_kernels(kernels[:])

        # get list of not required packages
        logger.info("getting list of not required packages")
        remove = [f[1:] for f in template if f[0] == "remove"]

        rdb = {}
        order = []
        for item in remove:
            package = None
            pattern = None

            if item[0] == "--path":
                # remove files
                package = None
                pattern = item[1]
            else:
                # remove package
                package = item[0]

                try:
                    pattern = item[1]
                except IndexError:
                    pattern = None

            if package not in rdb:
                rdb[package] = [pattern]
                order.append(package)
            elif pattern not in rdb[package]:
                rdb[package].append(pattern)

        for package in order:
            pattern_list = rdb[package]
            logger.debug("{0}\t{1}".format(package, pattern_list))
            self.installtree.yum.remove(package, pattern_list)

        # cleanup python files
        logger.info("cleaning up python files")
        self.installtree.cleanup_python_files()

        # compress install tree
        InitRD = namedtuple("InitRD", "fname fpath")
        initrd = InitRD("initrd.img", joinpaths(self.workdir, "initrd.img"))

        logger.info("compressing install tree")
        ok, elapsed = self.installtree.compress(initrd)
        if not ok:
            logger.error("error while compressing install tree")
        else:
            logger.info("took {0:.2f} seconds".format(elapsed))

        # copy initrd to pxebootdir
        shutil.copy2(initrd.fpath, self.outputtree.pxebootdir)

        # create initrd hard link in isolinuxdir
        source = joinpaths(self.outputtree.pxebootdir, initrd.fname)
        link_name = joinpaths(self.outputtree.isolinuxdir, initrd.fname)
        os.link(source, link_name)

        # create efi images
        efiboot = None
        if grubefi:
            kernel = kernels[0]

            # create efiboot image with kernel
            logger.info("creating efiboot image with kernel")
            efiboot = self.create_efiboot(kernel, initrd, grubefi, splash,
                                          include_kernel=True)

            if efiboot is None:
                logger.critical("unable to create efiboot image")
                sys.exit(1)

            # create efidisk image
            logger.info("creating efidisk image")
            efidisk = self.create_efidisk(efiboot)
            if efidisk is None:
                logger.critical("unable to create efidisk image")
                sys.exit(1)

            # remove efiboot image with kernel
            os.unlink(efiboot)

            # create efiboot image without kernel
            logger.info("creating efiboot image without kernel")
            efiboot = self.create_efiboot(kernel, initrd, grubefi, splash,
                                          include_kernel=False)

            if efiboot is None:
                logger.critical("unable to create efiboot image")
                sys.exit(1)

            # XXX copy efiboot and efidisk to imgdir
            shutil.copy2(efiboot, self.outputtree.imgdir)
            shutil.copy2(efidisk, self.outputtree.imgdir)

        # create boot iso
        logger.info("creating boot iso")
        bootiso = self.create_bootiso(self.outputtree, efiboot)
        if bootiso is None:
            logger.critical("unable to create boot iso")
            sys.exit(1)

        shutil.move(bootiso, self.outputtree.imgdir)

        # write .treeinfo
        treeinfo = TreeInfo(self.workdir, self.product, self.version,
                            self.variant, self.basearch)

        # add the boot.iso
        section = "general"
        data = {"boot.iso": "images/{0}".format(os.path.basename(bootiso))}
        treeinfo.add_section(section, data)

        treeinfo.write()

        shutil.copy2(treeinfo.path, self.outputtree.root)

    def get_buildarch(self):
        # get architecture of the available anaconda package
        installed, available = self.yum.search("anaconda")

        if available:
            anaconda = available[0]
            buildarch = anaconda.arch
        else:
            # fallback to the system architecture
            logger.warning("using system architecture")
            buildarch = os.uname()[4]

        return buildarch

    def create_efiboot(self, kernel, initrd, grubefi, splash,
                       include_kernel=True):

        # create the efi tree directory
        efitree = tempfile.mkdtemp(prefix="efitree.", dir=self.workdir)

        # copy kernel and initrd files to efi tree directory
        if include_kernel:
            shutil.copy2(kernel.fpath, efitree)
            shutil.copy2(initrd.fpath, efitree)
            efikernelpath = "/EFI/BOOT/{0}".format(kernel.fname)
            efiinitrdpath = "/EFI/BOOT/{0}".format(initrd.fname)
        else:
            efikernelpath = "/images/pxeboot/{0}".format(kernel.fname)
            efiinitrdpath = "/images/pxeboot/{0}".format(initrd.fname)

        efisplashpath = "/EFI/BOOT/splash.xpm.gz"

        # copy conf files to efi tree directory
        src = joinpaths(self.installtree.root, "usr/share/anaconda/boot",
                        "*.conf")

        for fname in glob.glob(src):
            shutil.copy2(fname, efitree)

        # edit the grub.conf file
        grubconf = joinpaths(efitree, "grub.conf")
        replace(grubconf, "@PRODUCT@", self.product)
        replace(grubconf, "@VERSION@", self.version)
        replace(grubconf, "@KERNELPATH@", efikernelpath)
        replace(grubconf, "@INITRDPATH@", efiinitrdpath)
        replace(grubconf, "@SPLASHPATH@", efisplashpath)

        if self.efiarch == "IA32":
            shutil.copy2(grubconf, joinpaths(efitree, "BOOT.conf"))

        dst = joinpaths(efitree, "BOOT{0}.conf".format(self.efiarch))
        shutil.move(grubconf, dst)

        # copy grub.efi
        if self.efiarch == "IA32":
            shutil.copy2(grubefi, joinpaths(efitree, "BOOT.efi"))

        dst = joinpaths(efitree, "BOOT{0}.efi".format(self.efiarch))
        shutil.copy2(grubefi, dst)

        # copy splash.xpm.gz
        shutil.copy2(splash, efitree)

        efiboot = joinpaths(self.workdir, "efiboot.img")
        if os.path.isfile(efiboot):
            os.unlink(efiboot)

        # XXX calculate the size of the efi tree directory
        overhead = 512 * 1024

        sizeinbytes = overhead
        for root, dnames, fnames in os.walk(efitree):
            for fname in fnames:
                fpath = joinpaths(root, fname)
                fsize = os.path.getsize(fpath)

                # round to multiplications of 4096
                fsize = math.ceil(fsize / 4096.0) * 4096
                sizeinbytes += fsize

        # mkdosfs needs the size in blocks of 1024 bytes
        size = int(math.ceil(sizeinbytes / 1024.0))

        cmd = [self.lcmds.MKDOSFS, "-n", "ANACONDA", "-C", efiboot, str(size)]
        logger.debug(cmd)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        p.wait()

        # mount the efiboot image
        efibootdir = tempfile.mkdtemp(prefix="efiboot.", dir=self.workdir)

        cmd = [self.lcmds.MOUNT, "-o", "loop,shortname=winnt,umask=0777",
               "-t", "vfat", efiboot, efibootdir]
        logger.debug(cmd)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        p.wait()

        # copy the files to the efiboot image
        dst = joinpaths(efibootdir, "EFI/BOOT")
        os.makedirs(dst)

        for fname in os.listdir(efitree):
            fpath = joinpaths(efitree, fname)
            shutil.copy2(fpath, dst)

            if not include_kernel:
                shutil.copy2(fpath, self.outputtree.efibootdir)

        # unmount the efiboot image
        cmd = [self.lcmds.UMOUNT, efibootdir]
        logger.debug(cmd)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        p.wait()

        # remove the work directories
        shutil.rmtree(efibootdir)
        #shutil.rmtree(efitree)

        return efiboot

    def create_efidisk(self, efiboot):
        efidisk = joinpaths(self.workdir, "efidisk.img")
        if os.path.isfile(efidisk):
            os.unlink(efidisk)

        partsize = os.path.getsize(efiboot)
        disksize = 17408 + partsize + 17408
        disksize = disksize + (disksize % 512)

        # create efidisk file
        with open(efidisk, "wb") as fobj:
            fobj.truncate(disksize)

        # create loop device
        loopdev = create_loop_dev(efidisk)

        if not loopdev:
            os.unlink(efidisk)
            return None

        # create dm device
        dmdev = create_dm_dev("efiboot", disksize / 512, loopdev)

        if not dmdev:
            remove_loop_dev(loopdev)
            os.unlink(efidisk)
            return None

        # create partition on dm device
        cmd = [self.lcmds.PARTED, "--script", dmdev, "mklabel", "gpt", "unit",
               "b", "mkpart", '\"EFI System Partition\"', "fat32", "17408",
               str(partsize + 17408), "set", "1", "boot", "on"]
        logger.debug(cmd)

        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        rc = p.wait()

        if not rc == 0:
            remove_dm_dev(dmdev)
            remove_loop_dev(loopdev)
            os.unlink(efidisk)
            return None

        with open(efiboot, "rb") as f_from:
            with open("{0}p1".format(dmdev), "wb") as f_to:
                efidata = f_from.read(1024)
                while efidata:
                    f_to.write(efidata)
                    efidata = f_from.read(1024)

        remove_dm_dev("{0}p1".format(dmdev))
        remove_dm_dev(dmdev)
        remove_loop_dev(loopdev)

        return efidisk

    def create_bootiso(self, outputtree, efiboot=None):

        bootiso = joinpaths(self.workdir, "boot.iso")
        if os.path.isfile(bootiso):
            os.unlink(bootiso)

        if efiboot is not None:
            efiargs = ["-eltorito-alt-boot", "-e", "images/efiboot.img",
                       "-no-emul-boot"]
            efigraft = ["EFI/BOOT={0}".format(outputtree.efibootdir)]
        else:
            efiargs = []
            efigraft = []

        cmd = [self.lcmds.MKISOFS, "-o", bootiso,
               "-b", "isolinux/isolinux.bin", "-c", "isolinux/boot.cat",
               "-no-emul-boot", "-boot-load-size", "4",
               "-boot-info-table"] + efiargs + ["-R", "-J", "-V", self.product,
               "-T", "-graft-points",
               "isolinux={0}".format(outputtree.isolinuxdir),
               "images={0}".format(outputtree.imgdir)] + efigraft
        logger.debug(cmd)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        rc = p.wait()

        if not rc == 0:
            return None

        # create hybrid iso
        cmd = [self.lcmds.ISOHYBRID, bootiso]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        rc = p.wait()

        return bootiso


class LoraxInstallTree(BaseLoraxClass):

    def __init__(self, yum, basearch, libdir):
        BaseLoraxClass.__init__(self)
        self.yum = yum
        self.root = self.yum.installroot
        self.basearch = basearch
        self.libdir = libdir

        self.lcmds = constants.LoraxRequiredCommands()

    def remove_locales(self):
        chroot = lambda: os.chroot(self.root)

        # get locales we need to keep
        langtable = joinpaths(self.root, "usr/share/anaconda/lang-table")
        with open(langtable, "r") as fobj:
            langs = fobj.readlines()

        langs = map(lambda l: l.split()[3].replace(".UTF-8", ".utf8"), langs)
        langs = set(langs)

        # get locales from locale-archive
        localearch = "/usr/lib/locale/locale-archive"

        cmd = [self.lcmds.LOCALEDEF, "--list-archive", localearch]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, preexec_fn=chroot)
        output = p.stdout.read()

        remove = set(output.split()) - langs

        # remove not needed locales
        cmd = [self.lcmds.LOCALEDEF, "-i", localearch,
               "--delete-from-archive"] + list(remove)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, preexec_fn=chroot)
        p.wait()

        localearch = joinpaths(self.root, localearch)
        shutil.move(localearch, localearch + ".tmpl")

        p = subprocess.Popen([self.lcmds.BUILD_LOCALE_ARCHIVE],
                             preexec_fn=chroot)
        p.wait()

        # remove unneeded locales from /usr/share/locale
        with open(langtable, "r") as fobj:
            langs = fobj.readlines()

        langs = map(lambda l: l.split()[1], langs)

        localedir = joinpaths(self.root, "usr/share/locale")
        for fname in os.listdir(localedir):
            fpath = joinpaths(localedir, fname)
            if os.path.isdir(fpath) and fname not in langs:
                shutil.rmtree(fpath)

        # move the lang-table to etc
        shutil.move(langtable, joinpaths(self.root, "etc"))

    def create_keymaps(self):
        keymaps = joinpaths(self.root, "etc/keymaps.gz")

        # look for override
        override = "keymaps-override-{0.basearch}".format(self)
        override = joinpaths(self.root, "usr/share/anaconda", override)
        if os.path.isfile(override):
            logger.debug("using keymaps override")
            shutil.move(override, keymaps)
        else:
            # create keymaps
            cmd = [joinpaths(self.root, "usr/share/anaconda", "getkeymaps"),
                   basearch, keymaps, self.root]
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            p.wait()

        return True

    def create_screenfont(self):
        dst = joinpaths(self.root, "etc/screenfont.gz")

        screenfont = "screenfont-{0.basearch}.gz".format(self)
        screenfont = joinpaths(self.root, "usr/share/anaconda", screenfont)
        if not os.path.isfile(screenfont):
            return False
        else:
            shutil.move(screenfont, dst)

        return True

    def move_stubs(self):
        stubs = ("list-harddrives", "loadkeys", "losetup", "mknod",
                 "raidstart", "raidstop")

        for stub in stubs:
            src = joinpaths(self.root, "usr/share/anaconda",
                            "{0}-stub".format(stub))
            dst = joinpaths(self.root, "usr/bin", stub)
            if os.path.isfile(src):
                shutil.move(src, dst)

        # move restart-anaconda
        src = joinpaths(self.root, "usr/share/anaconda", "restart-anaconda")
        dst = joinpaths(self.root, "usr/bin")
        shutil.move(src, dst)

        # move sitecustomize.py
        pythonpath = joinpaths(self.root, "usr", self.libdir, "python?.?")
        for path in glob.glob(pythonpath):
            src = joinpaths(path, "site-packages/pyanaconda/sitecustomize.py")
            dst = joinpaths(path, "site-packages")
            shutil.move(src, dst)

    def cleanup_python_files(self):
        for root, dnames, fnames in os.walk(self.root):
            for fname in fnames:
                if fname.endswith(".py"):
                    path = joinpaths(root, fname, follow_symlinks=False)
                    pyo, pyc = path + "o", path + "c"
                    if os.path.isfile(pyo):
                        os.unlink(pyo)
                    if os.path.isfile(pyc):
                        os.unlink(pyc)

                    os.symlink("/dev/null", pyc)

    def cleanup_kernel_modules(self, keepmodules, kernel):
        moddir = joinpaths(self.root, "lib/modules", kernel.version)
        fwdir = joinpaths(self.root, "lib/firmware")

        # expand required modules
        modules = set()
        pattern = re.compile(r"\.ko$")

        for name in keepmodules:
            if name.startswith("="):
                group = name[1:]
                if group in ("scsi", "ata"):
                    p = joinpaths(moddir, "modules.block")
                elif group == "net":
                    p = joinpaths(moddir, "modules.networking")
                else:
                    p = joinpaths(moddir, "modules.{0}".format(group))

                if os.path.isfile(p):
                    with open(p, "r") as fobj:
                        for line in fobj:
                            module = pattern.sub("", line.strip())
                            modules.add(module)
            else:
                modules.add(name)

        # resolve modules dependencies
        moddep = joinpaths(moddir, "modules.dep")
        with open(moddep, "r") as fobj:
            lines = map(lambda line: line.strip(), fobj.readlines())

        modpattern = re.compile(r"^.*/(?P<name>.*)\.ko:(?P<deps>.*)$")
        deppattern = re.compile(r"^.*/(?P<name>.*)\.ko$")
        unresolved = True

        while unresolved:
            unresolved = False
            for line in lines:
                m = modpattern.match(line)
                modname = m.group("name")
                if modname in modules:
                    # add the dependencies
                    for dep in m.group("deps").split():
                        m = deppattern.match(dep)
                        depname = m.group("name")
                        if depname not in modules:
                            unresolved = True
                            modules.add(depname)

        # required firmware
        firmware = set()

        # XXX required firmware
        firmware.add("atmel_at76c504c-wpa.bin")
        firmware.add("iwlwifi-3945-1.ucode")
        firmware.add("iwlwifi-3945.ucode")
        firmware.add("zd1211/zd1211_uph")
        firmware.add("zd1211/zd1211_uphm")
        firmware.add("zd1211/zd1211b_uph")
        firmware.add("zd1211/zd1211b_uphm")

        # remove not needed modules
        for root, dnames, fnames in os.walk(moddir):
            for fname in fnames:
                path = os.path.join(root, fname)
                name, ext = os.path.splitext(fname)

                if ext == ".ko":
                    if name not in modules:
                        os.unlink(path)
                        logger.debug("removed module {0}".format(path))
                    else:
                        # get the required firmware
                        cmd = [self.lcmds.MODINFO, "-F", "firmware", path]
                        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
                        output = p.stdout.read()
                        firmware |= set(output.split())

        # remove not needed firmware
        firmware = map(lambda fw: joinpaths(fwdir, fw), list(firmware))
        for root, dnames, fnames in os.walk(fwdir):
            for fname in fnames:
                path = joinpaths(root, fname)
                if path not in firmware:
                    os.unlink(path)
                    logger.debug("removed firmware {0}".format(path))

        # get the modules paths
        modpaths = {}
        for root, dnames, fnames in os.walk(moddir):
            for fname in fnames:
                modpaths[fname] = joinpaths(root, fname)

        # create the modules list
        modlist = {}
        for modtype, fname in (("scsi", "modules.block"),
                               ("eth", "modules.networking")):

            fname = joinpaths(moddir, fname)
            with open(fname, "r") as fobj:
                lines = map(lambda l: l.strip(), fobj.readlines())
                lines = filter(lambda l: l, lines)

            for line in lines:
                modname, ext = os.path.splitext(line)
                if (line not in modpaths or
                    modname in ("floppy", "libiscsi", "scsi_mod")):
                    continue

                cmd = [self.lcmds.MODINFO, "-F", "description", modpaths[line]]
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
                output = p.stdout.read()

                try:
                    desc = output.splitlines()[0]
                    desc = desc.strip()[:65]
                except IndexError:
                    desc = "{0} driver".format(modname)

                info = '{0}\n\t{1}\n\t"{2}"\n'
                info = info.format(modname, modtype, desc)
                modlist[modname] = info

        # write the module-info
        moduleinfo = joinpaths(os.path.dirname(moddir), "module-info")
        with open(moduleinfo, "w") as fobj:
            fobj.write("Version 0\n")
            for modname in sorted(modlist.keys()):
                fobj.write(modlist[modname])



        # create symlinks in /
        shutil.move(joinpaths(self.root, "lib/modules"),
                    joinpaths(self.root, "modules"))
        shutil.move(joinpaths(self.root, "lib/firmware"),
                    joinpaths(self.root, "firmware"))

        os.symlink("../modules", joinpaths(self.root, "lib/modules"))
        os.symlink("../firmware", joinpaths(self.root, "lib/firmware"))

    def compress_modules(self, kernel):
        moddir = joinpaths(self.root, "modules", kernel.version)

        for root, dnames, fnames in os.walk(moddir):
            for fname in filter(lambda f: f.endswith(".ko"), fnames):
                path = os.path.join(root, fname)
                with open(path, "rb") as fobj:
                    data = fobj.read()

                gzipped = gzip.open("{0}.gz".format(path), "wb")
                gzipped.write(data)
                gzipped.close()

                os.unlink(path)

    def run_depmod(self, kernel):
        systemmap = "System.map-{0.version}".format(kernel)
        systemmap = joinpaths(self.root, "boot", systemmap)

        cmd = [self.lcmds.DEPMOD, "-a", "-F", systemmap, "-b", self.root,
               kernel.version]

        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        rc = p.wait()
        if not rc == 0:
            logger.critical(p.stdout.read())
            sys.exit(1)

        moddir = joinpaths(self.root, "modules", kernel.version)

        # remove *map files
        mapfiles = joinpaths(moddir, "*map")
        for fpath in glob.glob(mapfiles):
            os.unlink(fpath)

        # remove build and source symlinks
        for fname in ["build", "source"]:
            os.unlink(joinpaths(moddir, fname))

    def create_gconf(self):
        gconfdir = joinpaths(self.root, ".gconf/desktop")
        os.makedirs(gconfdir)
        touch(joinpaths(gconfdir, "%gconf.xml"))

        gconfdir = joinpaths(gconfdir, "gnome")
        os.mkdir(gconfdir)
        touch(joinpaths(gconfdir, "%gconf.xml"))

        gconfdir = joinpaths(gconfdir, "interface")
        os.mkdir(gconfdir)

        text = """<?xml version="1.0"?>
<gconf>
        <entry name="accessibility" mtime="1176200664" type="bool" value="true">
        </entry>
</gconf>
"""

        with open(joinpaths(gconfdir, "%gconf.xml"), "w") as fobj:
            fobj.write(text)

    def move_repos(self):
        src = joinpaths(self.root, "etc/yum.repos.d")
        dst = joinpaths(self.root, "etc/anaconda.repos.d")
        shutil.move(src, dst)

    def create_depmod_conf(self):
        text = "search updates built-in\n"

        with open(joinpaths(self.root, "etc/depmod.d/dd.conf"), "w") as fobj:
            fobj.write(text)

    # XXX
    def misc_tree_modifications(self):
        # replace init with anaconda init
        src = joinpaths(self.root, "usr", self.libdir, "anaconda", "init")
        dst = joinpaths(self.root, "sbin", "init")
        os.unlink(dst)
        shutil.copy2(src, dst)

        # init symlinks
        target = "/sbin/init"
        name = joinpaths(self.root, "init")
        os.symlink(target, name)

        for fname in ["halt", "poweroff", "reboot"]:
            name = joinpaths(self.root, "sbin", fname)
            os.unlink(name)
            os.symlink("init", name)

        for fname in ["runlevel", "shutdown", "telinit"]:
            name = joinpaths(self.root, "sbin", fname)
            os.unlink(name)

        # mtab symlink
        target = "/proc/mounts"
        name = joinpaths(self.root, "etc", "mtab")
        os.symlink(target, name)

        # create resolv.conf
        touch(joinpaths(self.root, "etc", "resolv.conf"))

    def get_config_files(self, src_dir):
        # get gconf anaconda.rules
        src = joinpaths(src_dir, "anaconda.rules")
        dst = joinpaths(self.root, "etc", "gconf", "gconf.xml.defaults",
                        "anaconda.rules")
        dstdir = os.path.dirname(dst)
        shutil.copy2(src, dst)

        cmd = [self.lcmds.GCONFTOOL, "--direct",
               '--config-source=xml:readwrite:{0}'.format(dstdir),
               "--load", dst]

        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        p.wait()

        # get rsyslog config
        src = joinpaths(src_dir, "rsyslog.conf")
        dst = joinpaths(self.root, "etc")
        shutil.copy2(src, dst)

        # get .bash_history
        src = joinpaths(src_dir, ".bash_history")
        dst = joinpaths(self.root, "root")
        shutil.copy2(src, dst)

        # get .profile
        src = joinpaths(src_dir, ".profile")
        dst = joinpaths(self.root, "root")
        shutil.copy2(src, dst)

        # get libuser.conf
        src = joinpaths(src_dir, "libuser.conf")
        dst = joinpaths(self.root, "etc")
        shutil.copy2(src, dst)

        # get selinux config
        if os.path.exists(joinpaths(self.root, "etc/selinux/targeted")):
            src = joinpaths(src_dir, "selinux.config")
            dst = joinpaths(self.root, "etc/selinux", "config")
            shutil.copy2(src, dst)

    def setup_sshd(self, src_dir):
        # get sshd config
        src = joinpaths(src_dir, "sshd_config.anaconda")
        dst = joinpaths(self.root, "etc", "ssh")
        shutil.copy2(src, dst)

        src = joinpaths(src_dir, "pam.sshd")
        dst = joinpaths(self.root, "etc", "pam.d", "sshd")
        shutil.copy2(src, dst)

        dst = joinpaths(self.root, "etc", "pam.d", "login")
        shutil.copy2(src, dst)

        dst = joinpaths(self.root, "etc", "pam.d", "remote")
        shutil.copy2(src, dst)

        # enable root shell logins and
        # 'install' account that starts anaconda on login
        passwd = joinpaths(self.root, "etc", "passwd")
        with open(passwd, "a") as fobj:
            fobj.write("sshd:x:74:74:Privilege-separated SSH:/var/empty/sshd:/sbin/nologin\n")
            fobj.write("install:x:0:0:root:/root:/sbin/loader\n")

        shadow = joinpaths(self.root, "etc", "shadow")
        with open(shadow, "a") as fobj:
            fobj.write("root::14438:0:99999:7:::\n")
            fobj.write("install::14438:0:99999:7:::\n")

    def get_anaconda_portions(self):
        src = joinpaths(self.root, "usr", self.libdir, "anaconda", "loader")
        dst = joinpaths(self.root, "sbin")
        shutil.copy2(src, dst)

        src = joinpaths(self.root, "usr/share/anaconda", "loader.tr")
        dst = joinpaths(self.root, "etc")
        shutil.move(src, dst)

        src = joinpaths(self.root, "usr/libexec/anaconda", "auditd")
        dst = joinpaths(self.root, "sbin")
        shutil.copy2(src, dst)

    def compress(self, initrd):
        chdir = lambda: os.chdir(self.root)

        start = time.time()

        find = subprocess.Popen([self.lcmds.FIND, "."], stdout=subprocess.PIPE,
                                preexec_fn=chdir)

        cpio = subprocess.Popen([self.lcmds.CPIO, "--quiet", "-c", "-o"],
                                stdin=find.stdout, stdout=subprocess.PIPE,
                                preexec_fn=chdir)

        gzipped = gzip.open(initrd.fpath, "wb")
        gzipped.write(cpio.stdout.read())
        gzipped.close()

        elapsed = time.time() - start

        return True, elapsed

    @property
    def kernels(self):
        kerneldir = "boot"
        if self.basearch == "ia64":
            kerneldir = "boot/efi/EFI/redhat"

        kerneldir = joinpaths(self.root, kerneldir)
        kpattern = re.compile(r"vmlinuz-(?P<ver>[-._0-9a-z]+?"
                              r"(?P<pae>(PAE)?)(?P<xen>(xen)?))$")

        kernels = []
        for fname in os.listdir(kerneldir):
            m = kpattern.match(fname)
            if m:
                type = K_NORMAL
                if m.group("pae"):
                    type = K_PAE
                elif m.group("xen"):
                    type = K_XEN

                kernels.append(Kernel(fname,
                                      joinpaths(kerneldir, fname),
                                      m.group("ver"),
                                      type))

        kernels = sorted(kernels, key=operator.attrgetter("type"))
        return kernels


class LoraxOutputTree(BaseLoraxClass):

    def __init__(self, root, installtree, product, version):
        BaseLoraxClass.__init__(self)
        self.root = root
        self.installtree = installtree

        self.product = product
        self.version = version

    def prepare(self):
        imgdir = joinpaths(self.root, "images")
        os.makedirs(imgdir)
        logger.debug("created directory {0}".format(imgdir))

        pxebootdir = joinpaths(self.root, "images/pxeboot")
        os.makedirs(pxebootdir)
        logger.debug("created directory {0}".format(pxebootdir))

        isolinuxdir = joinpaths(self.root, "isolinux")
        os.makedirs(isolinuxdir)
        logger.debug("created directory {0}".format(isolinuxdir))

        efibootdir = joinpaths(self.root, "EFI/BOOT")
        os.makedirs(efibootdir)
        logger.debug("created directory {0}".format(efibootdir))

        self.imgdir = imgdir
        self.pxebootdir = pxebootdir
        self.isolinuxdir = isolinuxdir
        self.efibootdir = efibootdir

    def get_kernels(self, kernels):
        # get the main kernel
        self.main_kernel = kernels.pop(0)

        # copy kernel to isolinuxdir
        shutil.copy2(self.main_kernel.fpath, self.isolinuxdir)

        # create kernel hard link in pxebootdir
        source = joinpaths(self.isolinuxdir, self.main_kernel.fname)
        link_name = joinpaths(self.pxebootdir, self.main_kernel.fname)
        os.link(source, link_name)

        # other kernels
        for kernel in self.installtree.kernels:
            shutil.copy2(kernel.fpath, self.pxebootdir)

    def get_isolinux(self):
        isolinuxbin = joinpaths(self.installtree.root,
                                "usr/share/syslinux/isolinux.bin")
        syslinuxcfg = joinpaths(self.installtree.root,
                                "usr/share/anaconda/boot/syslinux.cfg")

        # copy isolinux.bin
        shutil.copy2(isolinuxbin, self.isolinuxdir)

        # copy syslinux.cfg
        isolinuxcfg = joinpaths(self.isolinuxdir, "isolinux.cfg")
        shutil.copy2(syslinuxcfg, isolinuxcfg)

        # set product and version in isolinux.cfg
        replace(isolinuxcfg, r"@PRODUCT@", self.product)
        replace(isolinuxcfg, r"@VERSION@", self.version)

        # copy memtest
        memtest = joinpaths(self.installtree.root,
                            "boot/memtest*")

        for fname in glob.glob(memtest):
            shutil.copy2(fname, joinpaths(self.isolinuxdir, "memtest"))

            text = """label memtest86
  menu label ^Memory test
  kernel memtest
  append -

"""

            with open(isolinuxcfg, "a") as fobj:
                fobj.write(text)

            break

        # get splash
        vesasplash = joinpaths(self.installtree.root, "usr/share/anaconda",
                               "boot/syslinux-vesa-splash.jpg")

        vesamenu = joinpaths(self.installtree.root,
                             "usr/share/syslinux/vesamenu.c32")

        splashtolss = joinpaths(self.installtree.root,
                                "usr/share/anaconda/splashtolss.sh")

        syslinuxsplash = joinpaths(self.installtree.root, "usr/share/anaconda",
                                   "boot/syslinux-splash.jpg")

        splashlss = joinpaths(self.installtree.root, "usr/share/anaconda",
                              "boot/splash.lss")

        if os.path.isfile(vesasplash):
            shutil.copy2(vesasplash, joinpaths(self.isolinuxdir, "splash.jpg"))
            shutil.copy2(vesamenu, self.isolinuxdir)
            replace(isolinuxcfg, r"default linux", "default vesamenu.c32")
            replace(isolinuxcfg, r"prompt 1", "#prompt 1")
        elif os.path.isfile(splashtolss):
            cmd = [splashtolss, syslinuxsplash, splashlss]
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            rc = p.wait()
            if not rc == 0:
                logger.error("failed to create splash.lss")
                sys.exit(1)

            if os.path.isfile(splashlss):
                shutil.copy2(splashlss, self.isolinuxdir)

    def get_msg_files(self):
        msgfiles = joinpaths(self.installtree.root,
                             "usr/share/anaconda/boot/*.msg")

        for fname in glob.glob(msgfiles):
            shutil.copy2(fname, self.isolinuxdir)
            path = joinpaths(self.isolinuxdir, os.path.basename(fname))
            replace(path, r"@VERSION@", self.version)

    def get_grub_conf(self):
        grubconf = joinpaths(self.installtree.root,
                             "usr/share/anaconda/boot/grub.conf")

        shutil.copy2(grubconf, self.isolinuxdir)

        grubconf = joinpaths(self.isolinuxdir, "grub.conf")
        replace(grubconf, r"@PRODUCT@", self.product)
        replace(grubconf, r"@VERSION@", self.version)


class BuildStamp(object):

    def __init__(self, workdir, product, version, bugurl, is_beta, buildarch):

        self.path = joinpaths(workdir, ".buildstamp")
        self.c = ConfigParser.ConfigParser()

        now = datetime.datetime.now()
        now = now.strftime("%Y%m%d%H%M")
        uuid = "{0}.{1}".format(now, buildarch)

        section = "main"
        data = {"product": product,
                "version": version,
                "bugurl": bugurl,
                "isbeta": is_beta,
                "uuid": uuid}

        self.c.add_section(section)
        map(lambda (key, value): self.c.set(section, key, value), data.items())

    def write(self):
        logger.info("writing .buildstamp file")
        with open(self.path, "w") as fobj:
            self.c.write(fobj)


class DiscInfo(object):

    def __init__(self, workdir, release, basearch, discnum="ALL"):

        self.path = joinpaths(workdir, ".discinfo")

        self.release = release
        self.basearch = basearch
        self.discnum = discnum

    def write(self):
        logger.info("writing .discinfo file")
        with open(self.path, "w") as fobj:
            fobj.write("{0:f}\n".format(time.time()))
            fobj.write("{0}\n".format(self.release))
            fobj.write("{0}\n".format(self.basearch))
            fobj.write("{0}\n".format(self.discnum))


class TreeInfo(object):

    def __init__(self, workdir, product, version, variant, basearch,
                 discnum=1, totaldiscs=1, packagedir=""):

        self.path = joinpaths(workdir, ".treeinfo")
        self.c = ConfigParser.ConfigParser()

        section = "general"
        data = {"timestamp": time.time(),
                "family": product,
                "version": version,
                "variant": variant or "",
                "arch": basearch,
                "discnum": discnum,
                "totaldiscs": totaldiscs,
                "packagedir": packagedir}

        self.c.add_section(section)
        map(lambda (key, value): self.c.set(section, key, value), data.items())

    def add_section(self, section, data):
        if not self.c.has_section(section):
            self.c.add_section(section)

        map(lambda (key, value): self.c.set(section, key, value), data.items())

    def write(self):
        logger.info("writing .treeinfo file")
        with open(self.path, "w") as fobj:
            self.c.write(fobj)
