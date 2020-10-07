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

import os

from composer import http_client as client
from composer.cli.help import sources_help
from composer.cli.utilities import argify, handle_api_result

def sources_cmd(opts):
    """Process sources commands

    :param opts: Cmdline arguments
    :type opts: argparse.Namespace
    :returns: Value to return from sys.exit()
    :rtype: int
    """
    cmd_map = {
        "list":     sources_list,
        "info":     sources_info,
        "add":      sources_add,
        "change":   sources_add,
        "delete":   sources_delete,
        }
    if opts.args[1] == "help" or opts.args[1] == "--help":
        print(sources_help)
        return 0
    elif opts.args[1] not in cmd_map:
        log.error("Unknown sources command: %s", opts.args[1])
        return 1

    return cmd_map[opts.args[1]](opts.socket, opts.api_version, opts.args[2:], opts.json)

def sources_list(socket_path, api_version, args, show_json=False):
    """Output the list of available sources

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    sources list
    """
    api_route = client.api_url(api_version, "/projects/source/list")
    result = client.get_url_json(socket_path, api_route)
    (rc, exit_now) = handle_api_result(result, show_json)
    if exit_now:
        return rc

    # "list" should output a plain list of identifiers, one per line.
    print("\n".join(result["sources"]))
    return rc

def sources_info(socket_path, api_version, args, show_json=False):
    """Output info on a list of projects

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    sources info <source-name>
    """
    if len(args) == 0:
        log.error("sources info is missing the name of the source")
        return 1

    if show_json:
        api_route = client.api_url(api_version, "/projects/source/info/%s" % ",".join(args))
        result = client.get_url_json(socket_path, api_route)
        rc = handle_api_result(result, show_json)[0]
    else:
        api_route = client.api_url(api_version, "/projects/source/info/%s?format=toml" % ",".join(args))
        try:
            result = client.get_url_raw(socket_path, api_route)
            print(result)
            rc = 0
        except RuntimeError as e:
            print(str(e))
            rc = 1

    return rc

def sources_add(socket_path, api_version, args, show_json=False):
    """Add or change a source

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    sources add <source.toml>
    """
    api_route = client.api_url(api_version, "/projects/source/new")
    rval = 0
    for source in argify(args):
        if not os.path.exists(source):
            log.error("Missing source file: %s", source)
            continue
        with open(source, "r") as f:
            source_toml = f.read()

        result = client.post_url_toml(socket_path, api_route, source_toml)
        if handle_api_result(result, show_json)[0]:
            rval = 1
    return rval

def sources_delete(socket_path, api_version, args, show_json=False):
    """Delete a source

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    sources delete <source-name>
    """
    api_route = client.api_url(api_version, "/projects/source/delete/%s" % args[0])
    result = client.delete_url_json(socket_path, api_route)

    return handle_api_result(result, show_json)[0]
