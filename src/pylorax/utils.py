#
# utils.py
#

import sys
import os
import shutil
import glob
import fileinput
import re
import pwd
import grp
import commands


def expand_path(path, globs=True):
    l = []

    m = re.match(r"(?P<prefix>.*){(?P<expand>.*?)}(?P<suffix>.*)", path)
    if m:
        for f in re.split(r"\s*,\s*", m.group("expand")):
            l.extend(expand_path(m.group("prefix") + f + m.group("suffix"),
                                 globs=globs))
    else:
        if globs:
            l.extend(glob.glob(path))
        else:
            l.append(path)

    return l


def remove(file):
    for fname in expand_path(file):
        if os.path.islink(fname) or os.path.isfile(fname):
            os.unlink(fname)
        else:
            shutil.rmtree(fname)


def __copy(src_path, dst_path, src_root="/", dst_root="/", symlinks=True,
           ignore_errors=False, deps=False):

    # ensure that roots end with "/"
    if not src_root.endswith("/"):
        src_root = src_root + "/"
    if not dst_root.endswith("/"):
        dst_root = dst_root + "/"

    smartcopy = SmartCopy(src_root, dst_root, symlinks, ignore_errors)

    src = os.path.join(src_root, src_path)
    for fname in expand_path(src):
        fname = fname.replace(src_root, "", 1)
        smartcopy.copy(fname, dst_path)

    if deps:
        smartcopy.get_deps()

    smartcopy.process()


def scopy(src_path, dst_path, src_root="/", dst_root="/", symlinks=True,
          ignore_errors=False):

    __copy(src_path, dst_path, src_root, dst_root, symlinks,
           ignore_errors, deps=False)


def dcopy(src_path, dst_path, src_root="/", dst_root="/", symlinks=True,
          ignore_errors=False):

    __copy(src_path, dst_path, src_root, dst_root, symlinks,
           ignore_errors, deps=True)


def symlink(link_target, link_name):
    if os.path.islink(link_name) or os.path.isfile(link_name):
        os.unlink(link_name)

    os.symlink(link_target, link_name)


def touch(file):
    if os.path.exists(file):
        os.utime(file, None)
    else:
        with open(file, "w") as f:
            pass


def mkdir(dir, mode=None):
    if mode is None:
        mode = 0755

    for d in expand_path(dir, globs=False):
        if not os.path.isdir(d):
            os.mkdir(d, mode)


def makedirs(dir, mode=None):
    if mode is None:
        mode = 0755

    for d in expand_path(dir, globs=False):
        if not os.path.isdir(d):
            os.makedirs(d, mode)


def chown(file, user=None, group=None, recursive=False):
    # if uid or gid is set to -1, it will not be changed
    uid = gid = -1

    if user is not None:
        uid = pwd.getpwnam(user)[2]
    if group is not None:
        gid = grp.getgrnam(group)[2]

    for fname in expand_path(file):
        os.chown(fname, uid, gid)

        if recursive and os.path.isdir(fname):
            for nested in os.listdir(fname):
                nested = os.path.join(fname, nested)
                chown(nested, user, group, recursive)


def chmod(file, mode, recursive=False):
    for fname in expand_path(file):
        os.chmod(fname, mode)

        if recursive and os.path.isdir(fname):
            for nested in os.listdir(fname):
                nested = os.path.join(fname, nested)
                chmod(nested, mode, recursive)


def edit(file, text, append=False):
    mode = "w"
    if append:
        mode = "a"

    with open(file, mode) as f:
        f.write(text)


def replace(file, find, replace):
    fin = fileinput.input(file, inplace=1)

    for line in fin:
        line = re.sub(find, replace, line)
        sys.stdout.write(line)

    fin.close()


class SmartCopyError(Exception):
    pass


class SmartCopy(object):

    def __init__(self, src_root="/", dst_root="/", symlinks=True,
                 ignore_errors=False):

        self.src_root = src_root
        self.dst_root = dst_root
        self.symlinks = symlinks
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

        # check if the source exists
        if not os.path.exists(src):
            err_msg = "cannot stat '%s': No such file or directory" % src
            if not self.ignore_errors:
                raise SmartCopyError(err_msg)
            else:
                self.errors.append(err_msg)
                return  # EXIT

        if os.path.isfile(src):
            self.__copy_file(src_path, dst_path, src, dst)
        elif os.path.isdir(src):
            self.__copy_dir(src_path, dst_path, src, dst)

    def __copy_file(self, src_path, dst_path, src, dst):
        # if destination is an existing directory,
        # append the source filename to the destination path
        if os.path.isdir(dst):
            dst = os.path.join(dst, os.path.basename(src))

            # check if the new destination is still an existing directory
            if os.path.isdir(dst):

                # do not overwrite a directory with a file
                err_msg = "cannot overwrite directory '%s' " \
                          "with non-directory" % dst
                if not self.ignore_errors:
                    raise SmartCopyError(err_msg)
                else:
                    self.errors.append(err_msg)
                    return  # EXIT

        if os.path.islink(src):

            if not self.symlinks:
                real_src = os.path.realpath(src)
                self.copyfiles.add((real_src, dst))
            else:
                self.__copy_link(src_path, dst_path, src, dst)

        else:

            self.copyfiles.add((src, dst))

    def __copy_dir(self, src_path, dst_path, src, dst):
            # append the source directory name to the destination path
            dirname = os.path.basename(src)
            new_dst = os.path.join(dst, dirname)

            # remove the trailing "/",
            # to make sure, that we don't try to create "dir" and "dir/"
            if new_dst.endswith("/"):
                new_dst = new_dst[:-1]

            if os.path.islink(src):

                if not self.symlinks:
                    real_src = os.path.realpath(src)

                    if not os.path.exists(new_dst) and \
                       new_dst not in self.makedirs:
                        self.makedirs.append(new_dst)

                    for fname in os.listdir(real_src):
                        fname = os.path.join(real_src, fname)
                        self.copy(fname, new_dst)

                else:
                    self.__copy_link(src_path, dst_path, src, new_dst)

            else:

                # create the destination directory, if it does not exist
                if not os.path.exists(new_dst) and \
                   new_dst not in self.makedirs:
                    self.makedirs.append(new_dst)

                elif os.path.isfile(new_dst):
                    err_msg = "cannot overwrite file '%s' with a directory" \
                              % new_dst
                    if not self.ignore_errors:
                        raise SmartCopyError(err_msg)
                    else:
                        self.errors.append(err_msg)
                        return  # EXIT

                new_dst_path = os.path.join(dst_path, dirname)

                try:
                    fnames = os.listdir(src)
                except OSError as why:
                    err_msg = "cannot list directory '%s': %s'" % (src, why)
                    if not self.ignore_errors:
                        raise SmartCopyError(err_msg)
                    else:
                        self.errors.append(err_msg)
                        return  # EXIT

                for fname in fnames:
                    fname = os.path.join(src_path, fname)
                    self.copy(fname, new_dst_path)

    def __copy_link(self, src_path, dst_path, src, dst):
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

        # create the destination directory, if it doesn't exist
        target_dst = os.path.join(self.dst_root, target_dst_dir)
        if not os.path.exists(target_dst) and \
           target_dst not in self.makedirs:
            self.makedirs.append(target_dst)

        # copy the target along with the link
        self.copy(target_src_path, target_dst_dir)

        # create the symlink named dst, pointing to link_target
        self.links.add((link_target, dst))

    def get_deps(self):
        deps = set()

        for src, dst in self.copyfiles:
            if self.linker.is_elf(src):
                deps = deps.union(self.linker.get_deps(src))

        for src in deps:
            src_path = src.replace(self.src_root, "", 1)
            dst_path = os.path.dirname(src_path)

            # create the destination directory
            dst_dir = os.path.join(self.dst_root, dst_path)
            if not os.path.exists(dst_dir) and \
               dst_dir not in self.makedirs:
                self.makedirs.append(dst_dir)

            self.copy(src_path, dst_path)

    def process(self):
        # create required directories
        map(mkdir, self.makedirs)

        # copy all the files

        # remove the dst, if it is a link to src
        for src, dst in self.copyfiles:
            if os.path.realpath(dst) == src:
                os.unlink(dst)

        map(lambda (src, dst): shutil.copy2(src, dst), self.copyfiles)

        # create symlinks
        map(lambda (target, name): symlink(target, name), self.links)


class LinkerError(Exception):
    pass


class Linker(object):

    LIBDIRS = ( "lib64",
                "usr/lib64",
                "lib",
                "usr/lib" )

    def __init__(self, root="/"):
        libdirs = map(lambda path: os.path.join(root, path), self.LIBDIRS)
        libdirs = ":".join(libdirs)

        ld_linux = None

        with open("/usr/bin/ldd", "r") as f:
            for line in f:
                m = re.match(r"^RTLDLIST=(?P<ld_linux>.*)$", line.strip())
                if m:
                    ld_linux = m.group("ld_linux")
                    break

        if ld_linux is None:
            raise LinkerError("unable to find the ld_linux executable")

        self.lddcmd = "LD_LIBRARY_PATH=%s %s --list" % (libdirs, ld_linux)
        self.pattern = re.compile(r"^[a-zA-Z0-9.-_/]*\s=>\s" \
                                  r"(?P<lib>[a-zA-Z0-9.-_/]*)" \
                                  r"\s\(0x[0-9a-f]*\)$")

    def is_elf(self, file):
        err, output = commands.getstatusoutput("file --brief %s" % file)
        if err:
            raise LinkerError("error getting the file type")

        if not output.startswith("ELF"):
            return False

        return True

    def get_deps(self, file):
        err, output = commands.getstatusoutput("%s %s" % (self.lddcmd, file))
        if err:
            raise LinkerError("error getting the file dependencies")

        deps = set()
        for line in output.splitlines():
            m = self.pattern.match(line.strip())
            if m:
                deps.add(m.group("lib"))

        return deps
