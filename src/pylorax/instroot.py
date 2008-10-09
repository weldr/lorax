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

    if not scrubInstRoot(destdir=destdir, libdir=libdir, arch=arch):
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
    os.makedirs(os.path.join(destdir, 'usr', 'lib', 'debug'))
    os.makedirs(os.path.join(destdir, 'usr', 'src', 'debug'))
    os.makedirs(os.path.join(destdir, 'tmp'))
    os.makedirs(os.path.join(destdir, 'var', 'log'))
    os.makedirs(os.path.join(destdir, 'var', 'lib'))
    os.symlink(os.path.join(os.path.sep, 'tmp'), os.path.join(destdir, 'var', 'lib', 'xkb'))

    # XXX: sort through yum errcodes and return False for actual bad things
    # we care about
    errcode = yummain.user_main(arglist, exit_code=False)
    return True

# Scrub the instroot tree (remove files we don't want, modify settings, etc)
def scrubInstRoot(destdir=None, libdir='lib', arch=None):
    """scrubInstRoot(destdir=None, libdir='lib', arch=None)

    Clean up the newly created instroot and make the tree more suitable to
    run the installer.

    destdir is the path to the instroot.  libdir is the subdirectory in
    /usr for libraries (either lib or lib64).  arch is the architecture
    the image is for (e.g., i386, x86_64, ppc, s390x, alpha, sparc).

    """

    if destdir is None or not os.path.isdir(destdir) or arch is None:
        return False

    print

    # drop custom configuration files in to the instroot
    dogtailconf = os.path.join(pylorax.conf['datadir'], 'dogtail-%conf.xml')
    if os.path.isfile(dogtailconf):
        os.makedirs(os.path.join(destdir, '.gconf', 'desktop', 'gnome', 'interface'))
        f = open(os.path.join(destdir, '.gconf', 'desktop', '%gconf.xml'), 'w')
        f.close()
        f = open(os.path.join(destdir, '.gconf', 'desktop', 'gnome', '%gconf.xml'), 'w')
        f.close()
        dest = os.path.join(destdir, '.gconf', 'desktop', 'gnome', 'interface', '%gconf.xml')
        print "Installing %s..." % (os.path.join(os.path.sep, '.gconf', 'desktop', 'gnome', 'interface', '%gconf.xml'),)
        shutil.copy(dogtailconf, dest)

    # create selinux config
    if os.path.isfile(os.path.join(destdir, 'etc', 'selinux', 'targeted')):
        src = os.path.join(pylorax.conf['datadir'], 'selinux-config')
        if os.path.isfile(src):
            dest = os.path.join(destdir, 'etc', 'selinux', 'config')
            print "Installing %s..." % (os.path.join(os.path.sep, 'etc', 'selinux', 'config'),)
            shutil.copy(src, dest)

    # create libuser.conf
    src = os.path.join(pylorax.conf['datadir'], 'libuser.conf')
    dest = os.path.join(destdir, 'etc', 'libuser.conf')
    if os.path.isfile(src):
        print "Installing %s..." % (os.path.join(os.path.sep, 'etc', 'libuser.conf'),)
        shutil.copy(src, dest)

    # figure out the gtk+ theme to keep
    gtkrc = os.path.join(destdir, 'etc', 'gtk-2.0', 'gtkrc')
    gtk_theme_name = None
    gtk_icon_themes = []
    gtk_engine = None

    if os.path.isfile(gtkrc):
        print "\nReading %s..." % (os.path.join(os.path.sep, 'etc', 'gtk-2.0', 'gtkrc'),)
        f = open(gtkrc, 'r')
        lines = f.readlines()
        f.close()

        for line in lines:
            line = line.strip()
            if line.startswith('gtk-theme-name'):
                gtk_theme_name = line[line.find('=') + 1:].replace('"', '').strip()
                print "    gtk-theme-name: %s" % (gtk_theme_name,)

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
                            print "    gtk-engine: %s" % (gtk_engine,)
                            break
            elif line.startswith('gtk-icon-theme-name'):
                icon_theme = line[line.find('=') + 1:].replace('"', '').strip()
                print "    gtk-icon-theme-name: %s" % (icon_theme,)
                gtk_icon_themes.append(icon_theme)

                # bring in all inherited themes
                while True:
                    icon_theme_index = os.path.join(destdir, 'usr', 'share', 'icons', icon_theme, 'index.theme')
                    if os.path.isfile(icon_theme_index):
                        inherits = False
                        f = open(icon_theme_index, 'r')
                        icon_lines = f.readlines()
                        f.close()

                        for icon_line in icon_lines:
                            icon_line = icon_line.strip()
                            if icon_line.startswith('Inherits='):
                                inherits = True
                                icon_theme = icon_line[icon_line.find('=') + 1:].replace('"', '')
                                print "    inherits gtk-icon-theme-name: %s" % (icon_theme,)
                                gtk_icon_themes.append(icon_theme)
                                break

                        if not inherits:
                            break
                    else:
                        break

    theme_path = os.path.join(destdir, 'usr', 'share', 'themes')
    if os.path.isdir(theme_path):
        for theme in os.listdir(theme_path):
            if theme != gtk_theme_name:
                theme = os.path.join(theme_path, theme)
                shutil.rmtree(theme, ignore_errors=True)

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

    # clean out unused locales
    langtable = os.path.join(destdir, 'usr', 'lib', 'anaconda', 'lang-table')
    localepath = os.path.join(destdir, 'usr', 'share', 'locale')
    if os.path.isfile(langtable):
        locales = set()
        all_locales = set()

        f = open(langtable, 'r')
        lines = f.readlines()
        f.close()

        print "Keeping locales used during installation..."
        for line in lines:
            line = line.strip()

            if line == '' or line.startswith('#'):
                continue

            fields = line.split('\t')

            if os.path.isdir(os.path.join(localepath, fields[1])):
                locales.add(fields[1])

            locale = fields[3].split('.')[0]
            if os.path.isdir(os.path.join(localepath, locale)):
                print "    %s" % (locale,)
                locales.add(locale)

        for locale in os.listdir(os.path.join(destdir, 'usr', 'share', 'locale')):
            all_locales.add(locale)

        print "Removing unused locales..."
        locales_to_remove = list(all_locales.difference(locales))
        for locale in locales_to_remove:
            rmpath = os.path.join(destdir, 'usr', 'share', 'locale', locale)
            print "    %s" % (locale,)
            shutil.rmtree(rmpath, ignore_errors=True)

    # fix up some links for man page related stuff
    for file in ['nroff', 'groff', 'iconv', 'geqn', 'gtbl', 'gpic', 'grefer']:
        src = os.path.join('mnt', 'sysimage', 'usr', 'bin', file)
        dest = os.path.join(destdir, 'usr', 'bin', file)
        os.symlink(src, dest)

    # install anaconda stub programs as instroot programs
    for subdir in ['lib', 'firmware']:
        subdir = os.path.join(destdir, subdir)
        if not os.path.isdir(subdir):
            os.makedirs(subdir)

    for subdir in ['modules', 'firmware']:
        src = os.path.join(os.path.sep, subdir)
        dst = os.path.join(destdir, 'lib', subdir)
        shutil.rmtree(dst, ignore_errors=True)
        os.symlink(src, dst)

    for prog in ['raidstart', 'raidstop', 'losetup', 'list-harddrives', 'loadkeys', 'mknod', 'sysklogd']:
        stub = "%s-stub" % (prog,)
        src = os.path.join(destdir, 'usr', 'lib', 'anaconda', stub)
        dst = os.path.join(destdir, 'usr', 'bin', prog)
        if os.path.isfile(src) and not os.path.isfile(dst):
            shutil.copy2(src, dst)

    # copy in boot loader files
    bootpath = os.path.join(destdir, 'usr', 'lib', 'anaconda-runtime', 'boot')
    os.makedirs(bootpath)
    if arch == 'i386' or arch == 'x86_64':
        for bootfile in os.listdir(os.path.join(destdir, 'boot')):
            if bootfile.startswith('memtest'):
                src = os.path.join(destdir, 'boot', bootfile)
                dst = os.path.join(bootpath, bootfile)
                shutil.copy2(src, dst)
    elif arch.startswith('sparc'):
        for bootfile in os.listdir(os.path.join(destdir, 'boot')):
            if bootfile.endswith('.b'):
                src = os.path.join(destdir, 'boot', bootfile)
                dst = os.path.join(bootpath, bootfile)
                shutil.copy2(src, dst)
    elif arch.startswith('ppc'):
        src = os.path.join(destdir, 'boot', 'efika.forth')
        dst = os.path.join(bootpath, 'efika.forth')
        shutil.copy2(src, dst)
    elif arch == 'alpha':
        src = os.path.join(destdir, 'boot', 'bootlx')
        dst = os.path.join(bootpath, 'bootlx')
        shutil.copy2(src, dst)
    elif arch == 'ia64':
        src = os.path.join(destdir, 'boot', 'efi', 'EFI', 'redhat')
        shutil.rmtree(bootpath, ignore_errors=True)
        shutil.copytree(src, bootpath)

    # move the yum repos configuration directory
    src = os.path.join(destdir, 'etc', 'yum.repos.d')
    dst = os.path.join(destdir, 'etc', 'anaconda.repos.d')
    if os.path.isdir(src):
        shutil.rmtree(dst, ignore_errors=True)
        shutil.move(src, dst)

    # remove things we do not want in the instroot
    for subdir in ['boot', 'home', 'root', 'tmp']:
        shutil.rmtree(os.path.join(destdir, subdir), ignore_errors=True)

    for subdir in ['doc', 'info']:
        shutil.rmtree(os.path.join(destdir, 'usr', 'share', subdir), ignore_errors=True)

    for libname in glob.glob(os.path.join(destdir, 'usr', libdir), 'libunicode-lite*'):
        shutil.rmtree(libname, ignore_errors=True)

    return True
