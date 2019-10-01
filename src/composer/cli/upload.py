#
# Copyright (C) 2019  Red Hat, Inc.
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

import json
import toml
import os

from composer import http_client as client
from composer.cli.help import upload_help
from composer.cli.utilities import handle_api_result

def upload_cmd(opts):
    """Process upload commands

    :param opts: Cmdline arguments
    :type opts: argparse.Namespace
    :returns: Value to return from sys.exit()
    :rtype: int

    This dispatches the upload commands to a function
    """
    cmd_map = {
        "list":   upload_list,
        "info":   upload_info,
        "start":  upload_start,
        "log":    upload_log,
        "cancel": upload_cancel,
        "delete": upload_delete,
        "reset":  upload_reset,
        }
    if opts.args[1] == "help" or opts.args[1] == "--help":
        print(upload_help)
        return 0
    elif opts.args[1] not in cmd_map:
        log.error("Unknown upload command: %s", opts.args[1])
        return 1

    return cmd_map[opts.args[1]](opts.socket, opts.api_version, opts.args[2:], opts.json, opts.testmode)

def upload_list(socket_path, api_version, args, show_json=False, testmode=0):
    """Return the composes and their associated upload uuids and status

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool
    :param testmode: unused in this function
    :type testmode: int

    upload list
    """
    api_route = client.api_url(api_version, "/compose/finished")
    r = client.get_url_json(socket_path, api_route)
    results = r["finished"]
    if not results:
        return 0

    if show_json:
        print(json.dumps(results, indent=4))
    else:
        compose_fmt = "{id} {queue_status} {blueprint} {version} {compose_type}"
        upload_fmt = '    {uuid} "{image_name}" {provider_name} {status}'
        for c in results:
            print(compose_fmt.format(**c))
            print("\n".join(upload_fmt.format(**u) for u in c["uploads"]))
            print()

    return 0

def upload_info(socket_path, api_version, args, show_json=False, testmode=0):
    """Return detailed information about the upload

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool
    :param testmode: unused in this function
    :type testmode: int

    upload info <uuid>

    This returns information about the upload, including uuid, name, status, service, and image.
    """
    if len(args) == 0:
        log.error("info is missing the upload uuid")
        return 1

    api_route = client.api_url(api_version, "/upload/info/%s" % args[0])
    result = client.get_url_json(socket_path, api_route)
    (rc, exit_now) = handle_api_result(result, show_json)
    if exit_now:
        return rc

    image_path = result["upload"]["image_path"]
    print("%s %-8s %-15s %-8s %s" % (result["upload"]["uuid"],
                                     result["upload"]["status"],
                                     result["upload"]["image_name"],
                                     result["upload"]["provider_name"],
                                     os.path.basename(image_path) if image_path else "UNFINISHED"))

    return rc

def upload_start(socket_path, api_version, args, show_json=False, testmode=0):
    """Start upload up a build uuid image

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool
    :param testmode: unused in this function
    :type testmode: int

    upload start <build-uuid> <image-name> [<provider> <profile> | <profile.toml>]
    """
    if len(args) == 0:
        log.error("start is missing the compose build id")
        return 1
    if len(args) == 1:
        log.error("start is missing the image name")
        return 1
    if len(args) == 2:
        log.error("start is missing the provider and profile details")
        return 1

    body = {"image_name": args[1]}
    if len(args) == 3:
        try:
            body.update(toml.load(args[2]))
        except toml.TomlDecodeError as e:
            log.error(str(e))
            return 1
    elif len(args) == 4:
        body["provider"] = args[2]
        body["profile"] = args[3]
    else:
        log.error("start has incorrect number of arguments")
        return 1

    api_route = client.api_url(api_version, "/compose/uploads/schedule/%s" % args[0])
    result = client.post_url_json(socket_path, api_route, json.dumps(body))
    (rc, exit_now) = handle_api_result(result, show_json)
    if exit_now:
        return rc

    print("Upload %s added to the queue" % result["upload_id"])
    return rc

def upload_log(socket_path, api_version, args, show_json=False, testmode=0):
    """Return the upload log

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool
    :param testmode: unused in this function
    :type testmode: int

    upload log <build-uuid>
    """
    if len(args) == 0:
        log.error("log is missing the upload uuid")
        return 1

    api_route = client.api_url(api_version, "/upload/log/%s" % args[0])
    result = client.get_url_json(socket_path, api_route)
    (rc, exit_now) = handle_api_result(result, show_json)
    if exit_now:
        return rc

    print("Upload log for %s:\n" % result["upload_id"])
    print(result["log"])

    return 0

def upload_cancel(socket_path, api_version, args, show_json=False, testmode=0):
    """Cancel the queued or running upload

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool
    :param testmode: unused in this function
    :type testmode: int

    upload cancel <build-uuid>
    """
    if len(args) == 0:
        log.error("cancel is missing the upload uuid")
        return 1

    api_route = client.api_url(api_version, "/upload/cancel/%s" % args[0])
    result = client.delete_url_json(socket_path, api_route)
    return handle_api_result(result, show_json)[0]

def upload_delete(socket_path, api_version, args, show_json=False, testmode=0):
    """Delete an upload and remove it from the build

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool
    :param testmode: unused in this function
    :type testmode: int

    upload delete <build-uuid>
    """
    if len(args) == 0:
        log.error("delete is missing the upload uuid")
        return 1

    api_route = client.api_url(api_version, "/upload/delete/%s" % args[0])
    result = client.delete_url_json(socket_path, api_route)
    return handle_api_result(result, show_json)[0]

def upload_reset(socket_path, api_version, args, show_json=False, testmode=0):
    """Reset the upload and execute it again

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool
    :param testmode: unused in this function
    :type testmode: int

    upload reset <build-uuid>
    """
    if len(args) == 0:
        log.error("reset is missing the upload uuid")
        return 1

    api_route = client.api_url(api_version, "/upload/reset/%s" % args[0])
    result = client.post_url_json(socket_path, api_route, json.dumps({}))
    return handle_api_result(result, show_json)[0]
