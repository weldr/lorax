#
# file.py
# lcs file actions
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

from base import LCSAction
import pylorax.utils as utils


COMMANDS = { "remove" : "Remove",
             "copy" : "Copy",
             "symlink" : "SymLink",
             "touch" : "Touch",
             "mkdir" : "MkDir",
             "makedirs" : "MakeDirs",
             "chown" : "Chown",
             "chmod" : "Chmod",
             "edit" : "Edit",
             "replace" : "Replace" }


class Remove(LCSAction):

    REGEX = r"^(?P<filename>.*?)$"

    def __init__(self, **kwargs):
        LCSAction.__init__(self)
        self._attrs["filename"] = kwargs.get("filename")

    def execute(self):
        utils.remove(self.filename)

    @property
    def filename(self):
        return self._attrs["filename"]


# TODO add the ignore_errors flag
class Copy(LCSAction):

    REGEX = r"^(?P<src_root>.*?)\s(?P<src_path>.*?)\sto\s" \
             "(?P<dst_root>.*?)\s(?P<dst_path>.*?)" \
             "(\s(?P<nosymlinks>nosymlinks))?$"

    def __init__(self, **kwargs):
        LCSAction.__init__(self)
        self._attrs["src_root"] = kwargs.get("src_root")
        self._attrs["src_path"] = kwargs.get("src_path")
        self._attrs["dst_root"] = kwargs.get("dst_root")
        self._attrs["dst_path"] = kwargs.get("dst_path")

        nosymlinks = kwargs.get("nosymlinks")
        if nosymlinks is not None:
            self._attrs["symlinks"] = False
        else:
            self._attrs["symlinks"] = True

    def execute(self):
        utils.dcopy(src_root=self.src_root, src_path=self.src_path,
                    dst_root=self.dst_root, dst_path=self.dst_path,
                    symlinks=self.symlinks)

    @property
    def src(self):
        path = os.path.join(self._attrs["src_root"], self._attrs["src_path"])
        return os.path.normpath(path)

    @property
    def src_root(self):
        return self._attrs["src_root"]

    @property
    def src_path(self):
        return self._attrs["src_path"]

    @property
    def dst(self):
        path = os.path.join(self._attrs["dst_root"], self._attrs["dst_path"])
        return os.path.normpath(path)

    @property
    def dst_root(self):
        return self._attrs["dst_root"]

    @property
    def dst_path(self):
        return self._attrs["dst_path"]

    @property
    def symlinks(self):
        return self._attrs["symlinks"]


class SymLink(LCSAction):

    REGEX = r"^name\s(?P<name>.*?)\starget\s(?P<target>.*?)$"

    def __init__(self, **kwargs):
        LCSAction.__init__(self)
        self._attrs["name"] = kwargs.get("name")
        self._attrs["target"] = kwargs.get("target")

    def execute(self):
        utils.symlink(link_name=self.name, link_target=self.target)

    @property
    def name(self):
        return self._attrs["name"]

    @property
    def target(self):
        return self._attrs["target"]


class Touch(LCSAction):

    REGEX = r"^(?P<filename>.*?)$"

    def __init__(self, **kwargs):
        LCSAction.__init__(self)
        self._attrs["filename"] = kwargs.get("filename")

    def execute(self):
        utils.touch(self.filename)

    @property
    def filename(self):
        return self._attrs["filename"]


class MkDir(LCSAction):

    REGEX = r"^(?P<dir>.*?)(\smode\s(?P<mode>.*?))?$"

    def __init__(self, **kwargs):
        LCSAction.__init__(self)
        self._attrs["dir"] = kwargs.get("dir")

        mode = kwargs.get("mode")
        if mode is not None:
            self._attrs["mode"] = int(mode, 8)
        else:
            self._attrs["mode"] = None

    def execute(self):
        utils.mkdir(self.dir, self.mode)

    @property
    def dir(self):
        return self._attrs["dir"]

    @property
    def mode(self):
        return self._attrs["mode"]


class MakeDirs(MkDir):

    def __init__(self, **kwargs):
        MkDir.__init__(self, **kwargs)

    def execute(self):
        utils.makedirs(self.dir, self.mode)


class Chown(LCSAction):

    REGEX = r"^(?P<filename>.*?)\suser\s(?P<user>.*?)" \
             "\sgroup\s(?P<group>.*?)(\s(?P<recursive>recursive))?$"

    def __init__(self, **kwargs):
        LCSAction.__init__(self)
        self._attrs["filename"] = kwargs.get("filename")
        self._attrs["user"] = kwargs.get("user")
        self._attrs["group"] = kwargs.get("group")

        recursive = kwargs.get("recursive")
        if recursive is not None:
            self._attrs["recursive"] = True
        else:
            self._attrs["recursive"] = False

    def execute(self):
        utils.chown(self.filename, self.user, self.group, self.recursive)

    @property
    def filename(self):
        return self._attrs["filename"]

    @property
    def user(self):
        return self._attrs["user"]

    @property
    def group(self):
        return self._attrs["group"]

    @property
    def recursive(self):
        return self._attrs["recursive"]


class Chmod(LCSAction):

    REGEX = r"^(?P<filename>.*?)\smode\s(?P<mode>[0-7]*?)" \
             "(\s(?P<recursive>recursive))?$"

    def __init__(self, **kwargs):
        LCSAction.__init__(self)
        self._attrs["filename"] = kwargs.get("filename")
        self._attrs["mode"] = int(kwargs.get("mode"), 8)

        recursive = kwargs.get("recursive")
        if recursive is not None:
            self._attrs["recursive"] = True
        else:
            self._attrs["recursive"] = False

    def execute(self):
        utils.chmod(self.filename, self.mode, self.recursive)

    @property
    def filename(self):
        return self._attrs["filename"]

    @property
    def mode(self):
        return self._attrs["mode"]

    @property
    def recursive(self):
        return self._attrs["recursive"]


class Edit(Touch):

    REGEX = r'^(?P<filename>.*?)\stext\s"(?P<text>.*?)"' \
             '(\s(?P<append>append))?$'

    def __init__(self, **kwargs):
        Touch.__init__(self, **kwargs)
        self._attrs["text"] = kwargs.get("text")

        append = kwargs.get("append")
        if append is not None:
            self._attrs["append"] = True
        else:
            self._attrs["append"] = False

    def execute(self):
        utils.edit(self.filename, self.text, self.append)

    @property
    def text(self):
        return self._attrs["text"]

    @property
    def append(self):
        return self._attrs["append"]


class Replace(Touch):

    REGEX = r'^(?P<filename>.*?)\sfind\s"(?P<find>.*?)"' \
             '\sreplace\s"(?P<replace>.*?)"$'

    def __init__(self, **kwargs):
        Touch.__init__(self, **kwargs)
        self._attrs["find"] = kwargs.get("find")
        self._attrs["replace"] = kwargs.get("replace")

    def execute(self):
        utils.replace(self.filename, self.find, self.replace)

    @property
    def find(self):
        return self._attrs["find"]

    @property
    def replace(self):
        return self._attrs["replace"]
