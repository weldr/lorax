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

import os
import shutil
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
    destdir = os.path.join(treedir, 'install')
    os.makedirs(destdir)

    # build a list of packages to install
    packages = set()

    packages_files = []
    packages_files.append(os.path.join(pylorax.conf['confdir'], 'packages'))
    packages_files.append(os.path.join(pylorax.conf['confdir'], arch, 'packages'))

    for pfile in packages_files:
        if os.path.isfile(pfile):
            f = open(pfile, 'r')
            for line in f.readlines():
                line = line.strip()

                if line.startswith('#') or line == '':
                    continue

                if line.startswith('-'):
                    try:
                        packages.remove(line[1:])
                    except KeyError:
                        pass
                else:
                    packages.add(line)

            f.close()

    packages = list(packages)
    packages.sort()

    # install the packages to the instroot
    if not installPackages(yumconf=yumconf, destdir=destdir, packages=packages):
        sys.stderr.write("ERROR: Could not install packages.\n")
        sys.exit(1)

    if not scrubInstRoot(destdir=destdir):
        sys.stderr.write("ERROR: Could not scrub instroot.\n")
        sys.exit(1)

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

    # build the list of arguments to pass to yum
    arglist = ['-c', yumconf]
    arglist.append("--installroot=%s" % (destdir,))
    arglist += ['install', '-y'] + packages

    # do some prep work on the destdir before calling yum
    os.makedirs(os.path.join(destdir, 'tmp'))
    os.makedirs(os.path.join(destdir, 'var', 'log'))
    os.makedirs(os.path.join(destdir, 'var', 'lib'))
    os.symlink(os.path.join(os.path.sep, 'tmp'), os.path.join(destdir, 'var', 'lib', 'xkb'))

    # XXX: sort through yum errcodes and return False for actual bad things
    # we care about
    errcode = yummain.user_main(arglist, exit_code=False)
    return True

# Scrub the instroot tree (remove files we don't want, modify settings, etc)
def scrubInstRoot(destdir=None):
    """scrubInstRoot(destdir=None)

    Clean up the newly created instroot and make the tree more suitable to
    run the installer.

    destdir is the path to the instroot and is the only required argument.

    """

    if destdir is None or not os.path.isdir(destdir):
        return False

    # drop custom configuration files in to the instroot
    dogtailconf = os.path.join(pylorax.conf['datadir'], 'dogtail-%conf.xml')
    if os.path.isfile(dogtailconf):
        os.makedirs(os.path.join(destdir, '.gconf', 'desktop', 'gnome', 'interface'))
        f = open(os.path.join(destdir, '.gconf', 'desktop', '%gconf.xml'), 'w')
        f.close()
        f = open(os.path.join(destdir, '.gconf', 'desktop', 'gnome', '%gconf.xml'), 'w')
        f.close()
        dest = os.path.join(destdir, '.gconf', 'desktop', 'gnome', 'interface', '%gconf.xml')
        shutil.copy(dogtailconf, dest)

    # create selinux config
    if os.path.isfile(os.path.join(destdir, 'etc', 'selinux', 'targeted')):
        src = os.path.join(pylorax.conf['datadir'], 'selinux-config')
        if os.path.isfile(src):
            dest = os.path.join(destdir, 'etc', 'selinux', 'config')
            shutil.copy(src, dest)

    # create libuser.conf
    src = os.path.join(pylorax.conf['datadir'], 'libuser.conf')
    dest = os.path.join(destdir, 'etc', 'libuser.conf')
    if os.path.isfile(src):
        shutil.copy(src, dest)

    # figure out the gtk+ theme to keep
    gtkrc = os.path.join(destdir, 'etc', 'gtk-2.0', 'gtkrc')
    gtk_theme_name = None
    gtk_icon_themes = []
    gtk_engine = None

    if os.path.isfile(gtkrc):
        f = open(gtkrc, 'r')
        lines = f.readlines()
        f.close()

        for line in lines:
            line = line.strip()
            if line.startswith('gtk-theme-name'):
                gtk_theme_name = line[line.find('=') + 1:].replace('"', '').strip()

                # find the engine for this theme
                gtkrc = os.path.join(destdir, 'usr', 'share', 'themes', gtk_theme_name, 'gtk-2.0', 'gtkrc')
                if os.path.isfile(gtkrc):
                    f = open(gtkrc, 'r')
                    engine_lines = f.readlines()
                    f.close()

                    for engine_line in engine_lines:
                        engine_line = engine_line.strip()

                        if engine_line.find('engine') != -1:
                            gtk_engine = engine_line[engine_line.find('"') + 1:].replace('"', '')
                            break
            if line.startswith('gtk-icon-theme-name'):
                icon_theme = line[line.find('=') + 1:].replace('"', '').strip()
                gtk_icon_themes.append(icon_theme)

                # bring in all inherited themes
                while icon_theme != '':
                    icon_theme_index = os.path.join(destdir, 'usr', 'share', 'icons', icon_theme, 'index.theme')
                    if os.path.isfile(icon_theme_index):
                        f = open(icon_theme_index, 'r')
                        icon_lines = f.readlines()
                        f.close()

                        for icon_line in icon_lines:
                            icon_line = icon_line.strip()
                            if icon_line.startswith('Inherits='):
                                icon_theme = line[line.find('=') + 1:].replace('"', '')
                                gtk_icon_themes.append(icon_theme)
                                break
                    else:
                        icon_theme = ''

    theme_path = os.path.join(destdir, 'usr', 'share', 'themes')
    if os.path.isdir(theme_path):
        for theme in os.listdir(theme_path):
            if theme != gtk_theme_name:
                theme = os.path.join(theme_path, theme)
                shutil.rmtree(theme, ignore_error=True)

    icon_path = os.path.join(destdir, 'usr', 'share', 'icons')
    if os.path.isdir(icon_path):
        for icon in os.listdir(icon_path):
            try:
                if gtk_icon_themes.index(icon):
                    continue
            except ValueError:
                icon = os.path.join(icon_path, icon)
                shutil.rmtree(icon, ignore_errors=True)

    tmp_path = os.path.join(destdir, 'usr', libdir, 'gtk-2.0')
    if os.path.isdir(tmp_path):
        for subdir in os.listdir(tmp_path):
            new_path = os.path.join(tmp_path, subdir, 'engines')
            if os.path.isdir(new_path):
                for engine in os.listdir(new_path):
                    if engine.find(gtk_engine) == -1:
                        tmp_engine = os.path.join(new_path, engine)
                        os.unlink(tmp_engine)

    return True
