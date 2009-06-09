# pylorax/__init__.py

import sys
import os
import shutil
import tempfile
import time
import ConfigParser
import re
from errors import LoraxError

from config import Container
from utils.rpmutils import Yum
from utils.fileutils import rm

import images


class Config(Container):
    def __init__(self):
        config = ('confdir', 'datadir', 'tempdir', 'debug', 'cleanup')

        # options
        required = ('product', 'version', 'release', 'outdir', 'repos')
        optional = ('variant', 'bugurl', 'updates', 'mirrorlist')

        Container.__init__(self, config + required + optional)

        # set defaults
        self.set(confdir='/etc/lorax',
                 datadir='/usr/share/lorax',
                 tempdir=tempfile.mkdtemp(prefix='lorax.tmp.', dir=tempfile.gettempdir()),
                 debug=False,
                 cleanup=False)

        self.set(product='',
                 version='',
                 release='',
                 outdir='',
                 repos=[])

        self.set(variant='',
                 bugurl='',
                 updates='',
                 mirrorlist=[])


class Lorax(object):
    def __init__(self, config):
        assert isinstance(config, Config) == True
        self.conf = config

        # check if we have all required options
        if not self.conf.repos:
            raise LoraxError, "missing required parameter 'repos'"
        if not self.conf.outdir:
            raise LoraxError, "missing required parameter 'outdir'"
        if not self.conf.product:
            raise LoraxError, "missing required parameter 'product'"
        if not self.conf.version:
            raise LoraxError, "missing required parameter 'version'"
        if not self.conf.release:
            raise LoraxError, "missing required parameter 'release'"

        self.yum = None

    def run(self):
        bold = ('\033[1m', '\033[0m')

        print('%sCollecting repos%s' % bold)
        self.collectRepos()

        # check if we have at least one valid repository
        if not self.conf.repo:
            sys.stderr.write('ERROR: No valid repository\n')
            sys.exit(1)

        print('%sInitializing directories%s' % bold)
        self.initDirs()

        print('%sInitializing yum%s' % bold)
        self.initYum()

        print('%sSetting build architecture%s' % bold)
        self.setBuildArch()

        print('%sWriting .treeinfo%s' % bold)
        self.writeTreeInfo()

        print('%sWriting .discinfo%s' % bold)
        self.writeDiscInfo()

        print('%sPreparing the install tree%s' % bold)
        self.prepareInstRoot()

        print('%sCreating the images%s' % bold)
        self.makeImages()

        if self.conf.cleanup:
            print('%sCleaning up%s' % bold)
            self.cleanUp()

    def collectRepos(self):
        repolist = []
        for repospec in self.conf.repos:
            if repospec.startswith('/'):
                repo = 'file://%s' % repospec
                print('Adding local repo: %s' % repo)
                repolist.append(repo)
            elif repospec.startswith('http://') or repospec.startswith('ftp://'):
                print('Adding remote repo: %s' % repospec)
                repolist.append(repospec)

        if not repolist:
            repo, extrarepos = None, []
        else:
            repo, extrarepos = repolist[0], repolist[1:]

        self.conf.addAttr(['repo', 'extrarepos'])
        self.conf.set(repo=repo, extrarepos=extrarepos)

        # remove repos attribute, to get a traceback, if we use it later 
        self.conf.delAttr('repos')

    def initDirs(self):
        if not os.path.isdir(self.conf.outdir):
            os.makedirs(self.conf.outdir, mode=0755)

        treedir = os.path.join(self.conf.tempdir, 'treedir', 'install')
        os.makedirs(treedir)
        cachedir = os.path.join(self.conf.tempdir, 'yumcache')
        os.makedirs(cachedir)
        initrddir = os.path.join(self.conf.tempdir, 'initrddir')
        os.makedirs(initrddir)

        print('Working directories:')
        print('    tempdir = %s' % self.conf.tempdir)
        print('    treedir = %s' % treedir)
        print('    cachedir = %s' % cachedir)
        print('    initrddir = %s' % initrddir)

        self.conf.addAttr(['treedir', 'cachedir', 'initrddir'])
        self.conf.set(treedir=treedir, cachedir=cachedir, initrddir=initrddir)

    def initYum(self):
        yumconf = os.path.join(self.conf.tempdir, 'yum.conf')

        try:
            f = open(yumconf, 'w')
        except IOError as why:
            sys.stderr.write('ERROR: Unable to write yum.conf file: %s\n' % why)
            sys.exit(1)
        else:
            f.write('[main]\n')
            f.write('cachedir=%s\n' % self.conf.cachedir)
            f.write('keepcache=0\n')
            f.write('gpgcheck=0\n')
            f.write('plugins=0\n')
            f.write('reposdir=\n')
            f.write('tsflags=nodocs\n\n')

            f.write('[loraxrepo]\n')
            f.write('name=lorax repo\n')
            f.write('baseurl=%s\n' % self.conf.repo)
            f.write('enabled=1\n\n')

            for n, extra in enumerate(self.conf.extrarepos, start=1):
                f.write('[lorax-extrarepo-%d]\n' % n)
                f.write('name=lorax extra repo %d\n' % n)
                f.write('baseurl=%s\n' % extra)
                f.write('enabled=1\n')

            for n, mirror in enumerate(self.conf.mirrorlist, start=1):
                f.write('[lorax-mirrorlistrepo-%d]\n' % n)
                f.write('name=lorax mirrorlist repo %d\n' % n)
                f.write('mirrorlist=%s\n' % mirror)
                f.write('enabled=1\n')

            f.close()

        self.conf.addAttr('yumconf')
        self.conf.set(yumconf=yumconf)

        # create the Yum object
        self.yum = Yum(yumconf=self.conf.yumconf, installroot=self.conf.treedir)

        # remove not needed attributes
        self.conf.delAttr(['repo', 'extrarepos', 'mirrorlist', 'cachedir'])

    def setBuildArch(self):
        unamearch = os.uname()[4]

        self.conf.addAttr('buildarch')
        self.conf.set(buildarch=unamearch)

        installed, available = self.yum.find('anaconda')
        try:
            self.conf.set(buildarch=available[0].arch)
        except:
            # FIXME specify what exceptions can we get here
            pass

        # set the libdir
        self.conf.addAttr('libdir')
        self.conf.set(libdir='lib')
        # on 64-bit systems, make sure we use lib64 as the lib directory
        if self.conf.buildarch.endswith('64') or self.conf.buildarch == 's390x':
            self.conf.set(libdir='lib64')

    def writeTreeInfo(self, discnum=1, totaldiscs=1, packagedir=''):
        outfile = os.path.join(self.conf.outdir, '.treeinfo')

        # don't print anything instead of None, if variant is not specified
        variant = ''
        if self.conf.variant:
            variant = self.conf.variant
            
        data = { 'timestamp': time.time(),
                 'family': self.conf.product,
                 'version': self.conf.version,
                 'arch': self.conf.buildarch,
                 'variant': variant,
                 'discnum': str(discnum),
                 'totaldiscs': str(totaldiscs),
                 'packagedir': packagedir }

        c = ConfigParser.ConfigParser()
        
        section = 'general'
        c.add_section(section)
        for key, value in data.items():
            c.set(section, key, value)

        section = 'images-%s' % self.conf.buildarch
        c.add_section(section)
        c.set(section, 'kernel', 'images/pxeboot/vmlinuz')
        c.set(section, 'initrd', 'images/pxeboot/initrd.img')

        # XXX actually create the boot iso somewhere before calling writeTreeInfo(),
        #     and set up this attribute properly
        self.conf.addAttr('bootiso')
        
        if self.conf.bootiso:
            c.set(section, 'boot.iso', 'images/%s' % self.conf.bootiso)

        try:
            f = open(outfile, 'w')
        except IOError:
            return False
        else:
            c.write(f)
            f.close()
            return True
    
    def writeDiscInfo(self, discnum=0):
        outfile = os.path.join(self.conf.outdir, '.discinfo')

        try:
            f = open(outfile, 'w')
        except IOError:
            return False
        else:
            f.write('%f\n' % time.time())
            f.write('%s\n' % self.conf.release)
            f.write('%s\n' % self.conf.buildarch)
            f.write('%d\n' % discnum)
            f.close()
            return True

    def prepareInstRoot(self):
        # XXX do we need this?
        os.symlink(os.path.join(os.path.sep, 'tmp'),
                   os.path.join(self.conf.treedir, 'var', 'lib', 'xkb'))

    def makeImages(self):
        i = images.Images(self.conf, self.yum)
        i.run()

    def cleanUp(self, trash=[]):
        for item in trash:
            if os.path.exists(item):
                rm(item)

        # remove the whole lorax tempdir
        if os.path.isdir(self.conf.tempdir):
            rm(self.conf.tempdir)
