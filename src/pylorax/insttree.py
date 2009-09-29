#
# instroot.py
# install root class
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

import os
import glob
import fnmatch
import shutil

from utils.fileutils import copy, move, remove, replace, touch


class InstallTree(object):

    def __init__(self, config, yum, output):
        self.conf = config
        self.yum = yum

        self.so, self.se = output

    def get_packages(self):
        required = ["anaconda", "anaconda-runtime", "/etc/gtk-2.0/gtkrc"]

        # kernel packages
        required.extend(["kernel", "*firmware*"])

        # add the XEN kernel package
        if self.conf.buildarch == "i386":
            required.append("kernel-PAE")

        # get additional packages from the configuration files
        packages_files = []
        packages_files.append(os.path.join(self.conf.confdir, "packages",
                "packages.all")),
        packages_files.append(os.path.join(self.conf.confdir, "packages",
                "packages.%s" % (self.conf.buildarch,)))

        packages = set()
        for file in packages_files:
            if os.path.isfile(file):
                try:
                    f = open(file, "r")
                except IOError as why:
                    self.se.error("Unable to read packages configuration:"
                            " %s" % (why,))
                else:
                    for line in f.readlines():
                        line, sep, comment = line.partition("#")
                        line = line.strip()
                        
                        if not line:
                            continue

                        if line.startswith("-"):
                            packages.discard(line[1:])
                        else:
                            packages.add(line)

                    f.close()

        required.extend(list(packages))

        # logos
        required.extend(["%s-logos" % (self.conf.product.lower(),),
                         "%s-release" % (self.conf.product.lower(),)])

        return required

    def add_packages(self, packages):
        for package in packages:
            ok = self.yum.add_package(package)
            if not ok:
                self.se.warning("No package '%s' available" (package,))

    def install_packages(self):
        # XXX why do we need this?
        os.symlink(os.path.join("/", "tmp"),
                   os.path.join(self.conf.treedir, "var", "lib", "xkb"))

        self.yum.install()

    def copy_updates(self):
        if self.conf.updates and os.path.isdir(self.conf.updates):
            copy(src_root=self.conf.updates, src_path="*",
                 dst_root=self.conf.treedir, dst_path="")

        self.conf.delAttr("updates")

    def fix_udev_links(self):
        # these links are broken by default (at least on i386)
        for filename in ("udevcontrol", "udevsettle", "udevtrigger"):
            filename = os.path.join(self.conf.treedir, "sbin", filename)
            if os.path.islink(filename):
                os.unlink(filename)
                os.symlink("udevadm", filename)

    def remove_modules_broken_links(self):
        # remove build and source links from modules directories
        build = os.path.join(self.conf.treedir, "lib", "modules", "*", "build")
        build_files = glob.glob(build)

        source = os.path.join(self.conf.treedir, "lib", "modules", "*", "source")
        source_files = glob.glob(source)

        [os.unlink(filename) for filename in build_files + source_files
                if os.path.islink(filename)]

    def get_kernelfiles(self):
        kerneldir = os.path.join(self.conf.treedir, "boot")
        
        if self.conf.buildarch == "ia64":
            kerneldir = os.path.join(kerneldir, "efi", "EFI", "redhat")

        return glob.glob(os.path.join(kerneldir, "vmlinuz-*"))

    def run(self):
        self.so.info("Getting the list of packages")
        packages = self.get_packages()

        self.so.info("Running yum")
        self.add_packages(packages)
        self.install_packages()

        self.so.info("Copying the updates")
        self.copy_updates()

        self.so.info("Fixing udev links")
        self.fix_udev_links()

        self.so.info("Removing build and source links in modules directories")
        self.remove_modules_broken_links()

        return self.get_kernelfiles()


    ####################
    ### tree scrubs

    def copy_stubs(self):
        for file in ("raidstart", "raidstop", "losetup", "list-harddrives",
                "loadkeys", "mknod", "syslogd"):

            src = os.path.join(self.conf.treedir, "usr", "lib", "anaconda",
                    "%s-stub" % (file,))
            dst = os.path.join(self.conf.treedir, "usr", "bin", file)

            shutil.copy2(src, dst)

    def create_dogtail_conf(self):
        dogtailconf = os.path.join(self.conf.datadir, "dogtail", "%gconf.xml")

        if os.path.isfile(dogtailconf):
            dst = os.path.join(self.conf.treedir, ".gconf", "desktop", "gnome",
                    "interface")
            
            os.makedirs(dst)
            shutil.copy2(dogtailconf, dst)

            touch(os.path.join(self.conf.treedir, ".gconf", "desktop",
                    "%gconf.xml"))
            touch(os.path.join(self.conf.treedir, ".gconf", "desktop", "gnome",
                    "%gconf.xml"))

    def create_libuser_conf(self):
        src = os.path.join(self.conf.datadir, "libuser", "libuser.conf")
        dst = os.path.join(self.conf.treedir, "etc", "libuser.conf")
        shutil.copy2(src, dst)

    def create_selinux_conf(self):
        if os.path.exists(os.path.join(self.conf.treedir, "etc", "selinux",
                "targeted")):

            src = os.path.join(self.conf.datadir, "selinux", "config")
            dst = os.path.join(self.conf.treedir, "etc", "selinux", "config")
            shutil.copy2(src, dst)

    def configure_fedorakmod(self):
        fedorakmodconf = os.path.join(self.conf.treedir, "etc", "yum",
                "pluginconf.d", "fedorakmod.conf")

        replace(fedorakmodconf, r"\(installforallkernels\) = 0", r"\1 = 1")

    def copy_bootloaders(self):
        bootpath = os.path.join(self.conf.treedir, "usr", "lib",
                "anaconda-runtime", "boot")

        if not os.path.isdir(bootpath):
            os.makedirs(bootpath)

        if self.conf.buildarch in ("i386", "i586", "x86_64"):
            for file in os.listdir(os.path.join(self.conf.treedir, "boot")):
                if file.startswith("memtest"):
                    src = os.path.join(self.conf.treedir, "boot", file)
                    dst = os.path.join(bootpath, file)
                    shutil.copy2(src, dst)
        elif self.conf.buildarch == "sparc":
            for file in os.listdir(os.path.join(self.conf.treedir, "boot")):
                if file.endswith(".b"):
                    src = os.path.join(self.conf.treedir, "boot", file)
                    dst = os.path.join(bootpath, file)
                    shutil.copy2(src, dst)
        elif self.conf.buildarch in ("ppc", "ppc64"):
            src = os.path.join(self.conf.treedir, "boot", "efika.forth")
            shutil.copy2(src, bootpath)
        elif self.conf.buildarch == "alpha":
            src = os.path.join(self.conf.treedir, "boot", "bootlx")
            shutil.copy2(src, bootpath)
        elif self.conf.buildarch == "ia64":
            srcdir = os.path.join(self.conf.treedir, "boot", "efi", "EFI", "redhat")
            copy(src_root=srcdir, src_path="*",
                    dst_root=bootpath, dst_dir="")

    def move_repos(self):
        src = os.path.join(self.conf.treedir, "etc", "yum.repos.d")
        dst = os.path.join(self.conf.treedir, "etc", "anaconda.repos.d")
        shutil.move(src, dst)

    def move_anaconda_files(self):
        # move anaconda executable
        src = os.path.join(self.conf.treedir, "usr", "sbin", "anaconda")
        dst = os.path.join(self.conf.treedir, "usr", "bin", "anaconda")
        shutil.move(src, dst)

        # move anaconda libraries
        srcdir = os.path.join(self.conf.treedir, "usr", "lib", "anaconda-runtime")
        dst = os.path.join(self.conf.treedir, "usr", self.conf.libdir)
        move(src_root=srcdir, src_path="lib*",
                dst_root=dst, dst_path="")

    def create_debug_directories(self):
        os.makedirs(os.path.join(self.conf.treedir, "usr", "lib", "debug"))
        os.makedirs(os.path.join(self.conf.treedir, "usr", "src", "debug"))

    def create_modules_symlinks(self):
        os.makedirs(os.path.join(self.conf.treedir, "modules"))
        os.makedirs(os.path.join(self.conf.treedir, "firmware"))

        # XXX are we sure we want to do this?
        remove(os.path.join(self.conf.treedir, "lib", "modules"))
        remove(os.path.join(self.conf.treedir, "lib", "firmware"))
        os.symlink("/modules", os.path.join(self.conf.treedir, "lib", "modules"))
        os.symlink("/firmware", os.path.join(self.conf.treedir, "lib", "firmware"))

    def fix_joe_links(self):
        joedir = os.path.join(self.conf.treedir, "etc", "joe")

        if os.path.isdir(joedir):
            os.symlink("jpicorc", os.path.join(joedir, "picorc"))
            os.symlink("jpicorc", os.path.join(joedir, "jnanorc"))
            os.symlink("jpicorc", os.path.join(joedir, "nanorc"))
            os.symlink("jmacsrc", os.path.join(joedir, "emacsrc"))
            os.symlink("jmacs", os.path.join(self.conf.treedir, "usr", "bin",
                    "emacs"))
            os.symlink("jpico", os.path.join(self.conf.treedir, "usr", "bin",
                    "pico"))
            os.symlink("jpico", os.path.join(self.conf.treedir, "usr", "bin",
                    "nano"))

    def fix_man_pages(self):
        # fix up some links for man page related stuff
        for file in ["nroff", "groff", "iconv", "geqn", "gtbl", "gpic", "grefer"]:
            src = os.path.join("mnt", "sysimage", "usr", "bin", file)
            dst = os.path.join(self.conf.treedir, "usr", "bin", file)
            if not os.path.isfile(dst):
                os.symlink(src, dst)

        # fix /etc/man.config to point into /mnt/sysimage
        manconfig = os.path.join(self.conf.treedir, "etc", "man.config")
       
        # don't change MANPATH_MAP lines now
        replace(manconfig, r"^MANPATH[^_MAP][ \t]*", r"&/mnt/sysimage")
        # change MANPATH_MAP lines now
        replace(manconfig, r"^MANPATH_MAP[ \t]*[a-zA-Z0-9/]*[ \t]*",
                r"&/mnt/sysimage")

    def remove_gtk_stuff(self):
        # figure out the gtk+ theme to keep
        gtkrc = os.path.join(self.conf.treedir, "etc", "gtk-2.0", "gtkrc")
        
        gtk_theme_name = None
        gtk_engine = None
        gtk_icon_themes = []

        if os.path.isfile(gtkrc):
            f = open(gtkrc, "r")
            lines = f.readlines()
            f.close()

            for line in lines:
                line = line.strip()
                if line.startswith("gtk-theme-name"):
                    gtk_theme_name = line[line.find("=") + 1:]
                    gtk_theme_name = gtk_theme_name.replace('"', "").strip()

                    # find the engine for this theme
                    gtkrc = os.path.join(self.conf.treedir, "usr", "share",
                            "themes", gtk_theme_name, "gtk-2.0", "gtkrc")
                    if os.path.isfile(gtkrc):
                        f = open(gtkrc, "r")
                        engine_lines = f.readlines()
                        f.close()

                        for engine_line in engine_lines:
                            engine_line = engine_line.strip()
                            if engine_line.find("engine") != -1:
                                gtk_engine = engine_line[engine_line.find('"') + 1:]
                                gtk_engine = gtk_engine.replace('"', "").strip()
                                break

                elif line.startswith("gtk-icon-theme-name"):
                    icon_theme = line[line.find("=") + 1:]
                    icon_theme = icon_theme.replace('"', "").strip()
                    gtk_icon_themes.append(icon_theme)

                    # bring in all inherited themes
                    while True:
                        icon_theme_index = os.path.join(self.conf.treedir, "usr",
                                "share", "icons", icon_theme, "index.theme")
                        if os.path.isfile(icon_theme_index):
                            inherits = False
                            f = open(icon_theme_index, "r")
                            icon_lines = f.readlines()
                            f.close()

                            for icon_line in icon_lines:
                                icon_line = icon_line.strip()
                                if icon_line.startswith("Inherits="):
                                    inherits = True
                                    icon_theme = icon_line[icon_line.find("=") + 1:]
                                    icon_theme = icon_theme.replace('"', "").strip()
                                    gtk_icon_themes.append(icon_theme)
                                    break

                            if not inherits:
                                break
                        else:
                            break

            # remove themes we don't need
            theme_path = os.path.join(self.conf.treedir, "usr", "share", "themes")
            if os.path.isdir(theme_path):
                for theme in filter(lambda theme: theme != gtk_theme_name,
                        os.listdir(theme_path)):

                    theme = os.path.join(theme_path, theme)
                    shutil.rmtree(theme, ignore_errors=True)

            # remove icons we don't need
            icon_path = os.path.join(self.conf.treedir, "usr", "share", "icons")
            if os.path.isdir(icon_path):
                for icon in filter(lambda icon: icon not in gtk_icon_themes,
                        os.listdir(icon_path)):

                    icon = os.path.join(icon_path, icon)
                    shutil.rmtree(icon, ignore_errors=True)

            # remove engines we don't need
            tmp_path = os.path.join(self.conf.treedir, "usr", self.conf.libdir,
                    "gtk-2.0")
            if os.path.isdir(tmp_path):
                fnames = map(lambda fname: os.path.join(tmp_path, fname, "engines"),
                        os.listdir(tmp_path))
                dnames = filter(lambda fname: os.path.isdir(fname), fnames)
                for dir in dnames:
                    engines = filter(lambda engine: engine.find(gtk_engine) == -1,
                            os.listdir(dir))
                    for engine in engines:
                        engine = os.path.join(dir, engine)
                        os.unlink(engine)

    def remove_locales(self):
        langtable = os.path.join(self.conf.treedir, "usr", "lib", "anaconda",
                "lang-table")
        localepath = os.path.join(self.conf.treedir, "usr", "share", "locale")

        if os.path.isfile(langtable):
            locales = set()
            all_locales = set()

            f = open(langtable, "r")
            lines = f.readlines()
            f.close()

            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                fields = line.split("\t")

                if os.path.isdir(os.path.join(localepath, fields[1])):
                    locales.add(fields[1])

                locale = fields[3].split(".")[0]
                if os.path.isdir(os.path.join(localepath, locale)):
                    locales.add(locale)

            for locale in os.listdir(localepath):
                all_locales.add(locale)

            locales_to_remove = list(all_locales.difference(locales))
            for locale in locales_to_remove:
                rmpath = os.path.join(localepath, locale)
                shutil.rmtree(rmpath, ignore_errors=True)

    def remove_unnecessary_files(self):
        to_remove = set()

        for root, dirs, files in os.walk(self.conf.treedir):
            for file in files:
                path = os.path.join(root, file)

                if fnmatch.fnmatch(path, "*.a"):
                    if path.find("kernel-wrapper/wrapper.a") == -1:
                        to_remove.add(path)
                elif fnmatch.fnmatch(path, "lib*.la"):
                    if path.find("usr/" + self.conf.libdir + "/gtk-2.0") == -1:
                        to_remove.add(path)
                elif fnmatch.fnmatch(path, "*.py"):
                    to_remove.add(path + "o")

                    try:
                        os.unlink(path + "c")
                    except OSError:
                        pass

                    os.symlink("/dev/null", path + "c")

        for file in to_remove:
            try:
                os.unlink(file)
            except OSError:
                pass

        # remove libunicode-lite
        remove(os.path.join(self.conf.treedir, "usr", self.conf.libdir,
                "libunicode-lite*"))

    def remove_python_stuff(self):
        for fname in ["bsddb", "compiler", "curses", "distutils", "email",
                "encodings", "hotshot", "idlelib", "test",
                "doctest.py", "pydoc.py"]:

            remove(os.path.join(self.conf.treedir, "usr", self.conf.libdir,
                    "python?.?", fname))

    def remove_unnecessary_directories(self):
        for dir in ["boot", "home", "root", "tmp"]:
            remove(os.path.join(self.conf.treedir, dir))

    def scrub(self):
        self.copy_stubs()
        self.create_dogtail_conf()
        self.create_libuser_conf()
        self.create_selinux_conf()
        self.configure_fedorakmod()

        self.copy_bootloaders()
        self.move_repos()
        self.move_anaconda_files()

        self.create_debug_directories()
        self.create_modules_symlinks()

        self.fix_joe_links()
        self.fix_man_pages()

        self.remove_gtk_stuff()
        self.remove_locales()
        self.remove_unnecessary_files()
        self.remove_python_stuff()

        self.remove_unnecessary_directories()
