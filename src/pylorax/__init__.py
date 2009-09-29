#
# __init__.py
# lorax main class
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
import tempfile
import re
import shutil
import ConfigParser
import time
import datetime
import commands

from config import Container
from utils.yumwrapper import Yum
from utils.fileutils import copy, edit, replace

import output
import insttree
import images


class Config(Container):

    def __init__(self):
        config = ("confdir", "datadir", "tempdir", "debug", "cleanup")

        # options
        required = ("product", "version", "release", "outdir", "repos")
        optional = ("variant", "bugurl", "updates", "mirrorlist")

        Container.__init__(self, config + required + optional)

        # set defaults
        self.set(confdir="/etc/lorax",
            datadir="/usr/share/lorax",
            tempdir=tempfile.mkdtemp(prefix="lorax.tmp.",
                    dir=tempfile.gettempdir()),
            debug=False,
            cleanup=False)

        self.set(product="",
            version="",
            release="",
            outdir="",
            repos=[])

        self.set(variant="",
            bugurl="",
            updates="",
            mirrorlist=[])


class LoraxError(Exception):
    pass

class Lorax(object):

    def __init__(self, config):
        assert isinstance(config, Config) == True
        self.conf = config

        # check if we have all required options
        if not self.conf.repos:
            raise LoraxError, "missing required parameter 'repos'"
        if not self.conf.outdir:
            raise LoraxError, "missing required parameter 'outdir'"
        if not self.conf.product:
            raise LoraxError, "missing required parameter 'product'"
        if not self.conf.version:
            raise LoraxError, "missing required parameter 'version'"
        if not self.conf.release:
            raise LoraxError, "missing required parameter 'release'"

        self.yum = None

        # initialize the output objects
        self.so, self.se = output.initialize(verbose=self.conf.debug)

    def collect_repositories(self):
        repolist = []

        for repospec in self.conf.repos:
            if repospec.startswith("/"):
                repo = "file://%s" % (repospec,)
                self.so.info("Adding local repo: %s" % (repo,))
                repolist.append(repo)
            elif repospec.startswith("http://") or repospec.startswith("ftp://"):
                self.so.info("Adding remote repo: %s" % (repospec,))
                repolist.append(repospec)
            else:
                self.se.warning("Invalid repo path: %s" % (repospec,))

        if not repolist:
            return False
        else:
            mainrepo, extrarepos = repolist[0], repolist[1:]

            self.conf.addAttr(["mainrepo", "extrarepos"])
            self.conf.set(mainrepo=mainrepo, extrarepos=extrarepos)
       
            # remove not needed attributes from config 
            self.conf.delAttr("repos")

        return True

    def initialize_directories(self):
        # create the temporary directories
        treedir = os.path.join(self.conf.tempdir, "treedir", "install")
        os.makedirs(treedir)

        self.so.info("Working directories:")
        
        self.so.indent()
        self.so.info("tempdir = %s" % (self.conf.tempdir,))
        self.so.info("treedir = %s" % (treedir,))
        self.so.unindent()

        self.conf.addAttr("treedir")
        self.conf.set(treedir=treedir)

        # create the destination directories
        if not os.path.isdir(self.conf.outdir):
            os.makedirs(self.conf.outdir, mode=0755)

        imagesdir = os.path.join(self.conf.outdir, "images")
        if not os.path.isdir(imagesdir):
            os.makedirs(imagesdir)

        pxebootdir = os.path.join(imagesdir, "pxeboot")
        if not os.path.isdir(pxebootdir):
            os.makedirs(pxebootdir)

        efibootdir = os.path.join(self.conf.outdir, "EFI", "BOOT")
        if not os.path.isdir(efibootdir):
            os.makedirs(efibootdir)

        # create the isolinux directory
        isolinuxdir = os.path.join(self.conf.outdir, "isolinux")
        if not os.path.isdir(isolinuxdir):
            os.makedirs(isolinuxdir)

        self.so.info("Destination directories:")

        self.so.indent()
        self.so.info("outdir = %s" % (self.conf.outdir,))
        self.so.info("imagesdir = %s" % (imagesdir,))
        self.so.info("pxebootdir = %s" % (pxebootdir,))
        self.so.info("efibootdir = %s" % (efibootdir,))
        self.so.info("isolinuxdir = %s" % (isolinuxdir,))
        self.so.unindent()

        self.conf.addAttr(["imagesdir", "pxebootdir",
                "efibootdir", "isolinuxdir"])
        self.conf.set(imagesdir=imagesdir, pxebootdir=pxebootdir,
                efibootdir=efibootdir, isolinuxdir=isolinuxdir)

    def initialize_yum(self):
        yumconf = os.path.join(self.conf.tempdir, "yum.conf")

        # create the yum cache directory
        cachedir = os.path.join(self.conf.tempdir, "yumcache")
        os.makedirs(cachedir)

        c = ConfigParser.ConfigParser()

        # main section
        section = "main"
        data = { "cachedir": cachedir,
                 "keepcache": 0,
                 "gpgcheck": 0,
                 "plugins": 0,
                 "reposdir": "",
                 "tsflags": "nodocs" }
        c.add_section(section)
        [c.set(section, key, value) for key, value in data.items()]

        # main repo
        section = "lorax-repo"
        data = { "name": "lorax repo",
                 "baseurl": self.conf.mainrepo,
                 "enabled": 1 }
        c.add_section(section)
        [c.set(section, key, value) for key, value in data.items()]

        # extra repos
        for n, extra in enumerate(self.conf.extrarepos, start=1):
            section = "lorax-extrarepo-%d" % (n,)
            data = { "name": "lorax extra repo %d" % (n,),
                     "baseurl": extra,
                     "enabled": 1 }
            c.add_section(section)
            [c.set(section, key, value) for key, value in data.items()]

        # mirrorlist repos
        for n, mirror in enumerate(self.conf.mirrorlist, start=1):
            section = "lorax-mirrorlistrepo-%d" % (n,)
            data = { "name": "lorax mirrorlist repo %d" % (n,),
                     "mirrorlist": mirror,
                     "enabled": 1 }
            c.add_section(section)
            [c.set(section, key, value) for key, value in data.items()]

        try:
            f = open(yumconf, "w")
        except IOError as why:
            self.se.error("Unable to write yum.conf file: %s" % (why,))
            return False
        else:
            c.write(f)
            f.close()

        self.conf.addAttr("yumconf")
        self.conf.set(yumconf=yumconf)

        # remove not needed attributes from config
        self.conf.delAttr(["mainrepo", "extrarepos", "mirrorlist"])

        # create the Yum object
        self.yum = Yum(yumconf=self.conf.yumconf, installroot=self.conf.treedir,
                errfile=os.path.join(self.conf.tempdir, "yum.errors"))

        return True

    def set_architecture(self):
        # get the system architecture
        unamearch = os.uname()[4]

        self.conf.addAttr("buildarch")
        self.conf.set(buildarch=unamearch)

        # get the anaconda package architecture
        installed, available = self.yum.find("anaconda")
        try:
            self.conf.set(buildarch=available[0].arch)
        except:
            pass

        # set basearch
        self.conf.addAttr("basearch")
        self.conf.set(basearch=self.conf.buildarch)

        if re.match(r"i.86", self.conf.basearch):
            self.conf.set(basearch="i386")
        elif self.conf.basearch == "sparc64":
            self.conf.set(basearch="sparc")

        # set the libdir
        self.conf.addAttr("libdir")
        self.conf.set(libdir="lib")

        # on 64-bit systems, make sure we use lib64 as the lib directory
        if self.conf.buildarch.endswith("64") or self.conf.buildarch == "s390x":
            self.conf.set(libdir="lib64")

        # set efiarch
        self.conf.addAttr("efiarch")
        self.conf.set(efiarch="")

        if self.conf.buildarch == "i386":
            self.conf.set(efiarch="ia32")
        elif self.conf.buildarch == "x86_64":
            self.conf.set(efiarch="x64")
        elif self.conf.buildarch == "ia64":
            self.conf.set(efiarch="ia64")

    def write_treeinfo(self, discnum=1, totaldiscs=1, packagedir=""):
        outfile = os.path.join(self.conf.outdir, ".treeinfo")

        # don't print anything instead of None, if variant is not specified
        variant = ""
        if self.conf.variant is not None:
            variant = self.conf.variant
           
        c = ConfigParser.ConfigParser()

        # general section
        section = "general"
        data = { "timestamp": time.time(),
                 "family": self.conf.product,
                 "version": self.conf.version,
                 "arch": self.conf.basearch,
                 "variant": variant,
                 "discnum": discnum,
                 "totaldiscs": totaldiscs,
                 "packagedir": packagedir }
        c.add_section(section)
        [c.set(section, key, value) for key, value in data.items()]

        # images section
        section = "images-%s" % (self.conf.basearch,)
        data = { "kernel": "images/pxeboot/vmlinuz",
                 "initrd": "images/pxeboot/initrd.img",
                 "boot.iso": "images/boot.iso" }
        c.add_section(section)
        [c.set(section, key, value) for key, value in data.items()]

        try:
            f = open(outfile, "w")
        except IOError as why:
            self.se.error("Unable to write .treeinfo file: %s" % (why,))
            return False
        else:
            c.write(f)
            f.close()
        
        return True

    def write_discinfo(self, discnum="ALL"):
        outfile = os.path.join(self.conf.outdir, ".discinfo")

        try:
            f = open(outfile, "w")
        except IOError as why:
            self.se.error("Unable to write .discinfo file: %s" % (why,))
            return False
        else:
            f.write("%f\n" % (time.time(),))
            f.write("%s\n" % (self.conf.release,))
            f.write("%s\n" % (self.conf.basearch,))
            f.write("%s\n" % (discnum,))
            f.close()
        
        return True

    def write_buildstamp(self):
        outfile = os.path.join(self.conf.treedir, ".buildstamp")

        # make image uuid
        now = datetime.datetime.now()
        uuid = "%s.%s" % (now.strftime("%Y%m%d%H%M"), self.conf.buildarch)

        try:
            f = open(outfile, "w")
        except IOError as why:
            self.se.error("Unable to write .buildstamp file: %s" % (why,))
            return False
        else:
            f.write("%s\n" % (uuid,))
            f.write("%s\n" % (self.conf.product,))
            f.write("%s\n" % (self.conf.version,))
            f.write("%s\n" % (self.conf.bugurl,))
            f.close()

        self.conf.addAttr("buildstamp")
        self.conf.set(buildstamp=outfile)

        return True

    def prepare_output_directory(self):
        # write the images/README
        src = os.path.join(self.conf.datadir, "images", "README")
        dst = os.path.join(self.conf.imagesdir, "README")
        shutil.copy2(src, dst)
        replace(dst, r"@PRODUCT@", self.conf.product)

        # write the images/pxeboot/README
        src = os.path.join(self.conf.datadir, "images", "pxeboot", "README")
        dst = os.path.join(self.conf.pxebootdir, "README")
        shutil.copy2(src, dst)
        replace(dst, r"@PRODUCT@", self.conf.product)

        # set up some dir variables for further use
        anacondadir = os.path.join(self.conf.treedir,
                "usr", "lib", "anaconda-runtime")
        
        bootdiskdir = os.path.join(anacondadir, "boot")
        self.conf.addAttr("bootdiskdir")
        self.conf.set(bootdiskdir=bootdiskdir)

        syslinuxdir = os.path.join(self.conf.treedir, "usr", "lib", "syslinux")
        isolinuxbin = os.path.join(syslinuxdir, "isolinux.bin")

        if os.path.isfile(isolinuxbin):
            # copy the isolinux.bin
            shutil.copy2(isolinuxbin, self.conf.isolinuxdir)

            # copy the syslinux.cfg to isolinux/isolinux.cfg
            isolinuxcfg = os.path.join(self.conf.isolinuxdir, "isolinux.cfg")
            shutil.copy2(os.path.join(bootdiskdir, "syslinux.cfg"), isolinuxcfg)

            # set the product and version in isolinux.cfg
            replace(isolinuxcfg, r"@PRODUCT@", self.conf.product)
            replace(isolinuxcfg, r"@VERSION@", self.conf.version)

            # set up the label for finding stage2 with a hybrid iso
            replace(isolinuxcfg, r"initrd=initrd.img",
                    "initrd=initrd.img stage2=hd:LABEL=%s" % (self.conf.product,))

            # copy the grub.conf
            shutil.copy2(os.path.join(bootdiskdir, "grub.conf"),
                    self.conf.isolinuxdir)

            # copy the splash files
            vesasplash = os.path.join(anacondadir, "syslinux-vesa-splash.jpg")
            if os.path.isfile(vesasplash):
                shutil.copy2(vesasplash,
                        os.path.join(self.conf.isolinuxdir, "splash.jpg"))

                vesamenu = os.path.join(syslinuxdir, "vesamenu.c32")
                shutil.copy2(vesamenu, self.conf.isolinuxdir)

                replace(isolinuxcfg, r"default linux", r"default vesamenu.c32")
                replace(isolinuxcfg, r"prompt 1", r"#prompt 1")
            else:
                splashtools = os.path.join(anacondadir, "splashtools.sh")
                splashlss = os.path.join(bootdiskdir, "splash.lss")

                if os.path.isfile(splashtools):
                    cmd = "%s %s %s" % (splashtools,
                            os.path.join(bootdiskdir, "syslinux-splash.jpg"),
                            splashlss)
                    out = commands.getoutput(cmd)

                if os.path.isfile(splashlss):
                    shutil.copy2(splashlss, self.conf.isolinuxdir)

            # copy the .msg files
            for file in os.listdir(bootdiskdir):
                if file.endswith(".msg"):
                    shutil.copy2(os.path.join(bootdiskdir, file),
                            self.conf.isolinuxdir)
                    replace(os.path.join(self.conf.isolinuxdir, file),
                            r"@VERSION@", self.conf.version)

            # if present, copy the memtest
            for fname in os.listdir(os.path.join(self.conf.treedir, "boot")):
                if fname.startswith("memtest"):
                    src = os.path.join(self.conf.treedir, "boot", fname)
                    dst = os.path.join(self.conf.isolinuxdir, "memtest")
                    shutil.copy2(src, dst)

                    text = "label memtest86\n"
                    text = text + "  menu label ^Memory test\n"
                    text = text + "  kernel memtest\n"
                    text = text + "  append -\n"
                    edit(isolinuxcfg, text, append=True)
        else:
            return False
        
        return True

    def create_install_image(self, type="squashfs"):
        installimg = os.path.join(self.conf.imagesdir, "install.img")

        if os.path.exists(installimg):
            os.unlink(installimg)

        if type == "squashfs":
            cmd = "mksquashfs %s %s -all-root -no-fragments -no-progress" \
                    % (self.conf.treedir, installimg)
            self.so.debug(cmd)
            err, output = commands.getstatusoutput(cmd)
            if err:
                self.se.info(output)
                return False

        elif type == "cramfs":
            if self.conf.buildarch == "sparc64":
                crambs = "--blocksize 8192"
            elif self.conf.buildarch == "sparc":
                crambs = "--blocksize 4096"
            else:
                crambs = ""

            cmd = "mkfs.cramfs %s %s %s" % (crambs, self.conf.treedir,
                    installimg)
            self.so.debug(cmd)
            err, output = commands.getstatusoutput(cmd)
            if err:
                self.se.info(output)
                return False

        elif type == "ext2":
            # TODO
            return False

        # append stage2 to .treeinfo file
        text = "\n[stage2]\n"
        text += "mainimage = %s\n" % (installimg,)
        edit(os.path.join(self.conf.outdir, ".treeinfo"), append=True, text=text)

        return True

    def create_boot_iso(self):
        bootiso = os.path.join(self.conf.imagesdir, "boot.iso")

        if os.path.exists(bootiso):
            os.unlink(bootiso)

        efiboot = os.path.join(self.conf.imagesdir, "efiboot.img")

        if os.path.exists(efiboot):
            self.so.info("Found efiboot.img, making an EFI-capable boot.iso")
            efiargs = "-eltorito-alt-boot -e images/efiboot.img -no-emul-boot"
            efigraft = "EFI/BOOT=%s" % (os.path.join(self.conf.outdir,
                    "EFI", "BOOT"),)
        else:
            self.so.info("No efiboot.img found, making BIOS-only boot.iso")
            efiargs = ""
            efigraft = ""

        biosargs = "-b isolinux/isolinux.bin -c isolinux/boot.cat" \
                " -no-emul-boot -boot-load-size 4 -boot-info-table"
        mkisocmd = "mkisofs -v -o %s %s %s -R -J -V %s -T -graft-points" \
                " isolinux=%s images=%s %s" % (bootiso, biosargs, efiargs,
                self.conf.product, self.conf.isolinuxdir, self.conf.imagesdir,
                efigraft)
        self.so.debug(mkisocmd)
        err, out = commands.getstatusoutput(mkisocmd)
        if err:
            self.se.info(out)
            return False

        hybrid = os.path.join("/", "usr", "bin", "isohybrid")
        if os.path.exists(hybrid):
            cmd = "%s %s" % (hybrid, os.path.join(self.conf.imagesdir, "boot.iso"))
            self.so.debug(cmd)
            err, out = commands.getstatusoutput(cmd)
            if err:
                self.se.info(out)
                # XXX is this a problem?
                # should we return false, or just go on?

        return True

    def clean_up(self):
        if os.path.isdir(self.conf.tempdir):
            shutil.rmtree(self.conf.tempdir, ignore_errors=True)

    def run(self):
        self.so.header(":: Collecting repositories")
        ok = self.collect_repositories()
        if not ok:
            # we have no valid repository to work with
            self.se.error("No valid repository")
            sys.exit(1)

        self.so.header(":: Initializing directories")
        self.initialize_directories()

        self.so.header(":: Initializing yum")
        ok = self.initialize_yum()
        if not ok:
            # the yum object could not be initialized
            self.se.error("Unable to initialize the yum object")
            sys.exit(1)

        self.so.header(":: Setting the architecture")
        self.set_architecture()

        self.so.header(":: Writing the .treeinfo file")
        ok = self.write_treeinfo()
        if not ok:
            # XXX is this a problem?
            pass

        self.so.header(":: Writing the .discinfo file")
        ok = self.write_discinfo()
        if not ok:
            # XXX is this a problem?
            pass

        self.so.header(":: Writing the .buildstamp file")
        ok = self.write_buildstamp()
        if not ok:
            # XXX is this a problem?
            pass

        self.so.header(":: Preparing the install tree")
        tree = insttree.InstallTree(self.conf, self.yum, (self.so, self.se))
        kernelfiles = tree.run()

        if not kernelfiles:
            self.se.error("No kernel image found")
            sys.exit(1)

        self.so.header(":: Preparing the output directory")
        ok = self.prepare_output_directory()
        if not ok:
            # XXX there's no isolinux.bin, i guess this is a problem...
            self.se.error("Unable to prepare the output directory")
            sys.exit(1)

        self.conf.addAttr(["kernelfile", "kernelver"])
        for kernelfile in kernelfiles:
            # get the kernel version
            m = re.match(r".*vmlinuz-(.*)", kernelfile)
            if m:
                kernelver = m.group(1)
                self.conf.set(kernelfile=kernelfile, kernelver=kernelver)
            else:
                self.se.warning("Invalid kernel filename '%s'" % (kernelfile,))
                continue

            self.so.header(":: Creating the initrd image for kernel '%s'" \
                    % (os.path.basename(kernelfile),))
            initrd = images.InitRD(self.conf, self.yum, (self.so, self.se))
            initrd.run()

        self.so.header(":: Creating the install image")
        
        self.so.info("Scrubbing the install tree")
        tree.scrub()
        
        ok = self.create_install_image()
        if not ok:
            self.se.error("Unable to create the install image")
            sys.exit(1)

        self.so.header(":: Creating the boot iso")
        ok = self.create_boot_iso()
        if not ok:
            self.se.error("Unable to create the boot iso")
            sys.exit(1)

        if self.conf.cleanup:
            self.so.header(":: Cleaning up")
            self.clean_up()
