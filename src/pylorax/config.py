#
# config.py
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

from decorators import singleton
import output


@singleton
class LoraxConfig(object):

    def __init__(self):
        # output settings
        self.colors = True
        self.encoding = "utf-8"
        self.debug = True

        self.pedantic = False

        self.confdir = "/etc/lorax"
        self.datadir = "/usr/share/lorax"

        self.ignore_errors = "/etc/lorax/ignore_errors"

    def __setattr__(self, attr, value):
        output.LoraxOutput().debug("[set {0}={1}]".format(attr, value))
        object.__setattr__(self, attr, value)
