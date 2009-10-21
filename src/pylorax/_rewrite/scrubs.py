import stat
import commands
import pwd
import grp

class Install(object):

    def scrub(self):
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

        # make bash link
        # XXX already exists
        #if os.path.isfile(os.path.join(self.conf.treedir, 'bin', 'bash')):
        #    rm(os.path.join(self.conf.treedir, 'bin', 'ash'))
        #    os.symlink('bash', os.path.join(self.conf.treedir, 'bin', 'sh'))

        # make awk link
        # XXX already exists
        #if os.path.isfile(os.path.join(self.conf.treedir, 'bin', 'gawk')):
        #    os.symlink('awk', os.path.join(self.conf.treedir, 'bin', 'gawk'))

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
