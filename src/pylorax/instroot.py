#
# pylorax instroot module
# Install image and tree support data generation tool -- Python module.
#
# Copyright (C) 2008  Red Hat, Inc.
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
# Author(s): David Cantrell <dcantrell@redhat.com>
#

import sys
import pylorax

sys.path.insert(0, '/usr/share/yum-cli')
import yummain

# Create inst root from which stage 1 and stage 2 images are built.
def createInstRoot(yumconf=None, arch=None, treedir=None, updates=None):
    """createInstRoot(yumconf=None, arch=None, treedir=None, [updates=None])

    Create a instroot tree for the specified architecture.  The list of
    packages to install are specified in the /etc/lorax/packages and
    /etc/lorax/ARCH/packages files.

    yumconf is the path to the yum configuration create for this run of
    lorax.  arch is the platform name we are building for, treedir is
    the location where the instroot tree should go
    (will be treedir + '/install').  updates is an optional path to a
    directory of update RPM packages for the instroot.

    The yumconf, arch, and treedir parameters are all required.

    On success, this function returns True.  On failure, False is
    returned or the program is aborted immediately.

    """

    if yumconf is None or arch is None or treedir is None:
        return False

    # on 64-bit systems, make sure we use lib64 as the lib directory
    if arch.endswith('64') or arch == 's390x':
        libdir = 'lib64'
    else:
        libdir = 'lib'

    # the directory where the instroot will be created
    destdir = treedir + '/install'
    os.makedirs(destdir)

    # build a list of packages to install
    packages = set()

    packages_files = []
    packages_files.append(pylorax.conf['confdir'] + '/packages')
    packages_files.append(pylorax.conf['confdir'] + '/' + arch + '/packages')

    for pfile in packages_file:
        if os.path.isfile(pfile):
            f = open(pfile, 'r')
            for line in f.readlines():
                if line.startswith('#') or line == '':
                    continue

                if line.startswith('-'):
                    try:
                        packages.remove(line[1:].strip())
                    except KeyError:
                        pass
                else:
                    packages.add(line.strip())

            f.close()

    packages = list(packages).sort()

    # install the packages to the instroot
    if not installPackages(yumconf=yumconf, destdir=destdir, packages=packages):
        sys.stderr.write("ERROR: Could not install packages.\n")
        sys.exit(1)

    # XXX: more coming!

    return True

# Call yummain to install the list of packages to destdir
def installPackages(yumconf=None, destdir=None, packages=None):
    """installPackages(yumconf=yumconf, destdir=destdir, packages=packages)

    Call yummain to install the list of packages.  All parameters are
    required.  yumconf is the yum configuration file created for this
    run of lorax.  destdir is the installroot that yum should install to.
    packages is a list of package names that yum should install.

    yum will resolve dependencies, so it is not necessary to list every
    package you want in the instroot.

    This function returns True on success, False on failre.

    """

    if yumconf is None or destdir is None or packages is None or packages == []:
        return False

    arglist = ['-c', yumconf, '-y']
    arglist.append("--installroot=%s" % (destdir,))
    arglist.append('install')

    pkgs = ''
    for package in packages:
        pkgs += ' ' + package

    arglist.append(pkgs.strip())

    return yummain.user_main(arglist, exit_code=False)
