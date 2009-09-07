#
# __init__.py
# lorax main class
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
# Red Hat Author(s):  David Cantrell <dcantrell@redhat.com>
#                     Martin Gracik <mgracik@redhat.com>
#

import sys
import os
import stat
import commands
import shutil
import glob
import tempfile
import time
import datetime
import ConfigParser
import re
import fnmatch
import pwd
import grp
from errors import LoraxError

from config import Container
from utils.rpmutils import Yum
from utils.fileutils import cp, mv, rm, touch, edit, replace

import images


class Config(Container):
    def __init__(self):
        config = ('confdir', 'datadir', 'tempdir', 'debug', 'cleanup')

        # options
        required = ('product', 'version', 'release', 'outdir', 'repos')
        optional = ('variant', 'bugurl', 'updates', 'mirrorlist')

        Container.__init__(self, config + required + optional)

        # set defaults
        self.set(confdir='/etc/lorax',
                 datadir='/usr/share/lorax',
                 tempdir=tempfile.mkdtemp(prefix='lorax.tmp.', dir=tempfile.gettempdir()),
                 debug=False,
                 cleanup=False)

        self.set(product='',
                 version='',
                 release='',
                 outdir='',
                 repos=[])

        self.set(variant='',
                 bugurl='',
                 updates='',
                 mirrorlist=[])


class Lorax(object):
    def __init__(self, config):
        assert isinstance(config, Config) == True
        self.conf = config

        # check if we have all required options
        if not self.conf.repos:
            raise LoraxError, "missing required parameter 'repos'"
        if not self.conf.outdir:
            raise LoraxError, "missing required parameter 'outdir'"
        if not self.conf.product:
            raise LoraxError, "missing required parameter 'product'"
        if not self.conf.version:
            raise LoraxError, "missing required parameter 'version'"
        if not self.conf.release:
            raise LoraxError, "missing required parameter 'release'"

        self.yum = None

    def run(self):
        bold = ('\033[1m', '\033[0m')

        print("%sCollecting repos%s" % bold)
        self.collect_repos()

        # check if we have at least one valid repository
        if not self.conf.repo:
            sys.stderr.write("ERROR: No valid repository\n")
            sys.exit(1)

        print("%sInitializing temporary directories%s" % bold)
        self.init_dirs()

        print("%sInitializing yum%s" % bold)
        self.init_yum()

        print("%sSetting build architecture%s" % bold)
        self.set_buildarch()

        print("%sWriting .treeinfo%s" % bold)
        self.write_treeinfo()

        print("%sWriting .discinfo%s" % bold)
        self.write_discinfo()

        print("%sPreparing the install tree%s" % bold)
        self.prepare_treedir()

        print("%sScrubbing the install tree%s" % bold)
        self.scrub_treedir()

        print("%sWriting .buildstamp%s" % bold)
        self.write_buildstamp()

        print("%sInitializing output directories%s" % bold)
        self.init_outputdirs()

        print("%sCreating the initrd.img%s" % bold)
        self.create_initrd()

        print("%sCreating the install.img%s" % bold)
        #self.create_installimg()

        print("%sCreating the boot.iso%s" % bold)
        #self.create_bootiso()

        if self.conf.cleanup:
            print("%sCleaning up%s" % bold)
            self.clean_up()

    def collect_repos(self):
        repolist = []
        for repospec in self.conf.repos:
            if repospec.startswith('/'):
                repo = 'file://%s' % repospec
                print("Adding local repo: %s" % repo)
                repolist.append(repo)
            elif repospec.startswith('http://') or repospec.startswith('ftp://'):
                print("Adding remote repo: %s" % repospec)
                repolist.append(repospec)
            else:
                print("Invalid repo path: %s" % repospec)

        if not repolist:
            repo, extrarepos = None, []
        else:
            repo, extrarepos = repolist[0], repolist[1:]

        self.conf.addAttr(['repo', 'extrarepos'])
        self.conf.set(repo=repo, extrarepos=extrarepos)

        # remove repos attribute, to get a traceback, if we use it later accidentaly
        self.conf.delAttr('repos')

    def init_dirs(self):
        if not os.path.isdir(self.conf.outdir):
            os.makedirs(self.conf.outdir, mode=0755)

        treedir = os.path.join(self.conf.tempdir, 'treedir', 'install')
        os.makedirs(treedir)
        cachedir = os.path.join(self.conf.tempdir, 'yumcache')
        os.makedirs(cachedir)
        initrddir = os.path.join(self.conf.tempdir, 'initrddir')
        os.makedirs(initrddir)

        print("Working directories:")
        print("    tempdir = %s" % self.conf.tempdir)
        print("    treedir = %s" % treedir)
        print("    cachedir = %s" % cachedir)
        print("    initrddir = %s" % initrddir)

        self.conf.addAttr(['treedir', 'cachedir', 'initrddir'])
        self.conf.set(treedir=treedir, cachedir=cachedir, initrddir=initrddir)

    def init_yum(self):
        yumconf = os.path.join(self.conf.tempdir, 'yum.conf')

        try:
            f = open(yumconf, 'w')
        except IOError as why:
            sys.stderr.write("ERROR: Unable to write yum.conf file: %s\n" % why)
            sys.exit(1)
        else:
            f.write('[main]\n')
            f.write('cachedir=%s\n' % self.conf.cachedir)
            f.write('keepcache=0\n')
            f.write('gpgcheck=0\n')
            f.write('plugins=0\n')
            f.write('reposdir=\n')
            f.write('tsflags=nodocs\n\n')

            f.write('[loraxrepo]\n')
            f.write('name=lorax repo\n')
            f.write('baseurl=%s\n' % self.conf.repo)
            f.write('enabled=1\n\n')

            for n, extra in enumerate(self.conf.extrarepos, start=1):
                f.write('[lorax-extrarepo-%d]\n' % n)
                f.write('name=lorax extra repo %d\n' % n)
                f.write('baseurl=%s\n' % extra)
                f.write('enabled=1\n')

            for n, mirror in enumerate(self.conf.mirrorlist, start=1):
                f.write('[lorax-mirrorlistrepo-%d]\n' % n)
                f.write('name=lorax mirrorlist repo %d\n' % n)
                f.write('mirrorlist=%s\n' % mirror)
                f.write('enabled=1\n')

            f.close()

        self.conf.addAttr('yumconf')
        self.conf.set(yumconf=yumconf)

        # create the yum err file path
        err_file = os.path.join(self.conf.tempdir, 'yum.errors')

        # create the Yum object
        self.yum = Yum(yumconf=self.conf.yumconf, installroot=self.conf.treedir,
                       err_file=err_file)

        # remove not needed attributes
        self.conf.delAttr(['repo', 'extrarepos', 'mirrorlist', 'cachedir'])

    def set_buildarch(self):
        unamearch = os.uname()[4]

        self.conf.addAttr('buildarch')
        self.conf.set(buildarch=unamearch)

        installed, available = self.yum.find('anaconda')
        try:
            self.conf.set(buildarch=available[0].arch)
        except:
            pass

        # set basearch
        self.conf.addAttr('basearch')
        self.conf.set(basearch=self.conf.buildarch)
        if re.match(r'i.86', self.conf.basearch):
            self.conf.set(basearch='i386')
        elif self.conf.buildarch == 'sparc64':
            self.conf.set(basearch='sparc')

        # set the libdir
        self.conf.addAttr('libdir')
        self.conf.set(libdir='lib')
        # on 64-bit systems, make sure we use lib64 as the lib directory
        if self.conf.buildarch.endswith('64') or self.conf.buildarch == 's390x':
            self.conf.set(libdir='lib64')

        # set efiarch
        self.conf.addAttr('efiarch')
        self.conf.set(efiarch='')

        if self.conf.buildarch == 'i386':
            self.conf.set(efiarch='ia32')
        elif self.conf.buildarch == 'x86_64':
            self.conf.set(efiarch='x64')
        elif self.conf.buildarch == 'ia64':
            self.conf.set(efiarch='ia64')

    def write_treeinfo(self, discnum=1, totaldiscs=1, packagedir=''):
        outfile = os.path.join(self.conf.outdir, '.treeinfo')

        # don't print anything instead of None, if variant is not specified
        variant = ''
        if self.conf.variant:
            variant = self.conf.variant
            
        data = { 'timestamp': time.time(),
                 'family': self.conf.product,
                 'version': self.conf.version,
                 'arch': self.conf.basearch,
                 'variant': variant,
                 'discnum': str(discnum),
                 'totaldiscs': str(totaldiscs),
                 'packagedir': packagedir }

        c = ConfigParser.ConfigParser()
        
        section = 'general'
        c.add_section(section)
        for key, value in data.items():
            c.set(section, key, value)

        section = 'images-%s' % self.conf.basearch
        c.add_section(section)
        c.set(section, 'kernel', 'images/pxeboot/vmlinuz')
        c.set(section, 'initrd', 'images/pxeboot/initrd.img')
        c.set(section, 'boot.iso', 'images/boot.iso')

        try:
            f = open(outfile, 'w')
        except IOError:
            return False
        else:
            c.write(f)
            f.close()
            return True
    
    def write_discinfo(self, discnum='ALL'):
        outfile = os.path.join(self.conf.outdir, '.discinfo')

        try:
            f = open(outfile, 'w')
        except IOError:
            return False
        else:
            f.write('%f\n' % time.time())
            f.write('%s\n' % self.conf.release)
            f.write('%s\n' % self.conf.basearch)
            f.write('%s\n' % discnum)
            f.close()
            return True

    def prepare_treedir(self):
        # required packages
        self.yum.addPackages(['anaconda', 'anaconda-runtime', 'kernel', '*firmware*', 'syslinux',
                              '/etc/gtk-2.0/gtkrc'])

        # get packages from confdir
        packages_files = []
        packages_files.append(os.path.join(self.conf.confdir, 'packages', 'packages.all'))
        packages_files.append(os.path.join(self.conf.confdir, 'packages', 'packages.%s' % self.conf.buildarch))

        packages = set()
        for pfile in packages_files:
            if os.path.isfile(pfile):
                f = open(pfile, 'r')
                for line in f.readlines():
                    line, sep, comment = line.partition('#')
                    line = line.strip()

                    if not line:
                        continue

                    if line.startswith('-'):
                        packages.discard(line[1:])
                    else:
                        packages.add(line)

                f.close()

        self.yum.addPackages(list(packages))

        # add logos
        self.yum.addPackages(['%s-logos' % self.conf.product.lower(),
                              '%s-release' % self.conf.product.lower()])

        # XXX why do we need this?
        os.symlink(os.path.join(os.path.sep, 'tmp'),
                   os.path.join(self.conf.treedir, 'var', 'lib', 'xkb'))

        # install packages
        self.yum.install()

        # copy updates
        if self.conf.updates and os.path.isdir(self.conf.updates):
            cp(src_root=self.conf.updates, src_path='*',
               dst_root=self.conf.treedir, dst_path='')
        self.conf.delAttr('updates')


        # XXX here comes a lot of crazy tree modification stuff, beware! XXX

        # create dogtail conf files
        dogtailconf = os.path.join(self.conf.datadir, 'dogtail', '%gconf.xml')
        if os.path.isfile(dogtailconf):
            dst = os.path.join(self.conf.treedir, '.gconf', 'desktop', 'gnome', 'interface')
            os.makedirs(dst)
            shutil.copy2(dogtailconf, dst)

            touch(os.path.join(self.conf.treedir, '.gconf', 'desktop', '%gconf.xml'))
            touch(os.path.join(self.conf.treedir, '.gconf', 'desktop', 'gnome', '%gconf.xml'))

        # XXX wth is this part useful for?

        # XXX this one already exists
        #os.makedirs(os.path.join(self.conf.treedir, 'lib'))
        os.makedirs(os.path.join(self.conf.treedir, 'firmware'))
        os.makedirs(os.path.join(self.conf.treedir, 'modules'))

        # XXX this will overwrite the modules which are installed, why would i want to do that?
        #os.symlink('/modules', os.path.join(self.conf.treedir, 'lib', 'modules'))
        #os.symlink('/firmware', os.path.join(self.conf.treedir, 'lib', 'firmware'))

        # create debug dirs
        os.makedirs(os.path.join(self.conf.treedir, 'usr', 'lib', 'debug'))
        os.makedirs(os.path.join(self.conf.treedir, 'usr', 'src', 'debug'))

        # copy stubs
        for file in ('raidstart', 'raidstop', 'losetup', 'list-harddrives', 'loadkeys', 'mknod',
                     'syslogd'):
            src = os.path.join(self.conf.treedir, 'usr', 'lib', 'anaconda', file + '-stub')
            dst = os.path.join(self.conf.treedir, 'usr', 'bin', file)
            shutil.copy2(src, dst)

        # move anaconda executable
        src = os.path.join(self.conf.treedir, 'usr', 'sbin', 'anaconda')
        dst = os.path.join(self.conf.treedir, 'usr', 'bin', 'anaconda')
        shutil.move(src, dst)

        # move anaconda libraries
        src = os.path.join(self.conf.treedir, 'usr', 'lib', 'anaconda-runtime', 'lib*')
        dst = os.path.join(self.conf.treedir, 'usr', self.conf.libdir)
        for name in glob.iglob(src):
            shutil.move(name, dst)

        # change tree permissions
        root_uid = pwd.getpwnam('root')[2]
        root_gid = grp.getgrnam('root')[2]

        for root, files, dirs in os.walk(self.conf.treedir):
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

        # create ld.so.conf
        ldsoconf = os.path.join(self.conf.treedir, 'etc', 'ld.so.conf')
        touch(ldsoconf)

        procdir = os.path.join(self.conf.treedir, 'proc')
        if not os.path.isdir(procdir):
            os.makedirs(procdir)
        os.system('mount -t proc proc %s' % procdir)

        f = open(ldsoconf, 'w')
        f.write('/usr/kerberos/%s\n' % self.conf.libdir)
        f.close()

        cwd = os.getcwd()
        os.chdir(self.conf.treedir)
        os.system('/usr/sbin/chroot %s /sbin/ldconfig' % self.conf.treedir)
        os.chdir(cwd)

        if self.conf.buildarch not in ('s390', 's390x'):
            # XXX this is not in usr
            rm(os.path.join(self.conf.treedir, 'usr', 'sbin', 'ldconfig'))
        
        # XXX why are we removing this?
        #rm(os.path.join(self.conf.treedir, 'etc', 'ld.so.conf'))
        os.system('umount %s' % procdir)

    def scrub_treedir(self):
        # XXX another part of crazy tree modification XXX

        # figure out the gtk+ theme to keep
        gtkrc = os.path.join(self.conf.treedir, 'etc', 'gtk-2.0', 'gtkrc')
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
                    gtkrc = os.path.join(self.conf.treedir, 'usr', 'share', 'themes',
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
                        icon_theme_index = os.path.join(self.conf.treedir, 'usr', 'share', 'icons',
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
            theme_path = os.path.join(self.conf.treedir, 'usr', 'share', 'themes')
            if os.path.isdir(theme_path):
                for theme in filter(lambda theme: theme != gtk_theme_name, os.listdir(theme_path)):
                    theme = os.path.join(theme_path, theme)
                    shutil.rmtree(theme, ignore_errors=True)

            # remove icons we don't need
            icon_path = os.path.join(self.conf.treedir, 'usr', 'share', 'icons')
            if os.path.isdir(icon_path):
                for icon in filter(lambda icon: icon not in gtk_icon_themes, os.listdir(icon_path)):
                    icon = os.path.join(icon_path, icon)
                    shutil.rmtree(icon, ignore_errors=True)

            # remove engines we don't need
            tmp_path = os.path.join(self.conf.treedir, 'usr', self.conf.libdir, 'gtk-2.0')
            if os.path.isdir(tmp_path):
                fnames = map(lambda fname: os.path.join(tmp_path, fname, 'engines'), os.listdir(tmp_path))
                dnames = filter(lambda fname: os.path.isdir(fname), fnames)
                for dir in dnames:
                    engines = filter(lambda engine: engine.find(gtk_engine) == -1, os.listdir(dir))
                    for engine in engines:
                        engine = os.path.join(dir, engine)
                        os.unlink(engine)

        # remove locales
        langtable = os.path.join(self.conf.treedir, 'usr', 'lib', 'anaconda', 'lang-table')
        localepath = os.path.join(self.conf.treedir, 'usr', 'share', 'locale')
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
        
        # fixup joe links
        joedir = os.path.join(self.conf.treedir, 'etc', 'joe')
        if os.path.isdir(joedir):
            os.symlink('jpicorc', os.path.join(joedir, 'picorc'))
            os.symlink('jpicorc', os.path.join(joedir, 'jnanorc'))
            os.symlink('jpicorc', os.path.join(joedir, 'nanorc'))
            os.symlink('jmacsrc', os.path.join(joedir, 'emacsrc'))
            os.symlink('jmacs', os.path.join(self.conf.treedir, 'usr', 'bin', 'emacs'))
            os.symlink('jpico', os.path.join(self.conf.treedir, 'usr', 'bin', 'pico'))
            os.symlink('jpico', os.path.join(self.conf.treedir, 'usr', 'bin', 'nano'))

        # fix up some links for man page related stuff
        for file in ['nroff', 'groff', 'iconv', 'geqn', 'gtbl', 'gpic', 'grefer']:
            src = os.path.join('mnt', 'sysimage', 'usr', 'bin', file)
            dst = os.path.join(self.conf.treedir, 'usr', 'bin', file)
            if not os.path.isfile(dst):
                os.symlink(src, dst)

        # create selinux config
        if os.path.exists(os.path.join(self.conf.treedir, 'etc', 'selinux', 'targeted')):
            src = os.path.join(self.conf.datadir, 'selinux', 'config')
            dst = os.path.join(self.conf.treedir, 'etc', 'selinux', 'config')
            shutil.copy2(src, dst)

        # create libuser.conf
        src = os.path.join(self.conf.datadir, 'libuser', 'libuser.conf')
        dst = os.path.join(self.conf.treedir, 'etc', 'libuser.conf')
        shutil.copy2(src, dst)

        # configure fedorakmod
        fedorakmodconf = os.path.join(self.conf.treedir, 'etc', 'yum', 'pluginconf.d',
                                      'fedorakmod.conf')
        replace(fedorakmodconf, r'\(installforallkernels\) = 0', r'\1 = 1')

        # fix /etc/man.config to point into /mnt/sysimage
        manconfig = os.path.join(self.conf.treedir, 'etc', 'man.config')
       
        # don't change MANPATH_MAP lines now
        replace(manconfig, r'^MANPATH[^_MAP][ \t]*', r'&/mnt/sysimage')
        # change MANPATH_MAP lines now
        replace(manconfig, r'^MANPATH_MAP[ \t]*[a-zA-Z0-9/]*[ \t]*', r'&/mnt/sysimage')

        # move yum repos
        src = os.path.join(self.conf.treedir, 'etc', 'yum.repos.d')
        dst = os.path.join(self.conf.treedir, 'etc', 'anaconda.repos.d')
        shutil.move(src, dst)

        # remove libunicode-lite
        rm(os.path.join(self.conf.treedir, 'usr', self.conf.libdir, 'libunicode-lite*'))

        # make bash link
        # XXX already exists
        #if os.path.isfile(os.path.join(self.conf.treedir, 'bin', 'bash')):
        #    rm(os.path.join(self.conf.treedir, 'bin', 'ash'))
        #    os.symlink('bash', os.path.join(self.conf.treedir, 'bin', 'sh'))

        # make awk link
        # XXX already exists
        #if os.path.isfile(os.path.join(self.conf.treedir, 'bin', 'gawk')):
        #    os.symlink('awk', os.path.join(self.conf.treedir, 'bin', 'gawk'))

        # copy bootloaders 
        bootpath = os.path.join(self.conf.treedir, 'usr', 'lib', 'anaconda-runtime', 'boot')
        if not os.path.isdir(bootpath):
            os.makedirs(bootpath)

        if self.conf.buildarch in ('i386', 'i586', 'x86_64'):
            for file in os.listdir(os.path.join(self.conf.treedir, 'boot')):
                if file.startswith('memtest'):
                    src = os.path.join(self.conf.treedir, 'boot', file)
                    dst = os.path.join(bootpath, file)
                    shutil.copy2(src, dst)
        elif self.conf.buildarch in ('sparc',):
            for file in os.listdir(os.path.join(self.conf.treedir, 'boot')):
                if file.endswith('.b'):
                    src = os.path.join(self.conf.treedir, 'boot', file)
                    dst = os.path.join(bootpath, file)
                    shutil.copy2(src, dst)
        elif self.conf.buildarch in ('ppc', 'ppc64'):
            src = os.path.join(self.conf.treedir, 'boot', 'efika.forth')
            shutil.copy2(src, bootpath)
        elif self.conf.buildarch in ('alpha',):
            src = os.path.join(self.conf.treedir, 'boot', 'bootlx')
            shutil.copy2(src, bootpath)
        elif self.conf.buildarch in ('ia64',):
            src = os.path.join(self.conf.treedir, 'boot', 'efi', 'EFI', 'redhat', '*')
            shutil.copy2(src, bootpath)

        # remove not needed directories
        # XXX i need this for kernel
        #for dir in ('boot', 'home', 'root', 'tmp'):
        #    rm(os.path.join(self.conf.treedir, dir))

        # remove not needed files
        to_remove = set()
        for root, dirs, files in os.walk(self.conf.treedir):
            for file in files:
                path = os.path.join(root, file)
                if fnmatch.fnmatch(path, '*.a'):
                    if path.find('kernel-wrapper/wrapper.a') == -1:
                        to_remove.add(path)
                elif fnmatch.fnmatch(path, 'lib*.la'):
                    if path.find('usr/' + self.conf.libdir + '/gtk-2.0') == -1:
                        to_remove.add(path)
                elif fnmatch.fnmatch(path, '*.py'):
                    to_remove.add(path + 'o')
                    
                    rm(path + 'c')
                    os.symlink('/dev/null', path + 'c')

        for file in to_remove:
            rm(file)

        # nuke some python stuff we don't need
        for fname in ['idle', 'distutils', 'bsddb', 'lib-old', 'hotshot', 'doctest.py', 'pydoc.py',
                      'site-packages/japanese', 'site-packages/japanese.pth']:
            rm(os.path.join(self.conf.treedir, fname))

        for fname in ['distutils', 'lib-dynload/japanese', 'encodings', 'compiler', 'email/test',
                      'curses', 'pydoc.py']:
            rm(os.path.join(self.conf.treedir, 'usr', self.conf.libdir, 'python?.?', 'site-packages',
                            fname))

    def write_buildstamp(self):
        outfile = os.path.join(self.conf.treedir, '.buildstamp')

        # make imageuuid
        now = datetime.datetime.now()
        arch = self.conf.buildarch
        imageuuid = '%s.%s' % (now.strftime('%Y%m%d%H%M'), arch)

        try:
            f = open(outfile, 'w')
        except IOError:
            return False
        else:
            f.write('%s\n' % imageuuid)
            f.write('%s\n' % self.conf.product)
            f.write('%s\n' % self.conf.version)
            f.write('%s\n' % self.conf.bugurl)
            f.close()
            return True

    def init_outputdirs(self):
        # create the destination directories
        imagesdir = os.path.join(self.conf.outdir, 'images')
        if os.path.exists(imagesdir):
            rm(imagesdir)
        os.makedirs(imagesdir)

        pxebootdir = os.path.join(imagesdir, 'pxeboot')
        os.makedirs(pxebootdir)

        # create the isolinux directory
        isolinuxdir = os.path.join(self.conf.outdir, 'isolinux')
        if os.path.exists(isolinuxdir):
            rm(isolinuxdir)
        os.makedirs(isolinuxdir)

        self.conf.addAttr(['imagesdir', 'pxebootdir', 'isolinuxdir'])
        self.conf.set(imagesdir=imagesdir, pxebootdir=pxebootdir, isolinuxdir=isolinuxdir)

        # create the temporary EFI tree dir
        efitreedir = os.path.join(self.conf.tempdir, 'EFI', 'BOOT')
        os.makedirs(efitreedir)
        self.conf.addAttr('efitreedir')
        self.conf.set(efitreedir=efitreedir)

        # write the images/README
        src = os.path.join(self.conf.datadir, 'images', 'README')
        dst = os.path.join(self.conf.imagesdir, 'README')
        shutil.copy2(src, dst)
        replace(dst, r'@PRODUCT@', self.conf.product)

        # write the images/pxeboot/README
        src = os.path.join(self.conf.datadir, 'images', 'pxeboot', 'README')
        dst = os.path.join(self.conf.pxebootdir, 'README')
        shutil.copy2(src, dst)
        replace(dst, r'@PRODUCT@', self.conf.product)


        # populate the isolinux directory

        # XXX don't see this used anywhere...
        syslinux = os.path.join(self.conf.treedir, 'usr', 'lib', 'syslinux', 'syslinux-nomtools')
        if not os.path.isfile(syslinux):
            sys.stderr.write('WARNING: %s does not exist\n' % syslinux)
            syslinux = os.path.join(self.conf.treedir, 'usr', 'bin', 'syslinux')
            if not os.path.isfile(syslinux):
                sys.stderr.write('ERROR: %s does not exist\n' % syslinux)
                sys.exit(1)

        # set up some dir variables for further use
        anacondadir = os.path.join(self.conf.treedir, 'usr', 'lib', 'anaconda-runtime')
        bootdiskdir = os.path.join(anacondadir, 'boot')
        self.conf.addAttr('bootdiskdir')
        self.conf.set(bootdiskdir=bootdiskdir)
        syslinuxdir = os.path.join(self.conf.treedir, 'usr', 'lib', 'syslinux')
        isolinuxbin = os.path.join(syslinuxdir, 'isolinux.bin')

        if os.path.exists(isolinuxbin):
            # copy the isolinux.bin
            shutil.copy2(isolinuxbin, self.conf.isolinuxdir)

            # copy the syslinux.cfg to isolinux/isolinux.cfg
            isolinuxcfg = os.path.join(self.conf.isolinuxdir, 'isolinux.cfg')
            shutil.copy2(os.path.join(bootdiskdir, 'syslinux.cfg'), isolinuxcfg)

            # set the product and version in isolinux.cfg
            replace(isolinuxcfg, r'@PRODUCT@', self.conf.product)
            replace(isolinuxcfg, r'@VERSION@', self.conf.version)

            # set up the label for finding stage2 with a hybrid iso
            replace(isolinuxcfg, r'initrd=initrd.img', 'initrd=initrd.img stage2=hd:LABEL=%s' % self.conf.product)

            # copy the grub.conf
            shutil.copy2(os.path.join(bootdiskdir, 'grub.conf'), self.conf.isolinuxdir)

            # copy the splash files
            vesasplash = os.path.join(anacondadir, 'syslinux-vesa-splash.jpg')
            if os.path.isfile(vesasplash):
                shutil.copy2(vesasplash, os.path.join(self.conf.isolinuxdir, 'splash.jpg'))
                vesamenu = os.path.join(syslinuxdir, 'vesamenu.c32')
                shutil.copy2(vesamenu, self.conf.isolinuxdir)
                replace(isolinuxcfg, r'default linux', r'default vesamenu.c32')
                replace(isolinuxcfg, r'prompt 1', r'#prompt 1')
            else:
                splashtools = os.path.join(anacondadir, 'splashtools.sh')
                splashlss = os.path.join(bootdiskdir, 'splash.lss')
                if os.path.isfile(splashtools):
                    cmd = '%s %s %s' % (splashtools,
                                        os.path.join(bootdiskdir, 'syslinux-splash.jpg'),
                                        splashlss)
                    os.system(cmd)
                if os.path.isfile(splashlss):
                    shutil.copy2(splashlss, self.conf.isolinuxdir)

            # copy the .msg files
            for file in os.listdir(bootdiskdir):
                if file.endswith('.msg'):
                    shutil.copy2(os.path.join(bootdiskdir, file), self.conf.isolinuxdir)
                    replace(os.path.join(self.conf.isolinuxdir, file), r'@VERSION@', self.conf.version)

            # if present, copy the memtest
            for fname in os.listdir(os.path.join(self.conf.treedir, 'boot')):
                if fname.startswith('memtest'):
                    src = os.path.join(self.conf.treedir, 'boot', fname)
                    dst = os.path.join(self.conf.isolinuxdir, 'memtest')
                    shutil.copy2(src, dst)

                    text = "label memtest86\n"
                    text = text + "  menu label ^Memory test\n"
                    text = text + "  kernel memtest\n"
                    text = text + "  append -\n"
                    edit(isolinuxcfg, text, append=True)
        else:
            sys.stderr.write('ERROR: %s does not exist\n' % isolinuxbin)
            sys.exit(1)

    def create_efi(self, kernelfile=None, initrd=None, kernelpath=None, initrdpath=None):
        rm(os.path.join(self.conf.efitreedir, '*'))

        # copy conf files to EFI tree dir
        cp(src_root=self.conf.bootdiskdir, src_path='*.conf',
           dst_root=self.conf.efitreedir, dst_path='')

        # copy files to efi tree dir
        if kernelfile and initrd:
            shutil.copy2(kernelfile, os.path.join(self.conf.efitreedir, 'vmlinuz'))
            shutil.copy2(initrd, self.conf.efitreedir)
            efikernelpath = os.path.join(os.sep, 'EFI', 'BOOT', 'vmlinuz')
            efiinitrdpath = os.path.join(os.sep, 'EFI', 'BOOT', 'initrd.img')
        else:
            efikernelpath = kernelpath
            efiinitrdpath = initrdpath

        splashpath = os.path.join(os.sep, 'EFI', 'BOOT', 'splash.xpm.gz')

        grubconf = os.path.join(self.conf.efitreedir, 'grub.conf')
        replace(grubconf, '@PRODUCT@', self.conf.product)
        replace(grubconf, '@VERSION@', self.conf.version)
        replace(grubconf, '@KERNELPATH@', efikernelpath)
        replace(grubconf, '@INITRDPATH@', efiinitrdpath)
        replace(grubconf, '@SPLASHPATH@', splashpath)

        src = os.path.join(self.conf.treedir, 'boot', 'efi', 'EFI', 'redhat', 'grub.efi')
        shutil.copy2(src, self.conf.efitreedir)

        # the first generation mactel machines get the bootloader name wrong
        if self.conf.efiarch in ('ia32'):
            src = os.path.join(self.conf.efitreedir, 'grub.efi')
            dst = os.path.join(self.conf.efitreedir, 'BOOT.efi')
            shutil.copy2(src, dst)

            src = os.path.join(self.conf.efitreedir, 'grub.conf')
            dst = os.path.join(self.conf.efitreedir, 'BOOT.conf')
            shutil.copy2(src, dst)

        efiarch = self.conf.efiarch
        if efiarch == 'x64':
            efiarch = 'X64'
        elif efiarch == 'ia32':
            efiarch = 'IA32'
        
        src = os.path.join(self.conf.efitreedir, 'grub.efi')
        dst = os.path.join(self.conf.efitreedir, 'BOOT%s.efi' % efiarch)
        shutil.move(src, dst)

        src = os.path.join(self.conf.efitreedir, 'grub.conf')
        dst = os.path.join(self.conf.efitreedir, 'BOOT%s.conf' % efiarch)
        shutil.move(src, dst)

        # copy splash
        src = os.path.join(self.conf.treedir, 'boot', 'grub', 'splash.xpm.gz')
        dst = os.path.join(self.conf.efitreedir, 'splash.xpm.gz')
        shutil.copy2(src, dst)

        # calculate the size of the dosfs
        cmd = 'du -kcs %s | tail -n1 | awk \'{print $1}\'' % self.conf.efitreedir
        size = int(commands.getoutput(cmd)) + 100

        efiimage = os.path.join(self.conf.outdir, 'images', 'efiboot.img')
        cmd = 'mkdosfs -n ANACONDA -C %s %s > /dev/null' % (efiimage, size)
        out = commands.getoutput(cmd)

        tempdir = os.path.join(self.conf.tempdir, 'efiimage')
        if not os.path.isdir(tempdir):
            os.makedirs(tempdir)
        cmd = 'mount -o loop,shortname=winnt,umask=0777 -t vfat %s %s' % \
              (efiimage, tempdir)
        out = commands.getoutput(cmd)

        cp(src_root=self.conf.efitreedir, src_path='*',
           dst_root=tempdir, dst_path='')

        cmd = 'umount %s' % tempdir
        out = commands.getoutput(cmd)

        # copy efi to cd
        if not kernelfile and not initrd:
            dst = os.path.join(self.conf.outdir, 'EFI', 'BOOT')
            if os.path.exists(dst):
                rm(dst)
            os.makedirs(dst)

            for name in glob.iglob(os.path.join(self.conf.efitreedir, '*.conf')):
                shutil.copy2(name, dst)

        return efiimage

    def create_initrd(self):
        # get installed kernel file
        kernelfile = None
        kerneldir = os.path.join(self.conf.treedir, 'boot')

        if self.conf.buildarch in ('ia64',):
            kerneldir = os.path.join(self.conf.treedir, 'boot', 'efi', 'EFI', 'redhat')

        for file in os.listdir(kerneldir):
            if fnmatch.fnmatch(file, 'vmlinuz-*'):
                kernelfile = os.path.join(self.conf.treedir, 'boot', file)

        if not kernelfile:
            sys.stderr.write('ERROR: No kernel image found\n')
            sys.exit(1)

        initrd = images.InitRD(self.conf, self.yum, kernelfile)

        # install needed packages
        packages = initrd.get_packages()
        self.yum.addPackages(list(packages))
        self.yum.install()

        # copy the kernel file
        shutil.copy2(kernelfile, os.path.join(self.conf.isolinuxdir, 'vmlinuz'))
        shutil.copy2(kernelfile, os.path.join(self.conf.pxebootdir, 'vmlinuz'))

        # create the initrd.img
        initrd.create(os.path.join(self.conf.isolinuxdir, 'initrd.img'))
        initrd.clean_up()

        # copy the initrd.img
        shutil.copy2(os.path.join(self.conf.isolinuxdir, 'initrd.img'), self.conf.pxebootdir)

        # create efiimage
        efiimage = self.create_efi(kernelfile=kernelfile,
                                   initrd=os.path.join(self.conf.isolinuxdir, 'initrd.img'))

        # create efi bootdisk
        # XXX now this is not nice, can it be done some other way?
        cmd = 'ls -l %s | awk \'{print $5}\'' % efiimage
        partsize = int(commands.getoutput(cmd))
        disksize = 17408 + partsize + 17408
        disksize = disksize + (disksize % 512)

        efidiskimg = os.path.join(self.conf.imagesdir, 'efidisk.img')
        touch(efidiskimg)

        cmd = 'dd if=/dev/zero of=%s count=1 bs=%s' % (efidiskimg, disksize)
        out = commands.getoutput(cmd)

        cmd = 'losetup -v -f %s | awk \'{print $4}\'' % efidiskimg
        loop = commands.getoutput(cmd)

        cmd = 'dmsetup create efiboot --table "0 %s linear %s 0"' % (disksize / 512, loop)
        out = commands.getoutput(cmd)

        cmd = 'parted --script /dev/mapper/efiboot mklabel gpt unit b mkpart \'"EFI System Partition"\' fat32 17408 %s set 1 boot on' % (partsize + 17408)
        out = commands.getoutput(cmd)

        cmd = 'dd if=%s of=/dev/mapper/efibootp1' % efiimage
        out = commands.getoutput(cmd)

        cmd = 'dmsetup remove /dev/mapper/efibootp1'
        out = commands.getoutput(cmd)
        cmd = 'dmsetup remove /dev/mapper/efiboot'
        out = commands.getoutput(cmd)

        cmd = 'losetup -d %s' % loop
        out = commands.getoutput(cmd)

        # remove efiimage
        rm(efiimage)

        # create new efiimage
        efiimage = self.create_efi(kernelpath='/images/pxeboot/vmlinuz',
                                   initrdpath='/images/pxeboot/initrd.img')

        # XEN
        if self.conf.buildarch in ('i386',):
            print('Installing the XEN kernel')
            self.yum.addPackages('kernel-PAE')
            self.yum.install()
            
            xenkernel = None
            for file in os.listdir(kerneldir):
                if fnmatch.fnmatch(file, 'vmlinuz-*.PAE'):
                    xenkernel = os.path.join(self.conf.treedir, 'boot', file)

            if not xenkernel:
                sys.stderr.write('ERROR: No XEN kernel image found\n')
                sys.exit(1)

            initrd = images.InitRD(self.conf, self.yum, xenkernel)

            shutil.copy2(xenkernel, os.path.join(self.conf.pxebootdir, 'vmlinuz-PAE'))

            initrd.create(os.path.join(self.conf.pxebootdir, 'initrd-PAE.img'))
            #initrd.clean_up()

            # add xen kernel files to .treeinfo
            text = '[images-xen]\n'
            text += 'kernel = images/pxeboot/vmlinuz-PAE\n'
            text += 'initrd = images/pxeboot/initrd-PAE.img\n'
            edit(os.path.join(self.conf.outdir, '.treeinfo'), append=True, text=text)

    def create_installimg(self, type='squashfs'):
        print('Removing not needed files from install tree')
        i = images.Install(self.conf)
        i.scrub()
        i.fix_links()

        print('Creating the image file')
        if type == 'squashfs':
            cmd = 'mksquashfs %s %s -all-root -no-fragments -no-progress' % (self.conf.treedir,
                                                                             os.path.join(self.conf.imagesdir, 'install.img'))
            err, output = commands.getstatusoutput(cmd)
        elif type == 'cramfs':
            if self.conf.buildarch == 'sparc64':
                crambs = '--blocksize 8192'
            elif self.conf.buildarch == 'sparc':
                crambs = '--blocksize 4096'
            else:
                crambs = ''

            cmd = 'mkfs.cramfs %s %s %s' % (crambs, self.conf.treedir, os.path.join(self.conf.imagesdir, 'install.img'))
            err, output = commands.getstatusoutput(cmd)
        elif type == 'ext2':
            # TODO
            pass

        text = '\n[stage2]\n'
        text += 'mainimage = %s/install.img\n' % self.conf.imagesdir
        edit(os.path.join(self.conf.outdir, '.treeinfo'), append=True, text=text)

    def create_bootiso(self):
        efiboot = os.path.join(self.conf.imagesdir, 'efiboot.img')
        efiargs = ''
        efigraft = ''
        if os.path.exists(efiboot):
            print('Found efiboot.img, making an EFI-capable boot.iso')
            efiargs = '-eltorito-alt-boot -e images/efiboot.img -no-emul-boot'
            efigraft = 'EFI/BOOT=%s' % os.path.join(self.conf.outdir, 'EFI', 'BOOT')
        else:
            print('No efiboot.img found, making BIOS-only boot.iso')

        biosargs = '-b isolinux/isolinux.bin -c isolinux/boot.cat -no-emul-boot -boot-load-size 4 -boot-info-table'
        mkisocmd = 'mkisofs -v -o %s %s %s -R -J -V %s -T -graft-points isolinux=%s images=%s %s' % (os.path.join(self.conf.imagesdir, 'boot.iso'), biosargs, efiargs, self.conf.product, self.conf.isolinuxdir, self.conf.imagesdir, efigraft)

        out = commands.getoutput(mkisocmd)

        hybrid = os.path.join(os.sep, 'usr', 'bin', 'isohybrid')
        if os.path.exists(hybrid):
            cmd = '%s %s' % (hybrid, os.path.join(self.conf.imagesdir, 'boot.iso'))
            out = commands.getoutput(cmd)

    def clean_up(self, trash=[]):
        for item in trash:
            if os.path.exists(item):
                rm(item)

        # remove the whole lorax temp directory
        if os.path.exists(self.conf.tempdir):
            rm(self.conf.tempdir)
