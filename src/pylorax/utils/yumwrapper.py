#
# yumwrapper.py
# yum wrapper
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

import sys
import os
import yum
import yum.callbacks
import yum.rpmtrans

from pylorax.misc import seq, get_console_size


class Callback(yum.rpmtrans.SimpleCliCallBack):

    def __init__(self):
        yum.rpmtrans.SimpleCliCallBack.__init__(self)
        self.height, self.width = get_console_size()

    def event(self, package, action, te_current, te_total, ts_current, ts_total):
        progress = float(te_current) / float(te_total)
        percentage = int(progress * 100)

        bar_length = 20
        bar = int(percentage / (100 / bar_length))

        total_progress_str = "[%s/%s] " % (ts_current, ts_total)
        package_progress_str = " [%s%s] %3d%%" % ("#" * bar, "-" * (bar_length - bar),
                                                  percentage)

        action_str = "%s %s" % (self.action[action], package)
        chars_left = self.width - len(total_progress_str) - len(package_progress_str)

        if len(action_str) > chars_left:
            action_str = action_str[:chars_left-3]
            action_str = action_str + "..."
        else:
            action_str = action_str + " " * (chars_left - len(action_str))

        msg = total_progress_str + action_str + package_progress_str

        sys.stdout.write(msg)
        sys.stdout.write("\r")

        if percentage == 100:
            sys.stdout.write("\n")
        
        sys.stdout.flush()


class Yum(object):

    def __init__(self, yumconf="/etc/yum/yum.conf", installroot="/",
            errfile="/dev/null"):

        self.yb = yum.YumBase()

        self.yumconf = os.path.abspath(yumconf)
        self.installroot = os.path.abspath(installroot)
        self.errfile = errfile

        self.yb.preconf.fn = self.yumconf
        self.yb.preconf.root = self.installroot
        self.yb._getConfig()

        self.yb._getRpmDB()
        self.yb._getRepos()
        self.yb._getSacks()

    def find(self, patterns):
        pl = self.yb.doPackageLists(patterns=seq(patterns))
        return pl.installed, pl.available

    def add_package(self, pattern):
        try:
            self.yb.install(name=pattern)
        except yum.Errors.InstallError:
            # didn't find an exact package name match 
            try:
                self.yb.install(pattern=pattern)
            except yum.Errors.InstallError:
                # no package found
                return False

        return True

    def install(self):
        self.yb.resolveDeps()
        self.yb.buildTransaction()

        cb = yum.callbacks.ProcessTransBaseCallback()
        #cb = yum.callbacks.ProcessTransNoOutputCallback()
        rpmcb = Callback()

        # XXX ATTENTION! ugly rpm error output hack
        # we redirect the error output from rpm to errfile,
        # so it does not show up in our "nice" output
        # 2 = err descriptor
        standard_err = os.dup(2)
        my_err = open(self.errfile, "a")
        os.dup2(my_err.fileno(), 2)

        # now we process the transactions without errors showing up in the output
        self.yb.processTransaction(callback=cb, rpmDisplay=rpmcb)

        # and we put the standard error output back, so nobody will notice
        os.dup2(standard_err, 2)
        my_err.close()

        self.yb.closeRpmDB()
        self.yb.close()
