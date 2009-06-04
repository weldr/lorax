# pylorax/initrd.py

import os
import re

import actions
from config import Template
from utils.libutil import LDD
from utils.fileutil import rm


class InitRD(object):
    def __init__(self, config, yum):
        self.conf = config
        self.yum = yum

        if not os.path.isdir(self.conf.initrddir):
            os.makedirs(self.conf.initrddir)

        # get supported actions
        supported_actions = actions.getActions()

        initrd_templates = []
        initrd_templates.append(os.path.join(self.conf.confdir, 'templates', 'initrd'))
        initrd_templates.append(os.path.join(self.conf.confdir, 'templates', self.conf.buildarch,
                                             'initrd'))

        vars = { '@instroot@': self.conf.treedir,
                 '@initrd@': self.conf.initrddir }
        self.template = Template()
        for file in initrd_templates:
            if os.path.isfile(file):
                self.template.parse(file, supported_actions, vars)

        self.actions = []

    def getPkgs(self):
        # get needed packages
        pkgs = []
        for action in filter(lambda action: hasattr(action, 'install'), self.template.actions):
            m = re.match(r'%s(.*)' % self.conf.treedir, action.install)
            if m:
                pkgs.append(m.group(1))

        return pkgs

    def getDeps(self):
        # get needed dependencies
        ldd = LDD(libroot=os.path.join(self.conf.treedir, self.conf.libdir))
        for action in filter(lambda action: hasattr(action, 'getDeps'), self.template.actions):
            file = action.getDeps()
            ldd.getDeps(file)

        # resolve symlinks
        ldd.getLinks()

        # add dependencies to actions
        for dep in ldd.deps:
            kwargs = {}
            kwargs['src'] = dep
            kwargs['dst'] = re.sub(r'%s(?P<file>.*)' % self.conf.treedir,
                                   '%s\g<file>' % self.conf.initrddir,
                                   dep)

            new_action = actions.fileactions.Copy(**kwargs)
            self.actions.append(new_action)

    def processActions(self):
        for action in self.template.actions:
            action.execute()

        for action in self.actions:
            action.execute()

    def create(self, dst):
        os.system('find %s | cpio --quiet -c -o | gzip -9 > %s' % (self.conf.initrddir, dst))

    def cleanUp(self):
        rm(self.conf.initrddir)
