#
# instroot.py
# install root class
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
import glob

from utils.fileutils import copy


class InstallTree(object):

    def __init__(self, config, yum, output):
        self.conf = config
        self.yum = yum

        self.so, self.se = output

    def get_packages(self):
        required = ["anaconda", "anaconda-runtime", "/etc/gtk-2.0/gtkrc"]

        # kernel packages
        required.extend(["kernel", "*firmware*"])

        # add the XEN kernel package
        if self.conf.buildarch == "i386":
            required.append("kernel-PAE")

        # get additional packages from the configuration files
        packages_files = []
        packages_files.append(os.path.join(self.conf.confdir, "packages",
                "packages.all")),
        packages_files.append(os.path.join(self.conf.confdir, "packages",
                "packages.%s" % (self.conf.buildarch,)))

        packages = set()
        for file in packages_files:
            if os.path.isfile(file):
                try:
                    f = open(file, "r")
                except IOError as why:
                    self.se.error("Unable to read packages configuration:"
                            " %s" % (why,))
                else:
                    for line in f.readlines():
                        line, sep, comment = line.partition("#")
                        line = line.strip()
                        
                        if not line:
                            continue

                        if line.startswith("-"):
                            packages.discard(line[1:])
                        else:
                            packages.add(line)

                    f.close()

        required.extend(list(packages))

        # logos
        required.extend(["%s-logos" % (self.conf.product.lower(),),
                         "%s-release" % (self.conf.product.lower(),)])

        return required

    def add_packages(self, packages):
        for package in packages:
            ok = self.yum.add_package(package)
            if not ok:
                self.se.warning("No package '%s' available" (package,))

    def install_packages(self):
        # XXX why do we need this?
        os.symlink(os.path.join("/", "tmp"),
                   os.path.join(self.conf.treedir, "var", "lib", "xkb"))

        self.yum.install()

    def copy_updates(self):
        if self.conf.updates and os.path.isdir(self.conf.updates):
            copy(src_root=self.conf.updates, src_path="*",
                 dst_root=self.conf.treedir, dst_path="")

        self.conf.delAttr("updates")

    def fix_udev_links(self):
        # these links are broken by default (at least on i386)
        for filename in ("udevcontrol", "udevsettle", "udevtrigger"):
            filename = os.path.join(self.conf.treedir, "sbin", filename)
            if os.path.islink(filename):
                os.unlink(filename)
                os.symlink("udevadm", filename)

    def remove_modules_broken_links(self):
        # remove build and source links from modules directories
        build = os.path.join(self.conf.treedir, "lib", "modules", "*", "build")
        build_files = glob.glob(build)

        source = os.path.join(self.conf.treedir, "lib", "modules", "*", "source")
        source_files = glob.glob(source)

        [os.unlink(filename) for filename in build_files + source_files
                if os.path.islink(filename)]

    def get_kernelfiles(self):
        kerneldir = os.path.join(self.conf.treedir, "boot")
        
        if self.conf.buildarch == "ia64":
            kerneldir = os.path.join(kerneldir, "efi", "EFI", "redhat")

        return glob.glob(os.path.join(kerneldir, "vmlinuz-*"))

    def run(self):
        self.so.info("Getting the list of packages")
        packages = self.get_packages()

        self.so.info("Running yum")
        self.add_packages(packages)
        self.install_packages()

        self.so.info("Copying the updates")
        self.copy_updates()

        self.so.info("Fixing udev links")
        self.fix_udev_links()

        self.so.info("Removing build and source links in modules directories")
        self.remove_modules_broken_links()

        return self.get_kernelfiles()
