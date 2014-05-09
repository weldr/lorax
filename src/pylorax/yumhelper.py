#
# yumhelper.py
#
# Copyright (C) 2010-2014 Red Hat, Inc.
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
import yum, yum.callbacks, yum.rpmtrans
import pylorax.output as output

__all__ = ['LoraxDownloadCallback', 'LoraxTransactionCallback',
           'LoraxRpmCallback']

class LoraxDownloadCallback(yum.callbacks.DownloadBaseCallback):
    def __init__(self):
        yum.callbacks.DownloadBaseCallback.__init__(self)

        self.pkgno = 0
        self.total = 0

        self.output = output.LoraxOutput()


    def updateProgress(self, name, frac, fread, ftime):
        """
            Update the progress bar
            @param name: filename
            @param frac: progress fraction (0 -> 1)
            @param fread: formated string containing BytesRead
            @param ftime: formated string containing remaining or elapsed time
        """
        # Only update when it is finished downloading
        if frac < 1:
            return

        self.pkgno += 1
        info = "({0:3d}/{1:3d}) "
        info = info.format(self.pkgno, self.total)

        infolen, pkglen = len(info), len(name)
        if (infolen + pkglen) > self.output.width:
            name = "{0}...".format(name[:self.output.width-infolen-3])

        msg = "{0}<b>{1}</b>\n".format(info, name)
        self.output.write(msg)


class LoraxTransactionCallback(object):

    def __init__(self, dl_callback):
        self.output = output.LoraxOutput()

        self.dl_callback = dl_callback

    def event(self, state, data=None):
        if state == yum.callbacks.PT_DOWNLOAD:
            self.output.write("downloading packages\n")
        elif state == yum.callbacks.PT_DOWNLOAD_PKGS:
            # Initialize the total number of packages being downloaded
            self.dl_callback.total = len(data)
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

        action_str = self.action[action].encode("utf-8")
        info = "({0:3d}/{1:3d}) [{2:3.0f}%] {3} "
        info = info.format(ts_current, ts_total,
                           float(te_current) / float(te_total) * 100,
                           action_str.lower())

        pkg = "{0}".format(package)

        infolen, pkglen = len(info), len(pkg)
        if (infolen + pkglen) > self.output.width:
            pkg = "{0}...".format(pkg[:self.output.width-infolen-3])

        msg = "{0}<b>{1}</b>".format(info, pkg)

        # When not outputting to a tty we only want to print it once at the end
        if sys.stdout.isatty():
            self.output.write(msg + "\r")
            if te_current == te_total:
                self.output.write("\n")
        elif te_current == te_total:
            self.output.write(msg + "\n")


    def filelog(self, package, action):
        if self.fileaction.get(action) == "Installed":
            logger.debug("{0} installed successfully".format(package))

    def errorlog(self, msg):
        logger.warning("RPM transaction error: %s", msg)

    def scriptout(self, package, msgs):
        if msgs:
            logger.info("%s scriptlet output:\n%s", package, msgs)
