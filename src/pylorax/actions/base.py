#
# base.py
# base actions
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

import os
import re
import pwd
import grp
import glob

from pylorax.utils.fileutils import copy, move, remove, touch, edit, replace, chmod


# command:action mapping
# maps a template command to an action class
# if you want your new action to be supported, you have to include it in this mapping
COMMANDS = { 'copy': 'Copy',
             'move': 'Move',
             'remove': 'Remove',
             'link': 'Link',
             'touch': 'Touch',
             'edit': 'Edit',
             'replace': 'Replace',
             'makedir': 'MakeDir',
             'chmod': 'Chmod',
             'chown': 'Chown',
             'genkey': 'GenerateSSHKey' }


class LoraxAction(object):
    """Actions base class.

    To create your own custom action, subclass this class and override the methods you need.

    A valid action has to have a REGEX class variable, which specifies the format of the action
    command line, so the needed parameters can be properly extracted from it.
    All the work should be done in the execute method, which will be called from Lorax.
    At the end, set the success to False, or True depending on the success or failure of your action.

    If you need to install some package prior to executing the action, return an install pattern
    with the "install" property. Lorax will get this first, and will try to install the needed
    package.

    Don't forget to include a command:action map for your new action in the COMMANDS dictionary.
    Action classes which are not in the COMMANDS dictionary will not be loaded.
    
    You can take a look at some of the builtin actions to get an idea of how to create your
    own actions."""


    REGEX = r'' # regular expression for extracting the parameters from the command line

    def __init__(self):
        if self.__class__ is LoraxAction:
            raise TypeError, 'LoraxAction is an abstract class, cannot be used this way'

        self._attrs = {}
        self._attrs['success'] = None   # success is None, if the action wasn't executed yet

    def __str__(self):
        return '%s: %s' % (self.__class__.__name__, self._attrs)

    def execute(self, verbose=False):
        """This method is the main body of the action. Put all the "work" stuff in here."""
        raise NotImplementedError, 'execute method not implemented for LoraxAction class'

    @property
    def success(self):
        """Returns if the action's execution was successful or not."""
        return self._attrs['success']

    @property
    def install(self):
        """Returns a pattern that needs to be installed, prior to calling the execute method."""
        return None

    @property
    def getDeps(self):
        return None


##### builtin actions

class Copy(LoraxAction):

    REGEX = r'^(?P<src_root>.*?)\s(?P<src_path>.*?)\sto\s(?P<dst_root>.*?)\s(?P<dst_path>.*?)(\s(?P<install>install))?(\s(?P<nolinks>nolinks))?$'

    def __init__(self, **kwargs):
        LoraxAction.__init__(self)
        self._attrs['src_root'] = kwargs.get('src_root')
        self._attrs['src_path'] = kwargs.get('src_path')
        self._attrs['dst_root'] = kwargs.get('dst_root')
        self._attrs['dst_path'] = kwargs.get('dst_path')

        install = kwargs.get('install', False)
        if install:
            self._attrs['install'] = True
        else:
            self._attrs['install'] = False

        nolinks = kwargs.get('nolinks', False)
        if nolinks:
            self._attrs['nolinks'] = True
        else:
            self._attrs['nolinks'] = False

    def execute(self, verbose=False):
        copy(src_root=self.src_root, src_path=self.src_path,
                dst_root=self.dst_root, dst_path=self.dst_path,
                nolinks=self.nolinks, ignore_errors=False, verbose=verbose)
        self._attrs['success'] = True

    @property
    def src(self):
        path = os.path.join(self._attrs['src_root'], self._attrs['src_path'])
        return os.path.normpath(path)

    @property
    def src_root(self):
        return self._attrs['src_root']

    @property
    def src_path(self):
        return self._attrs['src_path']

    @property
    def dst(self):
        path = os.path.join(self._attrs['dst_root'], self._attrs['dst_path'])
        return os.path.normpath(path)

    @property
    def dst_root(self):
        return self._attrs['dst_root']

    @property
    def dst_path(self):
        return self._attrs['dst_path']

    @property
    def mode(self):
        return self._attrs['mode']

    @property
    def install(self):
        if self._attrs['install']:
            return self._attrs['src']
        else:
            return None

    @property
    def getDeps(self):
        return self.src

    @property
    def nolinks(self):
        return self._attrs['nolinks']


class Move(Copy):
    def execute(self, verbose=False):
        move(src_root=self.src_root, src_path=self.src_path,
                dst_root=self.dst_root, dst_path=self.dst_path,
                nolinks=self.nolinks, ignore_errors=False, verbose=verbose)
        self._attrs['success'] = True


class Remove(LoraxAction):
    
    REGEX = r'^(?P<filename>.*?)$'

    def __init__(self, **kwargs):
        LoraxAction.__init__(self)
        self._attrs['filename'] = kwargs.get('filename')

    def execute(self, verbose=False):
        remove(self.filename, verbose=verbose)
        self._attrs['success'] = True

    @property
    def filename(self):
        return self._attrs['filename']


class Link(LoraxAction):

    REGEX = r'^(?P<name>.*?)\sto\s(?P<target>.*?)$'

    def __init__(self, **kwargs):
        LoraxAction.__init__(self)
        self._attrs['name'] = kwargs.get('name')
        self._attrs['target'] = kwargs.get('target')

    def execute(self, verbose=False):
        os.symlink(self.target, self.name)
        self._attrs['success'] = True

    @property
    def name(self):
        return self._attrs['name']

    @property
    def target(self):
        return self._attrs['target']

    @property
    def install(self):
        return self._attrs['target']


class Touch(LoraxAction):

    REGEX = r'^(?P<filename>.*?)$'

    def __init__(self, **kwargs):
        LoraxAction.__init__(self)
        self._attrs['filename'] = kwargs.get('filename')

    def execute(self, verbose=False):
        touch(filename=self.filename, verbose=verbose)
        self._attrs['success'] = True

    @property
    def filename(self):
        return self._attrs['filename']


class Edit(Touch):

    REGEX = r'^(?P<filename>.*?)\stext\s"(?P<text>.*?)"(\s(?P<append>append))?$'

    def __init__(self, **kwargs):
        Touch.__init__(self, **kwargs)
        self._attrs['text'] = kwargs.get('text')
        
        append = kwargs.get('append', False)
        if append:
            self._attrs['append'] = True
        else:
            self._attrs['append'] = False

    def execute(self, verbose=False):
        edit(filename=self.filename, text=self.text, append=self.append, verbose=verbose)
        self._attrs['success'] = True

    @property
    def text(self):
        return self._attrs['text']

    @property
    def append(self):
        return self._attrs['append']

    @property
    def install(self):
        return self._attrs['filename']


class Replace(Touch):

    REGEX = r'^(?P<filename>.*?)\sfind\s"(?P<find>.*?)"\sreplace\s"(?P<replace>.*?)"$'

    def __init__(self, **kwargs):
        Touch.__init__(self, **kwargs)
        self._attrs['find'] = kwargs.get('find')
        self._attrs['replace'] = kwargs.get('replace')

    def execute(self, verbose=False):
        replace(filename=self.filename, find=self.find, replace=self.replace, verbose=verbose)
        self._attrs['success'] = True

    @property
    def find(self):
        return self._attrs['find']

    @property
    def replace(self):
        return self._attrs['replace']

    @property
    def install(self):
        return self._attrs['filename']


class MakeDir(LoraxAction):

    REGEX = r'^(?P<dir>.*?)(\smode\s(?P<mode>.*?))?$'

    def __init__(self, **kwargs):
        LoraxAction.__init__(self)
        self._attrs['dir'] = kwargs.get('dir')
        self._attrs['mode'] = kwargs.get('mode')

    def execute(self, verbose=False):
        if not os.path.isdir(self.dir):
            if self.mode:
                os.makedirs(self.dir, mode=int(self.mode))
            else:
                os.makedirs(self.dir)
        self._attrs['success'] = True

    @property
    def dir(self):
        return self._attrs['dir']

    @property
    def mode(self):
        return self._attrs['mode']


class Chmod(LoraxAction):

    REGEX = r'^(?P<filename>.*?)\smode\s(?P<mode>[0-9]*?)$'

    def __init__(self, **kwargs):
        LoraxAction.__init__(self)
        self._attrs['filename'] = kwargs.get('filename')
        self._attrs['mode'] = kwargs.get('mode')

    def execute(self, verbose=False):
        chmod(self.filename, self.mode)
        self._attrs['success'] = True

    @property
    def filename(self):
        return self._attrs['filename']

    @property
    def mode(self):
        return self._attrs['mode']


class Chown(LoraxAction):

    REGEX = r'^(?P<filename>.*?)\suser\s(?P<user>.*?)\sgroup\s(?P<group>.*?)$'

    def __init__(self, **kwargs):
        LoraxAction.__init__(self)
        self._attrs['filename'] = kwargs.get('filename')
        self._attrs['user'] = kwargs.get('user')
        self._attrs['group'] = kwargs.get('group')

    def execute(self, verbose=False):
        uid = pwd.getpwnam(self.user)[2]
        gid = grp.getgrnam(self.group)[2]
        os.chown(self.filename, uid, gid)
        self._attrs['success'] = True

    @property
    def filename(self):
        return self._attrs['filename']

    @property
    def user(self):
        return self._attrs['user']

    @property
    def group(self):
        return self._attrs['group']


class GenerateSSHKey(LoraxAction):

    REGEX = r'^(?P<file>.*?)\stype\s(?P<type>.*?)$'

    def __init__(self, **kwargs):
        LoraxAction.__init__(self)
        self._attrs['file'] = kwargs.get('file')
        self._attrs['type'] = kwargs.get('type')

    def execute(self, verbose=False):
        cmd = "/usr/bin/ssh-keygen -q -t %s -f %s -C '' -N ''" % (self.type, self.file)
        err, output = commands.getstatusoutput(cmd)
        
        if not err:
            os.chmod(self.file, 0600)
            os.chmod(self.file + '.pub', 0644)

        self._attrs['success'] = True

    @property
    def file(self):
        return self._attrs['file']

    @property
    def type(self):
        return self._attrs['type']
