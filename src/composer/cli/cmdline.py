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

VERSION = "{0}-{1}".format(os.path.basename(sys.argv[0]), vernum)

# Documentation for the commands
epilog = """
compose start <BLUEPRINT> <TYPE>
    Start a compose using the selected blueprint and output type.

compose types
    List the supported output types.

compose status
    List the status of all running and finished composes.

compose log <UUID> [<SIZE>]
    Show the last SIZE kB of the compose log.

compose cancel <UUID>
    Cancel a running compose and delete any intermediate results.

compose delete <UUID,...>
    Delete the listed compose results.

compose info <UUID>
    Show detailed information on the compose.

compose metadata <UUID>
    Download the metadata use to create the compose to <uuid>-metadata.tar

compose logs <UUID>
    Download the compose logs to <uuid>-logs.tar

compose results <UUID>
    Download all of the compose results; metadata, logs, and image to <uuid>.tar

compose image <UUID>
    Download the output image from the compose. Filename depends on the type.

blueprints list
    List the names of the available blueprints.

blueprints show <BLUEPRINT,...>
    Display the blueprint in TOML format.

blueprints changes <BLUEPRINT,...>
    Display the changes for each blueprint.

blueprints diff <BLUEPRINT> <FROM-COMMIT> <TO-COMMIT>
    Display the differences between 2 versions of a blueprint.
    FROM-COMMIT can be a commit hash or NEWEST
    TO-COMMIT  can be a commit hash, NEWEST, or WORKSPACE

blueprints save <BLUEPRINT,...>
    Save the blueprint to a file, <BLUEPRINT>.toml

blueprints delete <BLUEPRINT>
    Delete a blueprint from the server

blueprints depsolve <BLUEPRINT,...>
    Display the packages needed to install the blueprint.

blueprints push <BLUEPRINT>
    Push a blueprint TOML file to the server.

blueprints freeze <BLUEPRINT,...>
    Display the frozen blueprint's modules and packages.

blueprints freeze show <BLUEPRINT,...>
    Display the frozen blueprint in TOML format.

blueprints freeze save <BLUEPRINT,...>
    Save the frozen blueprint to a file, <blueprint-name>.frozen.toml.

blueprints tag <BLUEPRINT>
    Tag the most recent blueprint commit as a release.

blueprints undo <BLUEPRINT> <COMMIT>
    Undo changes to a blueprint by reverting to the selected commit.

blueprints workspace <BLUEPRINT>
    Push the blueprint TOML to the temporary workspace storage.

modules list
    List the available modules.

projects list
    List the available projects.

projects info <PROJECT,...>
    Show details about the listed projects.

"""

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
    parser.add_argument("--log", dest="logfile", default="./composer-cli.log", metavar="LOG",
                        help="Path to logfile (./composer-cli.log)")
    parser.add_argument("-a", "--api", dest="api_version", default="0", metavar="APIVER",
                        help="API Version to use")
    parser.add_argument("--test", dest="testmode", default=0, type=int, metavar="TESTMODE",
                        help="Pass test mode to compose. 1=Mock compose with fail. 2=Mock compose with finished.")
    parser.add_argument("-V", action="store_true", dest="showver",
                        help="show program's version number and exit")

    # Commands are implemented by parsing the remaining arguments outside of argparse
    parser.add_argument('args', nargs=argparse.REMAINDER)

    return parser
