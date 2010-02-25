#
# sysutils.py
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

__all__ = ["mkdir_", "makedirs_", "remove_", "symlink_", "touch_",
           "chown_", "chmod_", "replace_", "scopy_", "dcopy_"]


import sys
import os
import shutil
import glob
import fileinput
import re
import pwd
import grp
import commands


class SysUtilsError(Exception):
    pass


class SmartCopyError(SysUtilsError):
    pass


class LinkerError(SysUtilsError):
    pass


def mkdir_(dir):
    if not os.path.isdir(dir):
        os.mkdir(dir)


def makedirs_(dir):
    if not os.path.isdir(dir):
        os.makedirs(dir)


def remove_(path):
    for fname in glob.iglob(path):
        if os.path.islink(fname) or os.path.isfile(fname):
            os.unlink(fname)
        else:
            shutil.rmtree(fname)


def symlink_(link_target, link_name, force=True):
    if force and (os.path.islink(link_name) or os.path.isfile(link_name)):
        os.unlink(link_name)

    os.symlink(link_target, link_name)


def touch_(fname):
    if os.path.exists(fname):
        os.utime(fname, None)
    else:
        with open(fname, "w") as f:
            pass


def chown_(path, user=None, group=None, recursive=False):
    uid = gid = -1

    if user is not None:
        uid = pwd.getpwnam(user)[2]
    if group is not None:
        gid = grp.getgrnam(group)[2]

    for fname in glob.iglob(path):
        os.chown(fname, uid, gid)

        if recursive and os.path.isdir(fname):
            for nested in os.listdir(fname):
                nested = os.path.join(fname, nested)
                chown_(nested, user, group, recursive)


def chmod_(path, mode, recursive=False):
    for fname in glob.iglob(path):
        os.chmod(fname, mode)

        if recursive and os.path.isdir(fname):
            for nested in os.listdir(fname):
                nested = os.path.join(fname, nested)
                chmod_(nested, mode, recursive)


def replace_(fname, find, replace):
    fin = fileinput.input(fname, inplace=1)
    pattern = re.compile(find)

    for line in fin:
        line = pattern.sub(replace, line)
        sys.stdout.write(line)

    fin.close()


def scopy_(src_path, dst_path, src_root="/", dst_root="/", symlinks=True,
           ignore_errors=False):

    __copy(src_path, dst_path, src_root, dst_root,
           symlinks, deps=False, ignore_errors=ignore_errors)


def dcopy_(src_path, dst_path, src_root="/", dst_root="/", symlinks=True,
           ignore_errors=False):

    __copy(src_path, dst_path, src_root, dst_root,
           symlinks, deps=True, ignore_errors=ignore_errors)


def __copy(src_path, dst_path, src_root="/", dst_root="/",
           symlinks=True, deps=False, ignore_errors=False):

    if not src_root.endswith("/"):
        src_root += "/"
    if not dst_root.endswith("/"):
        dst_root += "/"

    smartcopy = SmartCopy(src_root, dst_root, symlinks, deps, ignore_errors)

    src = os.path.join(src_root, src_path)
    pattern = re.compile(r"(\*|\?|\[.*?\])")
    if pattern.search(src):
        fnames = glob.glob(src)
    else:
        fnames = [src]

    if not fnames and not ignore_errors:
        err_msg = "cannot stat '{0}': No such file or directory"
        raise SysUtilsError(err_msg.format(src))

    for fname in fnames:
        fname = fname.replace(src_root, "", 1)
        smartcopy.copy(fname, dst_path)

    smartcopy.process()


# XXX
class SmartCopy(object):

    def __init__(self, src_root="/", dst_root="/", symlinks=True, deps=False,
                 ignore_errors=False):

        self.src_root = src_root
        self.dst_root = dst_root
        self.symlinks = symlinks
        self.deps = deps
        self.ignore_errors = ignore_errors

        self.linker = Linker(src_root)

        self.clear()

    def clear(self):
        self.makedirs = []
        self.copyfiles = set()
        self.links = set()
        self.errors = []

    def copy(self, src_path, dst_path):
        src = os.path.normpath(os.path.join(self.src_root, src_path))
        dst = os.path.normpath(os.path.join(self.dst_root, dst_path))

        # check if the source path exists
        if not os.path.exists(src):
            err_msg = "cannot stat '{0}': No such file or directory"
            err_msg = err_msg.format(src)
            if not self.ignore_errors:
                raise SmartCopyError(err_msg)
            else:
                self.errors.append(err_msg)
                return

        if os.path.isfile(src):
            self.__copy_file(src_path, dst_path, src, dst)
        elif os.path.isdir(src):
            self.__copy_dir(src_path, dst_path, src, dst)

    def __copy_file(self, src_path, dst_path, src, dst):
        # if destination is an existing directory,
        # append the source filename to the destination
        if os.path.isdir(dst):
            dst = os.path.join(dst, os.path.basename(src))

            # check if the new destination is still an existing directory
            if os.path.isdir(dst):
                err_msg = "cannot overwrite directory '{0}' with non-directory"
                err_msg = err_msg.format(dst)
                if not self.ignore_errors:
                    raise SmartCopyError(err_msg)
                else:
                    self.errors.append(err_msg)
                    return

        if os.path.islink(src):
            self.__copy_link(src_path, dst_path, src, dst)
        else:
            self.copyfiles.add((src, dst))

    def __copy_dir(self, src_path, dst_path, src, dst):
            # append the source directory name to the destination path
            dirname = os.path.basename(src)
            new_dst = os.path.join(dst, dirname)

            # remove the trailing "/"
            if new_dst.endswith("/"):
                new_dst = new_dst[:-1]

            if os.path.islink(src):
                self.__copy_link(src_path, dst_path, src, new_dst, dir=True)
            else:
                # create the destination directory
                if not os.path.isdir(new_dst) and new_dst not in self.makedirs:
                    self.makedirs.append(new_dst)
                elif os.path.isfile(new_dst):
                    err_msg = "cannot overwrite file '{0}' with directory"
                    err_msg = err_msg.format(new_dst)
                    if not self.ignore_errors:
                        raise SmartCopyError(err_msg)
                    else:
                        self.errors.append(err_msg)
                        return

                new_dst_path = os.path.join(dst_path, dirname)

                try:
                    fnames = os.listdir(src)
                except OSError as why:
                    err_msg = "cannot list directory '{0}': {1}'"
                    err_msg = err_msg.format(src, why)
                    if not self.ignore_errors:
                        raise SmartCopyError(err_msg)
                    else:
                        self.errors.append(err_msg)
                        return

                for fname in fnames:
                    fname = os.path.join(src_path, fname)
                    self.copy(fname, new_dst_path)

    def __copy_link(self, src_path, dst_path, src, dst, dir=False):
        if not self.symlinks:
            # TODO
            raise NotImplementedError

        # read the link target
        link_target = os.readlink(src)

        # get the target source and destination paths
        target_src_path = os.path.join(os.path.dirname(src_path), link_target)
        target_dst_dir = os.path.join(dst_path, os.path.dirname(link_target))

        # if the link target is an absolute path,
        # make sure we copy it relative to the dst_root
        if target_dst_dir.startswith("/"):
            target_dst_dir = target_dst_dir[1:]

        # remove the trailing "/"
        if target_dst_dir.endswith("/"):
            target_dst_dir = target_dst_dir[:-1]

        # create the destination directory
        target_dst = os.path.join(self.dst_root, target_dst_dir)
        if not os.path.isdir(target_dst) and target_dst not in self.makedirs:
            self.makedirs.append(target_dst)

        # copy the target along with the link
        self.copy(target_src_path, target_dst_dir)

        # create the symlink named dst, pointing to link_target
        self.links.add((link_target, dst))

    def __get_deps(self):
        deps = set()

        for src, dst in self.copyfiles:
            if self.linker.is_elf(src):
                deps = deps.union(self.linker.get_deps(src))

        for src in deps:
            src_path = src.replace(self.src_root, "", 1)
            dst_path = os.path.dirname(src_path)

            # create the destination directory
            dst_dir = os.path.join(self.dst_root, dst_path)
            if not os.path.isdir(dst_dir) and dst_dir not in self.makedirs:
                self.makedirs.append(dst_dir)

            self.copy(src_path, dst_path)

    def process(self):
        if self.deps:
            self.__get_deps()

        # create required directories
        map(makedirs_, self.makedirs)

        # remove the dst, if it is a link to src
        for src, dst in self.copyfiles:
            if os.path.realpath(dst) == src:
                os.unlink(dst)

        # copy all the files
        try:
            map(lambda (src, dst): shutil.copy2(src, dst), self.copyfiles)
        except shutil.Error as why:
            err_msg = "error copying file {0} -> {1}: {2}"
            err_msg = err_msg.format(src, dst, why)
            raise SmartCopyError(err_msg)

        # create symlinks
        try:
            map(lambda (target, name): symlink_(target, name), self.links)
        except OSError as why:
            err_msg = "error creating symlink {0} -> {1}: {2}"
            err_msg = err_msg.format(name, target, why)
            raise SmartCopyError(err_msg)


# XXX
class Linker(object):

    LIBDIRS = ("lib64",
               "usr/lib64",
               "lib",
               "usr/lib")

    LDDBIN = "/usr/bin/ldd"
    FILEBIN = "/usr/bin/file"

    def __init__(self, root="/"):
        libdirs = map(lambda path: os.path.join(root, path), self.LIBDIRS)
        libdirs = ":".join(libdirs)

        ld_linux = None
        pattern = re.compile(r'^RTLDLIST="?(?P<ld_linux>.*?)"?$')

        with open(self.LDDBIN, "r") as f:
            for line in f:
                m = pattern.match(line.strip())
                if m:
                    ld_linux = m.group("ld_linux")
                    break

        if ld_linux:
            ld_linux = filter(os.path.isfile, ld_linux.split())

        if not ld_linux:
            raise LinkerError("cannot find the ld_linux executable")

        self.lddcmd = "LD_LIBRARY_PATH={0} {1} --list"
        self.lddcmd = self.lddcmd.format(libdirs, ld_linux[0])

        self.pattern = re.compile(r"^[-._/a-zA-Z0-9]+\s=>\s"
                                  r"(?P<lib>[-._/a-zA-Z0-9]+)"
                                  r"\s\(0x[0-9a-f]+\)$")

    def is_elf(self, fname):
        cmd = "{0} --brief {1}".format(self.FILEBIN, fname)
        err, stdout = commands.getstatusoutput(cmd)
        if err:
            raise LinkerError(stdout)

        if not stdout.count("ELF"):
            return False

        return True

    def get_deps(self, fname):
        cmd = "{0} {1}".format(self.lddcmd, fname)
        err, stdout = commands.getstatusoutput(cmd)
        if err:
            raise LinkerError(stdout)

        deps = set()
        for line in stdout.splitlines():
            m = self.pattern.match(line.strip())
            if m:
                deps.add(m.group("lib"))

        return deps
