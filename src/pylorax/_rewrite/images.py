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


class Install(object):
    def __init__(self, config):
        self.conf = config

    def scrub(self):
        # move bin to usr/bin
        cp(src_root=self.conf.treedir,
           src_path=os.path.join('bin', '*'),
           dst_root=self.conf.treedir,
           dst_path=os.path.join('usr', 'bin'),
           ignore_errors=True)
        
        rm(os.path.join(self.conf.treedir, 'bin'))

        # move sbin to /usr/sbin
        cp(src_root=self.conf.treedir,
           src_path=os.path.join('sbin', '*'),
           dst_root=self.conf.treedir,
           dst_path=os.path.join('usr', 'sbin'),
           ignore_errors=True)
        
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
