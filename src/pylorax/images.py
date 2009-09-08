#
# images.py
# lorax images manipulation
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
import commands
import re
import fnmatch
import datetime
import glob

import actions
import actions.base
from config import Template

from utils.fileutils import cp, mv, rm, touch, edit, replace
from utils.ldd import LDD
from utils.genmodinfo import genmodinfo


class InitRD(object):
    def __init__(self, config, yum, kernelfile):
        self.conf = config
        self.yum = yum
        self.kernelfile = kernelfile

        # get the kernel version
        m = re.match(r'.*vmlinuz-(?P<ver>.*)', self.kernelfile)
        self.kernelver = m.group('ver')

        # get supported actions
        supported_actions = actions.getActions()

        # vars supported in template
        vars = { 'instroot': self.conf.treedir,
                 'initrd': self.conf.initrddir,
                 'libdir': self.conf.libdir,
                 'buildarch': self.conf.buildarch,
                 'confdir' : self.conf.confdir,
                 'datadir': self.conf.datadir }

        initrd_template = os.path.join(self.conf.confdir, 'templates',
                                       'initrd.%s' % self.conf.buildarch)
        self.template = Template()
        self.template.preparse(initrd_template)
        self.template.parse(supported_actions, vars)

        # additional actions that need to be processed
        self._actions = []

        if not os.path.isdir(self.conf.initrddir):
            os.makedirs(self.conf.initrddir)

    def get_packages(self):
        packages = set()
        for action in filter(lambda action: action.install, self.template.actions):
            m = re.match(r'%s(.*)' % self.conf.treedir, action.install)
            if m:
                packages.add(m.group(1))

        return packages

    def get_deps(self):
        libroots = []
        libroots.append(os.path.join(self.conf.treedir, self.conf.libdir))
        libroots.append(os.path.join(self.conf.treedir, 'usr', self.conf.libdir))
        
        # on 64 bit systems, add also normal lib directories
        if self.conf.libdir.endswith('64'):
            libroots.append(os.path.join(self.conf.treedir, self.conf.libdir[:-2]))
            libroots.append(os.path.join(self.conf.treedir, 'usr', self.conf.libdir[:-2]))

        ldd = LDD(libroots)
        for action in filter(lambda action: hasattr(action, 'getDeps'), self.template.actions):
            ldd.getDeps(action.getDeps)

        # resolve symlinks
        # XXX we don't need this, because cp function gets the symlinks
        #ldd.getLinks()

        # add dependencies to actions
        for dep in ldd.deps:
            kwargs = {}
            kwargs['src_root'] = self.conf.treedir
            kwargs['src_path'] = dep.replace(self.conf.treedir + os.sep, '', 1)
            kwargs['dst_root'] = self.conf.initrddir
            kwargs['dst_path'] = dep.replace(self.conf.treedir + os.sep, '', 1)
            kwargs['dst_path'] = os.path.dirname(kwargs['dst_path'])

            new_action = actions.base.Copy(**kwargs)
            self._actions.append(new_action)

    def process_actions(self):
        for action in self.template.actions + self._actions:
            action.execute()

    def get_keymaps(self):
        override = os.path.join(self.conf.treedir, 'usr', 'lib', 'anaconda-runtime',
                                'keymaps-override-%s' % self.conf.buildarch)
        if os.path.exists(override):
            print('Found keymap override, using it')
            shutil.copy2(override, os.path.join(self.conf.treedir, 'keymaps.gz'))
        else:
            cmd = '%s %s %s %s' % \
                  (os.path.join(self.conf.treedir, 'usr', 'lib', 'anaconda-runtime', 'getkeymaps'),
                   self.conf.buildarch, os.path.join(self.conf.treedir, 'keymaps.gz'), self.conf.treedir)
            rc = commands.getstatus(cmd)
            if rc != 0:
                sys.stderr.write('Unable to create keymaps and thus can\'t create initrd\n')
                sys.exit(1)

        shutil.copy2(os.path.join(self.conf.treedir, 'keymaps.gz'),
                     os.path.join(self.conf.initrddir, 'etc'))

    def create_locales(self):
        os.makedirs(os.path.join(self.conf.initrddir, 'usr', 'lib', 'locale'))
        rc, output = commands.getstatusoutput('localedef -c -i en_US -f UTF-8 --prefix %s en_US' % self.conf.initrddir)

    def get_modules(self):
        modlist = os.path.join(self.conf.treedir, 'usr', 'lib', 'anaconda-runtime', 'modlist')
        modinfo = os.path.join(self.conf.tempdir, 'modinfo')
        genmodinfo(os.path.join(self.conf.treedir, 'lib', 'modules', self.kernelver), modinfo)

        moddir = os.path.join(self.conf.treedir, 'lib', 'modules', self.kernelver)

        modfiles = []
        modfiles.append(os.path.join(self.conf.confdir, 'modules', 'modules'))
        modfiles.append(os.path.join(self.conf.confdir, 'modules', self.conf.buildarch, 'modules'))

        # expand modules
        modules = set()
        for file in modfiles:
            if os.path.isfile(file):
                f = open(file, 'r')
                lines = f.readlines()
                f.close()

                for line in lines:
                    line, sep, comment = line.partition('#')
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    if line.startswith('-'):
                        modules.discard(line[1:])
                    elif line.startswith('='):
                        group = line[1:]
                        
                        if group in  ('scsi', 'ata'):
                            path = os.path.join(moddir, 'modules.block')
                        elif group == 'net':
                            path = os.path.join(moddir, 'modules.networking')
                        else:
                            path = os.path.join(moddir, 'modules.%s' % group)

                        modules_to_add = []
                        if os.path.isfile(path):
                            f = open(path, 'r')
                            for module in f.readlines():
                                module = module.strip()
                                module = module.replace('.ko', '')
                                modules_to_add.append(module)
                            f.close()

                        # XXX do we really need to filter only ata or ahci if group == ata?

                        for module in modules_to_add:
                            modules.add(module)
                    else:
                        modules.add(line)

        # resolve deps
        depfile = os.path.join(self.conf.treedir, 'lib', 'modules', self.kernelver, 'modules.dep')
        f = open(depfile, 'r')
        lines = f.readlines()
        f.close()

        changed = True
        while changed:
            for line in lines:
                changed = False
                line = line.strip()
                m = re.match(r'^.*/(?P<name>.*)\.ko:(?P<deps>.*)$', line)
                modname = m.group('name')
                if modname in modules:
                    for dep in m.group('deps').split():
                        m = re.match(r'^.*/(?P<name>.*)\.ko$', dep)
                        if m.group('name') not in modules:
                            changed = True
                            modules.add(m.group('name'))

        srcdir = os.path.join(self.conf.treedir, 'lib', 'modules', self.kernelver)
        dstdir = os.path.join(self.conf.initrddir, 'lib', 'modules')
        
        cp(src_root=self.conf.treedir,
           src_path=os.path.join('lib', 'modules', self.kernelver),
           dst_root=self.conf.initrddir,
           dst_path=os.path.join('lib', 'modules'),
           ignore_errors=True)

        for root, dirs, files in os.walk(dstdir):
            for file in files:
                name, ext = os.path.splitext(file)
                if ext == '.ko':
                    if name not in modules:
                        rm(os.path.join(root, file))
                    else:
                        # copy the required firmware
                        module = os.path.join(root, file)
                        output = commands.getoutput('modinfo -F firmware %s' % module)
                        output = output.strip()

                        for fw in output.split():
                            print "copying firmware '%s'" % fw

                            dst = os.path.join(self.conf.initrddir, 'lib', 'firmware', fw)
                            dir = os.path.dirname(dst)
                            if not os.path.exists(dir):
                                os.makedirs(dir)

                            cp(src_root = self.conf.treedir,
                               src_path = os.path.join('lib', 'firmware', fw),
                               dst_root = self.conf.initrddir,
                               dst_path = os.path.join('lib', 'firmware', fw))

        # copy firmware
        srcdir = os.path.join(self.conf.treedir, 'lib', 'firmware')
        dstdir = os.path.join(self.conf.initrddir, 'lib', 'firmware')

        fw = ( ('ipw2100', 'ipw2100*'),
               ('ipw2200', 'ipw2200*'),
               ('iwl3945', 'iwlwifi-3945*'),
               ('iwl4965', 'iwlwifi-4965*'),
               ('atmel', 'atmel_*.bin'),
               ('zd1211rw', 'zd1211'),
               ('qla2xxx', 'ql*') )

        for module, file in fw:
            if module in modules:
                print('Copying firmware %s' % module)
                cp(src_root=self.conf.treedir,
                   src_path=os.path.join('lib', 'firmware', file),
                   dst_root=self.conf.initrddir,
                   dst_path=os.path.join('lib', 'firmware'))

        # create modinfo
        dst = os.path.join(self.conf.initrddir, 'lib', 'modules', 'module-info')
        cmd = '%s --modinfo-file %s --ignore-missing --modinfo %s > %s' % \
              (modlist, modinfo, ' '.join(list(modules)), dst)
        commands.getoutput(cmd)

        # compress modules
        cmd = 'find -H %s -type f -name *.ko -exec gzip -9 {} \\;' % \
              os.path.join(self.conf.initrddir, 'lib', 'modules')
        commands.getoutput(cmd)

        # run depmod
        cmd = '/sbin/depmod -a -F %s -b %s %s' % \
              (os.path.join(self.conf.treedir, 'boot', 'System.map-%s' % self.kernelver),
               self.conf.initrddir, self.kernelver)
        commands.getoutput(cmd)

        # remove leftovers
        rm(os.path.join(self.conf.initrddir, 'lib', 'modules', self.kernelver, 'modules.*map'))
        rm(os.path.join(self.conf.initrddir, 'lib', 'modules', self.kernelver, 'source'))
        rm(os.path.join(self.conf.initrddir, 'lib', 'modules', self.kernelver, 'build'))

        # trim pci ids
        vendors = set()
        devices = set()

        modulesalias = os.path.join(self.conf.treedir, 'lib', 'modules', self.kernelver, 'modules.alias')
        f = open(modulesalias)
        pcitable = f.readlines()
        f.close()
       
        for line in pcitable:
            if not line.startswith('alias pci:'):
                continue

            vend = '0x%s' % line[15:19]
            vend.upper()
            dev = '0x%s' % line[24:28]
            dev = dev.upper()

            vendors.add(vend)
            devices.add((vend, dev))

        videoaliases = os.path.join(self.conf.treedir, 'usr', 'share', 'hwdata', 'videoaliases', '*')
        for file in glob.iglob(videoaliases):
            f = open(file)
            pcitable = f.readlines()
            f.close()

            for line in pcitable:
                if not line.startswith('alias pcivideo:'):
                    continue

                vend = '0x%s' % line[20:24]
                vend = vend.upper()
                dev = '0x%s' % line[29:33]
                dev = dev.upper()

                vendors.add(vend)
                devices.add((vend, dev))

        # create pci.ids
        # XXX this file is NOT in the original initrd image...
        src = os.path.join(self.conf.treedir, 'usr', 'share', 'hwdata', 'pci.ids')
        #dst = os.path.join(self.conf.initrddir, 'pci.ids')
        dst = os.path.join(self.conf.treedir, 'pci.ids')

        input = open(src, 'r')
        pcitable = input.readlines()
        input.close()

        output = open(dst, 'w')

        current_vend = 0
        for line in pcitable:
            # skip lines that start with 2 tabs or #
            if line.startswith('\t\t') or line.startswith('#'):
                continue

            # skip empty lines
            if line == '\n':
                continue

            # end of file
            if line == 'ffff Illegal Vendor ID':
                break

            if not line.startswith('\t'):
                current_vend = '0x%s' % line.split()[0]
                current_vend = current_vend.upper()
                if current_vend in vendors:
                    output.write(line)
                continue

            dev = '0x%s' % line.split()[0]
            dev = dev.upper()
            if (current_vend, dev) in devices:
                output.write(line)

        output.close()

    def get_missing_links(self):
        missing_files = []

        for root, dnames, fnames in os.walk(self.conf.initrddir):
            for fname in fnames:
                file = os.path.join(root, fname)
                if os.path.islink(file) and not os.path.exists(file):
                    # broken link
                    target = os.readlink(file)
                    missing = os.path.join(os.path.dirname(file), target)
                    missing = os.path.normpath(missing)
                    
                    missing_files.append(missing)

        print 'Missing files:', missing_files

    def create(self, dst):
        # copy the productfile
        shutil.copy2(os.path.join(self.conf.treedir, '.buildstamp'),
                     os.path.join(self.conf.initrddir, '.buildstamp'))

        print('Getting dependencies')
        self.get_deps()
        print('Processing actions')
        self.process_actions()
        print('Getting keymaps')
        self.get_keymaps()
        print('Creating locales')
        self.create_locales()
        print('Getting modules')
        self.get_modules()
        print('Getting missing links')
        self.get_missing_links()

        # create the initrd
        print('Creating the %s' % dst)
        cwd = os.getcwd()
        os.chdir(self.conf.initrddir)
        out = commands.getoutput('find . | cpio --quiet -c -o | gzip -9 > %s' % dst)
        os.chdir(cwd)

    def clean_up(self):
        rm(self.conf.initrddir)


class Install(object):
    def __init__(self, config):
        self.conf = config

    def scrub(self):
        # move bin to usr/bin
        cp(src_root=self.conf.treedir,
           src_path=os.path.join('bin', '*'),
           dst_root=self.conf.treedir,
           dst_path=os.path.join('usr', 'bin'))
        
        rm(os.path.join(self.conf.treedir, 'bin'))

        # move sbin to /usr/sbin
        cp(src_root=self.conf.treedir,
           src_path=os.path.join('sbin', '*'),
           dst_root=self.conf.treedir,
           dst_path=os.path.join('usr', 'sbin'))
        
        rm(os.path.join(self.conf.treedir, 'sbin'))

        # remove dirs from root
        dirs = ('boot', 'dev', 'home', 'media', 'mnt', 'opt', 'root', 'selinux', 'srv', 'sys', 'tmp', 'keymaps')
        for dir in dirs:
            rm(os.path.join(self.conf.treedir, dir))

        # remove dirs from usr
        dirs = ('etc', 'games', 'include', 'kerberos', 'local', 'tmp')
        for dir in dirs:
            rm(os.path.join(self.conf.treedir, 'usr', dir))

        # remove dirs from var
        dirs = ('db', 'empty', 'games', 'local', 'lock', 'log', 'mail', 'nis', 'opt', 'preserve', 'spool', 'tmp', 'yp')
        for dir in dirs:
            rm(os.path.join(self.conf.treedir, 'var', dir))

        # remove modules and firmware
        rm(os.path.join(self.conf.treedir, 'lib', 'modules'))
        rm(os.path.join(self.conf.treedir, 'lib', 'firmware'))

        # remove dirs from usr/lib
        dirs = ('ConsoleKit', 'X11', 'alsa-lib', 'asterisk', 'avahi', 'booty', 'db4.5*', 'enchant', 'games', 'gio', 'gnome-keyring', 'gnome-vfs-2.0',
                'krb5', 'libglade', 'libxslt-plugins', 'lua', 'notification-daemon*', 'nss', 'openssl', 'orbit-2.0', 'perl5', 'pkgconfig', 'plymouth',
                'pm-utils', 'pppd', 'pygtk', 'rsyslog', 'samba', 'sasl2', 'sse2', 'syslinux', 'tc', 'tls', 'udev', 'window-manager-settings')
        for dir in dirs:
            rm(os.path.join(self.conf.treedir, 'usr', 'lib', dir))

        # remove dirs from usr/share
        dirs = ('GConf', 'NetworkManager', 'aclocal', 'alsa', 'application-registry', 'applications', 'asterisk', 'augeas', 'authconfig', 'avahi',
                'awk', 'createrepo', 'desktop-directories', 'dict', 'doc', 'dogtail', 'emacs', 'empty', 'enchant', 'file', 'firmware', 'firmware-tools',
                'firstboot', 'games', 'gnome*', 'gnupg', 'groff', 'gtk-*', 'help', 'i18n', 'info', 'kde*', 'librarian', 'libthai', 'lua',
                'makebootfat', 'man', 'metacity', 'mime*', 'misc', 'myspell', 'octave', 'omf', 'pkgconfig', 'plymouth', 'pygtk', 'selinux',
                'setuptool', 'sgml', 'system-config-firewall', 'system-config-network', 'system-config-users', 'tabset', 'tc', 'usermode', 'xml',
                'xsessions', 'yum-cli', 'magic')
        for dir in dirs:
            rm(os.path.join(self.conf.treedir, 'usr', 'share', dir))

        # remove dirs from usr/share/themes
        dirs = ('AgingGorilla', 'Atlanta', 'Bright', 'Clearlooks', 'ClearlooksClassic', 'Crux', 'Default', 'Emacs', 'Esco', 'Glider', 'Glossy',
                'HighContrast*', 'Industrial', 'Inverted', 'LargePrint', 'LowContrast*', 'Metabox', 'Mist', 'Raleigh', 'Simple', 'ThinIce')
        for dir in dirs:
            rm(os.path.join(self.conf.treedir, 'usr', 'share', 'themes', dir))

        # remove dirs from etc
        dirs = ('ConsoleKit', 'X11', 'alternatives', 'asterisk', 'avahi', 'blkid', 'bonobo-activation', 'chkconfig.d', 'cron.*', 'default', 'depmod.d',
                'dirmngr', 'dnsmasq.d', 'event.d', 'firmware', 'firstaidkit', 'gconf', 'gcrypt', 'gnome-vfs*', 'gnupg', 'gtk', 'hotplug', 'init.d',
                'iproute2', 'iscsi', 'kernel', 'ld.so.conf.d', 'logrotate.d', 'lvm', 'makedev.d', 'modprobe.d', 'netplug*', 'ntp', 'openldap', 'opt',
                'pam.d', 'pki', 'pm', 'popt.d', 'ppp', 'prelink.conf.d', 'profile.d', 'rc[0-6].d', 'rwtab.d', 'samba', 'sasl2', 'security', 'setuptool.d',
                'skel', 'ssh', 'statetab.d', 'terminfo', 'xdg', 'xinetd.d', 'yum.repos.d')
        for dir in dirs:
            rm(os.path.join(self.conf.treedir, 'etc', dir))

        # remove dirs from lib
        dirs = ('i686', 'kbd', 'rtkaio', 'security', 'tls', 'xtables')
        for dir in dirs:
            rm(os.path.join(self.conf.treedir, 'lib', dir))

        # remove dirs from usr/libexec
        dirs = ('awk', 'gcc', 'getconf', 'openssh', 'plymouth')
        for dir in dirs:
            rm(os.path.join(self.conf.treedir, 'usr', 'libexec', dir))

        # remove dirs from usr/share/locale
        dirs = ('af_ZA', 'ca_ES', 'cs_CZ', 'de_DE', 'el_GR', 'en', 'en_US', 'es_ES', 'et_EE', 'fa_IR', 'fr_FR', 'he_IL', 'hr_HR', 'it_IT', 'ja_JP',
                'ko_KR', 'nb_NO', 'nl_NL', 'nso', 'pl_PL', 'pt_PT', 'ru_RU', 'sr', 'sv_SE', 'uk_UA')
        for dir in dirs:
            rm(os.path.join(self.conf.treedir, 'usr', 'share', 'locale'))

        # remove dirs from var/cache
        dirs = ('dirmngr', 'fontconfig', 'man', 'yum')
        map(lambda dir: rm(os.path.join(self.conf.treedir, 'var', 'cache', dir)), dirs)

        # remove dirs from var/lib
        dirs = ('alternatives', 'asterisk', 'authconfig', 'dhclient', 'dhcpv6', 'dirmngr', 'dnsmasq', 'games', 'iscsi', 'nfs', 'ntp', 'plymouth',
                'rpcbind', 'rpm', 'samba', 'selinux', 'sepolgen', 'stateless', 'udev', 'yum', 'logrotate.status')
        map(lambda dir: rm(os.path.join(self.conf.treedir, 'var', 'lib', dir)), dirs)

        # remove dirs from var/run
        dirs = ('ConsoleKit', 'NetworkManager', 'asterisk', 'avahi-daemon', 'console', 'dirmngr', 'hald', 'mdadm', 'netreport', 'plymouth',
                'pm-utils', 'ppp', 'sepermit', 'setrans', 'winbindd', 'wpa_supplicant', 'utmp')
        map(lambda dir: rm(os.path.join(self.conf.treedir, 'var', 'run', dir)), dirs)

        # remove dirs from usr/share/terminfo
        dirs = ('A', 'E', 'a', 'c', 'd', 'g', 'h', 'j', 'k', 'm', 'n', 'p', 'r', 's', 't', 'w')
        map(lambda dir: rm(os.path.join(self.conf.treedir, 'usr', 'share', 'terminfo', dir)), dirs)

        # remove dirs from usr/share/pixmaps
        dirs = ('redhat', 'splash')
        map(lambda dir: rm(os.path.join(self.conf.treedir, 'usr', 'share', 'pixmaps', dir)), dirs)

        # remove dirs form usr/share/X11/fonts
        dirs = ('OTF', 'encodings', 'util')
        map(lambda dir: rm(os.path.join(self.conf.treedir, 'usr', 'share', 'X11', 'fonts', dir)), dirs)

        # remove dirs from usr/lib/python2.5/site-packages
        dirs = ('firmware_addon_dell', 'firmwaretools')
        map(lambda dir: rm(os.path.join(self.conf.treedir, 'usr', 'lib', 'python2.5', 'site-packages', dir)), dirs)

        # remove dirs from etc/rc.d
        dirs = ('rc?.d', 'rc', 'rc.local', 'rc.sysinit')
        map(lambda dir: rm(os.path.join(self.conf.treedir, 'etc', 'rc.d', dir)), dirs)

    def fix_links(self):
        print("Fixing broken links")
        for dir in ('bin', 'sbin'):
            dir = os.path.join(self.conf.treedir, 'usr', dir)

            brokenlinks = []
            for root, dnames, fnames in os.walk(dir):
                for fname in fnames:
                    fname = os.path.join(root, fname)
                    if os.path.islink(fname):
                        target = os.readlink(fname)
                        if not os.path.exists(fname):
                            brokenlinks.append(fname)

            for link in brokenlinks:
                target = os.readlink(link)
                for dir in ('bin', 'sbin'):
                    newtarget = re.sub(r'^\.\./\.\./%s/(.*)' % dir, '../%s/\g<1>' % dir, target)
                    if newtarget != target:
                        os.unlink(link)
                        os.symlink(newtarget, link)
