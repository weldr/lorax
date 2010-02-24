#
# base.py
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

from abc import ABCMeta, abstractmethod

import sys
import os
import shlex
import shutil

import config
import constants
import output
import ltmpl
from sysutils import *


class BaseLoraxClass(object):

    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self):
        self.conf = config.LoraxConfig()
        self.const = constants.LoraxConstants()
        self.cmd = constants.LoraxCommands()
        self.output = output.LoraxOutput()

    def pcritical(self, msg, file=sys.stdout):
        self.output.critical(msg, file)

    def perror(self, msg, file=sys.stdout):
        self.output.error(msg, file)

    def pwarning(self, msg, file=sys.stdout):
        self.output.warning(msg, file)

    def pinfo(self, msg, file=sys.stdout):
        self.output.info(msg, file)

    def pdebug(self, msg, file=sys.stdout):
        self.output.debug(msg, file)


class BaseImageClass(BaseLoraxClass):

    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self):
        BaseLoraxClass.__init__(self)
        self.srctree, self.dsttree = None, None

    def parse_template(self, template_file, variables={}):
        template = ltmpl.Template()

        for lineno, line in template.parse(template_file, variables):
            fields = shlex.split(line)
            func, args = fields[0], fields[1:]

            func = getattr(self, func, None)

            if not func:
                err = "invalid command: {0}"
                err = err.format(line)
                self.perror(err)
            else:
                try:
                    msg = "{0}({1})".format(func.__name__, ", ".join(args))
                    self.pdebug(msg)
                    func(*args)
                except TypeError:
                    err = "invalid command syntax: {0}"
                    err = err.format(line)
                    self.perror(err)

    def makedirs(self, *dirs):
        for dir in dirs:
            dir = os.path.join(self.dsttree, dir)
            makedirs_(dir)

    def remove(self, *fnames):
        for fname in fnames:
            fname = os.path.join(self.dsttree, fname)
            remove_(fname)

    def symlink(self, link_target, link_name):
        link_name = os.path.join(self.dsttree, link_name)
        symlink_(link_target, link_name)

    def touch(self, fname):
        fname = os.path.join(self.dsttree, fname)
        touch_(fname)

    def chown(self):
        # TODO
        raise NotImplementedError

    def chmod(self):
        # TODO
        raise NotImplementedError

    def replace(self):
        # TODO
        raise NotImplementedError

    def copy(self, fname, target=None):
        dstdir = os.path.dirname(fname)
        if target:
            dstdir = target

        if dstdir:
            makedirs_(os.path.join(self.dsttree, dstdir))

        dcopy_(fname, dstdir, self.srctree, self.dsttree)

    def rename(self, fname, target):
        fname = os.path.join(self.dsttree, fname)
        target = os.path.join(self.dsttree, target)
        shutil.move(fname, target)

    def edit(self, fname, text):
        fname = os.path.join(self.dsttree, fname)
        with open(fname, "w") as f:
            f.write(text)
