#
# config.py
# configuration classes for lorax
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

import os

import singleton
import output


class LoraxConfig(singleton.Singleton):

    def __init__(self):
        self.confdir = "/etc/lorax"
        self.datadir = "/usr/share/lorax"

        self.colors = True
        self.encoding = "utf-8"
        self.debug = False
        self.cleanup = False

    def __setattr__(self, attr, value):
        output.Terminal.get().debug("[%s = %s]" % (attr, value))
        singleton.Singleton.__setattr__(self, attr, value)


class LoraxPaths(singleton.Singleton):

    def __init__(self):
        self.datadir = LoraxConfig.get().datadir
        self.installtree = LoraxConfig.get().installtree

    @property
    def ANACONDA_PACKAGE(self): return "anaconda"

    @property
    def INITRD_DATADIR(self):
        return os.path.join(self.datadir, "initrd")

    @property
    def INSTALLTREE_DATADIR(self):
        return os.path.join(self.datadir, "installtree")

    @property
    def OUTPUTDIR_DATADIR(self):
        return os.path.join(self.datadir, "outputdir")

    @property
    def BOOTDIR(self):
        return os.path.join(self.installtree, "boot")

    @property
    def BOOTDIR_IA64(self):
        return os.path.join(self.BOOTDIR, "efi", "EFI", "redhat")

    @property
    def ANACONDA_RUNTIME(self):
        return os.path.join(self.installtree, "usr", "lib", "anaconda-runtime")

    @property
    def ANACONDA_BOOT(self):
        return os.path.join(self.ANACONDA_RUNTIME, "boot")

    @property
    def SYSLINUXDIR(self):
        return os.path.join(self.installtree, "usr", "share", "syslinux")

    @property
    def ISOLINUXBIN(self):
        return os.path.join(self.SYSLINUXDIR, "isolinux.bin")

    @property
    def SYSLINUXCFG(self):
        return os.path.join(self.ANACONDA_BOOT, "syslinux.cfg")

    @property
    def GRUBCONF(self):
        return os.path.join(self.ANACONDA_BOOT, "grub.conf")

    @property
    def GRUBEFI(self):
        return os.path.join(self.BOOTDIR, "efi", "EFI", "redhat", "grub.efi")

    @property
    def VESASPLASH(self):
        return os.path.join(self.ANACONDA_RUNTIME, "syslinux-vesa-splash.jpg")

    @property
    def VESAMENU(self):
        return os.path.join(self.SYSLINUXDIR, "vesamenu.c32")

    @property
    def SPLASHTOOLS(self):
        return os.path.join(self.ANACONDA_RUNTIME, "splashtools.sh")

    @property
    def SPLASHLSS(self):
        return os.path.join(self.ANACONDA_BOOT, "splash.lss")

    @property
    def SYSLINUXSPLASH(self):
        return os.path.join(self.ANACONDA_BOOT, "syslinux-splash.jpg")

    @property
    def SPLASHXPM(self):
        return os.path.join(self.BOOTDIR, "grub", "splash.xpm.gz")

    @property
    def MODULES_DIR(self):
        return os.path.join(self.installtree, "lib", "modules",
                            LoraxConfig.get().kernelver)

    @property
    def MODULES_DEP(self):
        return os.path.join(self.MODULES_DIR, "modules.dep")

    @property
    def MODINFO(self): return "/sbin/modinfo"

    @property
    def MODLIST(self):
        return os.path.join(self.ANACONDA_RUNTIME, "modlist")

    @property
    def DEPMOD(self): return "/sbin/depmod"

    @property
    def GETKEYMAPS(self):
        return os.path.join(self.ANACONDA_RUNTIME, "getkeymaps")

    @property
    def LOCALEDEF(self): return "/usr/bin/localedef"

    @property
    def GENINITRDSZ(self):
        return os.path.join(self.ANACONDA_RUNTIME, "geninitrdsz")

    @property
    def REDHAT_EXEC(self):
        return os.path.join(self.ANACONDA_BOOT, "redhat.exec")

    @property
    def GENERIC_PRM(self):
        return os.path.join(self.ANACONDA_BOOT, "generic.prm")

    @property
    def MKS390CD(self):
        return os.path.join(self.ANACONDA_RUNTIME, "mk-s390-cdboot")

    @property
    def MKSQUASHFS(self): return "/sbin/mksquashfs"

    @property
    def MKCRAMFS(self): return "/sbin/mkfs.cramfs"

    @property
    def MKISOFS(self): return "/usr/bin/mkisofs"

    @property
    def MKDOSFS(self): return "/sbin/mkdosfs"

    @property
    def ISOHYBRID(self): return "/usr/bin/isohybrid"

    @property
    def SYSTEM_MAP(self):
        return os.path.join(self.BOOTDIR,
                            "System.map-%s" % LoraxConfig.get().kernelver)

    @property
    def KEYMAPS_OVERRIDE(self):
        return os.path.join(self.ANACONDA_RUNTIME,
                            "keymaps-override-%s" % LoraxConfig.get().arch)

    @property
    def LANGTABLE(self):
        return os.path.join(self.installtree, "usr", "lib", "anaconda",
                            "lang-table")

    @property
    def LOCALEPATH(self):
        return os.path.join(self.installtree, "usr", "share", "locale")

    @property
    def MANCONFIG(self):
        return os.path.join(self.installtree, "etc", "man.config")

    @property
    def FEDORAKMODCONF(self):
        return os.path.join(self.installtree, "etc", "yum", "pluginconf.d",
                            "fedorakmod.conf")
