#
# __init__.py
#
# Copyright (C) 2010-2015  Red Hat, Inc.
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
#                     Will Woods <wwoods@redhat.com>

# set up logging
import logging
logger = logging.getLogger("pylorax")
logger.addHandler(logging.NullHandler())

import sys
import os
import configparser
import tempfile
import locale
from subprocess import CalledProcessError
import selinux

from pylorax.base import BaseLoraxClass, DataHolder
import pylorax.output as output

import dnf

from pylorax.sysutils import joinpaths, remove, linktree

from pylorax.treebuilder import RuntimeBuilder, TreeBuilder
from pylorax.buildstamp import BuildStamp
from pylorax.treeinfo import TreeInfo
from pylorax.discinfo import DiscInfo
from pylorax.executils import runcmd, runcmd_output

# List of drivers to remove on ppc64 arch to keep initrd < 32MiB
REMOVE_PPC64_DRIVERS = "floppy scsi_debug nouveau radeon cirrus mgag200"
REMOVE_PPC64_MODULES = "drm plymouth"

class ArchData(DataHolder):
    lib64_arches = ("x86_64", "ppc64", "ppc64le", "s390x", "ia64", "aarch64")
    bcj_arch = dict(i386="x86", x86_64="x86",
                    ppc="powerpc", ppc64="powerpc", ppc64le="powerpc",
                    arm="arm", armhfp="arm")

    def __init__(self, buildarch):
        super(ArchData, self).__init__()
        self.buildarch = buildarch
        self.basearch = dnf.arch.basearch(buildarch)
        self.libdir = "lib64" if self.basearch in self.lib64_arches else "lib"
        self.bcj = self.bcj_arch.get(self.basearch)

class Lorax(BaseLoraxClass):

    def __init__(self):
        BaseLoraxClass.__init__(self)
        self._configured = False
        self.product = None
        self.workdir = None
        self.arch = None
        self.conf = None
        self.inroot = None
        self.debug = False
        self.outputdir = None

        # set locale to C
        locale.setlocale(locale.LC_ALL, 'C')

    def configure(self, conf_file="/etc/lorax/lorax.conf"):
        self.conf = configparser.SafeConfigParser()

        # set defaults
        self.conf.add_section("lorax")
        self.conf.set("lorax", "debug", "1")
        self.conf.set("lorax", "sharedir", "/usr/share/lorax")
        self.conf.set("lorax", "logdir", "/var/log/lorax")

        self.conf.add_section("output")
        self.conf.set("output", "colors", "1")
        self.conf.set("output", "encoding", "utf-8")
        self.conf.set("output", "ignorelist", "/usr/share/lorax/ignorelist")

        self.conf.add_section("templates")
        self.conf.set("templates", "ramdisk", "ramdisk.ltmpl")

        self.conf.add_section("compression")
        self.conf.set("compression", "type", "xz")
        self.conf.set("compression", "args", "")
        self.conf.set("compression", "bcj", "on")

        # read the config file
        if os.path.isfile(conf_file):
            self.conf.read(conf_file)

        # set up the output
        self.debug = self.conf.getboolean("lorax", "debug")
        output_level = output.DEBUG if self.debug else output.INFO

        if sys.stdout.isatty():
            colors = self.conf.getboolean("output", "colors")
        else:
            colors = False
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

        # remove some environmental variables that can cause problems with package scripts
        env_remove = ('DISPLAY', 'DBUS_SESSION_BUS_ADDRESS')
        list(os.environ.pop(k) for k in env_remove if k in os.environ)

        self._configured = True

    def init_stream_logging(self):
        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        logger.addHandler(sh)

    def init_file_logging(self, logdir, logname="pylorax.log"):
        fh = logging.FileHandler(filename=joinpaths(logdir, logname), mode="w")
        fh.setLevel(logging.DEBUG)
        logger.addHandler(fh)

    def run(self, dbo, product, version, release, variant="", bugurl="",
            isfinal=False, workdir=None, outputdir=None, buildarch=None, volid=None,
            domacboot=True, doupgrade=True, remove_temp=False,
            installpkgs=None,
            size=2,
            add_templates=None,
            add_template_vars=None,
            add_arch_templates=None,
            add_arch_template_vars=None):

        assert self._configured

        installpkgs = installpkgs or []

        # get lorax version
        try:
            import pylorax.version
        except ImportError:
            vernum = "devel"
        else:
            vernum = pylorax.version.num

        if domacboot:
            try:
                runcmd(["rpm", "-q", "hfsplus-tools"])
            except CalledProcessError:
                logger.critical("you need to install hfsplus-tools to create mac images")
                sys.exit(1)

        # set up work directory
        self.workdir = workdir or tempfile.mkdtemp(prefix="pylorax.work.")
        if not os.path.isdir(self.workdir):
            os.makedirs(self.workdir)

        # set up log directory
        logdir = self.conf.get("lorax", "logdir")
        if not os.path.isdir(logdir):
            os.makedirs(logdir)

        self.init_stream_logging()
        self.init_file_logging(logdir)

        logger.debug("version is %s", vernum)
        logger.debug("using work directory %s", self.workdir)
        logger.debug("using log directory %s", logdir)

        # set up output directory
        self.outputdir = outputdir or tempfile.mkdtemp(prefix="pylorax.out.")
        if not os.path.isdir(self.outputdir):
            os.makedirs(self.outputdir)
        logger.debug("using output directory %s", self.outputdir)

        # do we have root privileges?
        logger.info("checking for root privileges")
        if not os.geteuid() == 0:
            logger.critical("no root privileges")
            sys.exit(1)

        # is selinux disabled?
        # With selinux in enforcing mode the rpcbind package required for
        # dracut nfs module, which is in turn required by anaconda module,
        # will not get installed, because it's preinstall scriptlet fails,
        # resulting in an incomplete initial ramdisk image.
        # The reason is that the scriptlet runs tools from the shadow-utils
        # package in chroot, particularly groupadd and useradd to add the
        # required rpc group and rpc user. This operation fails, because
        # the selinux context on files in the chroot, that the shadow-utils
        # tools need to access (/etc/group, /etc/passwd, /etc/shadow etc.),
        # is wrong and selinux therefore disallows access to these files.
        logger.info("checking the selinux mode")
        if selinux.is_selinux_enabled() and selinux.security_getenforce():
            logger.critical("selinux must be disabled or in Permissive mode")
            sys.exit(1)

        # do we have a proper dnf base object?
        logger.info("checking dnf base object")
        if not isinstance(dbo, dnf.Base):
            logger.critical("no dnf base object")
            sys.exit(1)
        self.inroot = dbo.conf.installroot
        logger.debug("using install root: %s", self.inroot)

        if not buildarch:
            buildarch = get_buildarch(dbo)

        logger.info("setting up build architecture")
        self.arch = ArchData(buildarch)
        for attr in ('buildarch', 'basearch', 'libdir'):
            logger.debug("self.arch.%s = %s", attr, getattr(self.arch,attr))

        logger.info("setting up build parameters")
        product = DataHolder(name=product, version=version, release=release,
                             variant=variant, bugurl=bugurl, isfinal=isfinal)
        self.product = product
        logger.debug("product data: %s", product)

        # NOTE: if you change isolabel, you need to change pungi to match, or
        # the pungi images won't boot.
        isolabel = volid or "%s-%s-%s" % (product, version, self.arch.basearch)

        if len(isolabel) > 32:
            logger.fatal("the volume id cannot be longer than 32 characters")
            sys.exit(1)

        templatedir = self.conf.get("lorax", "sharedir")
        # NOTE: rb.root = dbo.conf.installroot (== self.inroot)
        rb = RuntimeBuilder(product=self.product, arch=self.arch,
                            dbo=dbo, templatedir=templatedir,
                            installpkgs=installpkgs,
                            add_templates=add_templates,
                            add_template_vars=add_template_vars)

        logger.info("installing runtime packages")
        rb.install()

        # write .buildstamp
        buildstamp = BuildStamp(self.product.name, self.product.version,
                                self.product.bugurl, self.product.isfinal, self.arch.buildarch)

        buildstamp.write(joinpaths(self.inroot, ".buildstamp"))

        if self.debug:
            rb.writepkglists(joinpaths(logdir, "pkglists"))
            rb.writepkgsizes(joinpaths(logdir, "original-pkgsizes.txt"))

        logger.info("doing post-install configuration")
        rb.postinstall()

        # write .discinfo
        discinfo = DiscInfo(self.product.release, self.arch.basearch)
        discinfo.write(joinpaths(self.outputdir, ".discinfo"))

        logger.info("backing up installroot")
        installroot = joinpaths(self.workdir, "installroot")
        linktree(self.inroot, installroot)

        logger.info("generating kernel module metadata")
        rb.generate_module_data()

        logger.info("cleaning unneeded files")
        rb.cleanup()

        if self.debug:
            rb.writepkgsizes(joinpaths(logdir, "final-pkgsizes.txt"))

        logger.info("creating the runtime image")
        runtime = "images/install.img"
        compression = self.conf.get("compression", "type")
        compressargs = self.conf.get("compression", "args").split()     # pylint: disable=no-member
        if self.conf.getboolean("compression", "bcj"):
            if self.arch.bcj:
                compressargs += ["-Xbcj", self.arch.bcj]
            else:
                logger.info("no BCJ filter for arch %s", self.arch.basearch)
        rb.create_runtime(joinpaths(installroot,runtime),
                          compression=compression, compressargs=compressargs,
                          size=size)
        rb.finished()

        logger.info("preparing to build output tree and boot images")
        treebuilder = TreeBuilder(product=self.product, arch=self.arch,
                                  inroot=installroot, outroot=self.outputdir,
                                  runtime=runtime, isolabel=isolabel,
                                  domacboot=domacboot, doupgrade=doupgrade,
                                  templatedir=templatedir,
                                  add_templates=add_arch_templates,
                                  add_template_vars=add_arch_template_vars,
                                  workdir=self.workdir)

        logger.info("rebuilding initramfs images")
        dracut_args = ["--xz", "--install", "/.buildstamp"]
        anaconda_args = dracut_args + ["--add", "anaconda pollcdrom"]

        # ppc64 cannot boot an initrd > 32MiB so remove some drivers
        if self.arch.basearch in ("ppc64", "ppc64le"):
            dracut_args.extend(["--omit-drivers", REMOVE_PPC64_DRIVERS])

            # Only omit dracut modules from the initrd so that they're kept for
            # upgrade.img
            anaconda_args.extend(["--omit", REMOVE_PPC64_MODULES])

        treebuilder.rebuild_initrds(add_args=anaconda_args)

        if doupgrade:
            # Build upgrade.img. It'd be nice if these could coexist in the same
            # image, but that would increase the size of the anaconda initramfs,
            # which worries some people (esp. PPC tftpboot). So they're separate.
            try:
                # If possible, use the 'fedup' plymouth theme
                themes = runcmd_output(['plymouth-set-default-theme', '--list'],
                                       root=installroot)
                if 'fedup' in themes.splitlines():
                    os.environ['PLYMOUTH_THEME_NAME'] = 'fedup'
            except RuntimeError:
                pass
            upgrade_args = dracut_args + ["--add", "system-upgrade"]
            treebuilder.rebuild_initrds(add_args=upgrade_args, prefix="upgrade")

        logger.info("populating output tree and building boot images")
        treebuilder.build()

        # write .treeinfo file and we're done
        treeinfo = TreeInfo(self.product.name, self.product.version,
                            self.product.variant, self.arch.basearch)
        for section, data in treebuilder.treeinfo_data.items():
            treeinfo.add_section(section, data)
        treeinfo.write(joinpaths(self.outputdir, ".treeinfo"))

        # cleanup
        if remove_temp:
            remove(self.workdir)


def get_buildarch(dbo):
    # get architecture of the available anaconda package
    buildarch = None
    q = dbo.sack.query()
    a = q.available()
    for anaconda in a.filter(name="anaconda"):
        if anaconda.arch != "src":
            buildarch = anaconda.arch
            break
    if not buildarch:
        logger.critical("no anaconda package in the repository")
        sys.exit(1)

    return buildarch
