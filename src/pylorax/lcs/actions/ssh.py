#
# ssh.py
# lcs ssh actions
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

import commands

from base import LCSAction
import pylorax.utils as utils


COMMANDS = { "gensshkey" : "GenerateSSHKey" }


class GenerateSSHKey(LCSAction):

    REGEX = r"^(?P<filename>.*?)\stype\s(?P<type>.*?)$"

    def __init__(self, **kwargs):
        LCSAction.__init__(self)
        self._attrs["filename"] = kwargs.get("filename")
        self._attrs["type"] = kwargs.get("type")

    def execute(self):
        cmd = "/usr/bin/ssh-keygen -q -t %s -f %s -C '' -N ''" % \
              (self.type, self.filename)

        err, output = commands.getstatusoutput(cmd)

        if not err:
            utils.chmod(self.filename, 0600)
            utils.chmod(self.filename + ".pub", 0644)

    @property
    def filename(self):
        return self._attrs["filename"]

    @property
    def type(self):
        return self._attrs["type"]
