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
logger = logging.getLogger("pylorax")

sh = logging.StreamHandler()
sh.setLevel(logging.INFO)
logger.addHandler(sh)


import sys
import os
import ConfigParser
import tempfile
import shutil
import itertools
import glob
import math
import subprocess

from base import BaseLoraxClass, DataHolder
import output

import yum
import yumhelper
import ltmpl

import constants
from sysutils import *

from installtree import LoraxInstallTree
from outputtree import LoraxOutputTree
from buildstamp import BuildStamp
from treeinfo import TreeInfo
from discinfo import DiscInfo
import images


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

        # cron does not have sbin in PATH,
        # so we have to add it ourselves
        os.environ["PATH"] = "{0}:/sbin:/usr/sbin".format(os.environ["PATH"])

        self._configured = True

    def init_file_logging(self, logdir, logname="pylorax.log"):
        fh = logging.FileHandler(filename=joinpaths(logdir, logname), mode="w")
        fh.setLevel(logging.DEBUG)
        logger.addHandler(fh)

    def run(self, ybo, product, version, release, variant="", bugurl="",
            is_beta=False, workdir=None, outputdir=None):

        assert self._configured

        # set up work directory
        self.workdir = workdir or tempfile.mkdtemp(prefix="pylorax.work.")
        if not os.path.isdir(self.workdir):
            os.makedirs(self.workdir)

        # set up log directory
        logdir = joinpaths(self.workdir, "log")
        if not os.path.isdir(logdir):
            os.makedirs(logdir)

        self.init_file_logging(logdir)
        logger.debug("using work directory {0.workdir}".format(self))
        logger.debug("using log directory {0}".format(logdir))

        # set up output directory
        self.outputdir = outputdir or tempfile.mkdtemp(prefix="pylorax.out.")
        if not os.path.isdir(self.outputdir):
            os.makedirs(self.outputdir)
        logger.debug("using output directory {0.outputdir}".format(self))

        # do we have root privileges?
        logger.info("checking for root privileges")
        if not os.geteuid() == 0:
            logger.critical("no root privileges")
            sys.exit(1)

        # do we have all lorax required commands?
        self.lcmds = constants.LoraxRequiredCommands()
        missing = self.lcmds.get_missing()
        if missing:
            logger.critical("missing required command: {0}".format(missing))
            sys.exit(1)

        # do we have a proper yum base object?
        logger.info("checking yum base object")
        if not isinstance(ybo, yum.YumBase):
            logger.critical("no yum base object")
            sys.exit(1)

        # set up yum helper
        logger.info("setting up yum helper")
        self.yum = yumhelper.LoraxYumHelper(ybo)
        logger.debug("using install root: {0}".format(self.yum.installroot))

        # set up build architecture
        logger.info("setting up build architecture")

        self.buildarch = self.get_buildarch()
        logger.debug("set buildarch = {0.buildarch}".format(self))

        archmap = ARCHMAPS.get(self.buildarch)
        assert archmap is not None

        self.basearch = archmap.get("base")
        self.efiarch = archmap.get("efi")
        self.libdir = LIB64 if archmap.get("is64") else LIB32
        logger.debug("set basearch = {0.basearch}".format(self))
        logger.debug("set efiarch = {0.efiarch}".format(self))
        logger.debug("set libdir = {0.libdir}".format(self))

        # set up install tree
        logger.info("setting up install tree")
        self.installtree = LoraxInstallTree(self.yum, self.basearch,
                                            self.libdir, self.workdir)

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

        # parse the template
        logger.info("parsing the template")
        tfile = joinpaths(self.conf.get("lorax", "sharedir"),
                          self.conf.get("templates", "ramdisk"))

        tvars = { "basearch": self.basearch,
                  "buildarch": self.buildarch,
                  "libdir" : self.libdir,
                  "product": self.product.lower() }

        template = ltmpl.LoraxTemplate()
        template = template.parse(tfile, tvars)

        # get required directories
        logger.info("creating tree directories")
        dirs = [f[1:] for f in template if f[0] == "mkdir"]
        dirs = itertools.chain.from_iterable(dirs)

        # create directories
        for d in dirs:
            os.makedirs(joinpaths(self.installtree.root, d))

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

        # DEBUG save list of installed packages
        dname = joinpaths(self.workdir, "pkglists")
        os.makedirs(dname)
        for pkgname, pkgobj in self.installtree.yum.installed_packages.items():
            with open(joinpaths(dname, pkgname), "w") as fobj:
                for fname in pkgobj.filelist:
                  fobj.write("{0}\n".format(fname))

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
        modules = list(itertools.chain.from_iterable(modules))

        self.installtree.move_modules()

        for kernel in self.installtree.kernels:
            logger.info("cleaning up kernel modules")
            self.installtree.cleanup_kernel_modules(modules, kernel)

            logger.info("compressing modules")
            self.installtree.compress_modules(kernel)

            logger.info("running depmod")
            self.installtree.run_depmod(kernel)

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
        self.outputtree = LoraxOutputTree(self.outputdir, self.installtree,
                                          self.product, self.version)

        #self.outputtree.prepare()
        #self.outputtree.get_isolinux()
        #self.outputtree.get_memtest()
        #self.outputtree.get_splash()
        #self.outputtree.get_msg_files()
        #self.outputtree.get_grub_conf()

        # write .discinfo
        discinfo = DiscInfo(self.workdir, self.release, self.basearch)
        discinfo.write()

        shutil.copy2(discinfo.path, self.outputtree.root)

        # move grubefi to workdir
        grubefi = joinpaths(self.installtree.root, "boot/efi/EFI/redhat",
                            "grub.efi")

        if os.path.isfile(grubefi):
            shutil.move(grubefi, self.workdir)
            grubefi = joinpaths(self.workdir, os.path.basename(grubefi))
        else:
            grubefi = None

        # move grub splash to workdir
        splash = joinpaths(self.installtree.root, "boot/grub/",
                           "splash.xpm.gz")

        if os.path.isfile(splash):
            shutil.move(splash, self.workdir)
            splash = joinpaths(self.workdir, os.path.basename(splash))
        else:
            splash = None

        # copy kernels to output directory
        self.outputtree.get_kernels(self.workdir)

        # create .treeinfo
        treeinfo = TreeInfo(self.workdir, self.product, self.version,
                            self.variant, self.basearch)

        # get the image class
        factory = images.Factory()
        imgclass = factory.get_class(self.basearch)

        i = imgclass(kernellist=self.outputtree.kernels,
                     installtree=self.installtree,
                     outputroot=self.outputtree.root,
                     product=self.product,
                     version=self.version,
                     treeinfo=treeinfo,
                     basearch=self.basearch)

        # backup required files
        i.backup_required(self.workdir)

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

        # compress install tree (create initrd)
        logger.info("creating the initrd")
        i.create_initrd(self.libdir)

        #initrds = []
        #for kernel in self.outputtree.kernels:
        #    suffix = ""
        #    if kernel.ktype == constants.K_PAE:
        #        suffix = "-PAE"
        #    elif kernel.ktype == constants.K_XEN:
        #        suffix = "-XEN"
        #
        #    fname = "initrd{0}.img".format(suffix)
        #
        #    initrd = DataHolder(fname=fname,
        #                        fpath=joinpaths(self.workdir, fname),
        #                        itype=kernel.ktype)
        #
        #    logger.info("compressing install tree ({0})".format(kernel.version))
        #    success, elapsed = self.installtree.compress(initrd, kernel)
        #    if not success:
        #        logger.error("error while compressing install tree")
        #    else:
        #        logger.info("took {0:.2f} seconds".format(elapsed))
        #
        #    initrds.append(initrd)
        #
        #    # add kernel and initrd paths to .treeinfo
        #    section = "images-{0}".format("xen" if suffix else self.basearch)
        #    data = {"kernel": "images/pxeboot/{0}".format(kernel.fname)}
        #    treeinfo.add_section(section, data)
        #    data = {"initrd": "images/pxeboot/{0}".format(initrd.fname)}
        #    treeinfo.add_section(section, data)
        #
        ## copy initrds to outputtree
        #shutil.copy2(initrds[0].fpath, self.outputtree.isolinuxdir)
        #
        ## create hard link
        #source = joinpaths(self.outputtree.isolinuxdir, initrds[0].fname)
        #link_name = joinpaths(self.outputtree.pxebootdir, initrds[0].fname)
        #os.link(source, link_name)
        #
        #for initrd in initrds[1:]:
        #    shutil.copy2(initrd.fpath, self.outputtree.pxebootdir)

        # create efi images
        efiboot = None
        if grubefi and self.efiarch not in ("IA32",):
            # create efibootdir
            self.outputtree.efibootdir = joinpaths(self.outputtree.root,
                                                   "EFI/BOOT")
            os.makedirs(self.outputtree.efibootdir)

            # set imgdir
            self.outputtree.imgdir = joinpaths(self.outputtree.root,
                                               "images")

            kernel = i.kernels[0]
            initrd = i.initrds[0]

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

            # copy efiboot and efidisk to imgdir
            shutil.copy2(efiboot, self.outputtree.imgdir)
            shutil.copy2(efidisk, self.outputtree.imgdir)

        # create boot iso
        logger.info("creating boot iso")
        i.create_boot(efiboot)

        #bootiso = self.create_bootiso(self.outputtree, efiboot)
        #if bootiso is None:
        #    logger.critical("unable to create boot iso")
        #    sys.exit(1)
        #
        #shutil.move(bootiso, self.outputtree.imgdir)
        #
        ## add the boot.iso
        #section = "images-{0}".format(self.basearch)
        #data = {"boot.iso": "images/{0}".format(os.path.basename(bootiso))}
        #treeinfo.add_section(section, data)

        treeinfo.write()

        shutil.copy2(treeinfo.path, self.outputtree.root)

    def get_buildarch(self):
        # get architecture of the available anaconda package
        _, available = self.yum.search("anaconda")

        if available:
            anaconda = available.pop(0)
            # src is not a real arch
            if anaconda.arch == "src":
                anaconda = available.pop(0)
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

        # calculate the size of the efi tree directory
        overhead = constants.FS_OVERHEAD * 1024

        sizeinbytes = overhead
        for root, _, fnames in os.walk(efitree):
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
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        proc.wait()

        # mount the efiboot image
        efibootdir = tempfile.mkdtemp(prefix="efiboot.", dir=self.workdir)

        cmd = [self.lcmds.MOUNT, "-o", "loop,shortname=winnt,umask=0777",
               "-t", "vfat", efiboot, efibootdir]
        logger.debug(cmd)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        proc.wait()

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
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        proc.wait()

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

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        retcode = proc.wait()

        if not retcode == 0:
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
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        retcode = proc.wait()

        if not retcode == 0:
            return None

        # create hybrid iso
        cmd = [self.lcmds.ISOHYBRID, bootiso]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        retcode = proc.wait()

        # implant iso md5
        cmd = [self.lcmds.IMPLANTISOMD5, bootiso]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        retcode = proc.wait()

        return bootiso
