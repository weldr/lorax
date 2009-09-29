#
# images.py
# lorax images manipulation
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
import glob
import shutil
import commands
import re

import actions
import actions.base

from template import Template

from utils.fileutils import copy, remove, touch, edit, replace
from utils.ldd import LDD


class InitRD(object):

    def __init__(self, config, yum, output):
        self.conf = config
        self.yum = yum

        self.so, self.se = output

    def read_template(self):
        # get supported actions
        supported_actions = actions.getActions(verbose=self.conf.debug)

        # variables supported in templates
        vars = { "instroot": self.conf.treedir,
                 "initrd": self.conf.initrddir,
                 "libdir": self.conf.libdir,
                 "buildarch": self.conf.buildarch,
                 "basearch": self.conf.basearch,
                 "confdir" : self.conf.confdir,
                 "datadir": self.conf.datadir }

        # parse the template file
        initrd_template = os.path.join(self.conf.confdir, "initrd",
                "initrd.%s" % self.conf.buildarch)

        self.template = Template()
        self.template.preparse(initrd_template)
        self.template.parse(supported_actions, vars)

    def install_required_packages(self):
        packages = set()
        for action in filter(lambda action: action.install, self.template.actions):
            m = re.match(r"%s(.*)" % (self.conf.treedir,), action.install)
            if m:
                packages.add(m.group(1))

        for package in packages:
            ok = self.yum.add_package(package)
            if not ok:
                self.se.error("No package '%s' found" % (package,))

        self.yum.install()

    def get_file_dependencies(self):
        libroots = []
        libroots.append(os.path.join(self.conf.treedir, self.conf.libdir))
        libroots.append(os.path.join(self.conf.treedir, "usr", self.conf.libdir))
        
        # on 64 bit systems, add also normal lib directories
        if self.conf.libdir.endswith("64"):
            libdir = self.conf.libdir[:-2]
            libroots.append(os.path.join(self.conf.treedir, libdir))
            libroots.append(os.path.join(self.conf.treedir, "usr", libdir))

        ldd = LDD(libroots)
        
        for action in self.template.actions:
            if action.getDeps:
                [ldd.getDeps(fname) for fname in glob.glob(action.getDeps)]

        if ldd.errors:
            # XXX ldd didn't get all the dependencies, what now?
            for filename, error in ldd.errors:
                self.se.error(filename)
                self.se.error(error)

        # additional actions that need to be processed
        self._actions = []

        # add dependencies to actions, so they are copied too
        for dep in ldd.deps:
            kwargs = {}
            kwargs["src_root"] = self.conf.treedir
            kwargs["src_path"] = dep.replace(self.conf.treedir + "/", "", 1)
            kwargs["dst_root"] = self.conf.initrddir
            kwargs["dst_path"] = os.path.dirname(kwargs["src_path"])

            if kwargs["dst_path"].startswith("/"):
                kwargs["dst_path"] = kwargs["dst_path"][1:]

            new_action = actions.base.Copy(**kwargs)
            self._actions.append(new_action)

    def process_actions(self):
        for action in self.template.actions:
            action.execute()

        # process dependencies
        for action in self._actions:
            action.execute()

    def create_modinfo(self, moddir, target):
        # XXX why do we need this thing?
        mods = {}
        for root, dirs, files in os.walk(moddir):
            for file in files:
                mods[file] = os.path.join(root, file)

        modules = { "scsi_hostadapter" : ["block"],
                    "eth" : ["networking"] }
        blacklist = ("floppy", "scsi_mod", "libiscsi")

        list = {}
        for modtype in modules:
            list[modtype] = {}
            for file in modules[modtype]:
                try:
                    filename = os.path.join(moddir, "modules.%s" % file)
                    f = open(filename, "r")
                except IOError as why:
                    self.se.error("Unable to open file '%s'" % (filename,))
                    continue
                else:
                    lines = f.readlines()
                    f.close()

                for line in lines:
                    line = line.strip()
                    if line in mods:
                        modname, ext = os.path.splitext(line)
                        if modname in blacklist:
                            continue

                        cmd = "modinfo -F description %s" % (mods[line],)
                        outtext = commands.getoutput(cmd)

                        desc = outtext.split("\n")[0]
                        desc = desc.strip()
                        desc = desc[:65]

                        if not desc:
                            desc = "%s driver" % modname
                            modinfo = '%s\n\t%s\n\t"%s"\n' % (modname, modtype, desc)
                            list[modtype][modname] = modinfo

        f = open(target, "a")
        f.write("Version 0\n")
        for type in list:
            modlist = list[type].keys()
            modlist.sort()
            for m in modlist:
                f.write("%s\n" % (list[type][m],))
        f.close()

    def get_kernel_modules(self):
        kernelver = self.conf.kernelver

        modfiles = []
        modfiles.append(os.path.join(self.conf.confdir, "modules",
                "modules.all"))
        modfiles.append(os.path.join(self.conf.confdir, "modules",
                "modules.%s" % (self.conf.buildarch,)))
       
        src_moddir = os.path.join(self.conf.treedir, "lib", "modules", kernelver)
        dst_moddir = os.path.join(self.conf.initrddir, "lib", "modules", kernelver)

        # get the modules from configuration files
        modules = set()
        for file in modfiles:
            if os.path.isfile(file):
                f = open(file, "r")
                lines = f.readlines()
                f.close()

                for line in lines:
                    line, sep, comment = line.partition("#")
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    if line.startswith("-"):
                        modules.discard(line[1:])
                    elif line.startswith("="):
                        # expand modules
                        group = line[1:]
                        
                        if group in ("scsi", "ata"):
                            path = os.path.join(src_moddir, "modules.block")
                        elif group == "net":
                            path = os.path.join(src_moddir, "modules.networking")
                        else:
                            path = os.path.join(src_moddir, "modules.%s" % (group,))

                        if os.path.isfile(path):
                            f = open(path, "r")
                            for module in f.readlines():
                                module = module.strip()
                                module = module.replace(".ko", "")
                                modules.add(module)
                            f.close()
                    else:
                        modules.add(line)

        # resolve modules dependencies
        depfile = os.path.join(src_moddir, "modules.dep")
        f = open(depfile, "r")
        lines = f.readlines()
        f.close()

        changed = True
        while changed:
            for line in lines:
                changed = False
                line = line.strip()

                m = re.match(r"^.*/(?P<name>.*)\.ko:(?P<deps>.*)$", line)
                modname = m.group("name")
                
                if modname in modules:
                    for dep in m.group("deps").split():
                        m = re.match(r"^.*/(?P<name>.*)\.ko$", dep)
                        depname = m.group("name")

                        if depname not in modules:
                            changed = True
                            modules.add(depname)

        # copy the modules directory
        copy(src_root=self.conf.treedir,
                src_path=os.path.join("lib", "modules", kernelver),
                dst_root=self.conf.initrddir,
                dst_path=os.path.join("lib", "modules"))

        # remove not needed modules
        for root, dirs, files in os.walk(dst_moddir):
            for file in files:
                full_path = os.path.join(root, file)
                name, ext = os.path.splitext(file)

                if ext == ".ko":
                    if name not in modules:
                        remove(full_path)
                    else:
                        # copy the required firmware
                        cmd = "modinfo -F firmware %s" % (full_path,)
                        err, output = commands.getstatusoutput(cmd)

                        for fw in output.split():
                            dst = os.path.join(self.conf.initrddir,
                                    "lib", "firmware", fw)
                            
                            dir = os.path.dirname(dst)
                            if not os.path.exists(dir):
                                os.makedirs(dir)

                            copy(src_root = self.conf.treedir,
                                    src_path = os.path.join("lib", "firmware", fw),
                                    dst_root = self.conf.initrddir,
                                    dst_path = os.path.join("lib", "firmware", fw))

        # copy additional firmware
        srcdir = os.path.join(self.conf.treedir, "lib", "firmware")
        dstdir = os.path.join(self.conf.initrddir, "lib", "firmware")

        fw = ( ("ipw2100", "ipw2100*"),
               ("ipw2200", "ipw2200*"),
               ("iwl3945", "iwlwifi-3945*"),
               ("iwl4965", "iwlwifi-4965*"),
               ("atmel", "atmel_*.bin"),
               ("zd1211rw", "zd1211"),
               ("qla2xxx", "ql*") )

        for module, file in fw:
            if module in modules:
                copy(src_root=self.conf.treedir,
                        src_path=os.path.join("lib", "firmware", file),
                        dst_root=self.conf.initrddir,
                        dst_path=os.path.join("lib", "firmware"))

        # compress modules
        cmd = "find -H %s -type f -name *.ko -exec gzip -9 {} \\;" % (dst_moddir,)
        err, output = commands.getstatusoutput(cmd)
        if err:
            self.se.debug(output)
        
        # create modinfo
        modinfo = os.path.join(self.conf.tempdir, "modinfo")
        self.create_modinfo(src_moddir, modinfo)

        modlist = os.path.join(self.conf.treedir,
                "usr", "lib", "anaconda-runtime", "modlist")

        target = os.path.join(self.conf.initrddir, "lib", "modules", "module-info")
        cmd = "%s --modinfo-file %s --ignore-missing --modinfo %s > %s" % \
              (modlist, modinfo, " ".join(list(modules)), target)
        err, output = commands.getstatusoutput(cmd)
        if err:
            self.se.debug(output)

        # run depmod
        systemmap = os.path.join(self.conf.treedir, "boot", "System.map-%s" \
                % (kernelver,))
        cmd = "/sbin/depmod -a -F %s -b %s %s" % (systemmap,
                self.conf.initrddir, kernelver)
        err, output = commands.getstatusoutput(cmd)
        if err:
            self.se.debug(output)

        # remove leftovers
        remove(os.path.join(dst_moddir, "modules.*map"))

    def trim_pci_ids(self):
        kernelver = self.conf.kernelver
        # XXX is this needed? does it save so much space?
        vendors = set()
        devices = set()

        modulesalias = os.path.join(self.conf.treedir,
                "lib", "modules", kernelver, "modules.alias")
        f = open(modulesalias)
        pcitable = f.readlines()
        f.close()
       
        for line in pcitable:
            if not line.startswith("alias pci:"):
                continue

            vend = "0x%s" % (line[15:19],)
            vend = vend.upper()
            dev = "0x%s" % (line[24:28],)
            dev = dev.upper()

            vendors.add(vend)
            devices.add((vend, dev))

        videoaliases = os.path.join(self.conf.treedir,
                "usr", "share", "hwdata", "videoaliases", "*")
        for file in glob.iglob(videoaliases):
            f = open(file)
            pcitable = f.readlines()
            f.close()

            for line in pcitable:
                if not line.startswith("alias pcivideo:"):
                    continue

                vend = "0x%s" % (line[20:24],)
                vend = vend.upper()
                dev = "0x%s" % (line[29:33],)
                dev = dev.upper()

                vendors.add(vend)
                devices.add((vend, dev))

        # create the pci.ids file
        src = os.path.join(self.conf.treedir, "usr", "share", "hwdata", "pci.ids")
        dst = os.path.join(self.conf.initrddir, "usr", "share", "hwdata", "pci.ids")

        input = open(src, "r")
        pcitable = input.readlines()
        input.close()

        output = open(dst, "w")

        current_vend = 0
        for line in pcitable:
            # skip lines that start with 2 tabs or #
            if line.startswith("\t\t") or line.startswith("#"):
                continue

            # skip empty lines
            if line == "\n":
                continue

            # end of file
            if line == "ffff Illegal Vendor ID":
                break

            if not line.startswith("\t"):
                current_vend = "0x%s" % (line.split()[0],)
                current_vend = current_vend.upper()
                if current_vend in vendors:
                    output.write(line)
                continue

            dev = "0x%s" % (line.split()[0],)
            dev = dev.upper()
            if (current_vend, dev) in devices:
                output.write(line)

        output.close()

    def get_keymaps(self):
        anadir = os.path.join(self.conf.treedir, "usr", "lib", "anaconda-runtime")
        override = os.path.join(anadir,
                "keymaps-override-%s" % (self.conf.buildarch,))

        if os.path.isfile(override):
            self.so.debug("Found keymap override, using it")
            shutil.copy2(override,
                    os.path.join(self.conf.initrddir, "etc", "keymaps.gz"))
        else:
            cmd = "%s %s %s %s" % (os.path.join(anadir, "getkeymaps"),
                    self.conf.buildarch,
                    os.path.join(self.conf.initrddir, "etc", "keymaps.gz"),
                    self.conf.treedir)
            
            err, output = commands.getstatusoutput(cmd)
            if err:
                return False

        return True

    def create_locales(self):
        os.makedirs(os.path.join(self.conf.initrddir, "usr", "lib", "locale"))
        err, output = commands.getstatusoutput("localedef -c -i en_US -f UTF-8"
                " --prefix %s en_US" % (self.conf.initrddir,))

    def create(self, target):
        # copy the .buildstamp file
        shutil.copy2(self.conf.buildstamp, self.conf.initrddir)

        cwd = os.getcwd()
        os.chdir(self.conf.initrddir)
        
        cmd = "find . | cpio --quiet -c -o | gzip -9 > %s" % (target,)
        output = commands.getoutput(cmd)

        os.chdir(cwd)

    def run(self):
        # create the temporary directory for initrd
        initrddir = os.path.join(self.conf.tempdir, "initrddir",
                self.conf.kernelver)
        self.so.info("Creating the temporary initrd directory")
        os.makedirs(initrddir)
        self.conf.addAttr("initrddir")
        self.conf.set(initrddir=initrddir)

        self.so.info("Reading the initrd template file")
        self.read_template()

        self.so.info("Installing additional packages")
        self.install_required_packages()

        self.so.info("Getting required dependencies")
        self.get_file_dependencies()

        self.so.info("Copying required files to initrd directory")
        self.process_actions()

        self.so.info("Getting required kernel modules")
        self.get_kernel_modules()

        self.so.info("Getting the pci.ids file")
        self.trim_pci_ids()

        ok = self.get_keymaps()
        if not ok:
            self.se.error("Unable to create the keymaps")
            sys.exit(1)

        self.so.info("Creating locales")
        self.create_locales()

        initrd_filename = "initrd.img"
        kernel_filename = "vmlinuz"

        if self.conf.kernelfile.endswith("PAE"):
            initrd_filename = "initrd-PAE.img"
            kernel_filename = "vmlinuz-PAE"

            text = "[images-xen]\n"
            text += "kernel = images/pxeboot/vmlinuz-PAE\n"
            text += "initrd = images/pxeboot/initrd-PAE.img\n"
            edit(os.path.join(self.conf.outdir, ".treeinfo"),
                    append=True, text=text)

        self.so.info("Compressing the image file '%s'" % (initrd_filename,))
        self.create(os.path.join(self.conf.pxebootdir, initrd_filename))

        self.so.info("Copying the kernel file")
        shutil.copy2(self.conf.kernelfile,
                os.path.join(self.conf.pxebootdir, kernel_filename))

        if not self.conf.kernelfile.endswith("PAE"):
            # copy the kernel and initrd to the isolinux directory
            shutil.copy2(self.conf.kernelfile,
                    os.path.join(self.conf.isolinuxdir, kernel_filename))
            shutil.copy2(os.path.join(self.conf.pxebootdir, initrd_filename),
                    os.path.join(self.conf.isolinuxdir, initrd_filename))

            # create the efi images
            efi = EFI(self.conf, (self.so, self.se))
            efi.run(kernelfile=self.conf.kernelfile,
                    initrd=os.path.join(self.conf.pxebootdir, initrd_filename),
                    kernelpath="/images/pxeboot/vmlinuz",
                    initrdpath="/images/pxeboot/initrd.img")


class EFI(object):

    def __init__(self, config, output):
        self.conf = config
        self.so, self.se = output

        # create the temporary efi directory
        tempdir = os.path.join(self.conf.tempdir, "efi")
        if os.path.exists(tempdir):
            remove(tempdir)
        os.makedirs(tempdir)
        self.tempdir = tempdir

    def create(self, kernelfile=None, initrd=None, kernelpath=None, initrdpath=None):
        # create the temporary efi tree directory
        efitreedir = os.path.join(self.tempdir, "tree")
        if os.path.exists(efitreedir):
            remove(efitreedir)
        os.makedirs(efitreedir)

        # copy kernel and initrd files to efi tree directory
        if kernelfile and initrd:
            shutil.copy2(kernelfile, os.path.join(efitreedir, "vmlinuz"))
            shutil.copy2(initrd, os.path.join(efitreedir, "initrd.img"))
            efikernelpath = os.path.join("/", "EFI", "BOOT", "vmlinuz")
            efiinitrdpath = os.path.join("/", "EFI", "BOOT", "initrd.img")
        else:
            efikernelpath = kernelpath
            efiinitrdpath = initrdpath

        # copy conf files to efi tree directory
        copy(src_root=self.conf.bootdiskdir, src_path="*.conf",
                dst_root=efitreedir, dst_path="")

        # edit the grub.conf file
        grubconf = os.path.join(efitreedir, "grub.conf")
        replace(grubconf, "@PRODUCT@", self.conf.product)
        replace(grubconf, "@VERSION@", self.conf.version)
        replace(grubconf, "@KERNELPATH@", efikernelpath)
        replace(grubconf, "@INITRDPATH@", efiinitrdpath)
        replace(grubconf, "@SPLASHPATH@", "/EFI/BOOT/splash.xpm.gz")

        # copy grub.efi
        src = os.path.join(self.conf.treedir,
                "boot", "efi", "EFI", "redhat", "grub.efi")
        shutil.copy2(src, efitreedir)

        # the first generation mactel machines get the bootloader name wrong
        if self.conf.efiarch == "ia32":
            src = os.path.join(efitreedir, "grub.efi")
            dst = os.path.join(efitreedir, "BOOT.efi")
            shutil.copy2(src, dst)
            src = os.path.join(efitreedir, "grub.conf")
            dst = os.path.join(efitreedir, "BOOT.conf")
            shutil.copy2(src, dst)

        efiarch = self.conf.efiarch
        if efiarch == "x64":
            efiarch = efiarch.upper()
        elif efiarch == "ia32":
            efiarch = efiarch.upper()
        
        src = os.path.join(efitreedir, "grub.efi")
        dst = os.path.join(efitreedir, "BOOT%s.efi" % (efiarch,))
        shutil.move(src, dst)
        src = os.path.join(efitreedir, "grub.conf")
        dst = os.path.join(efitreedir, "BOOT%s.conf" % (efiarch,))
        shutil.move(src, dst)

        # copy splash
        src = os.path.join(self.conf.treedir, "boot", "grub", "splash.xpm.gz")
        shutil.copy2(src, efitreedir)

        # calculate the size of the efi image
        cmd = "du -kcs %s | tail -n1 | awk '{print $1}'" % (efitreedir,)
        self.so.debug(cmd)
        err, out = commands.getstatusoutput(cmd)
        if err:
            self.se.info(out)
            return False

        size = int(out) + 100

        efiimage = os.path.join(self.tempdir, "efiboot.img")
        if os.path.exists(efiimage):
            remove(efiimage)

        cmd = "mkdosfs -n ANACONDA -C %s %s > /dev/null" % (efiimage, size)
        self.so.debug(cmd)
        err, out = commands.getstatusoutput(cmd)
        if err:
            self.se.info(out)
            return False

        # mount the efi image
        efiimagedir = os.path.join(self.tempdir, "efiboot.img.d")
        if os.path.exists(efiimagedir):
            remove(efiimagedir)
        os.makedirs(efiimagedir)

        cmd = "mount -o loop,shortname=winnt,umask=0777 -t vfat %s %s" % \
                (efiimage, efiimagedir)
        self.so.debug(cmd)
        err, out = commands.getstatusoutput(cmd)
        if err:
            self.se.info(out)
            return False

        # copy the files to the efi image
        copy(src_root=efitreedir, src_path="*",
                dst_root=efiimagedir, dst_path="")

        # unmount the efi image
        cmd = "umount %s" % (efiimagedir,)
        self.so.debug(cmd)
        err, out = commands.getstatusoutput(cmd)
        if err:
            self.se.info(out)

        # copy the conf files to the output directory
        if not kernelfile and not initrd:
            copy(src_root=efitreedir, src_path="*.conf",
                    dst_root=self.conf.efibootdir, dst_path="")
            
        return efiimage

    def create_bootdisk(self, efiimage):
        cmd = "ls -l %s | awk '{print $5}'" % (efiimage,)
        self.so.debug(cmd)
        err, out = commands.getstatusoutput(cmd)
        if err:
            self.se.info(out)
            return False

        partsize = int(out)
        disksize = 17408 + partsize + 17408
        disksize = disksize + (disksize % 512)

        efidiskimg = os.path.join(self.tempdir, "efidisk.img")
        if os.path.exists(efidiskimg):
            remove(efidiskimg)
        touch(efidiskimg)

        cmd = "dd if=/dev/zero of=%s count=1 bs=%s" % (efidiskimg, disksize)
        self.so.debug(cmd)
        err, out = commands.getstatusoutput(cmd)
        if err:
            self.se.info(out)
            return False

        cmd = "losetup -v -f %s | awk '{print $4}'" % (efidiskimg,)
        self.so.debug(cmd)
        err, loop = commands.getstatusoutput(cmd)
        if err:
            self.se.info(loop)
            return False

        cmd = "dmsetup create efiboot --table \"0 %s linear %s 0\"" \
                % (disksize / 512, loop)
        self.so.debug(cmd)
        err, out = commands.getstatusoutput(cmd)
        if err:
            self.se.info(out)
            return False

        cmd = "parted --script /dev/mapper/efiboot" \
                " mklabel gpt unit b mkpart '\"EFI System Partition\"'" \
                " fat32 17408 %s set 1 boot on" % (partsize + 17408,)
        self.so.debug(cmd)
        err, out = commands.getstatusoutput(cmd)
        if err:
            self.se.info(out)
            return False

        cmd = "dd if=%s of=/dev/mapper/efibootp1" % (efiimage,)
        self.so.debug(cmd)
        err, out = commands.getstatusoutput(cmd)
        if err:
            self.se.info(out)
            return False

        cmd = "dmsetup remove /dev/mapper/efibootp1"
        self.so.debug(cmd)
        err, out = commands.getstatusoutput(cmd)
        if err:
            self.se.info(out)
            return False

        cmd = "dmsetup remove /dev/mapper/efiboot"
        self.so.debug(cmd)
        err, out = commands.getstatusoutput(cmd)
        if err:
            self.se.info(out)
            return False

        cmd = "losetup -d %s" % loop
        self.so.debug(cmd)
        err, out = commands.getstatusoutput(cmd)
        if err:
            self.se.info(out)
            return False

        return efidiskimg

    def run(self, kernelfile=None, initrd=None, kernelpath=None, initrdpath=None):
        self.so.info("Creating the EFI image file")
        efiimage = self.create(kernelfile, initrd)

        if not efiimage:
            sys.exit(1)

        self.so.info("Creating the boot disk")
        bootdisk = self.create_bootdisk(efiimage)

        if not bootdisk:
            sys.exit(1)

        # copy the boot disk file to the output directory
        dst = os.path.join(self.conf.imagesdir, "efidisk.img")
        shutil.copy2(bootdisk, dst)

        self.so.info("Creating the second EFI image file")
        efiimage = self.create(kernelpath=kernelpath, initrdpath=initrdpath)

        # copy the efi image to the output directory
        dst = os.path.join(self.conf.imagesdir, "efiboot.img")
        shutil.copy2(efiimage, dst)
