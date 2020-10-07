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
from composer.cli.help import providers_help
from composer.cli.utilities import handle_api_result, toml_filename

def providers_cmd(opts):
    """Process providers commands

    :param opts: Cmdline arguments
    :type opts: argparse.Namespace
    :returns: Value to return from sys.exit()
    :rtype: int

    This dispatches the providers commands to a function
    """
    cmd_map = {
        "list":     providers_list,
        "info":     providers_info,
        "show":     providers_show,
        "push":     providers_push,
        "save":     providers_save,
        "delete":   providers_delete,
        "template": providers_template
        }
    if opts.args[1] == "help" or opts.args[1] == "--help":
        print(providers_help)
        return 0
    elif opts.args[1] not in cmd_map:
        log.error("Unknown providers command: %s", opts.args[1])
        return 1

    return cmd_map[opts.args[1]](opts.socket, opts.api_version, opts.args[2:], opts.json, opts.testmode)

def providers_list(socket_path, api_version, args, show_json=False, testmode=0):
    """Return the list of providers

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

    providers list
    """
    api_route = client.api_url(api_version, "/upload/providers")
    r = client.get_url_json(socket_path, api_route)
    results = r["providers"]
    if not results:
        return 0

    if show_json:
        print(json.dumps(results, indent=4))
    else:
        if len(args) == 1:
            if args[0] not in results:
                log.error("%s is not a valid provider", args[0])
                return 1
            print("\n".join(sorted(results[args[0]]["profiles"].keys())))
        else:
            print("\n".join(sorted(results.keys())))

    return 0

def providers_info(socket_path, api_version, args, show_json=False, testmode=0):
    """Show information about each provider

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

    providers info <PROVIDER>
    """
    if len(args) == 0:
        log.error("info is missing the provider name")
        return 1

    api_route = client.api_url(api_version, "/upload/providers")
    r = client.get_url_json(socket_path, api_route)
    results = r["providers"]
    if not results:
        return 0

    if show_json:
        print(json.dumps(results, indent=4))
    else:
        if args[0] not in results:
            log.error("%s is not a valid provider", args[0])
            return 1
        p = results[args[0]]
        print("%s supports these image types: %s" % (p["display"], ", ".join(p["supported_types"])))
        print("Settings:")
        for k in p["settings-info"]:
            f = p["settings-info"][k]
            print("    %-20s: %s is a %s" % (k, f["display"], f["type"]))

    return 0

def providers_show(socket_path, api_version, args, show_json=False, testmode=0):
    """Return details about a provider

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

    providers show <provider> <profile>
    """
    if len(args) == 0:
        log.error("show is missing the provider name")
        return 1
    if len(args) == 1:
        log.error("show is missing the profile name")
        return 1

    api_route = client.api_url(api_version, "/upload/providers")
    r = client.get_url_json(socket_path, api_route)
    results = r["providers"]
    if not results:
        return 0

    if show_json:
        print(json.dumps(results, indent=4))
    else:
        if args[0] not in results:
            log.error("%s is not a valid provider", args[0])
            return 1
        if args[1] not in results[args[0]]["profiles"]:
            log.error("%s is not a valid %s profile", args[1], args[0])
            return 1

        # Print the details for this profile
        # fields are different for each provider, so we just print out the key:values
        for k in results[args[0]]["profiles"][args[1]]:
            print("%s: %s" % (k, results[args[0]]["profiles"][args[1]][k]))
    return 0

def providers_push(socket_path, api_version, args, show_json=False, testmode=0):
    """Add a new provider profile or overwrite an existing one

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

    providers push <profile.toml>

    """
    if len(args) == 0:
        log.error("push is missing the profile TOML file")
        return 1
    if not os.path.exists(args[0]):
        log.error("Missing profile TOML file: %s", args[0])
        return 1

    api_route = client.api_url(api_version, "/upload/providers/save")
    profile = toml.load(args[0])
    result = client.post_url_json(socket_path, api_route, json.dumps(profile))
    return handle_api_result(result, show_json)[0]

def providers_save(socket_path, api_version, args, show_json=False, testmode=0):
    """Save a provider's profile to a TOML file

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

    providers save <provider> <profile>

    """
    if len(args) == 0:
        log.error("save is missing the provider name")
        return 1
    if len(args) == 1:
        log.error("save is missing the profile name")
        return 1

    api_route = client.api_url(api_version, "/upload/providers")
    r = client.get_url_json(socket_path, api_route)
    results = r["providers"]
    if not results:
        return 0

    if show_json:
        print(json.dumps(results, indent=4))
    else:
        if args[0] not in results:
            log.error("%s is not a valid provider", args[0])
            return 1
        if args[1] not in results[args[0]]["profiles"]:
            log.error("%s is not a valid %s profile", args[1], args[0])
            return 1

        profile = {
            "provider": args[0],
            "profile": args[1],
            "settings": results[args[0]]["profiles"][args[1]]
        }
        with open(toml_filename(args[1]), "w") as f:
            f.write(toml.dumps(profile))

    return 0

def providers_delete(socket_path, api_version, args, show_json=False, testmode=0):
    """Delete a profile from a provider

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

    providers delete <provider> <profile>

    """
    if len(args) == 0:
        log.error("delete is missing the provider name")
        return 1
    if len(args) == 1:
        log.error("delete is missing the profile name")
        return 1

    api_route = client.api_url(api_version, "/upload/providers/delete/%s/%s" % (args[0], args[1]))
    result = client.delete_url_json(socket_path, api_route)
    return handle_api_result(result, show_json)[0]

def providers_template(socket_path, api_version, args, show_json=False, testmode=0):
    """Return a TOML template for setting the provider's fields

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

    providers template <provider>
    """
    if len(args) == 0:
        log.error("template is missing the provider name")
        return 1

    api_route = client.api_url(api_version, "/upload/providers")
    r = client.get_url_json(socket_path, api_route)
    results = r["providers"]
    if not results:
        return 0

    if show_json:
        print(json.dumps(results, indent=4))
        return 0

    if args[0] not in results:
        log.error("%s is not a valid provider", args[0])
        return 1

    template = {"provider": args[0]}
    settings = results[args[0]]["settings-info"]
    template["settings"] = dict([(k, settings[k]["display"]) for k in settings])
    print(toml.dumps(template))

    return 0
