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

program_log = logging.getLogger("program")

import sys
import os
import configparser
import tempfile
import locale
from subprocess import CalledProcessError
import selinux
from glob import glob

from pylorax.base import BaseLoraxClass, DataHolder
import pylorax.output as output

import libdnf5 as dnf5

from pylorax.sysutils import joinpaths, remove, linktree

from pylorax.treebuilder import RuntimeBuilder, TreeBuilder
from pylorax.buildstamp import BuildStamp
from pylorax.treeinfo import TreeInfo
from pylorax.discinfo import DiscInfo
from pylorax.executils import runcmd, runcmd_output


# get lorax version
try:
    import pylorax.version
except ImportError:
    vernum = "devel"
else:
    vernum = pylorax.version.num

DRACUT_DEFAULT = ["--xz", "--install", "/.buildstamp", "--no-early-microcode", "--add", "fips"]

# Used for DNF conf.module_platform_id
DEFAULT_PLATFORM_ID = "platform:f41"
DEFAULT_RELEASEVER = "41"

ROOTFSTYPES = ["squashfs", "squashfs-ext4", "erofs", "erofs-ext4"]

# XXX - Temporarily lifted from dnf.rpm module
def _invert(dct):
    return {v: k for k in dct for v in dct[k]}

_BASEARCH_MAP = _invert({
    'aarch64': ('aarch64',),
    'alpha': ('alpha', 'alphaev4', 'alphaev45', 'alphaev5', 'alphaev56',
              'alphaev6', 'alphaev67', 'alphaev68', 'alphaev7', 'alphapca56'),
    'arm': ('armv5tejl', 'armv5tel', 'armv5tl', 'armv6l', 'armv7l', 'armv8l'),
    'armhfp': ('armv6hl', 'armv7hl', 'armv7hnl', 'armv8hl'),
    'i386': ('i386', 'athlon', 'geode', 'i386', 'i486', 'i586', 'i686'),
    'ia64': ('ia64',),
    'mips': ('mips',),
    'mipsel': ('mipsel',),
    'mips64': ('mips64',),
    'mips64el': ('mips64el',),
    'loongarch64': ('loongarch64',),
    'noarch': ('noarch',),
    'ppc': ('ppc',),
    'ppc64': ('ppc64', 'ppc64iseries', 'ppc64p7', 'ppc64pseries'),
    'ppc64le': ('ppc64le',),
    'riscv32' : ('riscv32',),
    'riscv64' : ('riscv64',),
    'riscv128' : ('riscv128',),
    's390': ('s390',),
    's390x': ('s390x',),
    'sh3': ('sh3',),
    'sh4': ('sh4', 'sh4a'),
    'sparc': ('sparc', 'sparc64', 'sparc64v', 'sparcv8', 'sparcv9',
              'sparcv9v'),
    'x86_64': ('x86_64', 'amd64', 'ia32e'),
})


class ArchData(DataHolder):
    bcj_arch = dict(x86_64="x86", ppc64le="powerpc")

    def _basearch(self, arch):
        # :api
        return _BASEARCH_MAP[arch]

    def __init__(self, buildarch):
        super(ArchData, self).__init__()
        self.buildarch = buildarch
        self.basearch = self._basearch(buildarch)
        self.libdir = "lib64"
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
        self._templatedir = None

        # set locale to C
        locale.setlocale(locale.LC_ALL, 'C')

    def configure(self, conf_file="/etc/lorax/lorax.conf"):
        self.conf = configparser.ConfigParser()

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

    @property
    def templatedir(self):
        """Find the template directory.

        Pick the first directory under sharedir/templates.d/ if it exists.
        Otherwise use the sharedir
        """
        if not self._templatedir:
            self._templatedir = find_templates(self.conf.get("lorax", "sharedir"))
            logger.info("Using templatedir %s", self._templatedir)
        return self._templatedir

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
            installpkgs=None, excludepkgs=None,
            size=2,
            add_templates=None,
            add_template_vars=None,
            add_arch_templates=None,
            add_arch_template_vars=None,
            verify=True,
            user_dracut_args=None,
            rootfs_type="squashfs",
            skip_branding=False):

        assert self._configured

        installpkgs = installpkgs or []
        excludepkgs = excludepkgs or []

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

        self.init_file_logging(logdir)

        logger.debug("version is %s", vernum)
        log_selinux_state()

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

        # do we have a proper dnf base object?
        logger.info("checking dnf base object")
        if not isinstance(dbo, dnf5.base.Base):
            logger.critical("no dnf base object")
            sys.exit(1)
        self.inroot = dbo.get_config().installroot
        logger.debug("using install root: %s", self.inroot)

        if not buildarch:
            buildarch = get_buildarch(dbo)

        logger.info("setting up build architecture")
        self.arch = ArchData(buildarch)
        for attr in ('buildarch', 'basearch', 'libdir'):
            logger.debug("self.arch.%s = %s", attr, getattr(self.arch,attr))

        logger.info("setting up build parameters")
        self.product = DataHolder(name=product, version=version, release=release,
                                 variant=variant, bugurl=bugurl, isfinal=isfinal)
        logger.debug("product data: %s", self.product)

        # NOTE: if you change isolabel, you need to change pungi to match, or
        # the pungi images won't boot.
        isolabel = volid or "%s-%s-%s" % (self.product.name, self.product.version, self.arch.basearch)

        if len(isolabel) > 32:
            logger.fatal("the volume id cannot be longer than 32 characters")
            sys.exit(1)

        # NOTE: rb.root = dbo.get_config().installroot (== self.inroot)
        rb = RuntimeBuilder(product=self.product, arch=self.arch,
                            dbo=dbo, templatedir=self.templatedir,
                            installpkgs=installpkgs,
                            excludepkgs=excludepkgs,
                            add_templates=add_templates,
                            add_template_vars=add_template_vars,
                            skip_branding=skip_branding)

        logger.info("installing runtime packages")
        rb.install()

        # write .buildstamp
        buildstamp = BuildStamp(self.product.name, self.product.version,
                                self.product.bugurl, self.product.isfinal,
                                self.arch.buildarch, self.product.variant)

        buildstamp.write(joinpaths(self.inroot, ".buildstamp"))

        if self.debug:
            logger.info("writing debug data to pkglists and original-pkgsizes.txt")
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

        if verify:
            logger.info("verifying the installroot")
            if not rb.verify():
                sys.exit(1)
        else:
            logger.info("Skipping verify")

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
        if rootfs_type == "squashfs":
            # Create a squashfs compressed rootfs.img
            rc = rb.create_squashfs_runtime(joinpaths(installroot,runtime),
                    compression=compression, compressargs=compressargs,
                    size=size)
        elif rootfs_type == "squashfs-ext4":
            # Create an ext4 rootfs.img and compress it with squashfs
            rc = rb.create_ext4_runtime(joinpaths(installroot,runtime),
                    compression=compression, compressargs=compressargs,
                    size=size)
        elif rootfs_type == "erofs":
            # Create a erofs compressed rootfs.img
            # NOTE it does not support the same compression args as the other options
            # so they are not passed to it.
            rc = rb.create_erofs_runtime(joinpaths(installroot,runtime),
                    size=size)
        elif rootfs_type == "erofs-ext4":
            # Create an ext4 rootfs.img and compress it with erofs
            # NOTE it does not support the same compression args as the other options
            # so they are not passed to it.
            rc = rb.create_erofs_ext4_runtime(joinpaths(installroot,runtime),
                    size=size)
        else:
            raise RuntimeError(f"{rootfs_type} is not a supported type for the root filesystem")
        if rc != 0:
            logger.error("rootfs.img creation failed. See program.log")
            sys.exit(1)

        rb.finished()

        logger.info("preparing to build output tree and boot images")
        treebuilder = TreeBuilder(product=self.product, arch=self.arch,
                                  inroot=installroot, outroot=self.outputdir,
                                  runtime=runtime, isolabel=isolabel,
                                  domacboot=domacboot, doupgrade=doupgrade,
                                  templatedir=self.templatedir,
                                  add_templates=add_arch_templates,
                                  add_template_vars=add_arch_template_vars,
                                  workdir=self.workdir)

        logger.info("rebuilding initramfs images")
        if not user_dracut_args:
            dracut_args = DRACUT_DEFAULT
        else:
            dracut_args = []
            for arg in user_dracut_args:
                dracut_args += arg.split(" ", 1)

        anaconda_args = dracut_args + ["--add", "anaconda pollcdrom qemu qemu-net prefixdevname-tools"]

        logger.info("dracut args = %s", dracut_args)
        logger.info("anaconda args = %s", anaconda_args)
        treebuilder.rebuild_initrds(add_args=anaconda_args)

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
    q = dnf5.rpm.PackageQuery(dbo)
    q.filter_available()
    q.filter_name(["anaconda-core"])
    for anaconda in list(q):
        if anaconda.get_arch() != "src":
            buildarch = anaconda.get_arch()
            break
    if not buildarch:
        logger.critical("no anaconda-core package in the repository")
        sys.exit(1)

    return buildarch


def setup_logging(logfile, theLogger):
    """
    Setup the various logs

    :param logfile: filename to write the log to
    :type logfile: string
    :param theLogger: top-level logger
    :type theLogger: logging.Logger
    """
    if not os.path.isdir(os.path.abspath(os.path.dirname(logfile))):
        os.makedirs(os.path.abspath(os.path.dirname(logfile)))

    # Setup logging to console and to logfile
    logger.setLevel(logging.DEBUG)
    theLogger.setLevel(logging.DEBUG)

    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s: %(message)s")
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    theLogger.addHandler(sh)

    fh = logging.FileHandler(filename=logfile, mode="w")
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    theLogger.addHandler(fh)

    # External program output log
    program_log.setLevel(logging.DEBUG)
    f = os.path.abspath(os.path.dirname(logfile))+"/program.log"
    fh = logging.FileHandler(filename=f, mode="w")
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    fh.setFormatter(fmt)
    program_log.addHandler(fh)


def find_templates(templatedir="/usr/share/lorax"):
    """ Find the templates to use.

    :param str templatedir: Top directory to search for templates
    :returns: Path to templates
    :rtype: str

    If there is a templates.d directory under templatedir the
    lowest numbered directory entry is returned.

    eg. /usr/share/lorax/templates.d/99-generic/
    """
    if os.path.isdir(joinpaths(templatedir, "templates.d")):
        try:
            templatedir = sorted(glob(joinpaths(templatedir, "templates.d", "*")))[0]
        except IndexError:
            pass
    return templatedir

def log_selinux_state():
    """Log the current state of selinux"""
    if selinux.is_selinux_enabled():
        if selinux.security_getenforce():
            logger.info("selinux is enabled and in Enforcing mode")
        else:
            logger.info("selinux is enabled and in Permissive mode")
    else:
        logger.info("selinux is Disabled")
