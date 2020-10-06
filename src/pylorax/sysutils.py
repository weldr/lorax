#
# sysutils.py
#
# Copyright (C) 2009-2019 Red Hat, Inc.
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

__all__ = ["joinpaths", "touch", "replace", "chown_", "chmod_", "remove",
           "linktree"]

import sys
import os
import re
import fileinput
import pwd
import grp
import glob
import shutil
import shlex
from configparser import ConfigParser

from pylorax.executils import runcmd

def joinpaths(*args, **kwargs):
    path = os.path.sep.join(args)

    if kwargs.get("follow_symlinks"):
        return os.path.realpath(path)
    else:
        return path


def touch(fname):
    with open(fname, "w") as f:
        f.write("")


def replace(fname, find, sub):
    fin = fileinput.input(fname, inplace=1)
    pattern = re.compile(find)

    for line in fin:
        line = pattern.sub(sub, line)
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


def cpfile(src, dst):
    shutil.copy2(src, dst)
    if os.path.isdir(dst):
        dst = joinpaths(dst, os.path.basename(src))

    return dst

def mvfile(src, dst):
    if os.path.isdir(dst):
        dst = joinpaths(dst, os.path.basename(src))
    os.rename(src, dst)
    return dst

def remove(target):
    if os.path.isdir(target) and not os.path.islink(target):
        shutil.rmtree(target)
    else:
        os.unlink(target)

def linktree(src, dst):
    runcmd(["/bin/cp", "-alx", src, dst])

def unquote(s):
    return ' '.join(shlex.split(s))

class UnquotingConfigParser(ConfigParser):
    """A ConfigParser, only with unquoting of the values."""
    # pylint: disable=arguments-differ
    def get(self, *args, **kwargs):
        ret = super().get(*args, **kwargs)
        if ret:
            ret = unquote(ret)
        return ret

def flatconfig(filename):
    """Use UnquotingConfigParser to read a flat config file (without
    section headers) by adding a section header.
    """
    with open (filename, 'r') as conffh:
        conftext = "[main]\n" + conffh.read()
    config = UnquotingConfigParser()
    config.read_string(conftext)
    return config['main']

def read_tail(path, size):
    """Read up to `size` kibibytes from the end of a file"""

    # NOTE: In py3 text files are unicode, not bytes so we have to open it as bytes
    with open(path, "rb") as f:
        return _read_file_end(f, size)

def _read_file_end(f, size):
    """Read the end of a file

    This skips to the next line to avoid starting in the middle of a unicode character.
    And returns "" in the case of a UnicodeDecodeError
    """
    f.seek(0, 2)
    end = f.tell()
    if end < 1024 * size:
        f.seek(0, 0)
    else:
        f.seek(end - (1024 * size))
    data = f.read()
    try:
        # Find the first newline in the block
        newline = min(1+data.find(b'\n'), len(data))
        text = data[newline:].decode("UTF-8")
    except UnicodeDecodeError:
        return ""
    return text
