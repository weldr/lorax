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

import sys
import json

from composer import http_client as client
from composer.cli.utilities import argify, handle_api_result, packageNEVRA

def compose_cmd(opts):
    """Process compose commands

    :param opts: Cmdline arguments
    :type opts: argparse.Namespace
    :returns: Value to return from sys.exit()
    :rtype: int

    This dispatches the compose commands to a function
    """
    cmd_map = {
        "status":   compose_status,
        "types":    compose_types,
        "start":    compose_start,
        "log":      compose_log,
        "cancel":   compose_cancel,
        "delete":   compose_delete,
        "details":  compose_details,
        "metadata": compose_metadata,
        "results":  compose_results,
        "logs":     compose_logs,
        "image":    compose_image,
        }
    if opts.args[1] not in cmd_map:
        log.error("Unknown compose command: %s", opts.args[1])
        return 1

    return cmd_map[opts.args[1]](opts.socket, opts.api_version, opts.args[2:], opts.json)

def compose_status(socket_path, api_version, args, show_json=False):
    """Return the status of all known composes

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    This doesn't map directly to an API command, it combines the results from queue, finished,
    and failed so raw JSON output is not available.
    """
    def get_status(compose):
        return {"id": compose["id"],
                "recipe": compose["recipe"],
                "version": compose["version"],
                "status": compose["queue_status"]}

    # Sort the status in a specific order
    def sort_status(a):
        order = ["RUNNING", "WAITING", "FINISHED", "FAILED"]
        return (order.index(a["status"]), a["recipe"], a["version"])

    status = []

    # Get the composes currently in the queue
    api_route = client.api_url(api_version, "/compose/queue")
    result = client.get_url_json(socket_path, api_route)
    status.extend(map(get_status, result["run"] + result["new"]))

    # Get the list of finished composes
    api_route = client.api_url(api_version, "/compose/finished")
    result = client.get_url_json(socket_path, api_route)
    status.extend(map(get_status, result["finished"]))

    # Get the list of failed composes
    api_route = client.api_url(api_version, "/compose/failed")
    result = client.get_url_json(socket_path, api_route)
    status.extend(map(get_status, result["failed"]))

    # Sort them by status (running, waiting, finished, failed) and then by name and version.
    status.sort(key=sort_status)

    if show_json:
        print(json.dumps(status, indent=4))
        return 0

    # Print them as UUID RECIPE STATUS
    for c in status:
        print("%s %-8s %-15s %s" % (c["id"], c["status"], c["recipe"], c["version"]))


def compose_types(socket_path, api_version, args, show_json=False):
    """Return information about the supported compose types

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    Add additional details to types that are known to composer-cli. Raw JSON output does not
    include this extra information.
    """
    api_route = client.api_url(api_version, "/compose/types")
    result = client.get_url_json(socket_path, api_route)
    if show_json:
        print(json.dumps(result, indent=4))
        return 0

    print("Compose Types: " + ", ".join([t["name"] for t in result["types"]]))

def compose_start(socket_path, api_version, args, show_json=False):
    """Start a new compose using the selected recipe and type

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    compose start <recipe-name> <compose-type>
    """
    if len(args) == 0:
        log.error("start is missing the recipe name and output type")
        return 1
    if len(args) == 1:
        log.error("start is missing the output type")
        return 1

    config = {
        "recipe_name": args[0],
        "compose_type": args[1],
        "branch": "master"
        }
    api_route = client.api_url(api_version, "/compose")
    result = client.post_url_json(socket_path, api_route, json.dumps(config))

    if show_json:
        print(json.dumps(result, indent=4))
        return 0

    if result.get("error", False):
        log.error(result["error"]["msg"])
        return 1

    if result["status"] == False:
        return 1

    print("Compose %s added to the queue" % result["build_id"])
    return 0

def compose_log(socket_path, api_version, args, show_json=False):
    """Show the last part of the compose log

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    compose log <uuid> [<size>kB]

    This will display the last 1kB of the compose's log file. Can be used to follow progress
    during the build.
    """
    if len(args) == 0:
        log.error("log is missing the compose build id")
        return 1
    if len(args) == 2:
        try:
            log_size = int(args[1])
        except ValueError:
            log.error("Log size must be an integer.")
            return 1
    else:
        log_size = 1024

    api_route = client.api_url(api_version, "/compose/log/%s?size=%d" % (args[0], log_size))
    result = client.get_url_raw(socket_path, api_route)

    print(result)

def compose_cancel(socket_path, api_version, args, show_json=False):
    """Cancel a running compose

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    compose cancel <uuid>

    This will cancel a running compose. It does nothing if the compose has finished.
    """
    if len(args) == 0:
        log.error("cancel is missing the compose build id")
        return 1

    api_route = client.api_url(api_version, "/compose/cancel/%s" % args[0])
    result = client.delete_url_json(socket_path, api_route)
    return handle_api_result(result, show_json)

def compose_delete(socket_path, api_version, args, show_json=False):
    """Delete a finished compose's results

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    compose delete <uuid,...>

    Delete the listed compose results. It will only delete results for composes that have finished
    or failed, not a running compose.
    """
    if len(args) == 0:
        log.error("delete is missing the compose build id")
        return 1

    api_route = client.api_url(api_version, "/compose/delete/%s" % (",".join(argify(args))))
    result = client.delete_url_json(socket_path, api_route)

    if show_json:
        print(json.dumps(result, indent=4))
        return 0

    # Print any errors
    for err in result.get("errors", []):
        log.error("%s: %s", err["uuid"], err["msg"])

    if result.get("errors", []):
        return 1
    else:
        return 0

def compose_details(socket_path, api_version, args, show_json=False):
    """Return detailed information about the compose

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    compose details <uuid>

    This returns information about the compose, including the recipe and the dependencies.
    """
    if len(args) == 0:
        log.error("details is missing the compose build id")
        return 1

    api_route = client.api_url(api_version, "/compose/info/%s" % args[0])
    result = client.get_url_json(socket_path, api_route)
    if show_json:
        print(json.dumps(result, indent=4))
        return 0

    print("%s %-8s %-15s %s %s" % (result["id"], 
                                   result["queue_status"],
                                   result["recipe"]["name"],
                                   result["recipe"]["version"],
                                   result["compose_type"]))
    print("Recipe Packages:")
    for p in result["recipe"]["packages"]:
        print("    %s-%s" % (p["name"], p["version"]))

    print("Recipe Modules:")
    for m in result["recipe"]["modules"]:
        print("    %s-%s" % (m["name"], m["version"]))

    print("Dependencies:")
    for d in result["deps"]["packages"]:
        print("    " + packageNEVRA(d))

def compose_metadata(socket_path, api_version, args, show_json=False):
    """Download a tar file of the compose's metadata

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    compose metadata <uuid>

    Saves the metadata as uuid-metadata.tar
    """
    if len(args) == 0:
        log.error("metadata is missing the compose build id")
        return 1

    api_route = client.api_url(api_version, "/compose/metadata/%s" % args[0])
    return client.download_file(socket_path, api_route)

def compose_results(socket_path, api_version, args, show_json=False):
    """Download a tar file of the compose's results

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    compose results <uuid>

    The results includes the metadata, output image, and logs.
    It is saved as uuid.tar
    """
    if len(args) == 0:
        log.error("results is missing the compose build id")
        return 1

    api_route = client.api_url(api_version, "/compose/results/%s" % args[0])
    return client.download_file(socket_path, api_route, sys.stdout.isatty())

def compose_logs(socket_path, api_version, args, show_json=False):
    """Download a tar of the compose's logs

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    compose logs <uuid>

    Saves the logs as uuid-logs.tar
    """
    if len(args) == 0:
        log.error("logs is missing the compose build id")
        return 1

    api_route = client.api_url(api_version, "/compose/logs/%s" % args[0])
    return client.download_file(socket_path, api_route, sys.stdout.isatty())

def compose_image(socket_path, api_version, args, show_json=False):
    """Download the compose's output image

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    compose image <uuid>

    This downloads only the result image, saving it as the image name, which depends on the type
    of compose that was selected.
    """
    if len(args) == 0:
        log.error("logs is missing the compose build id")
        return 1

    api_route = client.api_url(api_version, "/compose/image/%s" % args[0])
    return client.download_file(socket_path, api_route, sys.stdout.isatty())
