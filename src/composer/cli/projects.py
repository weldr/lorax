#
# Copyright (C) 2018  Red Hat, Inc.
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
import logging
log = logging.getLogger("composer-cli")

import textwrap

from composer import http_client as client
from composer.cli.help import projects_help
from composer.cli.utilities import handle_api_result

def projects_cmd(opts):
    """Process projects commands

    :param opts: Cmdline arguments
    :type opts: argparse.Namespace
    :returns: Value to return from sys.exit()
    :rtype: int
    """
    cmd_map = {
        "list":      projects_list,
        "info":      projects_info,
        }
    if opts.args[1] == "help" or opts.args[1] == "--help":
        print(projects_help)
        return 0
    elif opts.args[1] not in cmd_map:
        log.error("Unknown projects command: %s", opts.args[1])
        return 1

    return cmd_map[opts.args[1]](opts.socket, opts.api_version, opts.args[2:], opts.json)

def projects_list(socket_path, api_version, args, show_json=False):
    """Output the list of available projects

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    projects list
    """
    api_route = client.api_url(api_version, "/projects/list")
    result = client.get_url_json_unlimited(socket_path, api_route)
    (rc, exit_now) = handle_api_result(result, show_json)
    if exit_now:
        return rc

    for proj in result["projects"]:
        for k in [field for field in ("name", "summary", "homepage", "description") if proj[field]]:
            print("%s: %s" % (k.title(), textwrap.fill(proj[k], subsequent_indent=" " * (len(k)+2))))
        print("\n\n")

    return rc

def projects_info(socket_path, api_version, args, show_json=False):
    """Output info on a list of projects

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    projects info <project,...>
    """
    if len(args) == 0:
        log.error("projects info is missing the packages")
        return 1

    api_route = client.api_url(api_version, "/projects/info/%s" % ",".join(args))
    result = client.get_url_json(socket_path, api_route)
    (rc, exit_now) = handle_api_result(result, show_json)
    if exit_now:
        return rc

    for proj in result["projects"]:
        for k in [field for field in ("name", "summary", "homepage", "description") if proj[field]]:
            print("%s: %s" % (k.title(), textwrap.fill(proj[k], subsequent_indent=" " * (len(k)+2))))
        print("Builds: ")
        for build in proj["builds"]:
            print("    %s%s-%s.%s at %s for %s" % ("" if not build["epoch"] else str(build["epoch"]) + ":",
                                                       build["source"]["version"],
                                                       build["release"],
                                                       build["arch"],
                                                       build["build_time"],
                                                       build["changelog"]))
        print("")
    return rc
