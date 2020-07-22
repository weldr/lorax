#
# Copyright (C) 2018-2020 Red Hat, Inc.
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

from datetime import datetime
import sys
import json
import toml

from composer import http_client as client
from composer.cli.help import compose_help
from composer.cli.utilities import argify, handle_api_result, packageNEVRA, get_arg

def compose_cmd(opts):
    """Process compose commands

    :param opts: Cmdline arguments
    :type opts: argparse.Namespace
    :returns: Value to return from sys.exit()
    :rtype: int

    This dispatches the compose commands to a function

    compose_cmd expects api to be passed. eg.

        {"version": 1, "backend": "lorax-composer"}

    """
    result = client.get_url_json(opts.socket, "/api/status")
    # Get the api version and fall back to 0 if it fails.
    api_version = result.get("api", "0")
    backend = result.get("backend", "unknown")
    api = {"version": api_version, "backend": backend}

    cmd_map = {
        "list":     compose_list,
        "status":   compose_status,
        "types":    compose_types,
        "start":    compose_start,
        "log":      compose_log,
        "cancel":   compose_cancel,
        "delete":   compose_delete,
        "info":     compose_info,
        "metadata": compose_metadata,
        "results":  compose_results,
        "logs":     compose_logs,
        "image":    compose_image,
        "start-ostree":    compose_ostree,
        }
    if opts.args[1] == "help" or opts.args[1] == "--help":
        print(compose_help)
        return 0
    elif opts.args[1] not in cmd_map:
        log.error("Unknown compose command: %s", opts.args[1])
        return 1

    return cmd_map[opts.args[1]](opts.socket, opts.api_version, opts.args[2:], opts.json, opts.testmode, api=api)

def get_size(args):
    """Return optional --size argument, and remaining args

    :param args: list of arguments
    :type args: list of strings
    :returns: (args, size)
    :rtype: tuple

    - check size argument for int
    - check other args for --size in wrong place
    - raise error? Or just return 0?
    - no size returns 0 in size
    - multiply by 1024**2 to make it easier on users to specify large sizes

    """
    args, value = get_arg(args, "--size", int)
    value = value * 1024**2 if value is not None else 0
    return (args, value)

def get_parent(args):
    """Return optional --parent argument, and remaining args

    :param args: list of arguments
    :type args: list of strings
    :returns: (args, parent)
    :rtype: tuple
    """
    args, value = get_arg(args, "--parent")
    value = value if value is not None else ""
    return (args, value)

def get_ref(args):
    """Return optional --ref argument, and remaining args

    :param args: list of arguments
    :type args: list of strings
    :returns: (args, parent)
    :rtype: tuple
    """
    args, value = get_arg(args, "--ref")
    value = value if value is not None else ""
    return (args, value)

def compose_list(socket_path, api_version, args, show_json=False, testmode=0, api=None):
    """Return a simple list of compose identifiers"""

    states = ("running", "waiting", "finished", "failed")

    which = set()

    if any(a not in states for a in args):
        # TODO: error about unknown state
        return 1
    elif not args:
        which.update(states)
    else:
        which.update(args)

    results = []

    if "running" in which or "waiting" in which:
        api_route = client.api_url(api_version, "/compose/queue")
        r = client.get_url_json(socket_path, api_route)
        if "running" in which:
            results += r["run"]
        if "waiting" in which:
            results += r["new"]

    if "finished" in which:
        api_route = client.api_url(api_version, "/compose/finished")
        r = client.get_url_json(socket_path, api_route)
        results += r["finished"]

    if "failed" in which:
        api_route = client.api_url(api_version, "/compose/failed")
        r = client.get_url_json(socket_path, api_route)
        results += r["failed"]

    if results:
        if show_json:
            print(json.dumps(results, indent=4))
        else:
            list_fmt = "{id} {queue_status} {blueprint} {version} {compose_type}"
            print("\n".join(list_fmt.format(**c) for c in results))

    return 0

def compose_status(socket_path, api_version, args, show_json=False, testmode=0, api=None):
    """Return the status of all known composes

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

    This doesn't map directly to an API command, it combines the results from queue, finished,
    and failed so raw JSON output is not available.
    """
    def get_status(compose):
        return {"id": compose["id"],
                "blueprint": compose["blueprint"],
                "version": compose["version"],
                "compose_type": compose["compose_type"],
                "image_size": compose["image_size"],
                "status": compose["queue_status"],
                "created": compose.get("job_created"),
                "started": compose.get("job_started"),
                "finished": compose.get("job_finished")}

    # Sort the status in a specific order
    def sort_status(a):
        order = ["RUNNING", "WAITING", "FINISHED", "FAILED"]
        return (order.index(a["status"]), a["blueprint"], a["version"], a["compose_type"])

    status = []

    # Get the composes currently in the queue
    api_route = client.api_url(api_version, "/compose/queue")
    result = client.get_url_json(socket_path, api_route)
    status.extend(list(map(get_status, result["run"] + result["new"])))

    # Get the list of finished composes
    api_route = client.api_url(api_version, "/compose/finished")
    result = client.get_url_json(socket_path, api_route)
    status.extend(list(map(get_status, result["finished"])))

    # Get the list of failed composes
    api_route = client.api_url(api_version, "/compose/failed")
    result = client.get_url_json(socket_path, api_route)
    status.extend(list(map(get_status, result["failed"])))

    # Sort them by status (running, waiting, finished, failed) and then by name and version.
    status.sort(key=sort_status)

    if show_json:
        print(json.dumps(status, indent=4))
        return 0

    # Print them as UUID blueprint STATUS
    for c in status:
        if c["image_size"] > 0:
            image_size = str(c["image_size"])
        else:
            image_size = ""

        dt = datetime.fromtimestamp(c.get("finished") or c.get("started") or c.get("created"))

        print("%s %-8s %s %-15s %s %-16s %s" % (c["id"], c["status"], dt.strftime("%c"), c["blueprint"],
                                                c["version"], c["compose_type"], image_size))


def compose_types(socket_path, api_version, args, show_json=False, testmode=0, api=None):
    """Return information about the supported compose types

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

    Add additional details to types that are known to composer-cli. Raw JSON output does not
    include this extra information.
    """
    api_route = client.api_url(api_version, "/compose/types")
    result = client.get_url_json(socket_path, api_route)
    if show_json:
        print(json.dumps(result, indent=4))
        return 0

    # output a plain list of identifiers, one per line
    print("\n".join(t["name"] for t in result["types"] if t["enabled"]))

def compose_start(socket_path, api_version, args, show_json=False, testmode=0, api=None):
    """Start a new compose using the selected blueprint and type

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool
    :param testmode: Set to 1 to simulate a failed compose, set to 2 to simulate a finished one.
    :type testmode: int
    :param api: Details about the API server, "version" and "backend"
    :type api: dict

    compose start [--size XXX] <blueprint-name> <compose-type> [<image-name> <provider> <profile> | <image-name> <profile.toml>]
    """
    if api == None:
        log.error("Missing api version/backend")
        return 1

    # Get the optional size before checking other parameters
    try:
        args, size = get_size(args)
    except (RuntimeError, ValueError) as e:
        log.error(str(e))
        return 1

    if len(args) == 0:
        log.error("start is missing the blueprint name and output type")
        return 1
    if len(args) == 1:
        log.error("start is missing the output type")
        return 1
    if len(args) == 3:
        log.error("start is missing the provider and profile details")
        return 1

    config = {
        "blueprint_name": args[0],
        "compose_type": args[1],
        "branch": "master"
        }
    if size > 0:
        if api["backend"] == "lorax-composer":
            log.warning("lorax-composer does not support --size, it will be ignored.")
        else:
            config["size"] = size

    if len(args) == 4:
        config["upload"] = {"image_name": args[2]}
        # profile TOML file (maybe)
        try:
            config["upload"].update(toml.load(args[3]))
        except toml.TomlDecodeError as e:
            log.error(str(e))
            return 1
    elif len(args) == 5:
        config["upload"] = {
            "image_name":  args[2],
            "provider":  args[3],
            "profile":  args[4]
        }

    if testmode:
        test_url = "?test=%d" % testmode
    else:
        test_url = ""
    api_route = client.api_url(api_version, "/compose" + test_url)
    result = client.post_url_json(socket_path, api_route, json.dumps(config))
    (rc, exit_now) = handle_api_result(result, show_json)
    if exit_now:
        return rc

    print("Compose %s added to the queue" % result["build_id"])

    if "upload_id" in result and result["upload_id"]:
        print ("Upload %s added to the upload queue" % result["upload_id"])

    return rc

def compose_ostree(socket_path, api_version, args, show_json=False, testmode=0, api=None):
    """Start a new ostree compose using the selected blueprint and type

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool
    :param testmode: Set to 1 to simulate a failed compose, set to 2 to simulate a finished one.
    :type testmode: int
    :param api: Details about the API server, "version" and "backend"
    :type api: dict

    compose start-ostree [--size XXXX] [--parent PARENT] [--ref REF] <BLUEPRINT> <TYPE> [<IMAGE-NAME> <PROFILE.TOML>]
    """
    if api == None:
        log.error("Missing api version/backend")
        return 1

    if api["backend"] == "lorax-composer":
        log.warning("lorax-composer doesn not support start-ostree.")
        return 1

    # Get the optional size before checking other parameters
    try:
        args, size = get_size(args)
        args, parent = get_parent(args)
        args, ref = get_ref(args)
    except (RuntimeError, ValueError) as e:
        log.error(str(e))
        return 1

    if len(args) == 0:
        log.error("start-ostree is missing the blueprint name, output type, and ostree details")
        return 1
    if len(args) == 1:
        log.error("start-ostree is missing the output type")
        return 1
    if len(args) == 3:
        log.error("start-ostree is missing the provider TOML file")
        return 1

    config = {
        "blueprint_name": args[0],
        "compose_type": args[1],
        "branch": "master",
        "ostree": {"ref": ref, "parent": parent},
        }
    if size > 0:
        config["size"] = size

    if len(args) == 4:
        config["upload"] = {"image_name": args[2]}
        # profile TOML file (maybe)
        try:
            config["upload"].update(toml.load(args[3]))
        except toml.TomlDecodeError as e:
            log.error(str(e))
            return 1

    if testmode:
        test_url = "?test=%d" % testmode
    else:
        test_url = ""
    api_route = client.api_url(api_version, "/compose" + test_url)
    result = client.post_url_json(socket_path, api_route, json.dumps(config))
    (rc, exit_now) = handle_api_result(result, show_json)
    if exit_now:
        return rc

    print("Compose %s added to the queue" % result["build_id"])

    if "upload_id" in result and result["upload_id"]:
        print ("Upload %s added to the upload queue" % result["upload_id"])

    return rc

def compose_log(socket_path, api_version, args, show_json=False, testmode=0, api=None):
    """Show the last part of the compose log

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
    try:
        result = client.get_url_raw(socket_path, api_route)
    except RuntimeError as e:
        print(str(e))
        return 1

    print(result)
    return 0

def compose_cancel(socket_path, api_version, args, show_json=False, testmode=0, api=None):
    """Cancel a running compose

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

    compose cancel <uuid>

    This will cancel a running compose. It does nothing if the compose has finished.
    """
    if len(args) == 0:
        log.error("cancel is missing the compose build id")
        return 1

    api_route = client.api_url(api_version, "/compose/cancel/%s" % args[0])
    result = client.delete_url_json(socket_path, api_route)
    return handle_api_result(result, show_json)[0]

def compose_delete(socket_path, api_version, args, show_json=False, testmode=0, api=None):
    """Delete a finished compose's results

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

    compose delete <uuid,...>

    Delete the listed compose results. It will only delete results for composes that have finished
    or failed, not a running compose.
    """
    if len(args) == 0:
        log.error("delete is missing the compose build id")
        return 1

    api_route = client.api_url(api_version, "/compose/delete/%s" % (",".join(argify(args))))
    result = client.delete_url_json(socket_path, api_route)
    return handle_api_result(result, show_json)[0]

def compose_info(socket_path, api_version, args, show_json=False, testmode=0, api=None):
    """Return detailed information about the compose

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

    compose info <uuid>

    This returns information about the compose, including the blueprint and the dependencies.
    """
    if len(args) == 0:
        log.error("info is missing the compose build id")
        return 1

    api_route = client.api_url(api_version, "/compose/info/%s" % args[0])
    result = client.get_url_json(socket_path, api_route)
    (rc, exit_now) = handle_api_result(result, show_json)
    if exit_now:
        return rc

    if result["image_size"] > 0:
        image_size = str(result["image_size"])
    else:
        image_size = ""


    print("%s %-8s %-15s %s %-16s %s" % (result["id"],
                                         result["queue_status"],
                                         result["blueprint"]["name"],
                                         result["blueprint"]["version"],
                                         result["compose_type"],
                                         image_size))
    print("Packages:")
    for p in result["blueprint"]["packages"]:
        print("    %s-%s" % (p["name"], p["version"]))

    print("Modules:")
    for m in result["blueprint"]["modules"]:
        print("    %s-%s" % (m["name"], m["version"]))

    print("Dependencies:")
    for d in result["deps"]["packages"]:
        print("    " + packageNEVRA(d))

    return rc

def compose_metadata(socket_path, api_version, args, show_json=False, testmode=0, api=None):
    """Download a tar file of the compose's metadata

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

    compose metadata <uuid>

    Saves the metadata as uuid-metadata.tar
    """
    if len(args) == 0:
        log.error("metadata is missing the compose build id")
        return 1

    api_route = client.api_url(api_version, "/compose/metadata/%s" % args[0])
    try:
        rc = client.download_file(socket_path, api_route)
    except RuntimeError as e:
        print(str(e))
        rc = 1

    return rc

def compose_results(socket_path, api_version, args, show_json=False, testmode=0, api=None):
    """Download a tar file of the compose's results

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

    compose results <uuid>

    The results includes the metadata, output image, and logs.
    It is saved as uuid.tar
    """
    if len(args) == 0:
        log.error("results is missing the compose build id")
        return 1

    api_route = client.api_url(api_version, "/compose/results/%s" % args[0])
    try:
        rc = client.download_file(socket_path, api_route, sys.stdout.isatty())
    except RuntimeError as e:
        print(str(e))
        rc = 1

    return rc

def compose_logs(socket_path, api_version, args, show_json=False, testmode=0, api=None):
    """Download a tar of the compose's logs

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

    compose logs <uuid>

    Saves the logs as uuid-logs.tar
    """
    if len(args) == 0:
        log.error("logs is missing the compose build id")
        return 1

    api_route = client.api_url(api_version, "/compose/logs/%s" % args[0])
    try:
        rc = client.download_file(socket_path, api_route, sys.stdout.isatty())
    except RuntimeError as e:
        print(str(e))
        rc = 1

    return rc

def compose_image(socket_path, api_version, args, show_json=False, testmode=0, api=None):
    """Download the compose's output image

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

    compose image <uuid>

    This downloads only the result image, saving it as the image name, which depends on the type
    of compose that was selected.
    """
    if len(args) == 0:
        log.error("logs is missing the compose build id")
        return 1

    api_route = client.api_url(api_version, "/compose/image/%s" % args[0])
    try:
        rc = client.download_file(socket_path, api_route, sys.stdout.isatty())
    except RuntimeError as e:
        print(str(e))
        rc = 1

    return rc
