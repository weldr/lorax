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

        self.initrddir = os.path.join(self.conf.tempdir, 'initrd')
        os.makedirs(self.initrddir)

        # get supported actions
        supported_actions = actions.getActions()

        initrd_templates = []
        initrd_templates.append(os.path.join(self.conf.confdir, 'templates', 'initrd'))
        initrd_templates.append(os.path.join(self.conf.confdir, 'templates', self.conf.buildarch,
                                             'initrd'))

        self.template = Template()
        for file in initrd_templates:
            if os.path.isfile(file):
                self.template.parse(file, supported_actions)

        self.actions = []

    def prepare(self):
        # install needed packages
        for action in filter(lambda action: hasattr(action, 'install'), self.template.actions):
            self.yum.addPackages(action.install)

        self.yum.install()

        # get needed dependencies
        ldd = LDD(libroot=os.path.join(self.conf.treedir, self.conf.libdir))
        for action in filter(lambda action: hasattr(action, 'getDeps'), self.template.actions):
            file = re.sub(r'@instroot@(?P<file>.*)', '%s\g<file>' % self.conf.treedir,
                          action.getDeps())
            ldd.getDeps(file)
            
        # resolve symlinks
        ldd.getLinks()

        # add dependencies to actions
        for dep in ldd.deps:
            kwargs = {}
            kwargs['src'] = dep
            kwargs['dst'] = re.sub(r'%s(?P<file>.*)' % self.conf.treedir,
                                   '%s\g<file>' % self.initrddir,
                                   dep)

            new_action = actions.fileactions.Copy(**kwargs)
            self.actions.append(new_action)

    def processActions(self):
        for action in self.template.actions:
            action.execute()

        for action in self.actions:
            action.execute()

    def create(self, dst):
        os.system('find %s | cpio --quiet -c -o | gzip -9 > %s' % (self.initrddir, dst))

    def cleanUp(self):
        rm(self.initrddir)
