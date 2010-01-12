#
# install.py
# class for creating install images
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

import os
import shutil
import glob
import fnmatch
import re
import commands
import pwd
import grp
import stat

import config
import output
import lcs
import utils


class InstallImage(object):

    def __init__(self):
        self.conf = config.LoraxConfig.get()
        self.paths = config.LoraxPaths.get()
        self.output = output.Terminal.get()

        self.actions = self.get_actions_from_template()

    def get_actions_from_template(self):
        variables = { "instroot" : self.conf.installtree }

        if self.conf.scrubs_template is not None:
            template = lcs.TemplateParser(variables)
            return template.get_actions(self.conf.scrubs_template)

        return []

    def move_shared_files(self):
        dirs = [os.path.join(self.paths.INSTALLTREE_DATADIR, "noarch"),
                os.path.join(self.paths.INSTALLTREE_DATADIR, self.conf.arch)]

        self.output.info(":: copying the custom install tree files")
        for dir in [dir for dir in dirs if os.path.isdir(dir)]:
            utils.scopy(src_root=dir, src_path="*",
                        dst_root=self.conf.installtree, dst_path="")

    def process_actions(self):
        for action in self.actions:
            action.execute()

    # XXX why do we need this?
    def copy_stubs(self):
        for file in ("raidstart", "raidstop", "losetup", "list-harddrives",
                     "loadkeys", "mknod", "syslogd"):

            src = os.path.join(self.conf.installtree, "usr", "lib", "anaconda",
                               "%s-stub" % file)
            dst = os.path.join(self.conf.installtree, "usr", "bin", file)
            shutil.copy2(src, dst)

    # XXX i cannot find this in the repos for f12
    def configure_fedorakmod(self):
        if os.path.isfile(self.paths.FEDORAKMODCONF):
            utils.replace(self.paths.FEDORAKMODCONF,
                          r"installforallkernels = 0",
                          r"installforallkernels = 1")

    # XXX why do we need this?
    def copy_bootloaders(self):
        if self.conf.arch in ("i386", "i586", "x86_64"):
            for f in glob.glob(os.path.join(self.paths.BOOTDIR, "memtest*")):
                shutil.copy2(f, self.paths.ANACONDA_BOOT)

        elif self.conf.arch == "sparc":
            for f in glob.glob(os.path.join(self.paths.BOOTDIR, "*.b")):
                shutil.copy2(f, self.paths.ANACONDA_BOOT)

        elif self.conf.arch in ("ppc", "ppc64"):
            f = os.path.join(self.paths.BOOTDIR, "efika.forth")
            shutil.copy2(f, self.paths.ANACONDA_BOOT)

        # XXX alpha stuff should not be needed anymore
        #elif self.conf.arch == "alpha":
        #    f = os.path.join(self.paths.BOOTDIR, "bootlx")
        #    shutil.copy2(f, self.paths.ANACONDA_BOOT)

        elif self.conf.arch == "ia64":
            utils.scopy(src_root=self.paths.BOOTDIR_IA64, src_path="*",
                        dst_root=self.paths.ANACONDA_BOOT, dst_dir="")

    # XXX why do we need this?
    def move_repos(self):
        src = os.path.join(self.conf.installtree, "etc", "yum.repos.d")
        dst = os.path.join(self.conf.installtree, "etc", "anaconda.repos.d")
        shutil.move(src, dst)

    # XXX why do we need this?
    def move_anaconda_files(self):
        # move anaconda executable
        src = os.path.join(self.conf.installtree, "usr", "sbin", "anaconda")
        dst = os.path.join(self.conf.installtree, "usr", "bin", "anaconda")
        shutil.move(src, dst)

        # move anaconda libraries
        dstdir = os.path.join(self.conf.installtree, "usr", self.conf.libdir)
        utils.scopy(src_root=self.paths.ANACONDA_RUNTIME, src_path="lib*",
                    dst_root=dstdir, dst_path="")

        utils.remove(os.path.join(self.paths.ANACONDA_RUNTIME, "lib*"))

    # XXX this saves 40 MB
    def create_modules_symlinks(self):
        utils.mkdir(os.path.join(self.conf.installtree, "modules"))
        utils.mkdir(os.path.join(self.conf.installtree, "firmware"))

        utils.remove(os.path.join(self.conf.installtree, "lib", "modules"))
        utils.remove(os.path.join(self.conf.installtree, "lib", "firmware"))

        utils.symlink("/modules",
                      os.path.join(self.conf.installtree, "lib", "modules"))
        utils.symlink("/firmware",
                      os.path.join(self.conf.installtree, "lib", "firmware"))

    # XXX why do we need this?
    def fix_man_pages(self):
        # fix up some links for man page related stuff
        for file in ("nroff", "groff", "iconv", "geqn", "gtbl", "gpic",
                     "grefer"):

            target = os.path.join("/mnt/sysimage/usr/bin", file)
            name = os.path.join(self.conf.installtree, "usr", "bin", file)

            if not os.path.isfile(name):
                utils.symlink(target, name)

        # fix /etc/man.config to point into /mnt/sysimage
        utils.replace(self.paths.MANCONFIG, r"^MANPATH\s+(\S+)",
                      "MANPATH\t/mnt/sysimage\g<1>")
        utils.replace(self.paths.MANCONFIG, r"^MANPATH_MAP\s+(\S+)\s+(\S+)",
                      "MANPATH_MAP\t\g<1>\t/mnt/sysimage\g<2>")

    # XXX this saves 2 MB
    def remove_gtk_stuff(self):
        # figure out the gtk+ theme to keep
        gtkrc = os.path.join(self.conf.installtree, "etc", "gtk-2.0", "gtkrc")

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
                    gtkrc = os.path.join(self.conf.installtree, "usr", "share",
                            "themes", gtk_theme_name, "gtk-2.0", "gtkrc")
                    if os.path.isfile(gtkrc):
                        f = open(gtkrc, "r")
                        engine_lines = f.readlines()
                        f.close()

                        for engine_l in engine_lines:
                            engine_l = engine_l.strip()
                            if engine_l.find("engine") != -1:
                                gtk_engine = engine_l[engine_l.find('"') + 1:]
                                gtk_engine = gtk_engine.replace('"', "").strip()
                                break

                elif line.startswith("gtk-icon-theme-name"):
                    icon_theme = line[line.find("=") + 1:]
                    icon_theme = icon_theme.replace('"', "").strip()
                    gtk_icon_themes.append(icon_theme)

                    # bring in all inherited themes
                    while True:
                        icon_theme_index = os.path.join(self.conf.installtree,
                                "usr", "share", "icons", icon_theme,
                                "index.theme")

                        if os.path.isfile(icon_theme_index):
                            inherits = False
                            f = open(icon_theme_index, "r")
                            icon_lines = f.readlines()
                            f.close()

                            for icon_l in icon_lines:
                                icon_l = icon_l.strip()
                                if icon_l.startswith("Inherits="):
                                    inherits = True
                                    icon_theme = icon_l[icon_l.find("=") + 1:]
                                    icon_theme = \
                                        icon_theme.replace('"', "").strip()

                                    gtk_icon_themes.append(icon_theme)
                                    break

                            if not inherits:
                                break
                        else:
                            break

            # remove themes we don't need
            theme_path = os.path.join(self.conf.installtree, "usr", "share",
                                      "themes")

            if os.path.isdir(theme_path):
                for theme in filter(lambda theme: theme != gtk_theme_name,
                                    os.listdir(theme_path)):

                    theme = os.path.join(theme_path, theme)
                    shutil.rmtree(theme, ignore_errors=True)

            # remove icons we don't need
            icon_path = os.path.join(self.conf.installtree, "usr", "share",
                                     "icons")

            if os.path.isdir(icon_path):
                for icon in filter(lambda icon: icon not in gtk_icon_themes,
                        os.listdir(icon_path)):

                    icon = os.path.join(icon_path, icon)
                    shutil.rmtree(icon, ignore_errors=True)

            # remove engines we don't need
            tmp_path = os.path.join(self.conf.installtree, "usr",
                                    self.conf.libdir, "gtk-2.0")

            if os.path.isdir(tmp_path):
                fnames = map(lambda fname: os.path.join(tmp_path, fname,
                    "engines"), os.listdir(tmp_path))

                dnames = filter(lambda fname: os.path.isdir(fname), fnames)
                for dir in dnames:
                    engines = filter(lambda e: e.find(gtk_engine) == -1,
                                     os.listdir(dir))
                    for engine in engines:
                        engine = os.path.join(dir, engine)
                        os.unlink(engine)

    # XXX this saves 5 MB
    def remove_locales(self):
        if os.path.isfile(self.paths.LANGTABLE):
            keep = set()

            with open(self.paths.LANGTABLE, "r") as f:
                lines = f.readlines()

            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                fields = line.split("\t")

                dir = os.path.join(self.paths.LOCALEPATH, fields[1])
                if os.path.isdir(dir):
                    keep.add(fields[1])

                locale = fields[3].split(".")[0]
                dir = os.path.join(self.paths.LOCALEPATH, locale)
                if os.path.isdir(dir):
                    keep.add(locale)

            for locale in os.listdir(self.paths.LOCALEPATH):
                if locale not in keep:
                    path = os.path.join(self.paths.LOCALEPATH, locale)
                    utils.remove(path)

    # XXX this saves 5 MB
    def remove_unnecessary_files(self):
        for root, dirs, files in os.walk(self.conf.installtree):
            for file in files:
                path = os.path.join(root, file)

                if fnmatch.fnmatch(path, "*.a"):
                    if path.find("kernel-wrapper/wrapper.a") == -1:
                        os.unlink(path)

                if fnmatch.fnmatch(path, "lib*.la"):
                    if path.find("usr/" + self.conf.libdir + "/gtk-2.0") == -1:
                        os.unlink(path)

                if fnmatch.fnmatch(path, "*.py"):
                    if os.path.isfile(path + "o"):
                        os.unlink(path + "o")
                    if os.path.isfile(path + "c"):
                        os.unlink(path + "c")

                    utils.symlink("/dev/null", path + "c")

        # remove libunicode-lite
        utils.remove(os.path.join(self.conf.installtree, "usr",
                                  self.conf.libdir, "libunicode-lite*"))

    # XXX this saves 1 MB
    def remove_python_stuff(self):
        for fname in ("bsddb", "compiler", "curses", "distutils", "email",
                      "encodings", "hotshot", "idlelib", "test",
                      "doctest.py", "pydoc.py"):

            utils.remove(os.path.join(self.conf.installtree, "usr",
                         self.conf.libdir, "python?.?", fname))

    # XXX the udev package should get fixed,
    # but for now, we have to fix it ourselves, otherwise we get an error
    def fix_udev_links(self):
        # these links are broken by default (at least on i386)
        for filename in ("udevcontrol", "udevsettle", "udevtrigger"):
            filename = os.path.join(self.conf.installtree, "sbin", filename)
            if os.path.islink(filename):
                os.unlink(filename)
                os.symlink("udevadm", filename)

    def move_bins(self):
        # move bin to usr/bin
        utils.scopy(src_root=self.conf.installtree,
                    src_path=os.path.join("bin", "*"),
                    dst_root=self.conf.installtree,
                    dst_path=os.path.join("usr", "bin"))
        utils.remove(os.path.join(self.conf.installtree, "bin"))

        # move sbin to /usr/sbin
        utils.scopy(src_root=self.conf.installtree,
                    src_path=os.path.join("sbin", "*"),
                    dst_root=self.conf.installtree,
                    dst_path=os.path.join("usr", "sbin"))
        utils.remove(os.path.join(self.conf.installtree, "sbin"))

        # fix broken links
        brokenlinks = []
        for dir in ("bin", "sbin"):
            dir = os.path.join(self.conf.installtree, "usr", dir)
            for root, dnames, fnames in os.walk(dir):
                for fname in fnames:
                    fname = os.path.join(root, fname)
                    if os.path.islink(fname) and not os.path.exists(fname):
                        brokenlinks.append(fname)

        for link in brokenlinks:
            target = os.readlink(link)
            newtarget = re.sub(r"^\.\./\.\./(bin|sbin)/(.*)$",
                               r"../\g<1>/\g<2>", target)

            if newtarget != target:
                os.unlink(link)
                utils.symlink(newtarget, link)

    def create_ld_so_conf(self):
        ldsoconf = os.path.join(self.conf.installtree, "etc", "ld.so.conf")
        utils.touch(ldsoconf)

        procdir = os.path.join(self.conf.installtree, "proc")
        if not os.path.isdir(procdir):
            utils.mkdir(procdir)

        cmd = "mount -t proc proc %s" % procdir
        err, output = commands.getstatusoutput(cmd)

        with open(ldsoconf, "w") as f:
            f.write("/usr/kerberos/%s\n" % self.conf.libdir)

        cwd = os.getcwd()
        os.chdir(self.conf.installtree)

        # XXX os.chroot does not support exiting from the root
        cmd = "/usr/sbin/chroot %s /sbin/ldconfig" % self.conf.installtree
        err, output = commands.getstatusoutput(cmd)

        os.chdir(cwd)

        cmd = "umount %s" % procdir
        err, output = commands.getstatusoutput(cmd)

        os.unlink(ldsoconf)

    def change_tree_permissions(self):
        root_uid = pwd.getpwnam("root")[2]
        root_gid = grp.getgrnam("root")[2]

        for root, dirs, files in os.walk(self.conf.installtree):
            os.chown(root, root_uid, root_gid)
            os.chmod(root, 0755)

            for file in files:
                # skip broken symlinks
                if not os.path.exists(file):
                    continue

                path = os.path.join(root, file)
                os.chown(path, root_uid, root_gid)

                mode = os.stat(path).st_mode
                if (mode & stat.S_IXUSR) or (mode & stat.S_IXGRP) \
                   or (mode & stat.S_IXOTH):
                    os.chmod(path, 0555)
                else:
                    os.chmod(path, 0444)

    def prepare(self):
        # copy the .buildstamp
        shutil.copy2(self.conf.buildstamp, self.conf.installtree)

        self.move_shared_files()
        self.process_actions()

        self.copy_stubs()
        self.configure_fedorakmod()
        self.copy_bootloaders()
        self.move_repos()
        self.move_anaconda_files()
        self.create_modules_symlinks()
        self.fix_man_pages()
        self.remove_gtk_stuff()
        self.remove_locales()
        self.remove_unnecessary_files()
        self.remove_python_stuff()
        self.fix_udev_links()
        self.move_bins()

        self.create_ld_so_conf()
        self.change_tree_permissions()

    def create(self, type="squashfs"):
        self.prepare()

        installimg = os.path.join(self.conf.tempdir, "install.img")

        if os.path.exists(installimg):
            os.unlink(installimg)

        self.output.info(":: compressing the image file")

        if type == "squashfs":
            if not os.path.exists(self.paths.MKSQUASHFS):
                self.output.error("'%s' does not exist" % self.paths.MKSQUASHFS)
                return None

            cmd = "%s %s %s -all-root -no-fragments -no-progress" % \
                  (self.paths.MKSQUASHFS, self.conf.installtree, installimg)

            err, output = commands.getstatusoutput(cmd)
            if err:
                self.output.error(output)
                return None

        elif type == "cramfs":
            if not os.path.exists(self.paths.MKCRAMFS):
                self.output.error("'%s' does not exist" % self.paths.MKCRAMFS)
                return None

            crambs = ""
            if self.conf.arch == "sparc64":
                crambs = "--blocksize 8192"
            elif self.conf.arch == "sparc":
                crambs = "--blocksize 4096"

            cmd = "%s %s %s %s" % (self.paths.MKCRAMFS, crambs,
                                   self.conf.installtree, installimg)

            err, output = commands.getstatusoutput(cmd)
            if err:
                self.output.error(output)
                return None

        elif type == "ext2":
            # TODO
            raise NotImplementedError

        # edit the .treeinfo
        text = "[stage2]\nmainimage = images/install.img\n"
        utils.edit(self.conf.treeinfo, append=True, text=text)

        return installimg
