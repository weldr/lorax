#
# pylorax
# Install image and tree support data generation tool -- Python module.
#
# Copyright (C) 2008, 2009  Red Hat, Inc.
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
#            Martin Gracik <mgracik@redhat.com>
#

import sys
import os
import shutil
import tempfile
import time
import ConfigParser

import yum
import rpmUtils

import instroot
import images


class Lorax:
    def __init__(self, repos, options):
        self.repos = repos

        # required
        self.product = options.product
        self.version = options.version
        self.release = options.release
        self.output = options.output

        # optional
        self.debug = options.debug
        self.variant = options.variant
        self.bugurl = options.bugurl
        self.updates = options.updates
        self.mirrorlist = options.mirrorlist
        self.confdir = options.confdir
        self.cleanup = options.cleanup

        self.conf = {}
        if not self.confdir:
            self.confdir = '/etc/lorax'
        self.conf['confdir'] = self.confdir
        self.conf['datadir'] = '/usr/share/lorax'
        self.conf['tmpdir'] = tempfile.gettempdir()

    def run(self):
        """run()

        Generate install images.
        """

        print('Collecting repos...')
        self.repo, self.extrarepos = self.__collectRepos()

        if not self.repo:
            sys.stderr.write('No valid repository.\n')
            sys.exit(1)

        print('Initializing directories...')
        self.buildinstdir, self.treedir, self.cachedir = self.__initializeDirs()

        print('Writing yum configuration...')
        self.yumconf = self.__writeYumConf()

        print('Getting the build architecture...')
        self.buildarch = self.__getBuildArch()

        print('Creating install root tree...')
        self.makeInstRoot()

        print('Writing .treeinfo...')
        self.__writeTreeInfo()

        print('Writing .discinfo...')
        self.__writeDiscInfo()

        print('Creating images...')
        self.makeImages()

        if self.cleanup:
            print('Cleaning up...')
            self.cleanUp()

    def __collectRepos(self):
        """_collectRepos()

        Get the main repo (the first one) and then build a list of all remaining
        repos in the list.  Sanitize each repo URL for proper yum syntax.
        """

        repolist = []
        for repospec in self.repos:
            if repospec.startswith('/'):
                repo = 'file://%s' % (repospec,)
                print('Adding local repo:\n    %s' % (repo,))
                repolist.append(repo)
            elif repospec.startswith('http://') or repospec.startswith('ftp://'):
                print('Adding remote repo:\n    %s' % (repospec,))
                repolist.append(repospec)

        if not repolist:
            return None, []
        else:
            return repolist[0], repolist[1:]

    def __initializeDirs(self):
        """_initializeDirs()

        Create directories used for image generation.
        """

        if not os.path.isdir(self.output):
            os.makedirs(self.output, mode=0755)

        self.conf['tmpdir'] = tempfile.mkdtemp('XXXXXX', 'lorax.tmp.', self.conf['tmpdir'])
        buildinstdir = tempfile.mkdtemp('XXXXXX', 'buildinstall.tree.', self.conf['tmpdir'])
        treedir = tempfile.mkdtemp('XXXXXX', 'treedir.', self.conf['tmpdir'])
        cachedir = tempfile.mkdtemp('XXXXXX', 'yumcache.', self.conf['tmpdir'])

        print('Working directories:')
        print('    tmpdir = %s' % (self.conf['tmpdir'],))
        print('    buildinstdir = %s' % (buildinstdir,))
        print('    treedir = %s' % (treedir,))
        print('    cachedir = %s' % (cachedir,))

        return buildinstdir, treedir, cachedir

    def __writeYumConf(self):
        """_writeYumConf()

        Generate a temporary yum.conf file for image generation.  Returns the path
        to the temporary yum.conf file on success, None of failure.
        """

        (fd, yumconf) = tempfile.mkstemp(prefix='yum.conf', dir=self.conf['tmpdir'])
        f = os.fdopen(fd, 'w')

        f.write('[main]\n')
        f.write('cachedir=%s\n' % (self.cachedir,))
        f.write('keepcache=0\n')
        f.write('gpgcheck=0\n')
        f.write('plugins=0\n')
        f.write('reposdir=\n')
        f.write('tsflags=nodocs\n\n')

        f.write('[loraxrepo]\n')
        f.write('name=lorax repo\n')
        f.write('baseurl=%s\n' % (self.repo,))
        f.write('enabled=1\n\n')

        for n, extra in enumerate(self.extrarepos, start=1):
            f.write('[lorax-extrarepo-%d]\n' % (n,))
            f.write('name=lorax extra repo %d\n' % (n,))
            f.write('baseurl=%s\n' % (extra,))
            f.write('enabled=1\n')

        for n, mirror in enumerate(self.mirrorlist, start=1):
            f.write('[lorax-mirrorlistrepo-%d]\n' % (n,))
            f.write('name=lorax mirrorlist repo %d\n' % (n,))
            f.write('mirrorlist=%s\n' % (mirror,))
            f.write('enabled=1\n')

        f.close()
        print('Wrote lorax yum configuration to %s' % (yumconf,))

        return yumconf

    def __getBuildArch(self):
        """_getBuildArch()

        Query the configured yum repositories to determine our build architecture,
        which is the architecture of the anaconda package in the repositories.

        This function is based on a subset of what repoquery(1) does.
        """

        uname_arch = os.uname()[4]

        if not self.yumconf or not os.path.isfile(self.yumconf):
            sys.stderr.write('ERROR: yum.conf does not exist, defaulting to %s\n' % (uname_arch,))
            return uname_arch

        repoq = yum.YumBase()
        repoq.doConfigSetup(self.yumconf)

        try:
            repoq.doRepoSetup()
        except yum.Errors.RepoError:
            sys.stderr.write('ERROR: cannot query yum repo, defaulting to %s\n' % (uname_arch,))
            return uname_arch

        repoq.doSackSetup(rpmUtils.arch.getArchList())
        repoq.doTsSetup()

        ret_arch = None
        for pkg in repoq.pkgSack.simplePkgList():
            (n, a, e, v, r) = pkg
            if n == 'anaconda':
                ret_arch = a
                break

        if not ret_arch:
            ret_arch = uname_arch

        return ret_arch

    def __writeTreeInfo(self, discnum=1, totaldiscs=1, packagedir=''):
        outfile = os.path.join(self.output, '.treeinfo')

        data = { 'timestamp': time.time(),
                 'family': self.product,
                 'version': self.version,
                 'arch': self.buildarch,
                 'variant': self.variant,
                 'discnum': str(discnum),
                 'totaldiscs': str(totaldiscs),
                 'packagedir': packagedir }

        c = ConfigParser.ConfigParser()
        
        section = 'general'
        c.add_section(section)
        for key, value in data.items():
            c.set(section, key, value)

        try:
            f = open(outfile, 'w')
        except IOError:
            return False
        else:
            c.write(f)
            f.close()
            return True
    
    def __writeDiscInfo(self, discnum=0):
        outfile = os.path.join(self.output, '.discinfo')

        try:
            f = open(outfile, 'w')
        except IOError:
            return False
        else:
            f.write('%f\n' % (time.time(),))
            f.write('%s\n' % (self.release,))
            f.write('%s\n' % (self.buildarch,))
            f.write('%d\n' % (discnum,))
            f.close()
            return True

    def makeInstRoot(self):
        root = instroot.InstRoot(conf=self.conf,
                                 yumconf=self.yumconf,
                                 arch=self.buildarch,
                                 treedir=self.treedir,
                                 updates=self.updates)
        root.run()

    # TODO
    def makeImages(self):
        pass

    def cleanUp(self, trash=[]):
        """cleanup([trash])

        Given a list of things to remove, cleanUp() will remove them if it can.
        Never fails, just tries to remove things and returns regardless of
        failures removing things.
        """

        for item in trash:
            if os.path.isdir(item):
               shutil.rmtree(item, ignore_errors=True)
            else:
               os.unlink(item)

        if os.path.isdir(self.conf['tmpdir']):
            shutil.rmtree(self.conf['tmpdir'], ignore_errors=True)

