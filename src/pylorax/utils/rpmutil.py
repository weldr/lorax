# pylorax/utils/rpmutil.py

import sys
import os
import stat
import yum
import urlgrabber
import shutil

import yum.callbacks
import yum.rpmtrans

from rpmUtils.miscutils import rpm2cpio
from cpioarchive import CpioArchive

from pylorax.base import seq, getConsoleSize


class Callback(yum.rpmtrans.SimpleCliCallBack):
    def __init__(self):
        yum.rpmtrans.SimpleCliCallBack.__init__(self)
        self.height, self.width = getConsoleSize()

    def event(self, package, action, te_current, te_total, ts_current, ts_total):
        # XXX crazy output stuff
        progress = float(te_current) / float(te_total)

        percentage = int(progress * 100)

        bar_length = 20
        bar = int(percentage / (100/bar_length))

        total_progress_str = '[%s/%s] ' % (ts_current, ts_total)
        package_progress_str = ' [%s%s] %3d%%' % ('#' * bar, '-' * (bar_length - bar), percentage)

        action_str = '%s %s' % (self.action[action], package)
        chars_left = self.width - len(total_progress_str) - len(package_progress_str)

        if len(action_str) > chars_left:
            action_str = action_str[:chars_left-3]
            action_str = action_str + '...'
        else:
            action_str = action_str + ' ' * (chars_left - len(action_str))

        msg = total_progress_str + action_str + package_progress_str

        sys.stdout.write(msg)
        sys.stdout.write('\b' * len(msg))

        if percentage == 100:
            sys.stdout.write('\n')

        sys.stdout.flush()


class Yum(object):
    def __init__(self, yumconf='/etc/yum/yum.conf', installroot='/'):
        self.yb = yum.YumBase()

        self.yumconf = os.path.abspath(yumconf)
        self.installroot = os.path.abspath(installroot)

        self.yb.preconf.fn = self.yumconf
        self.yb.preconf.root = self.installroot
        self.yb._getConfig()

        self.yb._getRpmDB()
        self.yb._getRepos()
        self.yb._getSacks()

    def find(self, patterns):
        pl = self.yb.doPackageLists(patterns=seq(patterns))
        return pl.installed, pl.available

    def isInstalled(self, pattern):
        print('searching for package matching %s' % pattern)
        pl = self.yb.doPackageLists(pkgnarrow='installed', patterns=[pattern])
        print('found %s' % pl.installed)
        return pl.installed

    def download(self, packages):
        for package in seq(packages):
            print('Downloading package %s...' % package)
            fn = urlgrabber.urlgrab(package.remote_url)
            shutil.copy(fn, self.installroot)

        return os.path.join(self.installroot, os.path.basename(fn))

    def addPackages(self, patterns):
        # FIXME don't add packages already installed
        for pattern in seq(patterns):
            installed = self.isInstalled(pattern)
            if installed:
                print 'Package %s already installed' % installed
                return

            print('Adding package matching %s...' % pattern)
            try:
                self.yb.install(name=pattern)
            except yum.Errors.InstallError:
                try:
                    self.yb.install(pattern=pattern)
                except yum.Errors.InstallError:
                    sys.stderr.write('ERROR: No package matching %s available\n' % pattern)

    def install(self):
        self.yb.resolveDeps()
        self.yb.buildTransaction()

        cb = yum.callbacks.ProcessTransBaseCallback()
        rpmcb = Callback()
        self.yb.processTransaction(callback=cb, rpmDisplay=rpmcb)


def extract_rpm(rpmfile, destdir):
    if not os.path.isdir(destdir):
        os.makedirs(destdir)

    rpm = os.open(rpmfile, os.O_RDONLY)
    output = open(os.path.join(destdir, 'CONTENT.cpio'), 'w')

    rpm2cpio(rpm, output)
    output.close()

    cwd = os.getcwd()
    os.chdir(destdir)

    cpio = CpioArchive(name=output.name)
    for entry in cpio:
        path = os.path.abspath(entry.name)
        isdir = stat.S_ISDIR(entry.mode)

        if isdir:
            if not os.path.isdir(path):
                os.makedirs(path)
        else:
            print('Extracting %s...' % entry.name)
            dir = os.path.dirname(path)
            if not os.path.isdir(dir):
                os.makedirs(dir)

            try:
                f = open(path, 'w')
            except IOError:
                sys.stderr.write('ERROR: Unable to extract file %s\n' % path)
            else:
                f.write(entry.read())
                f.close()

            os.chmod(path, entry.mode)
            os.chown(path, entry.uid, entry.gid)

    cpio.close()
    os.unlink(output.name)

    os.chdir(cwd)

    return True
