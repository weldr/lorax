#
# images.py
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
#

import sys
import os
import re
import shutil
import gzip
import commands
import tempfile
import math
import glob
import fnmatch

from base import BaseImageClass
from sysutils import *


class InitRD(BaseImageClass):

    def __init__(self, installtree, modules, template_file, workdir="/tmp"):
        BaseImageClass.__init__(self)

        self.installtree = installtree
        self.modules = modules
        self.template_file = template_file
        self.workdir = workdir

        self.srctree = self.installtree.rootdir
        self.dsttree = None

    def create(self):
        for kernel in self.installtree.kernels:
            msg = ":: creating the initrd image for <b>{0}</b>"
            msg = msg.format(kernel.filename)
            self.pinfo(msg)

            # prepare the working environment
            self.pinfo("preparing the work environment")
            self.prepare(kernel)

            # get the kernel modules
            self.pinfo("getting the kernel modules")
            self.get_kernel_modules(kernel, self.modules)

            # get keymaps
            self.pinfo("creating keymaps")
            ok = self.get_keymaps()
            if not ok:
                self.perror("could not create keymaps")
                continue

            # create locales
            self.pinfo("creating locales")
            ok = self.create_locales()
            if not ok:
                self.perror("could not create locales")
                continue

            # parse the template file
            self.pinfo("parsing the template")
            variables = {"buildarch": self.conf.buildarch,
                         "basearch": self.conf.basearch,
                         "libdir": self.conf.libdir}
            self.parse_template(self.template_file, variables)

            # create the initrd file
            self.pinfo("compressing the initrd image file")
            initrdfile = self.compress(kernel)
            if not initrdfile:
                self.perror("could not create the initrd image file")
                continue

            yield (kernel, initrdfile)

    def prepare(self, kernel):
        # create the initrd working directory
        dir = os.path.join(self.workdir, "initrd-{0}".format(kernel.version))
        if os.path.isdir(dir):
            shutil.rmtree(dir)
        os.mkdir(dir)

        # set the destination tree
        self.dsttree = dir

        # copy the buildstamp
        shutil.copy2(self.conf.buildstamp, self.dsttree)

        # create the .profile
        profile = os.path.join(self.dsttree, ".profile")
        text = """PS1="[anaconda \u@\h \W]\\$ "
PATH=/bin:/usr/bin:/usr/sbin:/mnt/sysimage/sbin:/mnt/sysimage/usr/sbin:/mnt/sysimage/bin:/mnt/sysimage/usr/bin
export PS1 PATH

"""

        with open(profile, "w") as f:
            f.write(text)

        # create the lib directory
        os.mkdir(os.path.join(self.dsttree, self.conf.libdir))

    # XXX
    def get_kernel_modules(self, kernel, modset):
        moddir = os.path.join(self.const.MODDIR, kernel.version)
        src_moddir = os.path.join(self.srctree, moddir)
        dst_moddir = os.path.join(self.dsttree, moddir)

        # copy all modules to the initrd tree
        os.makedirs(os.path.dirname(dst_moddir))
        shutil.copytree(src_moddir, dst_moddir)

        # expand modules
        modules = set()
        pattern = re.compile(r"\.ko$")
        for name in modset:
            if name.startswith("="):
                group = name[1:]
                if group in ("scsi", "ata"):
                    p = os.path.join(src_moddir, "modules.block")
                elif group == "net":
                    p = os.path.join(src_moddir, "modules.networking")
                else:
                    p = os.path.join(src_moddir, "modules.{0}".format(group))

                if os.path.isfile(p):
                    with open(p, "r") as f:
                        for line in f:
                            module = pattern.sub("", line.strip())
                            modules.add(module)
            else:
                modules.add(name)

        # resolve modules dependencies
        moddep = os.path.join(src_moddir, self.const.MODDEPFILE)
        with open(moddep, "r") as f:
            lines = map(lambda line: line.strip(), f.readlines())

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

        # remove not needed modules
        for root, dirs, files in os.walk(dst_moddir):
            for file in files:
                path = os.path.join(root, file)
                name, ext = os.path.splitext(file)

                if ext == ".ko":
                    if name not in modules:
                        os.unlink(path)
                    else:
                        # get the required firmware
                        cmd = "{0.MODINFO} -F firmware {1}"
                        cmd = cmd.format(self.cmd, path)
                        err, stdout = commands.getstatusoutput(cmd)
                        if err:
                            self.perror(stdout)
                            continue

                        for fw in stdout.split():
                            fw = os.path.join(self.const.FWDIR, fw)
                            src = os.path.join(self.srctree, fw)
                            if not os.path.exists(src):
                                msg = "missing firmware {0}".format(fw)
                                self.pwarning(msg)
                                continue

                            # copy the firmware
                            dst = os.path.join(self.dsttree, fw)
                            dir = os.path.dirname(dst)
                            makedirs_(dir)
                            shutil.copy2(src, dst)

        # copy additional firmware
        fw = [("ipw2100", "ipw2100*"),
              ("ipw2200", "ipw2200*"),
              ("iwl3945", "iwlwifi-3945*"),
              ("iwl4965", "iwlwifi-4965*"),
              ("atmel", "atmel_*.bin"),
              ("zd1211rw", "zd1211"),
              ("qla2xxx", "ql*")]

        for module, fname in fw:
            if module in modules:
                scopy_(src_root=self.srctree,
                       src_path=os.path.join(self.const.FWDIR, fname),
                       dst_root=self.dsttree,
                       dst_path=self.const.FWDIR)

        # XXX
        # remove empty directories
        #empty_dirs = set()
        #for root, dirs, files in os.walk(dst_moddir, topdown=False):
        #    if not dirs and not files:
        #        shutil.rmtree(root)

        # get the modules paths
        modpaths = {}
        for root, dirs, files in os.walk(dst_moddir):
            for file in files:
                modpaths[file] = os.path.join(root, file)

        # create the modules list
        modlist = {}
        for modtype, fname in {"scsi": "modules.block",
                               "eth": "modules.networking"}.items():

            modlist[modtype] = {}

            fname = os.path.join(dst_moddir, fname)
            with open(fname, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    modname, ext = os.path.splitext(line)
                    if (line not in modpaths or
                        modname in ("floppy", "libiscsi", "scsi_mod")):
                        continue

                    cmd = "{0.MODINFO} -F description {1}"
                    cmd = cmd.format(self.cmd, modpaths[line])
                    err, stdout = commands.getstatusoutput(cmd)
                    if err:
                        self.pwarning(stdout)
                        desc = ""
                    else:
                        desc = stdout.split("\n")[0]
                        desc = desc.strip()[:65]

                    if not desc:
                        desc = "{0} driver".format(modname)

                    info = '{0}\n\t{1}\n\t"{2}"\n'
                    info = info.format(modname, modtype, desc)
                    modlist[modtype][modname] = info

        # write the source module-info
        moduleinfo = os.path.join(self.workdir, self.const.MODULEINFO)
        with open(moduleinfo, "w") as f:
            f.write("Version 0\n")
            for modtype, modules in modlist.items():
                for modname in sorted(modules.keys()):
                    f.write(modlist[modtype][modname])

        # create the final module-info
        dst = os.path.join(os.path.dirname(dst_moddir), self.const.MODULEINFO)
        modlist = os.path.join(self.srctree, self.const.MODLIST)
        cmd = "{0} --modinfo-file {1} --ignore-missing --modinfo {2} > {3}"
        cmd = cmd.format(modlist, moduleinfo, " ".join(list(modules)), dst)
        err, stdout = commands.getstatusoutput(cmd)
        if err:
            self.perror(stdout)

        # remove the source module-info
        #os.unlink(moduleinfo)

        # run depmod
        systemmap = os.path.join(self.srctree, self.const.BOOTDIR,
                                 "System.map-{0}".format(kernel.version))

        cmd = "{0.DEPMOD} -a -F {1} -b {2} {3}"
        cmd = cmd.format(self.cmd, systemmap,
                         self.srctree, kernel.version)

        err, stdout = commands.getstatusoutput(cmd)
        if err:
            self.perror(stdout)

        # compress modules
        for root, dirs, files in os.walk(dst_moddir):
            for file in filter(lambda f: f.endswith(".ko"), files):
                path = os.path.join(root, file)
                with open(path, "rb") as f:
                    data = f.read()

                gzipped = gzip.open("{0}.gz".format(path), "wb")
                gzipped.write(data)
                gzipped.close()
                os.unlink(path)

    def get_keymaps(self):
        override = "keymaps-override-{0}".format(self.conf.basearch)
        override = os.path.join(self.srctree, self.const.ANACONDA_RUNTIME,
                                override)

        getkeymaps = os.path.join(self.srctree, self.const.ANACONDA_RUNTIME,
                                  "getkeymaps")

        dst = os.path.join(self.dsttree, "etc/keymaps.gz")
        dir = os.path.dirname(dst)
        if not os.path.isdir(dir):
            os.makedirs(dir)

        if os.path.isfile(override):
            self.pinfo("using keymaps override")
            shutil.copy2(override, dst)
        else:
            cmd = "{0} {1} {2} {3}"
            cmd = cmd.format(getkeymaps, self.conf.basearch, dst, self.srctree)
            err, stdout = commands.getstatusoutput(cmd)
            if err:
                self.perror(stdout)
                return False

        return True

    def create_locales(self):
        localedir = os.path.join(self.dsttree, self.const.LOCALEDIR)
        os.makedirs(localedir)

        cmd = "{0.LOCALEDEF} -c -i en_US -f UTF-8 --prefix {1} en_US"
        cmd = cmd.format(self.cmd, self.dsttree)
        err, stdout = commands.getstatusoutput(cmd)
        if err:
            self.perror(stdout)
            return False

        return True

    def compress(self, kernel):
        filename = "initrd-{0}.img".format(kernel.version)
        filepath = os.path.join(self.workdir, filename)

        # create the cpio archive
        cpioarchive = "{0}.cpio".format(filepath)

        cwd = os.getcwd()
        os.chdir(self.dsttree)

        cmd = "find . | cpio --quiet -c -o > {0}".format(cpioarchive)
        err, stdout = commands.getstatusoutput(cmd)

        os.chdir(cwd)

        if err:
            self.perror(stdout)
            return None

        # create the gzip archive
        with open(cpioarchive, "rb") as f:
            cpiodata = f.read()

        gzipped = gzip.open(filepath, "wb")
        gzipped.write(cpiodata)
        gzipped.close()

        # remove the cpio archive
        os.unlink(cpioarchive)

        # remove the initrd tree
        #shutil.rmtree(self.dsttree)

        return filepath


class EFI(BaseImageClass):

    def __init__(self, installtree, kernel, initrd, product, version,
                 workdir="/tmp"):

        BaseImageClass.__init__(self)

        self.srctree = installtree.rootdir
        self.dsttree = None

        self.kernel = kernel
        self.initrd = initrd
        self.product = product
        self.version = version

        self.workdir = workdir

    def create(self):
        msg = ":: creating the efi images for <b>{0}</b>"
        self.pinfo(msg.format(self.kernel.filename))

        # create efiboot image with kernel
        self.pinfo("creating efiboot image with kernel")
        efiboot_kernel = self.create_efiboot(with_kernel=True)
        if efiboot_kernel is None:
            self.perror("unable to create the efiboot image")
            return None, None

        # create the efidisk image
        self.pinfo("creating efidisk image")
        efidisk = self.create_efidisk(efiboot_kernel)
        if efidisk is None:
            self.perror("unable to create the efidisk image")
            return None, None

        # remove the efiboot image with kernel
        os.unlink(efiboot_kernel)

        # create efiboot image without kernel
        self.pinfo("creating efiboot image without kernel")
        efiboot_nokernel = self.create_efiboot(with_kernel=False)
        if efiboot_nokernel is None:
            self.perror("unable to create the efiboot image")
            return None, None

        return efiboot_nokernel, efidisk

    def create_efiboot(self, with_kernel=True):
        # create the efi tree directory
        efitree = tempfile.mkdtemp(prefix="efitree.", dir=self.workdir)

        efikernelpath = "/images/pxeboot/vmlinuz"
        efiinitrdpath = "/images/pxeboot/initrd.img"
        efisplashpath = "/EFI/BOOT/splash.xpm.gz"

        # copy kernel and initrd files to efi tree directory
        if with_kernel:
            kpath = self.kernel.path
            shutil.copy2(kpath, os.path.join(efitree, "vmlinuz"))
            shutil.copy2(self.initrd, os.path.join(efitree, "initrd.img"))
            efikernelpath = "/EFI/BOOT/vmlinuz"
            efiinitrdpath = "/EFI/BOOT/initrd.img"

        # copy conf files to efi tree directory
        srcdir = os.path.join(self.srctree, self.const.ANACONDA_BOOTDIR)
        scopy_(src_root=srcdir, src_path="*.conf",
               dst_root=efitree, dst_path="")

        # edit the grub.conf file
        grubconf = os.path.join(efitree, "grub.conf")
        replace_(grubconf, "@PRODUCT@", self.product)
        replace_(grubconf, "@VERSION@", self.version)
        replace_(grubconf, "@KERNELPATH@", efikernelpath)
        replace_(grubconf, "@INITRDPATH@", efiinitrdpath)
        replace_(grubconf, "@SPLASHPATH@", efisplashpath)

        if self.conf.efiarch == "IA32":
            shutil.copy2(grubconf, os.path.join(efitree, "BOOT.conf"))

        dst = os.path.join(efitree, "BOOT{0}.conf".format(self.conf.efiarch))
        shutil.move(grubconf, dst)

        # copy grub.efi
        grubefi = os.path.join(self.srctree, self.const.EFIDIR, "grub.efi")

        if self.conf.efiarch == "IA32":
            shutil.copy2(grubefi, os.path.join(efitree, "BOOT.efi"))

        dst = os.path.join(efitree, "BOOT{0}.efi".format(self.conf.efiarch))
        shutil.copy2(grubefi, dst)

        # copy splash.xpm.gz
        splash = os.path.join(self.srctree, self.const.SPLASH)
        shutil.copy2(splash, efitree)

        efiboot = os.path.join(self.workdir, "efiboot.img")
        if os.path.isfile(efiboot):
            os.unlink(efiboot)

        # calculate the size of the efi tree directory
        fsoverhead = 100 * 1024
        sizeinbytes = fsoverhead
        for root, dirs, files in os.walk(efitree):
            for file in files:
                filepath = os.path.join(root, file)
                sizeinbytes += os.path.getsize(filepath)

        # mkdosfs needs the size in blocks of 1024 bytes
        size = int(math.ceil(sizeinbytes / 1024.0))

        cmd = "{0.MKDOSFS} -n ANACONDA -C {1} {2} > /dev/null"
        cmd = cmd.format(self.cmd, efiboot, size)
        err, stdout = commands.getstatusoutput(cmd)
        if err:
            self.perror(stdout)
            return None

        # mount the efiboot image
        efibootdir = tempfile.mkdtemp(prefix="efiboot.", dir=self.workdir)

        cmd = "mount -o loop,shortname=winnt,umask=0777 -t vfat {0} {1}"
        cmd = cmd.format(efiboot, efibootdir)
        err, stdout = commands.getstatusoutput(cmd)
        if err:
            self.perror(stdout)
            return None

        # copy the files to the efiboot image
        dstdir = os.path.join(efibootdir, "EFI/BOOT")
        os.makedirs(dstdir)

        scopy_(src_root=efitree, src_path="*",
               dst_root=dstdir, dst_path="")

        # unmount the efiboot image
        cmd = "umount {0}".format(efibootdir)
        err, stdout = commands.getstatusoutput(cmd)
        if err:
            self.pwarning(stdout)

        # remove the working directories
        shutil.rmtree(efibootdir)
        #shutil.rmtree(efitree)

        # XXX copy the conf files and splash.xpm.gz to the output directory
        if not with_kernel:
            scopy_(src_root=efitree, src_path="*.conf",
                   dst_root=self.conf.efidir, dst_path="")
            shutil.copy2(splash, self.conf.efidir)

        return efiboot

    def create_efidisk(self, efiboot):
        efidisk = os.path.join(self.workdir, "efidisk.img")
        if os.path.isfile(efidisk):
            os.unlink(efidisk)

        partsize = os.path.getsize(efiboot)
        disksize = 17408 + partsize + 17408
        disksize = disksize + (disksize % 512)

        # create the efidisk file
        with open(efidisk, "wb") as f:
            f.truncate(disksize)

        # create the loop device
        cmd = "{0.LOSETUP} -v -f {1} | {0.AWK} '{{print $4}}'"
        cmd = cmd.format(self.cmd, efidisk)
        err, loop = commands.getstatusoutput(cmd)
        if err:
            self.perror(loop)
            os.unlink(efidisk)
            return None

        # create the dm device
        dmdev = "efiboot"
        cmd = '{0.DMSETUP} create {1} --table "0 {2} linear {3} 0"'
        cmd = cmd.format(self.cmd, dmdev, disksize / 512, loop)
        err, stdout = commands.getstatusoutput(cmd)
        if err:
            self.perror(output)
            self.remove_loop_dev(loop)
            os.unlink(efidisk)
            return None

        cmd = ("{0.PARTED} --script /dev/mapper/{1} "
               "mklabel gpt unit b mkpart '\"EFI System Partition\"' "
               "fat32 17408 {2} set 1 boot on")
        cmd = cmd.format(self.cmd, dmdev, partsize + 17408)
        err, stdout = commands.getstatusoutput(cmd)
        if err:
            self.perror(stdout)
            self.remove_dm_dev(dmdev)
            self.remove_loop_dev(loop)
            os.unlink(efidisk)
            return None

        with open(efiboot, "rb") as f_from:
            with open("/dev/mapper/{0}p1".format(dmdev), "wb") as f_to:
                efidata = f_from.read(1024)
                while efidata:
                    f_to.write(efidata)
                    efidata = f_from.read(1024)

        self.remove_dm_dev("{0}p1".format(dmdev))
        self.remove_dm_dev(dmdev)
        self.remove_loop_dev(loop)

        return efidisk

    def remove_loop_dev(self, dev):
        cmd = "{0.LOSETUP} -d {1}".format(self.cmd, dev)
        err, stdout = commands.getstatusoutput(cmd)
        if err:
            self.pwarning(stdout)

    def remove_dm_dev(self, dev):
        cmd = "{0.DMSETUP} remove /dev/mapper/{1}".format(self.cmd, dev)
        err, stdout = commands.getstatusoutput(cmd)
        if err:
            self.pwarning(stdout)


class Install(BaseImageClass):

    def __init__(self, installtree, template_file, workdir="/tmp"):
        BaseImageClass.__init__(self)

        self.srctree = installtree.rootdir
        self.dsttree = installtree.rootdir
        self.template_file = template_file
        self.workdir = workdir

    def create(self, type="squashfs"):
        self.pinfo(":: creating the install image")

        # copy the .buildstamp
        shutil.copy2(self.conf.buildstamp, self.srctree)

        self.copy_stubs()
        self.copy_bootloaders()
        self.rename_repos()
        self.move_anaconda_files()
        self.create_modules_symlinks()
        self.fix_man_pages()
        self.remove_locales()
        self.remove_unnecessary_files()
        self.move_bins()

        # parse the template file
        self.pinfo("parsing the template")
        variables = {"buildarch": self.conf.buildarch,
                     "basearch": self.conf.basearch,
                     "libdir": self.conf.libdir}
        self.parse_template(self.template_file, variables)

        installimg = os.path.join(self.workdir, "install.img")
        if os.path.isfile(installimg):
            os.unlink(installimg)

        if type == "squashfs":
            self.pinfo("using squash filesystem")
            cmd = "{0.MKSQUASHFS} {1} {2} -all-root -no-fragments -no-progress"
            cmd = cmd.format(self.cmd, self.srctree, installimg)
            err, stdout = commands.getstatusoutput(cmd)
            if err:
                self.perror(stdout)
                return None
        elif type == "cramfs":
            # TODO
            raise NotImplementedError
        elif type == "ext2":
            # TODO
            raise NotImplementedError

        return installimg

    def copy_stubs(self):
        stubs = ("raidstart", "raidstop", "losetup", "list-harddrives",
                 "loadkeys", "mknod", "syslogd")

        for stub in map(lambda s: "{0}-stub".format(s), stubs):
            src = os.path.join(self.srctree, "usr/lib/anaconda", stub)
            dst = os.path.join(self.srctree, "usr/bin", stub)
            if os.path.isfile(src):
                shutil.copy2(src, dst)

    def copy_bootloaders(self):
        srcdir = os.path.join(self.srctree, self.const.BOOTDIR)
        dstdir = os.path.join(self.srctree, self.const.ANACONDA_BOOTDIR)

        if self.conf.buildarch in ("i386", "i586", "i686", "x86_64"):
            for f in glob.iglob(os.path.join(srcdir, "memtest*")):
                shutil.copy2(f, dstdir)

        elif self.conf.buildarch in ("ppc", "ppc64"):
            f = os.path.join(srcdir, "efika.forth")
            shutil.copy2(f, dstdir)

        elif self.conf.buildarch in ("sparc", "sparc64"):
            for f in glob.iglob(os.path.join(srcdir, "*.b")):
                shutil.copy2(f, dstdir)

        elif self.conf.buildarch == "ia64":
            srcdir = os.path.join(self.srctree, self.const.BOOTDIR_IA64)
            for f in glob.iglob(os.path.join(srcdir, "*")):
                shutil.copy2(dstdir)

    def rename_repos(self):
        src = os.path.join(self.srctree, "etc/yum.repos.d")
        dst = os.path.join(self.srctree, "etc/anaconda.repos.d")
        shutil.move(src, dst)

    def move_anaconda_files(self):
        # move anaconda executable
        src = os.path.join(self.srctree, "usr/sbin/anaconda")
        dst = os.path.join(self.srctree, "usr/bin/anaconda")
        shutil.move(src, dst)

        # move anaconda libraries
        srcdir = os.path.join(self.srctree, self.const.ANACONDA_RUNTIME)
        dstdir = os.path.join(self.srctree, "usr", self.conf.libdir)
        for f in glob.iglob(os.path.join(srcdir, "lib*")):
            shutil.move(f, dstdir)

    def create_modules_symlinks(self):
        mkdir_(os.path.join(self.srctree, "modules"))
        mkdir_(os.path.join(self.srctree, "firmware"))
        remove_(os.path.join(self.srctree, self.const.MODDIR))
        remove_(os.path.join(self.srctree, self.const.FWDIR))
        os.symlink("/modules", os.path.join(self.srctree, self.const.MODDIR))
        os.symlink("/firmware", os.path.join(self.srctree, self.const.FWDIR))

    def fix_man_pages(self):
        # fix up some links for man page related stuff
        for file in ("nroff", "groff", "iconv", "geqn", "gtbl", "gpic",
                     "grefer"):

            target = os.path.join("/mnt/sysimage/usr/bin", file)
            name = os.path.join(self.srctree, "usr/bin", file)
            if not os.path.isfile(name):
                os.symlink(target, name)

        # fix /etc/man.config to point into /mnt/sysimage
        manconf = os.path.join(self.srctree, self.const.MANCONF)
        replace_(manconf, r"^MANPATH\s+(\S+)", "MANPATH\t/mnt/sysimage\g<1>")
        replace_(manconf, r"^MANPATH_MAP\s+(\S+)\s+(\S+)",
                 "MANPATH_MAP\t\g<1>\t/mnt/sysimage\g<2>")

    def remove_locales(self):
        langtable = os.path.join(self.srctree, self.const.LANGTABLE)
        localepath = os.path.join(self.srctree, self.const.LOCALES)

        if os.path.isfile(langtable):
            keep = set()

            with open(langtable, "r") as f:
                lines = f.readlines()

            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                fields = line.split("\t")

                dir = os.path.join(localepath, fields[1])
                if os.path.isdir(dir):
                    keep.add(fields[1])

                locale = fields[3].split(".")[0]
                dir = os.path.join(localepath, locale)
                if os.path.isdir(dir):
                    keep.add(locale)

            for locale in os.listdir(localepath):
                if locale not in keep:
                    path = os.path.join(localepath, locale)
                    remove_(path)

    def remove_unnecessary_files(self):
        for root, dirs, files in os.walk(self.srctree):
            for file in files:
                path = os.path.join(root, file)

                if (fnmatch.fnmatch(path, "*.a") and
                    not path.count("kernel-wrapper/wrapper.a")):
                    os.unlink(path)

                if (fnmatch.fnmatch(path, "lib*.la") and
                    not path.count("gtk-2.0")):
                    os.unlink(path)

                if fnmatch.fnmatch(path, "*.py"):
                    pyo, pyc = path + "o", path + "c"
                    if os.path.isfile(pyo):
                        os.unlink(pyo)
                    if os.path.isfile(pyc):
                        os.unlink(pyc)

                    os.symlink("/dev/null", pyc)

        # remove libunicode-lite
        remove_(os.path.join(self.srctree, "usr", self.conf.libdir,
                             "libunicode-lite*"))

    def move_bins(self):
        # move bin to usr/bin
        scopy_(src_root=self.srctree, src_path="bin/*",
               dst_root=self.srctree, dst_path="usr/bin")
        remove_(os.path.join(self.srctree, "bin"))

        # move sbin to /usr/sbin
        scopy_(src_root=self.srctree, src_path="sbin/*",
               dst_root=self.srctree, dst_path="usr/sbin")
        remove_(os.path.join(self.srctree, "sbin"))

        # fix broken links
        brokenlinks = []
        for dir in ("bin", "sbin"):
            dir = os.path.join(self.srctree, "usr", dir)
            for root, dnames, fnames in os.walk(dir):
                for fname in fnames:
                    fname = os.path.join(root, fname)
                    if os.path.islink(fname) and not os.path.exists(fname):
                        brokenlinks.append(fname)

        pattern = re.compile(r"^\.\./\.\./(bin|sbin)/(.*)$")
        for link in brokenlinks:
            target = os.readlink(link)
            newtarget = pattern.sub(r"../\g<1>/\g<2>", target)
            if newtarget != target:
                os.unlink(link)
                os.symlink(newtarget, link)


class Boot(BaseImageClass):

    def __init__(self, product, workdir="/tmp"):
         BaseImageClass.__init__(self)
         self.product = product
         self.workdir = workdir

         self.efiboot = os.path.join(self.conf.imgdir, "efiboot.img")

    def create(self):
        self.pinfo(":: creating the boot iso image")
        bootiso = os.path.join(self.workdir, "boot.iso")
        if os.path.isfile(bootiso):
            os.unlink(bootiso)

        if os.path.isfile(self.efiboot):
            self.pinfo("creating efi capable boot iso")
            efiargs = "-eltorito-alt-boot -e images/efiboot.img -no-emul-boot"
            efigraft = "EFI/BOOT={0}".format(self.conf.efidir)
        else:
            efiargs = ""
            efigraft = ""

        cmd = ("{0.MKISOFS} -U -A {1} -V {1} -volset {1} -J -joliet-long"
               " -r -v -T -o {2} -b isolinux/isolinux.bin -c isolinux/boot.cat"
               " -no-emul-boot -boot-load-size 4 -boot-info-table"
               " {3} -graft-points isolinux={4} images={5} {6}")
        cmd = cmd.format(self.cmd, self.product, bootiso, efiargs,
                         self.conf.isodir, self.conf.imgdir, efigraft)

        err, stdout = commands.getstatusoutput(cmd)
        if err:
            self.perror(stdout)
            return None

        if os.path.isfile(self.cmd.ISOHYBRID):
            self.pinfo("creating hybrid boot iso")
            cmd = "{0.ISOHYBRID} {1}".format(self.cmd, bootiso)
            err, stdout = commands.getstatusoutput(cmd)
            if err:
                self.pwarning(stdout)

        return bootiso
