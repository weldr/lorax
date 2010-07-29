#
# insttree.py
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
import re
import commands

from base import BaseLoraxClass
from sysutils import *


class Kernel(object):
    pass


class InstallTree(BaseLoraxClass):

    def __init__(self, yum, rootdir, updatesdir=None):
        BaseLoraxClass.__init__(self)
        self.yum = yum
        self.rootdir = rootdir
        self.updatesdir = updatesdir

        self.kpattern = re.compile(r"vmlinuz-(?P<ver>[-._0-9a-z]+?"
                                   r"(?P<pae>(PAE)?)(?P<xen>(xen)?))$")

    def install_packages(self, packages):
        for name in packages:
            if not self.yum.install(name):
                self.pwarning("no package <b>{0}</b> found".format(name))

        self.yum.process_transaction()

    def run_ldconfig(self):
        ldsoconf = os.path.join(self.rootdir, self.const.LDSOCONF)

        # XXX
        with open(ldsoconf, "w") as f:
            f.write("/usr/kerberos/{0}\n".format(self.conf.libdir))

        procdir = os.path.join(self.rootdir, "proc")
        mkdir_(procdir)

        # mount proc
        cmd = "{0.MOUNT} -t proc proc {1}".format(self.cmd, procdir)
        err, stdout = commands.getstatusoutput(cmd)
        if err:
            self.perror(stdout)
            return

        cwd = os.getcwd()

        # chroot to the install tree directory, and run ldconfig
        pid = os.fork()
        if pid:
            # parent
            os.waitpid(pid, 0)
        else:
            # child
            os.chroot(self.rootdir)
            os.chdir("/")

            err, stdout = commands.getstatusoutput(self.cmd.LDCONFIG)
            if err:
                self.perror(stdout)

            os._exit(0)

        os.chdir(cwd)

        # umount proc
        cmd = "{0.UMOUNT} {1}".format(self.cmd, procdir)
        err, stdout = commands.getstatusoutput(cmd)
        if err:
            self.pwarning(stdout)

        # XXX
        os.unlink(ldsoconf)

    def copy_updates(self):
        if self.updatesdir and os.path.isdir(self.updatesdir):
            scopy_(src_root=self.updatesdir, src_path="*",
                   dst_root=self.rootdir, dst_path="")

    @property
    def kernels(self):
        if self.conf.buildarch == "ia64":
            kerneldir = self.const.BOOTDIR_IA64
        else:
            kerneldir = self.const.BOOTDIR

        self.kerneldir = os.path.join(self.rootdir, kerneldir)
        for filename in os.listdir(self.kerneldir):
            m = self.kpattern.match(filename)
            if m:
                kernel = Kernel()
                kernel.filename = filename
                kernel.path = os.path.join(self.kerneldir, filename)
                kernel.version = m.group("ver")
                kernel.is_pae = bool(m.group("pae"))
                kernel.is_xen = bool(m.group("xen"))

                yield kernel

    @property
    def do_efi(self):
        return os.path.isdir(os.path.join(self.rootdir, self.const.EFIDIR))

    # XXX this should be just a temporary fix,
    # should get fixed in the respective packages
    def fix_problems(self):
        # remove broken build and source links from the modules directory
        for kernel in self.kernels:
            moddir = os.path.join(self.rootdir, self.const.MODDIR,
                                  kernel.version)

            build = os.path.join(moddir, "build")
            if os.path.islink(build) and not os.path.exists(build):
                os.unlink(build)

            source = os.path.join(moddir, "source")
            if os.path.islink(source) and not os.path.exists(source):
                os.unlink(source)

        # fix udev broken links
        for fname in ("udevcontrol", "udevsettle", "udevtrigger"):
            fname = os.path.join(self.rootdir, "sbin", fname)
            if os.path.islink(fname):
                os.unlink(fname)
                os.symlink("udevadm", fname)
