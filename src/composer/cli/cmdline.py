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
compose start <blueprint> <type>    Start a compose using the selected blueprint and output type.
        types                       List the supported output types.
        status                      List the status of all running and finished composes.
        log <uuid> [<size>kB]       Show the last 1kB of the compose log.
        cancel <uuid>               Cancel a running compose and delete any intermediate results.
        delete <uuid,...>           Delete the listed compose results.
        info <uuid>                 Show detailed information on the compose.
        metadata <uuid>             Download the metadata use to create the compose to <uuid>-metadata.tar
        logs <uuid>                 Download the compose logs to <uuid>-logs.tar
        results <uuid>              Download all of the compose results; metadata, logs, and image to <uuid>.tar
        image <uuid>                Download the output image from the compose. Filename depends on the type.
blueprints list                     List the names of the available blueprints.
        show <blueprint,...>        Display the blueprint in TOML format.
        changes <blueprint,...>     Display the changes for each blueprint.
        diff <blueprint-name>       Display the differences between 2 versions of a blueprint.
             <from-commit>          Commit hash or NEWEST
             <to-commit>            Commit hash, NEWEST, or WORKSPACE
        save <blueprint,...>        Save the blueprint to a file, <blueprint-name>.toml
        delete <blueprint>          Delete a blueprint from the server
        depsolve <blueprint,...>    Display the packages needed to install the blueprint.
        push <blueprint>            Push a blueprint TOML file to the server.
        freeze <blueprint,...>      Display the frozen blueprint's modules and packages.
        freeze show <blueprint,...> Display the frozen blueprint in TOML format.
        freeze save <blueprint,...> Save the frozen blueprint to a file, <blueprint-name>.frozen.toml.
        tag <blueprint>             Tag the most recent blueprint commit as a release.
        undo <blueprint> <commit>   Undo changes to a blueprint by reverting to the selected commit.
        workspace <blueprint>       Push the blueprint TOML to the temporary workspace storage.
modules list                        List the available modules.
projects list                       List the available projects.
projects info <project,...>         Show details about the listed projects.
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
