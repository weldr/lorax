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
from composer.cli.help import blueprints_help
from composer.cli.utilities import argify, frozen_toml_filename, toml_filename, handle_api_result
from composer.cli.utilities import packageNEVRA

def blueprints_cmd(opts):
    """Process blueprints commands

    :param opts: Cmdline arguments
    :type opts: argparse.Namespace
    :returns: Value to return from sys.exit()
    :rtype: int

    This dispatches the blueprints commands to a function
    """
    cmd_map = {
        "list":      blueprints_list,
        "show":      blueprints_show,
        "changes":   blueprints_changes,
        "diff":      blueprints_diff,
        "save":      blueprints_save,
        "delete":    blueprints_delete,
        "depsolve":  blueprints_depsolve,
        "push":      blueprints_push,
        "freeze":    blueprints_freeze,
        "tag":       blueprints_tag,
        "undo":      blueprints_undo,
        "workspace": blueprints_workspace
        }
    if opts.args[1] == "help" or opts.args[1] == "--help":
        print(blueprints_help)
        return 0
    elif opts.args[1] not in cmd_map:
        log.error("Unknown blueprints command: %s", opts.args[1])
        return 1

    return cmd_map[opts.args[1]](opts.socket, opts.api_version, opts.args[2:], opts.json)

def blueprints_list(socket_path, api_version, args, show_json=False):
    """Output the list of available blueprints

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    blueprints list
    """
    api_route = client.api_url(api_version, "/blueprints/list")
    result = client.get_url_json_unlimited(socket_path, api_route)
    (rc, exit_now) = handle_api_result(result, show_json)
    if exit_now:
        return rc

    # "list" should output a plain list of identifiers, one per line.
    print("\n".join(result["blueprints"]))

    return rc

def blueprints_show(socket_path, api_version, args, show_json=False):
    """Show the blueprints, in TOML format

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    blueprints show <blueprint,...>        Display the blueprint in TOML format.

    Multiple blueprints will be separated by \n\n
    """
    for blueprint in argify(args):
        api_route = client.api_url(api_version, "/blueprints/info/%s?format=toml" % blueprint)
        print(client.get_url_raw(socket_path, api_route) + "\n\n")

    return 0

def blueprints_changes(socket_path, api_version, args, show_json=False):
    """Display the changes for each of the blueprints

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    blueprints changes <blueprint,...>     Display the changes for each blueprint.
    """
    def changes_total_fn(data):
        """Return the maximum number of possible changes"""

        # Each blueprint can have a different total, return the largest one
        return max([c["total"] for c in data["blueprints"]])

    api_route = client.api_url(api_version, "/blueprints/changes/%s" % (",".join(argify(args))))
    result = client.get_url_json_unlimited(socket_path, api_route, total_fn=changes_total_fn)
    (rc, exit_now) = handle_api_result(result, show_json)
    if exit_now:
        return rc

    for blueprint in result["blueprints"]:
        print(blueprint["name"])
        for change in blueprint["changes"]:
            prettyCommitDetails(change)

    return rc

def prettyCommitDetails(change, indent=4):
    """Print the blueprint's change in a nice way

    :param change: The individual blueprint change dict
    :type change: dict
    :param indent: Number of spaces to indent
    :type indent: int
    """
    def revision():
        if change["revision"]:
            return "  revision %d" % change["revision"]
        else:
            return ""

    print(" " * indent + change["timestamp"] + "  " + change["commit"] + revision())
    print(" " * indent + change["message"] + "\n")

def blueprints_diff(socket_path, api_version, args, show_json=False):
    """Display the differences between 2 versions of a blueprint

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    blueprints diff <blueprint-name>       Display the differences between 2 versions of a blueprint.
                 <from-commit>       Commit hash or NEWEST
                 <to-commit>         Commit hash, NEWEST, or WORKSPACE
    """
    if len(args) == 0:
        log.error("blueprints diff is missing the blueprint name, from commit, and to commit")
        return 1
    elif len(args) == 1:
        log.error("blueprints diff is missing the from commit, and the to commit")
        return 1
    elif len(args) == 2:
        log.error("blueprints diff is missing the to commit")
        return 1

    api_route = client.api_url(api_version, "/blueprints/diff/%s/%s/%s" % (args[0], args[1], args[2]))
    result = client.get_url_json(socket_path, api_route)
    (rc, exit_now) = handle_api_result(result, show_json)
    if exit_now:
        return rc

    for diff in result["diff"]:
        print(pretty_diff_entry(diff))

    return rc

def pretty_dict(d):
    """Return the dict as a human readable single line

    :param d: key/values
    :type d: dict
    :returns: String of the dict's keys and values
    :rtype: str

    key="str", key="str1,str2", ...
    """
    result = []
    for k in d:
        if type(d[k]) == type(""):
            result.append('%s="%s"' % (k, d[k]))
        elif type(d[k]) == type([]) and type(d[k][0]) == type(""):
            result.append('%s="%s"' % (k, ", ".join(d[k])))
        elif type(d[k]) == type([]) and type(d[k][0]) == type({}):
            result.append('%s="%s"' % (k, pretty_dict(d[k])))
    return " ".join(result)

def dict_names(lst):
    """Return comma-separated list of the dict's name/user fields

    :param d: key/values
    :type d: dict
    :returns: String of the dict's keys and values
    :rtype: str

    root, norm
    """
    if "user" in lst[0]:
        field_name = "user"
    elif "name" in lst[0]:
        field_name = "name"
    else:
        # Use first fields in sorted keys
        field_name = sorted(lst[0].keys())[0]

    return ", ".join(d[field_name] for d in lst)

def pretty_diff_entry(diff):
    """Generate nice diff entry string.

    :param diff: Difference entry dict
    :type diff: dict
    :returns: Nice string
    """
    if diff["old"] and diff["new"]:
        change = "Changed"
    elif diff["new"] and not diff["old"]:
        change = "Added"
    elif diff["old"] and not diff["new"]:
        change = "Removed"
    else:
        change = "Unknown"

    if diff["old"]:
        name = list(diff["old"].keys())[0]
    elif diff["new"]:
        name = list(diff["new"].keys())[0]
    else:
        name = "Unknown"

    def details(diff):
        if change == "Changed":
            if type(diff["old"][name]) == type(""):
                if name == "Description" or " " in diff["old"][name]:
                    return '"%s" -> "%s"' % (diff["old"][name], diff["new"][name])
                else:
                    return "%s -> %s" % (diff["old"][name], diff["new"][name])
            elif name in ["Module", "Package"]:
                return "%s %s -> %s" % (diff["old"][name]["name"], diff["old"][name]["version"],
                                        diff["new"][name]["version"])
            elif type(diff["old"][name]) == type([]):
                if type(diff["old"][name][0]) == type(""):
                    return "%s -> %s" % (" ".join(diff["old"][name]), " ".join(diff["new"][name]))
                elif type(diff["old"][name][0]) == type({}):
                    # Lists of dicts are too long to display in detail, just show their names
                    return "%s -> %s" % (dict_names(diff["old"][name]), dict_names(diff["new"][name]))
            elif type(diff["old"][name]) == type({}):
                return "%s -> %s" % (pretty_dict(diff["old"][name]), pretty_dict(diff["new"][name]))
            else:
                return "Unknown"
        elif change == "Added":
            if name in ["Module", "Package"]:
                return "%s %s" % (diff["new"][name]["name"], diff["new"][name]["version"])
            elif name in ["Group"]:
                return diff["new"][name]["name"]
            elif type(diff["new"][name]) == type(""):
                return diff["new"][name]
            elif type(diff["new"][name]) == type([]):
                if type(diff["new"][name][0]) == type(""):
                    return " ".join(diff["new"][name])
                elif type(diff["new"][name][0]) == type({}):
                    # Lists of dicts are too long to display in detail, just show their names
                    return dict_names(diff["new"][name])
            elif type(diff["new"][name]) == type({}):
                return pretty_dict(diff["new"][name])
            else:
                return "unknown/todo: %s" % type(diff["new"][name])
        elif change == "Removed":
            if name in ["Module", "Package"]:
                return "%s %s" % (diff["old"][name]["name"], diff["old"][name]["version"])
            elif name in ["Group"]:
                return diff["old"][name]["name"]
            elif type(diff["old"][name]) == type(""):
                return diff["old"][name]
            elif type(diff["old"][name]) == type([]):
                if type(diff["old"][name][0]) == type(""):
                    return " ".join(diff["old"][name])
                elif type(diff["old"][name][0]) == type({}):
                    # Lists of dicts are too long to display in detail, just show their names
                    return dict_names(diff["old"][name])
            elif type(diff["old"][name]) == type({}):
                return pretty_dict(diff["old"][name])
            else:
                return "unknown/todo: %s" % type(diff["new"][name])

    return change + " " + name + " " + details(diff)

def blueprints_save(socket_path, api_version, args, show_json=False):
    """Save the blueprint to a TOML file

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    blueprints save <blueprint,...>        Save the blueprint to a file, <blueprint-name>.toml
    """
    for blueprint in argify(args):
        api_route = client.api_url(api_version, "/blueprints/info/%s?format=toml" % blueprint)
        blueprint_toml = client.get_url_raw(socket_path, api_route)
        with open(toml_filename(blueprint), "w") as f:
            f.write(blueprint_toml)

    return 0

def blueprints_delete(socket_path, api_version, args, show_json=False):
    """Delete a blueprint from the server

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    delete <blueprint>          Delete a blueprint from the server
    """
    api_route = client.api_url(api_version, "/blueprints/delete/%s" % args[0])
    result = client.delete_url_json(socket_path, api_route)

    return handle_api_result(result, show_json)[0]

def blueprints_depsolve(socket_path, api_version, args, show_json=False):
    """Display the packages needed to install the blueprint

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    blueprints depsolve <blueprint,...>    Display the packages needed to install the blueprint.
    """
    api_route = client.api_url(api_version, "/blueprints/depsolve/%s" % (",".join(argify(args))))
    result = client.get_url_json(socket_path, api_route)
    (rc, exit_now) = handle_api_result(result, show_json)
    if exit_now:
        return rc

    for blueprint in result["blueprints"]:
        if blueprint["blueprint"].get("version", ""):
            print("blueprint: %s v%s" % (blueprint["blueprint"]["name"], blueprint["blueprint"]["version"]))
        else:
            print("blueprint: %s" % (blueprint["blueprint"]["name"]))
        for dep in blueprint["dependencies"]:
            print("    " + packageNEVRA(dep))

    return rc

def blueprints_push(socket_path, api_version, args, show_json=False):
    """Push a blueprint TOML file to the server, updating the blueprint

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    push <blueprint>            Push a blueprint TOML file to the server.
    """
    api_route = client.api_url(api_version, "/blueprints/new")
    rval = 0
    for blueprint in argify(args):
        if not os.path.exists(blueprint):
            log.error("Missing blueprint file: %s", blueprint)
            continue
        with open(blueprint, "r") as f:
            blueprint_toml = f.read()

        result = client.post_url_toml(socket_path, api_route, blueprint_toml)
        if handle_api_result(result, show_json)[0]:
            rval = 1

    return rval

def blueprints_freeze(socket_path, api_version, args, show_json=False):
    """Handle the blueprints freeze commands

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    blueprints freeze <blueprint,...>      Display the frozen blueprint's modules and packages.
    blueprints freeze show <blueprint,...> Display the frozen blueprint in TOML format.
    blueprints freeze save <blueprint,...> Save the frozen blueprint to a file, <blueprint-name>.frozen.toml.
    """
    if args[0] == "show":
        return blueprints_freeze_show(socket_path, api_version, args[1:], show_json)
    elif args[0] == "save":
        return blueprints_freeze_save(socket_path, api_version, args[1:], show_json)

    if len(args) == 0:
        log.error("freeze is missing the blueprint name")
        return 1

    api_route = client.api_url(api_version, "/blueprints/freeze/%s" % (",".join(argify(args))))
    result = client.get_url_json(socket_path, api_route)
    (rc, exit_now) = handle_api_result(result, show_json)
    if exit_now:
        return rc

    for entry in result["blueprints"]:
        blueprint = entry["blueprint"]
        if blueprint.get("version", ""):
            print("blueprint: %s v%s" % (blueprint["name"], blueprint["version"]))
        else:
            print("blueprint: %s" % (blueprint["name"]))

        for m in blueprint["modules"]:
            print("    %s-%s" % (m["name"], m["version"]))

        for p in blueprint["packages"]:
            print("    %s-%s" % (p["name"], p["version"]))

    return rc

def blueprints_freeze_show(socket_path, api_version, args, show_json=False):
    """Show the frozen blueprint in TOML format

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    blueprints freeze show <blueprint,...> Display the frozen blueprint in TOML format.
    """
    if len(args) == 0:
        log.error("freeze show is missing the blueprint name")
        return 1

    for blueprint in argify(args):
        api_route = client.api_url(api_version, "/blueprints/freeze/%s?format=toml" % blueprint)
        print(client.get_url_raw(socket_path, api_route))

    return 0

def blueprints_freeze_save(socket_path, api_version, args, show_json=False):
    """Save the frozen blueprint to a TOML file

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    blueprints freeze save <blueprint,...> Save the frozen blueprint to a file, <blueprint-name>.frozen.toml.
    """
    if len(args) == 0:
        log.error("freeze save is missing the blueprint name")
        return 1

    for blueprint in argify(args):
        api_route = client.api_url(api_version, "/blueprints/freeze/%s?format=toml" % blueprint)
        blueprint_toml = client.get_url_raw(socket_path, api_route)
        with open(frozen_toml_filename(blueprint), "w") as f:
            f.write(blueprint_toml)

    return 0

def blueprints_tag(socket_path, api_version, args, show_json=False):
    """Tag the most recent blueprint commit as a release

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    blueprints tag <blueprint>             Tag the most recent blueprint commit as a release.
    """
    api_route = client.api_url(api_version, "/blueprints/tag/%s" % args[0])
    result = client.post_url(socket_path, api_route, "")

    return handle_api_result(result, show_json)[0]

def blueprints_undo(socket_path, api_version, args, show_json=False):
    """Undo changes to a blueprint

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    blueprints undo <blueprint> <commit>   Undo changes to a blueprint by reverting to the selected commit.
    """
    if len(args) == 0:
        log.error("undo is missing the blueprint name and commit hash")
        return 1
    elif len(args) == 1:
        log.error("undo is missing commit hash")
        return 1

    api_route = client.api_url(api_version, "/blueprints/undo/%s/%s" % (args[0], args[1]))
    result = client.post_url(socket_path, api_route, "")

    return handle_api_result(result, show_json)[0]

def blueprints_workspace(socket_path, api_version, args, show_json=False):
    """Push the blueprint TOML to the temporary workspace storage

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    blueprints workspace <blueprint>       Push the blueprint TOML to the temporary workspace storage.
    """
    api_route = client.api_url(api_version, "/blueprints/workspace")
    rval = 0
    for blueprint in argify(args):
        if not os.path.exists(blueprint):
            log.error("Missing blueprint file: %s", blueprint)
            continue
        with open(blueprint, "r") as f:
            blueprint_toml = f.read()

        result = client.post_url_toml(socket_path, api_route, blueprint_toml)
        if handle_api_result(result, show_json)[0]:
            rval = 1

    return rval
