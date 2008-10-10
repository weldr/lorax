#
# pylorax
# Install image and tree support data generation tool -- Python module.
#
# Copyright (C) 2008  Red Hat, Inc.
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
# Author(s): David Cantrell <dcantrell@redhat.com>
#

version = (0, 1)

__all__ = ['discinfo', 'treeinfo', 'instroot']

import os
import shutil
import tempfile

import yum
import rpmUtils

import discinfo
import treeinfo
import instroot

conf = {}
conf['confdir'] = '/etc/lorax'
conf['tmpdir'] = tempfile.gettempdir()
conf['datadir'] = '/usr/share/lorax'

class Lorax:
    def __init__(self, repos=[], output=None, mirrorlist=[], updates=None):
        print("\n+=======================================================+")
        print("| Setting up work directories and configuration data... |")
        print("+=======================================================+\n")

        if repos != []:
            self.repo, self.extrarepos = self._collectRepos(repos)
        else:
            self.repo = None
            self.extrarepos = []

        self.output = output
        self.mirrorlist = mirrorlist
        self.updates = updates
        self.buildinstdir, self.treedir, self.cachedir = self._initializeDirs()
        self.yumconf = self._writeYumConf()
        self.buildarch = self.getBuildArch()

    def run(self):
        """run()

        Generate install images.

        """

        print("\n+================================================+")
        print("| Creating instroot tree to build images from... |")
        print("+================================================+\n")

        self.instroot = pylorax.instroot.InstRoot(yumconf=self.yumconf, arch=self.buildarch, treedir=self.treedir, updates=self.updates)

    def showVersion(self, driver=None):
        """showVersion(driver)

        Display program name (driver) and version number.  If prog is an empty
        string or None, use the value 'pylorax'.

        """

        if prog is None or prog == '':
            prog = 'pylorax'

        print "%s version %d.%d" % (prog, version[0], version[1],)

    def cleanup(self, trash=[]):
        """cleanup(trash)

        Given a list of things to remove, cleanup() will remove them if it can.
        Never fails, just tries to remove things and returns regardless of
        failures removing things.

        """

        if trash != []:
            for item in trash:
                if os.path.isdir(item):
                   shutil.rmtree(item, ignore_errors=True)
                else:
                   os.unlink(item)

        if os.path.isdir(conf['tmpdir']):
            shutil.rmtree(conf['tmpdir'], ignore_errors=True)

    def getBuildArch(self):
        """getBuildArch()

        Query the configured yum repositories to determine our build architecture,
        which is the architecture of the anaconda package in the repositories.

        This function is based on a subset of what repoquery(1) does.

        """

        uname_arch = os.uname()[4]

        if self.yumconf == '' or self.yumconf is None or not os.path.isfile(self.yumconf):
            return uname_arch

        repoq = yum.YumBase()
        repoq.doConfigSetup()

        try:
            repoq.doRepoSetup()
        except yum.Errors.RepoError, e:
            sys.stderr.write("ERROR: could not query yum repository for build arch, defaulting to %s\n" % (uname_arch,))
            return uname_arch

        repoq.doSackSetup(rpmUtils.arch.getArchList())
        repoq.doTsSetup()

        ret_arch = None
        for pkg in repoq.pkgSack.simplePkgList():
            (n, a, e, v, r) = pkg
            if n == 'anaconda':
                ret_arch = a
                break

        if ret_arch is None:
            ret_arch = uname_arch

        print("Building images for %s" % (ret_arch,))

        return ret_arch

    def _collectRepos(self, repos):
        """_collectRepos(repos)

        Get the main repo (the first one) and then build a list of all remaining
        repos in the list.  Sanitize each repo URL for proper yum syntax.

        """

        if repos is None or repos == []:
            return '', []

        repolist = []
        for repospec in repos:
            if repospec.startswith('/'):
                repo = "file://%s" % (repospec,)
                print("Adding local repo:\n    %s" % (repo,))
                repolist.append(repo)
            elif repospec.startswith('http://') or repospec.startswith('ftp://'):
                print("Adding remote repo:\n    %s" % (repospec,))
                repolist.append(repospec)

        repo = repolist[0]
        extrarepos = []

        if len(repolist) > 1:
            for extra in repolist[1:]:
                print("Adding extra repo:\n   %s" % (extra,))
                extrarepos.append(extra)

        return repo, extrarepos

    def _initializeDirs(self):
        """_initializeDirs()

        Create directories used for image generation.

        """

        if not os.path.isdir(self.output):
            os.makedirs(self.output, mode=0755)

        conf['tmpdir'] = tempfile.mkdtemp('XXXXXX', 'lorax.tmp.', conf['tmpdir'])
        buildinstdir = tempfile.mkdtemp('XXXXXX', 'buildinstall.tree.', conf['tmpdir'])
        treedir = tempfile.mkdtemp('XXXXXX', 'treedir.', conf['tmpdir'])
        cachedir = tempfile.mkdtemp('XXXXXX', 'yumcache.', conf['tmpdir'])

        print("Working directories:")
        print("    tmpdir = %s" % (conf['tmpdir'],))
        print("    buildinstdir = %s" % (buildinstdir,))
        print("    treedir = %s" % (treedir,))
        print("    cachedir = %s" % (cachedir,))

        return buildinstdir, treedir, cachedir

    def _writeYumConf():
        """_writeYumConf()

        Generate a temporary yum.conf file for image generation.  Returns the path
        to the temporary yum.conf file on success, None of failure.
        """

        tmpdir = conf['tmpdir']
        (fd, yumconf) = tempfile.mkstemp(prefix='yum.conf', dir=tmpdir)
        f = os.fdopen(fd, 'w')

        f.write("[main]\n")
        f.write("cachedir=%s\n" % (self.cachedir,))
        f.write("keepcache=0\n")
        f.write("gpgcheck=0\n")
        f.write("plugins=0\n")
        f.write("reposdir=\n")
        f.write("tsflags=nodocs\n\n")
        f.write("[loraxrepo]\n")
        f.write("name=lorax repo\n")
        f.write("baseurl=%s\n" % (self.repo,))
        f.write("enabled=1\n\n")

        if self.extrarepos != []:
            n = 1
            for extra in self.extrarepos:
                f.write("[lorax-extrarepo-%d]\n" % (n,))
                f.write("name=lorax extra repo %d\n" % (n,))
                f.write("baseurl=%s\n" % (extra,))
                f.write("enabled=1\n")
                n += 1

        if self.mirrorlist != []:
            n = 1
            for mirror in self.mirrorlist:
                f.write("[lorax-mirrorlistrepo-%d]\n" % (n,))
                f.write("name=lorax mirrorlist repo %d\n" % (n,))
                f.write("mirrorlist=%s\n" % (mirror,))
                f.write("enabled=1\n")
                n += 1

        f.close()
        print("Wrote lorax yum configuration to %s" % (yumconf,))

        return yumconf
