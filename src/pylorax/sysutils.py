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

__all__ = ["joinpaths", "touch", "replace",
           "create_loop_dev", "remove_loop_dev",
           "create_dm_dev", "remove_dm_dev"]


import sys
import os
import re
import fileinput
import subprocess


def joinpaths(*args, **kwargs):
    path = os.path.sep.join(args)

    if kwargs.get("follow_symlinks"):
        return os.path.realpath(path)
    else:
        return path


def touch(fname):
    with open(fname, "w") as fobj:
        pass


def replace(fname, find, replace):
    fin = fileinput.input(fname, inplace=1)
    pattern = re.compile(find)

    for line in fin:
        line = pattern.sub(replace, line)
        sys.stdout.write(line)

    fin.close()


def create_loop_dev(fname):
    cmd = ["losetup", "-f"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    rc = p.wait()
    if not rc == 0:
        return None

    loopdev = p.stdout.read().strip()

    cmd = ["losetup", loopdev, fname]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    rc = p.wait()
    if not rc == 0:
        return None

    return loopdev


def remove_loop_dev(dev):
    cmd = ["losetup", "-d", dev]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    rc = p.wait()


def create_dm_dev(name, size, loopdev):
    table = '0 {0} linear {1} 0'.format(size, loopdev)

    cmd = ["dmsetup", "create", name, "--table", table]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    rc = p.wait()
    if not rc == 0:
        return None

    return joinpaths("/dev/mapper", name)


def remove_dm_dev(dev):
    cmd = ["dmsetup", "remove", dev]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    rc = p.wait()
