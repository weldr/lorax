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

__all__ = ["joinpaths", "touch", "replace", "chown_", "chmod_",
           "create_loop_dev", "remove_loop_dev",
           "create_dm_dev", "remove_dm_dev"]


import sys
import os
import re
import fileinput
import pwd
import grp
import glob
import subprocess
import shutil


def joinpaths(*args, **kwargs):
    path = os.path.sep.join(args)

    if kwargs.get("follow_symlinks"):
        return os.path.realpath(path)
    else:
        return path


def touch(fname):
    with open(fname, "w") as _:
        pass


def replace(fname, find, replace):
    fin = fileinput.input(fname, inplace=1)
    pattern = re.compile(find)

    for line in fin:
        line = pattern.sub(replace, line)
        sys.stdout.write(line)

    fin.close()


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
                nested = joinpaths(fname, nested)
                chown_(nested, user, group, recursive)


def chmod_(path, mode, recursive=False):
    for fname in glob.iglob(path):
        os.chmod(fname, mode)

        if recursive and os.path.isdir(fname):
            for nested in os.listdir(fname):
                nested = joinpaths(fname, nested)
                chmod_(nested, mode, recursive)


def create_loop_dev(fname):
    cmd = ["losetup", "-f"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    retcode = proc.wait()
    if not retcode == 0:
        return None

    loopdev = proc.stdout.read().strip()

    cmd = ["losetup", loopdev, fname]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    retcode = proc.wait()
    if not retcode == 0:
        return None

    return loopdev


def remove_loop_dev(dev):
    cmd = ["losetup", "-d", dev]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    return proc.wait()


def create_dm_dev(name, size, loopdev):
    table = '0 {0} linear {1} 0'.format(size, loopdev)

    cmd = ["dmsetup", "create", name, "--table", table]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    retcode = proc.wait()
    if not retcode == 0:
        return None

    return joinpaths("/dev/mapper", name)


def remove_dm_dev(dev):
    cmd = ["dmsetup", "remove", dev]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    return proc.wait()


def cpfile(src, dst):
    shutil.copy2(src, dst)
    if os.path.isdir(dst):
        dst = joinpaths(dst, os.path.basename(src))

    return dst

def remove(target):
    if os.path.isdir(target):
        shutil.rmtree(target)
    else:
        os.unlink(target)
