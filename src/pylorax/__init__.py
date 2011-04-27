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
from buildstamp import BuildStamp
from treeinfo import TreeInfo
from discinfo import DiscInfo
import images

class ArchData(object):
    lib64_arches = ("x86_64", "ppc64", "sparc64", "s390x", "ia64")
    archmap = {"i386": "i386", "i586":"i386", "i686":"i386", "x86_64":"x86_64",
               "ppc":"ppc", "ppc64": "ppc",
               "sparc":"sparc", "sparcv9":"sparc", "sparc64":"sparc",
               "s390":"s390", "s390x":"s390x",
    }
    def __init__(self, buildarch):
        self.buildarch = buildarch
        self.basearch = self.archmap.get(buildarch) or buildarch
        self.libdir = "lib64" if buildarch in self.lib64_arches else "lib"

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

        self.conf.add_section("yum")
        self.conf.set("yum", "skipbroken", "0")

        self.conf.add_section("compression")
        self.conf.set("compression", "type", "xz")
        self.conf.set("compression", "speed", "9")

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
        # TODO: actually check for required commands

        # do we have a proper yum base object?
        logger.info("checking yum base object")
        if not isinstance(ybo, yum.YumBase):
            logger.critical("no yum base object")
            sys.exit(1)

        logger.info("setting up yum helper")
        self.yum = yumhelper.LoraxYumHelper(ybo)
        logger.debug("using install root: {0}".format(self.yum.installroot))

        logger.info("setting up build architecture")
        self.arch = ArchData(self.get_buildarch())
        for attr in ('buildarch', 'basearch', 'libdir'):
            logger.debug("self.arch.%s = %s", attr, getattr(self.arch,attr))

        logger.info("setting up install tree")
        self.installtree = LoraxInstallTree(self.yum, self.arch.basearch,
                                            self.arch.libdir, self.workdir)

        logger.info("setting up build parameters")
        product = DataHolder(name=product, version=version, release=release,
                             variant=variant, bugurl=bugurl, is_beta=is_beta)
        self.product = product
        logger.debug("product data: %s" % product)

        logger.info("parsing the template")
        tfile = joinpaths(self.conf.get("lorax", "sharedir"),
                          self.conf.get("templates", "ramdisk"))

        # TODO: normalize with arch templates:
        #       tvars = dict(product=product, arch=arch)
        tvars = { "basearch": self.arch.basearch,
                  "buildarch": self.arch.buildarch,
                  "libdir" : self.arch.libdir,
                  "product": self.product.name.lower() }

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

        skipbroken = self.conf.getboolean("yum", "skipbroken")
        self.installtree.yum.process_transaction(skipbroken)

        # write .buildstamp
        buildstamp = BuildStamp(self.workdir, self.product.name, self.product.version,
                                self.product.bugurl, self.product.is_beta, self.arch.buildarch)

        buildstamp.write()
        shutil.copy2(buildstamp.path, self.installtree.root)

        # DEBUG save list of installed packages
        dname = joinpaths(self.workdir, "pkglists")
        os.makedirs(dname)
        for pkgname, pkgobj in self.installtree.yum.installed_packages.items():
            with open(joinpaths(dname, pkgname), "w") as fobj:
                for fname in pkgobj.filelist:
                  fobj.write("{0}\n".format(fname))

        logger.info("removing locales")
        self.installtree.remove_locales()

        logger.info("creating keymaps")
        self.installtree.create_keymaps()

        logger.info("creating screenfont")
        self.installtree.create_screenfont()

        logger.info("moving stubs")
        self.installtree.move_stubs()

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

        # write .discinfo
        discinfo = DiscInfo(self.workdir, self.product.release, self.arch.basearch)
        discinfo.write()

        shutil.copy2(discinfo.path, self.outputdir)

        # create .treeinfo
        treeinfo = TreeInfo(self.workdir, self.product.name, self.product.version,
                            self.product.variant, self.arch.basearch)

        # get the image class
        factory = images.Factory()
        imgclass = factory.get_class(self.arch.basearch)

        ctype = self.conf.get("compression", "type")
        cspeed = self.conf.get("compression", "speed")

        i = imgclass(kernellist=kernels,
                     installtree=self.installtree,
                     outputroot=self.outputdir,
                     product=self.product.name,
                     version=self.product.version,
                     treeinfo=treeinfo,
                     basearch=self.arch.basearch,
                     ctype=ctype,
                     cspeed=cspeed)

        # backup required files
        i.backup_required(self.workdir)

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
        i.create_initrd(self.arch.libdir)

        # create boot iso
        logger.info("creating boot iso")
        i.create_boot(efiboot=None) # FIXME restore proper EFI function

        treeinfo.write()

        shutil.copy2(treeinfo.path, self.outputdir)

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
