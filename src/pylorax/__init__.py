# __init__.py

import sys
import os
import shutil
import tempfile
import time
import ConfigParser
import re

from config import Container
import utils.rpmutil as rpmutil

import images

from exceptions import LoraxError


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
            raise LoraxError, 'missing repos'
        if not self.conf.outdir:
            raise LoraxError, 'missing outdir'
        if not self.conf.product:
            raise LoraxError, 'missing product'
        if not self.conf.version:
            raise LoraxError, 'missing version'
        if not self.conf.release:
            raise LoraxError, 'missing release'

        self.yum = None

    def run(self):
        print('Collecting repos...')
        self.collectRepos()

        # check if we have at least one valid repository
        if not self.conf.repo:
            sys.stderr.write('ERROR: no valid repository\n')
            sys.exit(1)

        print('Initializing directories...')
        self.initDirs()

        print('Initializing yum...')
        self.initYum()

        print('Setting build architecture...')
        self.setBuildArch()

        print('Writing .treeinfo...')
        self.writeTreeInfo()

        print('Writing .discinfo...')
        self.writeDiscInfo()

        print('Preparing the install tree...')
        self.prepareInstRoot()

        print('Creating the images...')
        self.makeImages()

        if self.conf.cleanup:
            print('Cleaning up...')
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
        cachedir = os.path.join(self.conf.tempdir, 'yumcache')

        print('Working directories:')
        print('    tempdir = %s' % self.conf.tempdir)
        print('    treedir = %s' % treedir)
        print('    cachedir = %s' % cachedir)

        self.conf.addAttr(['treedir', 'cachedir'])
        self.conf.set(treedir=treedir, cachedir=cachedir)

    def initYum(self):
        yumconf = os.path.join(self.conf.tempdir, 'yum.conf')
        
        try:
            f = open(yumconf, 'w')
        except IOError:
            sys.stderr.write('ERROR: Unable to write yum.conf file\n')
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

        self.yum = rpmutil.Yum(yumconf=self.conf.yumconf, installroot=self.conf.treedir)

        # remove not needed options
        self.conf.delAttr(['repo', 'extrarepos', 'mirrorlist'])

    def setBuildArch(self):
        unamearch = os.uname()[4]

        self.conf.addAttr('buildarch')
        self.conf.set(buildarch=unamearch)

        anaconda = self.yum.find('anaconda')
        try:
            self.conf.set(buildarch=anaconda[0].arch)
        except:
            pass

        # set the libdir
        self.conf.addAttr('libdir')
        self.conf.set(libdir='lib')
        # on 64-bit systems, make sure we use lib64 as the lib directory
        if self.conf.buildarch.endswith('64') or self.conf.buildarch == 's390x':
            self.conf.set(libdir='lib64')

    def writeTreeInfo(self, discnum=1, totaldiscs=1, packagedir=''):
        outfile = os.path.join(self.conf.outdir, '.treeinfo')

        # don't print anything instead of None if variant is not specified
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

        # XXX actually create the boot iso somewhere, and set up this attribute
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
        # XXX why do we need this?
        os.symlink(os.path.join(os.path.sep, 'tmp'),
                   os.path.join(self.conf.treedir, 'var', 'lib', 'xkb'))

    def makeImages(self):
        i = images.Images(self.conf, self.yum)
        i.run()

    # XXX figure out where to put this
    #def copyUpdates(self):
    #    if self.conf.updates and os.path.isdir(self.conf.updates):
    #        cp(os.path.join(self.conf.updates, '*'), self.conf.treedir)
    #    self.conf.delAttr('updates')

    def cleanUp(self, trash=[]):
        for item in trash:
            if os.path.isdir(item):
               shutil.rmtree(item, ignore_errors=True)
            else:
               os.unlink(item)

        # remove the whole lorax tempdir
        if os.path.isdir(self.conf.tempdir):
            shutil.rmtree(self.conf.tempdir, ignore_errors=True)
