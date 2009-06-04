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
import tempfile

from fileutils import cp, mv, touch
from yumutils import extract_rpm

import utils


class InstRoot:
    """InstRoot(config, options, yum)

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

    def __init__(self, config, options, yum):
        self.conf = config
        self.opts = options
        self.yum = yum

        self.destdir = self.conf.treedir

    def run(self):
        """run()

        Generate the instroot tree and prepare it for building images.
        """

        self.packages = self.__getPackageList()
        self.__installPackages()

        if not self.__installKernel():
            sys.exit(1)

        # XXX
        #self.__scrubInstRoot()

    def __getPackageList(self):
        packages = set()

        packages_files = []
        packages_files.append(os.path.join(self.conf.confdir, 'packages'))
        packages_files.append(os.path.join(self.conf.confdir, self.opts.buildarch, 'packages'))

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
        # XXX i don't think this is needed
        # do some prep work on the destdir before calling yum
        #os.makedirs(os.path.join(self.destdir, 'boot'))
        #os.makedirs(os.path.join(self.destdir, 'usr', 'sbin'))
        #os.makedirs(os.path.join(self.destdir, 'usr', 'lib', 'debug'))
        #os.makedirs(os.path.join(self.destdir, 'usr', 'src', 'debug'))
        #os.makedirs(os.path.join(self.destdir, 'tmp'))
        #os.makedirs(os.path.join(self.destdir, 'var', 'log'))
        #os.makedirs(os.path.join(self.destdir, 'var', 'lib', 'yum'))

        # XXX maybe only this...
        #os.makedirs(os.path.join(self.destdir, 'var', 'lib'))
        os.symlink(os.path.join(os.path.sep, 'tmp'), os.path.join(self.destdir, 'var', 'lib', 'xkb'))

        self.yum.install(self.packages)

        # copy updates to treedir
        if self.opts.updates and os.path.isdir(self.opts.updates):
            cp(os.path.join(self.opts.updates, '*'), self.destdir)

    # XXX
    def __installKernel(self):
        arches = [self.opts.buildarch]
        efiarch = []
        kerneltags = ['kernel']
        kernelxen = []

        if self.opts.buildarch == 'ppc':
            arches = ['ppc64', 'ppc']
        elif self.opts.buildarch == 'i386':
            arches = ['i586']
            efiarch = ['ia32']
            kerneltags = ['kernel', 'kernel-PAE']
            kernelxen = ['kernel-PAE']
        elif self.opts.buildarch == 'x86_64':
            efiarch = ['x64']
        elif self.opts.buildarch == 'ia64':
            efiarch = ['ia64']

        kpackages = self.yum.find(kerneltags)

        if not kpackages:
            sys.stderr.write('ERROR: Unable to find any kernel package\n')
            return False

        # create the modinfo file
        (fd, modinfo) = tempfile.mkstemp(prefix='modinfo-%s.' % self.opts.buildarch,
                                         dir=self.conf.tempdir)
        self.conf.addAttr('modinfo')
        self.conf.set(modinfo=modinfo)

        for kernel in kpackages:
            fn = self.yum.download(kernel)
            kernelroot = os.path.join(self.conf.kernelbase, kernel.arch)
            extract_rpm(fn, kernelroot)
            os.unlink(fn)

            # get vmlinuz and version
            dir = os.path.join(kernelroot, 'boot')
            if self.opts.buildarch == 'ia64':
                dir = os.path.join(dir, 'efi', 'EFI', 'redhat')

            vmlinuz = None
            for file in os.listdir(dir):
                if file.startswith('vmlinuz'):
                    vmlinuz = file
                    prefix, sep, version = file.partition('-')

            if not vmlinuz:
                sys.stderr.write('ERROR: vmlinuz file not found\n')
                return False

            modules_dir = os.path.join(kernelroot, 'lib', 'modules', version)
            if not os.path.isdir(modules_dir):
                sys.stderr.write('ERROR: modules directory not found\n')
                return False

            allmods = []
            for file in os.listdir(modules_dir):
                if file.endswith('.ko'):
                    allmods.append(os.path.join(modules_dir, file))

            # install firmware
            fpackages = self.yum.find('*firmware*')
            for firmware in fpackages:
                fn = self.yum.download(firmware)
                extract_rpm(fn, kernelroot)
                os.unlink(fn)

            utils.genmodinfo(modules_dir, self.conf.modinfo)

        return True

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
        #self.__moveBins()
        self.__removeUnwanted()
        self.__changeDestDirPermissions()
        self.__createLDConfig()
        self.__setBusyboxLinks()
        self.__strip()
        #self.__fixBrokenLinks()

    def __createConfigFiles(self):
        # create %gconf.xml
        dogtailconf = os.path.join(self.conf.datadir, 'dogtail-%gconf.xml')
        if os.path.isfile(dogtailconf):
            os.makedirs(os.path.join(self.destdir, '.gconf', 'desktop', 'gnome', 'interface'))
            touch(os.path.join(self.destdir, '.gconf', 'desktop', '%gconf.xml'))
            touch(os.path.join(self.destdir, '.gconf', 'desktop', 'gnome', '%gconf.xml'))
            
            dst = os.path.join(self.destdir, '.gconf', 'desktop', 'gnome', 'interface', '%gconf.xml')
            cp(dogtailconf, dst)

        # create selinux config
        if os.path.isfile(os.path.join(self.destdir, 'etc', 'selinux', 'targeted')):
            selinuxconf = os.path.join(self.conf.datadir, 'selinux-config')
            if os.path.isfile(selinuxconf):
                dst = os.path.join(self.destdir, 'etc', 'selinux', 'config')
                cp(selinuxconf, dst)

        # create libuser.conf
        libuserconf = os.path.join(self.conf.datadir, 'libuser.conf')
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
        tmp_path = os.path.join(self.destdir, 'usr', self.opts.libdir, 'gtk-2.0')
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

        if self.opts.buildarch == 'i386' or self.opts.buildarch == 'x86_64':
            for bootfile in os.listdir(os.path.join(self.destdir, 'boot')):
                if bootfile.startswith('memtest'):
                    src = os.path.join(self.destdir, 'boot', bootfile)
                    dst = os.path.join(bootpath, bootfile)
                    cp(src, dst)
        elif self.opts.buildarch.startswith('sparc'):
            for bootfile in os.listdir(os.path.join(self.destdir, 'boot')):
                if bootfile.endswith('.b'):
                    src = os.path.join(self.destdir, 'boot', bootfile)
                    dst = os.path.join(bootpath, bootfile)
                    cp(src, dst)
        elif self.opts.buildarch.startswith('ppc'):
            src = os.path.join(self.destdir, 'boot', 'efika.forth')
            dst = os.path.join(bootpath, 'efika.forth')
            cp(src, dst)
        elif self.opts.buildarch == 'alpha':
            src = os.path.join(self.destdir, 'boot', 'bootlx')
            dst = os.path.join(bootpath, 'bootlx')
            cp(src, dst)
        elif self.opts.buildarch == 'ia64':
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
        # XXX why do we want to move everything to /usr when in mk-images we copy it back?
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
        touch(ldsoconf)

        proc_dir = os.path.join(self.destdir, 'proc')
        if not os.path.isdir(proc_dir):
            os.makedirs(proc_dir)

        os.system('mount -t proc proc %s' % proc_dir)

        f = open(ldsoconf, 'w')

        x11_libdir = os.path.join(self.destdir, 'usr', 'X11R6', self.opts.libdir)
        if os.path.exists(x11_libdir):
            f.write('/usr/X11R6/%s\n' % self.opts.libdir)

        f.write('/usr/kerberos/%s\n' % self.opts.libdir)

        cwd = os.getcwd()
        os.chdir(self.destdir)
        os.system('/usr/sbin/chroot %s /sbin/ldconfig' % self.destdir)
        os.chdir(cwd)

        if self.opts.buildarch not in ('s390', 's390x'):
            os.unlink(os.path.join(self.destdir, 'sbin', 'ldconfig'))
        
        os.unlink(os.path.join(self.destdir, 'etc', 'ld.so.conf'))

        os.system('umount %s' % proc_dir)

    def __setBusyboxLinks(self):
        src = os.path.join(self.destdir, 'sbin', 'busybox.anaconda')
        dst = os.path.join(self.destdir, 'bin', 'busybox')
        mv(src, dst)

        cwd = os.getcwd()
        os.chdir(os.path.join(self.destdir, 'bin'))

        busybox_process = subprocess.Popen(['./busybox'], stdout=subprocess.PIPE)
        busybox_process.wait()

        if busybox_process.returncode:
            raise Error, 'busybox error'
        
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

    def __makeAdditionalDirs(self):
        os.makedirs(os.path.join(self.destdir, 'modules'))
        os.makedirs(os.path.join(self.destdir, 'tmp'))
        for dir in ('a', 'b', 'd', 'l', 's', 'v', 'x'):
            os.makedirs(os.path.join(self.destdir, 'etc', 'terminfo', dir))
        os.makedirs(os.path.join(self.destdir, 'var', 'lock', 'rpm'))
