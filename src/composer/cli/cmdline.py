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

from composer import vernum
from composer.cli.help import epilog

VERSION = "{0}-{1}".format(os.path.basename(sys.argv[0]), vernum)

def composer_cli_parser():
    """ Return the ArgumentParser for composer-cli"""

    parser = argparse.ArgumentParser(description="Lorax Composer commandline tool",
                                     epilog=epilog,
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     fromfile_prefix_chars="@")

    parser.add_argument("-j", "--json", action="store_true", default=False,
                        help="Output the raw JSON response instead of the normal output.")
    parser.add_argument("-s", "--socket", default="/run/weldr/api.socket", metavar="SOCKET",
                        help="Path to the socket file to listen on")
    parser.add_argument("--log", dest="logfile", default=None, metavar="LOG",
                        help="Path to logfile (./composer-cli.log)")
    parser.add_argument("-a", "--api", dest="api_version", default="1", metavar="APIVER",
                        help="API Version to use")
    parser.add_argument("--test", dest="testmode", default=0, type=int, metavar="TESTMODE",
                        help="Pass test mode to compose. 1=Mock compose with fail. 2=Mock compose with finished.")
    parser.add_argument("-V", action="store_true", dest="showver",
                        help="show program's version number and exit")

    # Commands are implemented by parsing the remaining arguments outside of argparse
    parser.add_argument('args', nargs=argparse.REMAINDER)

    return parser
