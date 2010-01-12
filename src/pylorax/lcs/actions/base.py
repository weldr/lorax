#
# base.py
# base lorax control system action class
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

class LCSAction(object):
    """LCS Action base class.

    To create your own custom action, subclass this class, and override
    the methods you need.

    A valid action has to have a REGEX class variable, which specifies
    the format of the action command, so the needed parameters can be
    properly extracted, and an execute() method, where all the work
    should be done. This medhod will be called by Lorax.

    Don't forget to include a command : action map for your new action
    in the COMMANDS dictionary in the beginning of your file.
    Action classes which are not in the COMMANDS dictionary will not
    be loaded by Lorax.

    """

    # regular expression for extracting the parameters from the command
    REGEX = r""

    def __init__(self):
        if self.__class__ is LCSAction:
            raise TypeError("LCSAction is an abstract class, " \
                            "cannot be used this way")

        self._attrs = {}

    def __str__(self):
        return "%s: %s" % (self.__class__.__name__, self._attrs)

    def execute(self):
        raise NotImplementedError("execute() method not implemented")
