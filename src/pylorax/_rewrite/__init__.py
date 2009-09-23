import stat
import commands
import glob
import fnmatch
import pwd
import grp


class Lorax(object):

    def scrub_treedir(self):
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
