#
# efi.py
# class for creating efi images
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
import shutil
import tempfile
import commands

import config
import output
import utils


class EFI(object):

    def __init__(self):
        self.conf = config.LoraxConfig.get()
        self.paths = config.LoraxPaths.get()
        self.output = output.Terminal.get()

    def create_efiboot(self, kernel=None, initrd=None,
                       kernelpath=None, initrdpath=None):

        # create the temporary efi tree directory
        efitreedir = tempfile.mkdtemp(prefix="efitree.", dir=self.conf.tempdir)

        # copy kernel and initrd files to efi tree directory
        if kernel and initrd:
            shutil.copy2(kernel, os.path.join(efitreedir, "vmlinuz"))
            shutil.copy2(initrd, os.path.join(efitreedir, "initrd.img"))
            efikernelpath = "/EFI/BOOT/vmlinuz"
            efiinitrdpath = "/EFI/BOOT/initrd.img"
        else:
            efikernelpath = kernelpath
            efiinitrdpath = initrdpath

        # copy conf files to efi tree directory
        utils.scopy(src_root=self.conf.anaconda_boot, src_path="*.conf",
                    dst_root=efitreedir, dst_path="")

        # edit the grub.conf file
        grubconf = os.path.join(efitreedir, "grub.conf")
        utils.replace(grubconf, "@PRODUCT@", self.conf.product)
        utils.replace(grubconf, "@VERSION@", self.conf.version)
        utils.replace(grubconf, "@KERNELPATH@", efikernelpath)
        utils.replace(grubconf, "@INITRDPATH@", efiinitrdpath)
        utils.replace(grubconf, "@SPLASHPATH@", "/EFI/BOOT/splash.xpm.gz")

        # copy grub.efi
        shutil.copy2(self.paths.GRUBEFI, efitreedir)

        # the first generation mactel machines get the bootloader name wrong
        if self.conf.efiarch == "IA32":
            src = os.path.join(efitreedir, "grub.efi")
            dst = os.path.join(efitreedir, "BOOT.efi")
            shutil.copy2(src, dst)

            src = os.path.join(efitreedir, "grub.conf")
            dst = os.path.join(efitreedir, "BOOT.conf")
            shutil.copy2(src, dst)

        src = os.path.join(efitreedir, "grub.efi")
        dst = os.path.join(efitreedir, "BOOT%s.efi" % self.conf.efiarch)
        shutil.move(src, dst)

        src = os.path.join(efitreedir, "grub.conf")
        dst = os.path.join(efitreedir, "BOOT%s.conf" % self.conf.efiarch)
        shutil.move(src, dst)

        # copy splash.xpm.gz
        shutil.copy2(self.paths.SPLASHXPM, efitreedir)

        efiboot = os.path.join(self.conf.tempdir, "efiboot.img")
        if os.path.isfile(efiboot):
            os.unlink(efiboot)

        # calculate the size of the efitree directory
        sizeinbytes = 0
        for root, dirs, files in os.walk(efitreedir):
            for file in files:
                filepath = os.path.join(root, file)
                sizeinbytes += os.path.getsize(filepath)

        # mkdosfs needs the size in blocks of 1024 bytes
        size = int(round(sizeinbytes / 1024.0))

        # add 100 blocks for the filesystem overhead
        size += 100

        cmd = "%s -n ANACONDA -C %s %s > /dev/null" % (self.paths.MKDOSFS,
                                                       efiboot, size)
        err, output = commands.getstatusoutput(cmd)
        if err:
            self.output.error(output)
            return None

        # mount the efiboot image
        efibootdir = tempfile.mkdtemp(prefix="efiboot.", dir=self.conf.tempdir)

        cmd = "mount -o loop,shortname=winnt,umask=0777 -t vfat %s %s" % \
              (efiboot, efibootdir)
        err, output = commands.getstatusoutput(cmd)
        if err:
            self.output.error(output)
            return None

        # copy the files to the efiboot image
        dstdir = os.path.join(efibootdir, "EFI", "BOOT")
        utils.makedirs(dstdir)

        utils.scopy(src_root=efitreedir, src_path="*",
                    dst_root=dstdir, dst_path="")

        # unmount the efiboot image
        cmd = "umount %s" % efibootdir
        err, output = commands.getstatusoutput(cmd)
        if err:
            self.output.warning(output)
            pass

        # copy the conf files to the output directory
        if not kernel and not initrd:
            utils.scopy(src_root=efitreedir, src_path="*.conf",
                        dst_root=self.conf.efibootdir, dst_path="")

        return efiboot

    def create_efidisk(self, efiboot):
        efidisk = os.path.join(self.conf.tempdir, "efidisk.img")
        if os.path.isfile(efidisk):
            os.unlink(efidisk)

        partsize = os.path.getsize(efiboot)
        disksize = 17408 + partsize + 17408
        disksize = disksize + (disksize % 512)

        with open(efidisk, "wb") as f:
            f.truncate(disksize)

        cmd = "losetup -v -f %s | awk '{print $4}'" % efidisk
        err, loop = commands.getstatusoutput(cmd)
        if err:
            self.output.error(loop)
            os.unlink(efidisk)
            return None

        cmd = 'dmsetup create efiboot --table "0 %s linear %s 0"' % \
              (disksize / 512, loop)
        err, output = commands.getstatusoutput(cmd)
        if err:
            self.output.error(output)
            self.remove_loop_dev(loop)
            os.unlink(efidisk)
            return None

        cmd = "parted --script /dev/mapper/efiboot " \
              "mklabel gpt unit b mkpart '\"EFI System Partition\"' " \
              "fat32 17408 %s set 1 boot on" % (partsize + 17408)
        err, output = commands.getstatusoutput(cmd)
        if err:
            self.output.error(output)
            self.remove_dm_dev("efiboot")
            self.remove_loop_dev(loop)
            os.unlink(efidisk)
            return None

        with open(efiboot, "rb") as f_from:
            with open("/dev/mapper/efibootp1", "wb") as f_to:
                efidata = f_from.read(1024)
                while efidata:
                    f_to.write(efidata)
                    efidata = f_from.read(1024)

        self.remove_dm_dev("efibootp1")
        self.remove_dm_dev("efiboot")
        self.remove_loop_dev(loop)

        return efidisk

    def remove_loop_dev(self, dev):
        cmd = "losetup -d %s" % dev
        err, output = commands.getstatusoutput(cmd)
        if err:
            self.output.warning(output)

    def remove_dm_dev(self, dev):
        cmd = "dmsetup remove /dev/mapper/%s" % dev
        err, output = commands.getstatusoutput(cmd)
        if err:
            self.output.warning(output)

    def create(self, kernel=None, initrd=None,
               kernelpath=None, initrdpath=None):

        # create the efiboot image
        efiboot = self.create_efiboot(kernel, initrd)
        if efiboot is None:
            self.output.critical("unable to create the efiboot image")
            sys.exit(1)

        # create the efidisk image
        efidisk = self.create_efidisk(efiboot)
        if efidisk is None:
            self.output.critical("unable to create the efidisk image")
            sys.exit(1)

        # create the efiboot image again
        efiboot = self.create_efiboot(kernelpath=kernelpath,
                                      initrdpath=initrdpath)
        if efiboot is None:
            self.output.critical("unable to create the efiboot image")
            sys.exit(1)

        return efiboot, efidisk
