# pylorax/actions/fileactions.py

from pylorax.base import LoraxAction

import os
import re
from pylorax.utils.fileutil import cp, mv, touch, edit, replace


COMMANDS = { 'copy': 'Copy',
             'move': 'Move',
             'link': 'Link',
             'touch': 'Touch',
             'edit': 'Edit',
             'replace': 'Replace' }


class Copy(LoraxAction):

    REGEX = r'^(?P<src>.*?)\sto\s(?P<dst>.*?)(\smode\s(?P<mode>.*?))?$'

    def __init__(self, **kwargs):
        LoraxAction.__init__(self)
        self._attrs['src'] = kwargs.get('src')
        self._attrs['dst'] = kwargs.get('dst')
        self._attrs['mode'] = kwargs.get('mode')

    def execute(self, verbose=False):
        dst_dir = os.path.dirname(self.dst)
        if not os.path.isdir(dst_dir):
            os.makedirs(dst_dir)

        cp(src=self.src, dst=self.dst, mode=self.mode, verbose=verbose)
        self._attrs['success'] = True

    def getDeps(self):
        return self._attrs['src']

    @property
    def src(self):
        return self._attrs['src']

    @property
    def dst(self):
        return self._attrs['dst']

    @property
    def mode(self):
        return self._attrs['mode']

    @property
    def install(self):
        return self._attrs.get('src')


class Move(Copy):
    def execute(self, verbose=False):
        mv(src=self.src, dst=self.dst, mode=self.mode, verbose=verbose)
        self._attrs['success'] = True


class Link(LoraxAction):

    REGEX = r'^(?P<name>.*?)\sto\s(?P<target>.*?)$'

    def __init__(self, **kwargs):
        LoraxAction.__init__(self)
        self._attrs['name'] = kwargs.get('name')
        self._attrs['target'] = kwargs.get('target')

        file = getFileName(self._attrs['name'])
        if file:
            self._attrs['install'] = file

    def execute(self, verbose=False):
        os.symlink(self.name, self.target)
        self._attrs['success'] = True

    @property
    def name(self):
        return self._attrs['name']

    @property
    def target(self):
        return self._attrs['target']

    @property
    def install(self):
        return self._attrs['install']


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

    REGEX = r'^(?P<filename>.*?)\stext\s"(?P<text>.*?)"((?P<append>\sappend?))?$'

    def __init__(self, **kwargs):
        Touch.__init__(self, **kwargs)
        self._attrs['text'] = kwargs.get('text')
        
        append = kwargs.get('append', False)
        if append:
            self._attrs['append'] = True
        else:
            self._attrs['append'] = False

        file = getFileName(self._attrs['filename'])
        if file:
            self._attrs['install'] = file

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
        return self._attrs['install']


class Replace(Touch):

    REGEX = r'^(?P<filename>.*?)\sfind\s"(?P<find>.*?)"\sreplace\s"(?P<replace>.*?)"$'

    def __init__(self, **kwargs):
        Touch.__init__(self, **kwargs)
        self._attrs['find'] = kwargs.get('find')
        self._attrs['replace'] = kwargs.get('replace')

        file = getFileName(self._attrs['filename'])
        if file:
            self._attrs['install'] = file

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
        return self._attrs['install']
