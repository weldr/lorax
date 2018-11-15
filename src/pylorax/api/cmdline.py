#
# cmdline.py
#
# Copyright (C) 2018 Red Hat, Inc.
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
import os
import sys
import argparse

from pylorax import vernum

DEFAULT_USER  = "root"
DEFAULT_GROUP = "weldr"

version = "{0}-{1}".format(os.path.basename(sys.argv[0]), vernum)

def lorax_composer_parser():
    """ Return the ArgumentParser for lorax-composer"""

    parser = argparse.ArgumentParser(description="Lorax Composer API Server",
                                     fromfile_prefix_chars="@")

    parser.add_argument("--socket", default="/run/weldr/api.socket", metavar="SOCKET",
                        help="Path to the socket file to listen on")
    parser.add_argument("--user", default=DEFAULT_USER, metavar="USER",
                        help="User to use for reduced permissions")
    parser.add_argument("--group", default=DEFAULT_GROUP, metavar="GROUP",
                        help="Group to set ownership of the socket to")
    parser.add_argument("--log", dest="logfile", default="/var/log/lorax-composer/composer.log", metavar="LOG",
                        help="Path to logfile (/var/log/lorax-composer/composer.log)")
    parser.add_argument("--mockfiles", default="/var/tmp/bdcs-mockfiles/", metavar="MOCKFILES",
                        help="Path to JSON files used for /api/mock/ paths (/var/tmp/bdcs-mockfiles/)")
    parser.add_argument("--sharedir", type=os.path.abspath, metavar="SHAREDIR",
                        help="Directory containing all the templates. Overrides config file sharedir")
    parser.add_argument("-V", action="store_true", dest="showver",
                        help="show program's version number and exit")
    parser.add_argument("-c", "--config", default="/etc/lorax/composer.conf", metavar="CONFIG",
                        help="Path to lorax-composer configuration file.")
    parser.add_argument("--releasever", default=None, metavar="STRING",
                        help="Release version to use for $releasever in dnf repository urls")
    parser.add_argument("--tmp", default="/var/tmp",
                        help="Top level temporary directory")
    parser.add_argument("--proxy", default=None, metavar="PROXY",
                        help="Set proxy for DNF, overrides configuration file setting.")
    parser.add_argument("--no-system-repos", action="store_true", default=False,
                        help="Do not copy over system repos from /etc/yum.repos.d/ at startup")
    parser.add_argument("BLUEPRINTS", metavar="BLUEPRINTS",
                        help="Path to the blueprints")

    return parser
