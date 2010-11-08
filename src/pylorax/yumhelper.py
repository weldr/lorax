#
# yumhelper.py
#
# Copyright (C) 2010  Red Hat, Inc.
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

import logging
logger = logging.getLogger("pylorax.yumhelper")

import sys
import os
import fnmatch
import glob
import shutil
import re

import yum
import yum.callbacks
import yum.rpmtrans

import output
from sysutils import joinpaths


class LoraxYumHelper(object):

    def __init__(self, yb):
        self.yb = yb
        self.installroot = self.yb.conf.installroot
        self.installed_packages = self.get_packages("installed")

    def install(self, pattern):
        try:
            self.yb.install(name=pattern)
        except yum.Errors.InstallError:
            try:
                self.yb.install(pattern=pattern)
            except yum.Errors.InstallError as e:
                msg = "cannot install {0}: {1}"
                logger.error(msg.format(pattern, e))
                return False

        return True

    def remove(self, package, pattern_list):
        if package:
            pkgobj = self.installed_packages.get(package)
            if not pkgobj:
                msg = "cannot erase {0}: Package not installed"
                logger.error(msg.format(package))
                return False

            # XXX match every file if no pattern specified
            if None in pattern_list:
                if len(pattern_list) > 1:
                    msg = "redundant patterns specified, " \
                          "removing whole package {0}"
                    logger.warning(msg.format(pkgobj.name))

                pattern_list = ["*"]

            logger.debug("erasing package {0}".format(pkgobj.name))

            total = len(pkgobj.filelist)
            newline = False
            count = 0
            for n, fname in enumerate(pkgobj.filelist, start=1):
                msg = "[{0:3.0f}%] erasing <b>{1.ui_envra}</b>\r"
                msg = msg.format(float(n) / float(total) * 100, pkgobj)
                output.LoraxOutput().write(msg)
                newline = True

                for pattern in pattern_list:
                    if fnmatch.fnmatch(fname, pattern):
                        fullpath = joinpaths(self.installroot, fname)
                        if (os.path.islink(fullpath) or
                            os.path.isfile(fullpath)):

                            os.unlink(fullpath)
                            logger.debug("removed {0}".format(fullpath))
                            count += 1

            if newline:
                output.LoraxOutput().write("\n")

            if not count:
                msg = "no files matched patterns {0}"
                logger.warning(msg.format(pattern_list))

        else:
            for pattern in pattern_list:
                msg = "erasing files matching pattern {0}"
                logger.info(msg.format(pattern))

                fullpattern = joinpaths(self.installroot, pattern)
                count = 0
                for fname in glob.glob(fullpattern):
                    if os.path.islink(fname) or os.path.isfile(fname):
                        os.unlink(fname)
                    else:
                        shutil.rmtree(fname)

                    logger.debug("removed {0}".format(fname))
                    count += 1

                if not count:
                    msg = "no files matched pattern {0}"
                    logger.error(msg.format(pattern))

        return True

    def process_transaction(self, skip_broken=True):
        # skip broken
        self.yb.conf.skip_broken = skip_broken
        self.yb.buildTransaction()

        self.yb.repos.setProgressBar(LoraxDownloadCallback())

        try:
            self.yb.processTransaction(callback=LoraxTransactionCallback(),
                                       rpmDisplay=LoraxRpmCallback())
        except yum.Errors.YumRPMCheckError as e:
            logger.error("yum transaction error: {0}".format(e))
            sys.exit(1)

        self.yb.closeRpmDB()

        self.installed_packages = self.get_packages("installed")

    def search(self, pattern):
        pl = self.yb.doPackageLists(patterns=[pattern])
        return pl.installed, pl.available

    def get_packages(self, type="available"):
        if type not in ("available", "installed"):
            raise TypeError

        pl = self.yb.doPackageLists(pkgnarrow=type)

        d = {}
        for pkgobj in getattr(pl, type):
            d[pkgobj.name] = pkgobj

        return d


class LoraxDownloadCallback(yum.callbacks.DownloadBaseCallback):

    def __init__(self):
        yum.callbacks.DownloadBaseCallback.__init__(self)
        self.output = output.LoraxOutput()

        pattern = "\((?P<pkgno>\d+)/(?P<total>\d+)\):\s+(?P<pkgname>.*)"
        self.pattern = re.compile(pattern)

    def updateProgress(self, name, frac, fread, ftime):
        """
            Update the progress bar
            @param name: filename
            @param frac: progress fraction (0 -> 1)
            @param fread: formated string containing BytesRead
            @param ftime: formated string containing remaining or elapsed time
        """

        m = self.pattern.match(name)

        pkgno = 0
        total = 0
        pkgname = "error"
        if m:
            pkgno = int(m.group("pkgno"))
            total = int(m.group("total"))
            pkgname = m.group("pkgname")

        info = "({0:3d}/{1:3d}) [{2:3.0f}%] downloading "
        info = info.format(pkgno, total, frac * 100)

        infolen, pkglen = len(info), len(pkgname)
        if (infolen + pkglen) > self.output.width:
            pkgname = "{0}...".format(pkg[:self.output.width-infolen-3])

        msg = "{0}<b>{1}</b>\r".format(info, pkgname)
        self.output.write(msg)
        if frac == 1:
            self.output.write("\n")


class LoraxTransactionCallback(object):

    def __init__(self):
        self.output = output.LoraxOutput()

    def event(self, state, data=None):
        # XXX
        if state == yum.callbacks.PT_DOWNLOAD:
            self.output.write("downloading packages\n")
        elif state == yum.callbacks.PT_DOWNLOAD_PKGS:
            pass
        elif state == yum.callbacks.PT_GPGCHECK:
            self.output.write("checking package signatures\n")
        elif state == yum.callbacks.PT_TEST_TRANS:
            self.output.write("running test transaction\n")
        elif state == yum.callbacks.PT_TRANSACTION:
            self.output.write("running transaction\n")


class LoraxRpmCallback(yum.rpmtrans.RPMBaseCallback):

    def __init__(self):
        yum.rpmtrans.RPMBaseCallback.__init__(self)
        self.output = output.LoraxOutput()

    def event(self, package, action, te_current, te_total,
              ts_current, ts_total):

        info = "({0:3d}/{1:3d}) [{2:3.0f}%] {3} "
        info = info.format(ts_current, ts_total,
                           float(te_current) / float(te_total) * 100,
                           self.action[action].lower())

        pkg = "{0}".format(package)

        infolen, pkglen = len(info), len(pkg)
        if (infolen + pkglen) > self.output.width:
            pkg = "{0}...".format(pkg[:self.output.width-infolen-3])

        msg = "{0}<b>{1}</b>\r".format(info, pkg)
        self.output.write(msg)
        if te_current == te_total:
            self.output.write("\n")

    def filelog(self, package, action):
        if self.fileaction.get(action) == "Installed":
            logger.debug("{0} installed successfully".format(package))
