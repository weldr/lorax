#
# pylorax instroot module
# Install image and tree support data generation tool -- Python module.
#
# Copyright (C) 2008, 2009  Red Hat, Inc.
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
#            Martin Gracik <mgracik@redhat.com>
#

import sys
import os
import stat
import shutil
import glob
import fnmatch
import re
import fileinput
import subprocess

import pwd
import grp

from fileutils import cp, mv

sys.path.insert(0, '/usr/share/yum-cli')
import yummain

class InstRoot:
    """InstRoot(conf, yumconf, arch, treedir, [updates=None])

    Create a instroot tree for the specified architecture.  The list of
    packages to install are specified in the /etc/lorax/packages and
    /etc/lorax/ARCH/packages files.

    yumconf is the path to the yum configuration file created for this run of
    lorax.  arch is the platform name we are building for, treedir is
    the location where the instroot tree should go
    (will be treedir + '/install').  updates is an optional path to a
    directory of updated RPM packages for the instroot.

    The conf, yumconf, arch, and treedir parameters are all required.

    On success, this function returns True.  On failure, False is
    returned or the program is aborted immediately.
    """

    def __init__(self, conf, yumconf, arch, treedir, updates=None):
        self.conf = conf
        self.yumconf = yumconf
        self.arch = arch
        self.treedir = treedir
        self.updates = updates

        self.libdir = 'lib'
        # on 64-bit systems, make sure we use lib64 as the lib directory
        if self.arch.endswith('64') or self.arch == 's390x':
            self.libdir = 'lib64'

        # the directory where the instroot will be created
        self.destdir = os.path.join(self.treedir, 'install')

    def run(self):
        """run()

        Generate the instroot tree and prepare it for building images.
        """

        if not os.path.isdir(self.destdir):
            os.makedirs(self.destdir)

        # build a list of packages to install
        self.packages = self.__getPackageList()

        # install the packages to the instroot
        self.__installPackages()

        # scrub instroot
        self.__scrubInstRoot()

    def __getPackageList(self):
        packages = set()

        packages_files = []
        packages_files.append(os.path.join(self.conf['confdir'], 'packages'))
        packages_files.append(os.path.join(self.conf['confdir'], self.arch, 'packages'))

        for pfile in packages_files:
            if os.path.isfile(pfile):
                f = open(pfile, 'r')
                for line in f.readlines():
                    line = line.strip()

                    if not line or line.startswith('#'):
                        continue

                    if line.startswith('-'):
                        packages.discard(line[1:])
                    else:
                        packages.add(line)

                f.close()

        packages = list(packages)
        packages.sort()

        return packages

    def __installPackages(self):
        # build the list of arguments to pass to yum
        arglist = ['-c', self.yumconf]
        arglist.append("--installroot=%s" % (self.destdir,))
        arglist.extend(['install', '-y'])
        arglist.extend(self.packages)

        # do some prep work on the destdir before calling yum
        os.makedirs(os.path.join(self.destdir, 'boot'))
        os.makedirs(os.path.join(self.destdir, 'usr', 'sbin'))
        os.makedirs(os.path.join(self.destdir, 'usr', 'lib', 'debug'))
        os.makedirs(os.path.join(self.destdir, 'usr', 'src', 'debug'))
        os.makedirs(os.path.join(self.destdir, 'tmp'))
        os.makedirs(os.path.join(self.destdir, 'var', 'log'))
        os.makedirs(os.path.join(self.destdir, 'var', 'lib'))
        os.makedirs(os.path.join(self.destdir, 'var', 'lib', 'yum'))
        os.symlink(os.path.join(os.path.sep, 'tmp'), os.path.join(self.destdir, 'var', 'lib', 'xkb'))

        # XXX sort through yum errcodes and return False for actual bad things we care about
        errcode = yummain.user_main(arglist, exit_code=False)

        # copy updates to destdir
        if self.updates and os.path.isdir(self.updates):
            cp(os.path.join(self.updates, '*'), self.destdir)

    def __scrubInstRoot(self):
        self.__createConfigFiles()
        self.__removeGtkThemes()
        self.__removeLocales()
        self.__fixManPages()
        self.__installStubs()
        self.__copyBootloaders()
        self.__moveYumRepos()
        self.__configureKmod()
        self.__moveAnacondaFiles()
        self.__setShellLinks()
        self.__moveBins()
        self.__removeUnwanted()
        self.__changeDestDirPermissions()
        self.__createLDConfig()
        self.__setBusyboxLinks()
        self.__strip()
        self.__fixBrokenLinks()

    def __createConfigFiles(self):
        # create %gconf.xml
        dogtailconf = os.path.join(self.conf['datadir'], 'dogtail-%gconf.xml')
        if os.path.isfile(dogtailconf):
            os.makedirs(os.path.join(self.destdir, '.gconf', 'desktop', 'gnome', 'interface'))
            f = open(os.path.join(self.destdir, '.gconf', 'desktop', '%gconf.xml'), 'w')
            f.close()
            f = open(os.path.join(self.destdir, '.gconf', 'desktop', 'gnome', '%gconf.xml'), 'w')
            f.close()
            dst = os.path.join(self.destdir, '.gconf', 'desktop', 'gnome', 'interface', '%gconf.xml')
            cp(dogtailconf, dst)

        # create selinux config
        if os.path.isfile(os.path.join(self.destdir, 'etc', 'selinux', 'targeted')):
            selinuxconf = os.path.join(self.conf['datadir'], 'selinux-config')
            if os.path.isfile(selinuxconf):
                dst = os.path.join(self.destdir, 'etc', 'selinux', 'config')
                cp(selinuxconf, dst)

        # create libuser.conf
        libuserconf = os.path.join(self.conf['datadir'], 'libuser.conf')
        if os.path.isfile(libuserconf):
            dst = os.path.join(self.destdir, 'etc', 'libuser.conf')
            cp(libuserconf, dst)

    def __removeGtkThemes(self):
        # figure out the gtk+ theme to keep
        gtkrc = os.path.join(self.destdir, 'etc', 'gtk-2.0', 'gtkrc')
        gtk_theme_name = None
        gtk_engine = None
        gtk_icon_themes = []

        if os.path.isfile(gtkrc):
            f = open(gtkrc, 'r')
            lines = f.readlines()
            f.close()

            for line in lines:
                line = line.strip()
                if line.startswith('gtk-theme-name'):
                    gtk_theme_name = line[line.find('=') + 1:]
                    gtk_theme_name = gtk_theme_name.replace('"', '').strip()

                    # find the engine for this theme
                    gtkrc = os.path.join(self.destdir, 'usr', 'share', 'themes',
                                         gtk_theme_name, 'gtk-2.0', 'gtkrc')
                    if os.path.isfile(gtkrc):
                        f = open(gtkrc, 'r')
                        engine_lines = f.readlines()
                        f.close()

                        for engine_line in engine_lines:
                            engine_line = engine_line.strip()
                            if engine_line.find('engine') != -1:
                                gtk_engine = engine_line[engine_line.find('"') + 1:]
                                gtk_engine = gtk_engine.replace('"', '').strip()
                                break

                elif line.startswith('gtk-icon-theme-name'):
                    icon_theme = line[line.find('=') + 1:]
                    icon_theme = icon_theme.replace('"', '').strip()
                    gtk_icon_themes.append(icon_theme)

                    # bring in all inherited themes
                    while True:
                        icon_theme_index = os.path.join(self.destdir, 'usr', 'share', 'icons',
                                                        icon_theme, 'index.theme')
                        if os.path.isfile(icon_theme_index):
                            inherits = False
                            f = open(icon_theme_index, 'r')
                            icon_lines = f.readlines()
                            f.close()

                            for icon_line in icon_lines:
                                icon_line = icon_line.strip()
                                if icon_line.startswith('Inherits='):
                                    inherits = True
                                    icon_theme = icon_line[icon_line.find('=') + 1:]
                                    icon_theme = icon_theme.replace('"', '').strip()
                                    gtk_icon_themes.append(icon_theme)
                                    break

                            if not inherits:
                                break
                        else:
                            break

        # remove themes we don't need
        theme_path = os.path.join(self.destdir, 'usr', 'share', 'themes')
        if os.path.isdir(theme_path):
            for theme in filter(lambda theme: theme != gtk_theme_name, os.listdir(theme_path)):
                theme = os.path.join(theme_path, theme)
                shutil.rmtree(theme, ignore_errors=True)

        # remove icons we don't need
        icon_path = os.path.join(self.destdir, 'usr', 'share', 'icons')
        if os.path.isdir(icon_path):
            for icon in filter(lambda icon: icon not in gtk_icon_themes, os.listdir(icon_path)):
                icon = os.path.join(icon_path, icon)
                shutil.rmtree(icon, ignore_errors=True)

        # remove engines we don't need
        tmp_path = os.path.join(self.destdir, 'usr', self.libdir, 'gtk-2.0')
        if os.path.isdir(tmp_path):
            fnames = map(lambda fname: os.path.join(tmp_path, fname, 'engines'), os.listdir(tmp_path))
            dnames = filter(lambda fname: os.path.isdir(fname), fnames)
            for dir in dnames:
                engines = filter(lambda engine: engine.find(gtk_engine) == -1, os.listdir(dir))
                for engine in engines:
                    engine = os.path.join(dir, engine)
                    os.unlink(engine)

    def __removeLocales(self):
        langtable = os.path.join(self.destdir, 'usr', 'lib', 'anaconda', 'lang-table')
        localepath = os.path.join(self.destdir, 'usr', 'share', 'locale')
        if os.path.isfile(langtable):
            locales = set()
            all_locales = set()

            f = open(langtable, 'r')
            lines = f.readlines()
            f.close()

            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                fields = line.split('\t')

                if os.path.isdir(os.path.join(localepath, fields[1])):
                    locales.add(fields[1])

                locale = fields[3].split('.')[0]
                if os.path.isdir(os.path.join(localepath, locale)):
                    locales.add(locale)

            for locale in os.listdir(localepath):
                all_locales.add(locale)

            locales_to_remove = list(all_locales.difference(locales))
            for locale in locales_to_remove:
                rmpath = os.path.join(localepath, locale)
                shutil.rmtree(rmpath, ignore_errors=True)

    def __fixManPages(self):
        for file in ['nroff', 'groff', 'iconv', 'geqn', 'gtbl', 'gpic', 'grefer']:
            src = os.path.join('mnt', 'sysimage', 'usr', 'bin', file)
            dst = os.path.join(self.destdir, 'usr', 'bin', file)
            if not os.path.isfile(dst):
                os.symlink(src, dst)

        # fix /etc/man.config to point to /mnt/sysimage
        manconfig = os.path.join(self.destdir, 'etc', 'man.config')
       
        # XXX WHY?
        # don't change MANPATH_MAP lines now
        fin = fileinput.input(manconfig, inplace=1)
        for line in fin:
            line = re.sub(r'^MANPATH[^_MAP][ \t]*', r'&/mnt/sysimage', line)
            sys.stdout.write(line)
        fin.close()

        # change MANPATH_MAP lines
        fin = fileinput.input(manconfig, inplace=1)
        for line in fin:
            line = re.sub(r'^MANPATH_MAP[ \t]*[a-zA-Z0-9/]*[ \t]*', r'&/mnt/sysimage', line)
            sys.stdout.write(line)
        fin.close()

    def __installStubs(self):
        for subdir in ['lib', 'firmware']:
            subdir = os.path.join(self.destdir, subdir)
            if not os.path.isdir(subdir):
                os.makedirs(subdir)

        for subdir in ['modules', 'firmware']:
            src = os.path.join(os.path.sep, subdir)
            dst = os.path.join(self.destdir, 'lib', subdir)
            shutil.rmtree(dst, ignore_errors=True)
            os.symlink(src, dst)

        for prog in ['raidstart', 'raidstop', 'losetup', 'list-harddrives', 'loadkeys', 'mknod',
                     'syslogd']:
            stub = "%s-stub" % (prog,)
            src = os.path.join(self.destdir, 'usr', 'lib', 'anaconda', stub)
            dst = os.path.join(self.destdir, 'usr', 'bin', prog)
            if os.path.isfile(src) and not os.path.isfile(dst):
                cp(src, dst)

    def __copyBootloaders(self):
        bootpath = os.path.join(self.destdir, 'usr', 'lib', 'anaconda-runtime', 'boot')
        if not os.path.isdir(bootpath):
            os.makedirs(bootpath)

        if self.arch == 'i386' or self.arch == 'x86_64':
            for bootfile in os.listdir(os.path.join(self.destdir, 'boot')):
                if bootfile.startswith('memtest'):
                    src = os.path.join(self.destdir, 'boot', bootfile)
                    dst = os.path.join(bootpath, bootfile)
                    cp(src, dst)
        elif self.arch.startswith('sparc'):
            for bootfile in os.listdir(os.path.join(self.destdir, 'boot')):
                if bootfile.endswith('.b'):
                    src = os.path.join(self.destdir, 'boot', bootfile)
                    dst = os.path.join(bootpath, bootfile)
                    cp(src, dst)
        elif self.arch.startswith('ppc'):
            src = os.path.join(self.destdir, 'boot', 'efika.forth')
            dst = os.path.join(bootpath, 'efika.forth')
            cp(src, dst)
        elif self.arch == 'alpha':
            src = os.path.join(self.destdir, 'boot', 'bootlx')
            dst = os.path.join(bootpath, 'bootlx')
            cp(src, dst)
        elif self.arch == 'ia64':
            src = os.path.join(self.destdir, 'boot', 'efi', 'EFI', 'redhat')
            shutil.rmtree(bootpath, ignore_errors=True)
            cp(src, bootpath)

    def __moveYumRepos(self):
        src = os.path.join(self.destdir, 'etc', 'yum.repos.d')
        dst = os.path.join(self.destdir, 'etc', 'anaconda.repos.d')
        if os.path.isdir(src):
            shutil.rmtree(dst, ignore_errors=True)
            mv(src, dst)

    def __configureKmod(self):
        fedorakmodconf = os.path.join(self.destdir, 'etc', 'yum', 'pluginconf.d', 'fedorakmod.conf')
        
        # XXX this file does not exist, what package provides it?
        if not os.path.exists(fedorakmodconf):
            return
        
        fin = fileinput.input(fedorakmodconf, inplace=1)
        for line in fin:
            line = re.sub(r'\(installforallkernels\) = 0', r'\1 = 1', line)
            sys.stdout.write(line)
        fin.close()

    def __moveAnacondaFiles(self):
        # move executable
        src = os.path.join(self.destdir, 'usr', 'sbin', 'anaconda')
        dst = os.path.join(self.destdir, 'usr', 'bin', 'anaconda')
        mv(src, dst)

        # move libraries
        src = os.path.join(self.destdir, 'usr', 'lib', 'anaconda-runtime', 'lib')
        dst = os.path.join(self.destdir, 'usr', self.libdir)
        for fname in glob.glob(src + '*'):
            mv(fname, dst)

    def __setShellLinks(self):
        bash = os.path.join(self.destdir, 'bin', 'bash')
        ash = os.path.join(self.destdir, 'bin', 'ash')
        sh = os.path.join(self.destdir, 'bin', 'sh')
        busybox = os.path.join(self.destdir, 'bin', 'busybox')

        if os.path.exists(bash):
            # XXX is this needed? i don't have ash in the tree...
            try:
                os.unlink(ash)
            except OSError:
                pass

            os.unlink(sh)
            os.symlink(bash, sh)
        else:
            os.unlink(sh)
            os.symlink(busybox, sh)

    def __moveBins(self):
        bin = os.path.join(self.destdir, 'bin')
        sbin = os.path.join(self.destdir, 'sbin')

        if not os.path.exists(bin) or not os.path.exists(sbin):
            raise Error, 'bin or sbin directory missing'

        dst = os.path.join(self.destdir, 'usr')
        for src in (bin, sbin):
            mv(src, dst)

    def __removeUnwanted(self):
        for subdir in ['boot', 'home', 'root', 'tmp']:
            shutil.rmtree(os.path.join(self.destdir, subdir), ignore_errors=True)

        for subdir in ['doc', 'info']:
            shutil.rmtree(os.path.join(self.destdir, 'usr', 'share', subdir), ignore_errors=True)

        for libname in glob.glob(os.path.join(self.destdir, 'usr', self.libdir, 'libunicode-lite*')):
            shutil.rmtree(libname, ignore_errors=True)

        to_remove = set()
        for root, files, dirs in os.walk(self.destdir):
            for file in files:
                path = os.path.join(root, file)
                if fnmatch.fnmatch(path, '*.a'):
                    if path.find('kernel-wrapper/wrapper.a') == -1:
                        to_remove.append(path)
                elif fnmatch.fnmatch(path, 'lib*.la'):
                    if path.find('usr/' + self.libdir + '/gtk-2.0') == -1:
                        to_remove.append(path)
                elif fnmatch.fnmatch(path, '*.py'):
                    to_remove.append(path + 'o')
                    to_remove.append(path + 'c')
                    os.symlink('/dev/null', path + 'c')

        for file in to_remove:
            if os.path.isdir(file):
                shutil.rmtree(file)
            else:
                os.unlink(file)

        # nuke some python stuff we don't need
        for fname in ['idle', 'distutils', 'bsddb', 'lib-old', 'hotshot', 'doctest.py', 'pydoc.py',
                      'site-packages/japanese', 'site-packages/japanese.pth']:
            path = os.path.join(self.destdir, fname)
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                try:
                    os.unlink(path)
                except OSError:
                    pass

        for fname in ['distutils', 'lib-dynload/japanese', 'encodings', 'compiler', 'email/test',
                      'curses', 'pydoc.py']:
            path = os.path.join(self.destdir, 'usr', self.libdir, 'python?.?', 'site-packages',
                                fname)
            for item in glob.glob(path):
                if os.path.isdir(item):
                    shutil.rmtree(item)
                else:
                    os.unlink(item)

    def __changeDestDirPermissions(self):
        root_uid = pwd.getpwnam('root')[2]
        root_gid = grp.getgrnam('root')[2]

        for root, files, dirs in os.walk(self.destdir):
            os.chown(root, root_uid, root_gid)
            os.chmod(root, 0755)

            for file in files:
                path = os.path.join(root, file)
                os.chown(path, root_uid, root_gid)
                
                mode = os.stat(path).st_mode
                if (mode & stat.S_IXUSR) or (mode & stat.S_IXGRP) or (mode & stat.S_IXOTH):
                    os.chmod(path, 0555)
                else:
                    os.chmod(path, 0444)

    def __createLDConfig(self):
        ldsoconf = os.path.join(self.destdir, 'etc', 'ld.so.conf')
        f = open(ldsoconf, 'w')
        f.close()

        proc_dir = os.path.join(self.destdir, 'proc')
        if not os.path.isdir(proc_dir):
            os.makedirs(proc_dir)

        # XXX isn't there a better way?
        os.system('mount -t proc proc %s' % (proc_dir,))

        f = open(ldsoconf, 'w')
        x11_libdir = os.path.join(self.destdir, 'usr', 'X11R6', self.libdir)
        if os.path.exists(x11_libdir):
            f.write('/usr/X11R6/%s\n' % (self.libdir,))
        f.write('/usr/kerberos/%s\n' % (self.libdir,))

        cwd = os.getcwd()
        os.chdir(self.destdir)
        # XXX can't exit from os.chroot() :(
        os.system('/usr/sbin/chroot %s /usr/sbin/ldconfig' % (self.destdir,))
        os.chdir(cwd)

        if self.arch not in ('s390', 's390x'):
            os.unlink(os.path.join(self.destdir, 'usr', 'sbin', 'ldconfig'))
        
        os.unlink(os.path.join(self.destdir, 'etc', 'ld.so.conf'))

        # XXX isn't there a better way?
        os.system('umount %s' % (proc_dir,))

    def __setBusyboxLinks(self):
        src = os.path.join(self.destdir, 'usr', 'sbin', 'busybox.anaconda')
        dst = os.path.join(self.destdir, 'usr', 'bin', 'busybox')
        mv(src, dst)

        cwd = os.getcwd()
        os.chdir(os.path.join(self.destdir, 'usr', 'bin'))

        busybox_process = subprocess.Popen(['./busybox'], stdout=subprocess.PIPE)
        busybox_process.wait()

        if busybox_process.returncode:
            raise LoraxError, 'cannot run busybox'
        
        busybox_output = busybox_process.stdout.readlines()
        busybox_output = map(lambda line: line.strip(), busybox_output)
        busybox_output = busybox_output[busybox_output.index('Currently defined functions:') + 1:]

        commands = []
        for line in busybox_output:
            commands.extend(map(lambda c: c.strip(), line.split(',')))

        # remove empty strings
        commands = filter(lambda c: c, commands)

        for command in commands:
            # XXX why do we skip these commands? can "busybox" be there at all?
            if command not in ['buxybox', 'sh', 'shutdown', 'poweroff', 'reboot']:
                if not os.path.exists(command):
                    os.symlink('busybox', command)

        os.chdir(cwd)

    def __strip(self):
        # XXX is this thing really needed? it's ugly
        fnames = map(lambda fname: os.path.join(self.destdir, fname), os.listdir(self.destdir))
        fnames = filter(lambda fname: os.path.isfile(fname), fnames)

        executables = []
        xmodules = os.path.join('usr', 'X11R6', self.libdir, 'modules')
        for fname in fnames:
            if not fname.find(xmodules) == -1:
                continue

            mode = os.stat(fname).st_mode
            if (mode & stat.S_IXUSR):
                executables.append(fname)

        elfs = []
        for exe in executables:
            p = subprocess.Popen(['file', exe], stdout=subprocess.PIPE)
            p.wait()

            output = p.stdout.readlines()
            output = ''.join(output)
            if re.match(r'^[^:]*:.*ELF.*$', output):
                elfs.append(exe)

        for elf in elfs:
            p = subprocess.Popen(['objdump', '-h', elf], stdout=subprocess.PIPE)
            p.wait()

            cmd = ['strip']
            if self.arch == 'ia64':
                cmd.append('--strip-debug')

            arglist = [elf, '-R', '.comment', '-R', '.note']
            for line in p.stdout.readlines():
                m = re.match(r'^.*(?P<warning>\.gnu\.warning\.[^ ]*) .*$', line)
                if m:
                    arglist.extend(['-R', m.group('warning')])

            p = subprocess.Popen(cmd + arglist)
            p.wait()

    def __fixBrokenLinks(self):
        for dir in ['bin', 'sbin']:
            dir = os.path.join(self.destdir, 'usr', dir)
                
            brokenlinks = []
            for root, fnames, dnames in os.walk(dir):
                for fname in fnames:
                    fname = os.path.join(root, fname)
                    if os.path.islink(fname) and not os.path.lexists(fname):
                        brokenlinks.append(fname)

            for link in brokenlinks:
                target = os.readlink(link)

                for dir in ['bin', 'sbin']:
                    newtarget = re.sub(r'^\.\./\.\./%s/\(.*\)' % dir, r'\.\./%s/\1' % dir, target)
                    if newtarget != target:
                        os.symlink(newtarget, link)
