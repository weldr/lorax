#
# ssh.py
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
