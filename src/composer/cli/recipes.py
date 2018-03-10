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
import json

from composer import http_client as client
from composer.cli.utilities import argify, frozen_toml_filename, toml_filename, handle_api_result

def recipes_cmd(opts):
    """Process recipes commands

    :param opts: Cmdline arguments
    :type opts: argparse.Namespace
    :returns: Value to return from sys.exit()
    :rtype: int

    This dispatches the recipes commands to a function
    """
    cmd_map = {
        "list":      recipes_list,
        "show":      recipes_show,
        "changes":   recipes_changes,
        "diff":      recipes_diff,
        "save":      recipes_save,
        "delete":    recipes_delete,
        "depsolve":  recipes_depsolve,
        "push":      recipes_push,
        "freeze":    recipes_freeze,
        "tag":       recipes_tag,
        "undo":      recipes_undo,
        "workspace": recipes_workspace
        }
    return cmd_map[opts.args[1]](opts.socket, opts.api_version, opts.args[2:], opts.json)

def recipes_list(socket_path, api_version, args, show_json=False):
    """Output the list of available recipes

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    recipes list
    """
    api_route = client.api_url(api_version, "/recipes/list")
    result = client.get_url_json(socket_path, api_route)
    if show_json:
        print(json.dumps(result, indent=4))
        return 0

    print("Recipes: " + ", ".join([r for r in result["recipes"]]))

    return 0

def recipes_show(socket_path, api_version, args, show_json=False):
    """Show the recipes, in TOML format

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    recipes show <recipe,...>        Display the recipe in TOML format.

    Multiple recipes will be separated by \n\n
    """
    for recipe in argify(args):
        api_route = client.api_url(api_version, "/recipes/info/%s?format=toml" % recipe)
        print(client.get_url_raw(socket_path, api_route) + "\n\n")

    return 0

def recipes_changes(socket_path, api_version, args, show_json=False):
    """Display the changes for each of the recipes

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    recipes changes <recipe,...>     Display the changes for each recipe.
    """
    api_route = client.api_url(api_version, "/recipes/changes/%s" % (",".join(argify(args))))
    result = client.get_url_json(socket_path, api_route)
    if show_json:
        print(json.dumps(result, indent=4))
        return 0

    for recipe in result["recipes"]:
        print(recipe["name"])
        for change in recipe["changes"]:
            prettyCommitDetails(change)

    return 0

def prettyCommitDetails(change, indent=4):
    """Print the recipe's change in a nice way

    :param change: The individual recipe change dict
    :type change: dict
    :param indent: Number of spaces to indent
    :type indent: int
    """
    def revision():
        if change["revision"]:
            return "  revision %d" % change["revision"]
        else:
            return ""

    print " " * indent + change["timestamp"] + "  " + change["commit"] + revision()
    print " " * indent + change["message"] + "\n"

def recipes_diff(socket_path, api_version, args, show_json=False):
    """Display the differences between 2 versions of a recipe

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    recipes diff <recipe-name>       Display the differences between 2 versions of a recipe.
                 <from-commit>       Commit hash or NEWEST
                 <to-commit>         Commit hash, NEWEST, or WORKSPACE
    """
    if len(args) == 0:
        log.error("recipes diff is missing the recipe name, from commit, and to commit")
        return 1
    elif len(args) == 1:
        log.error("recipes diff is missing the from commit, and the to commit")
        return 1
    elif len(args) == 2:
        log.error("recipes diff is missing the to commit")
        return 1

    api_route = client.api_url(api_version, "/recipes/diff/%s/%s/%s" % (args[0], args[1], args[2]))
    result = client.get_url_json(socket_path, api_route)

    if show_json:
        print(json.dumps(result, indent=4))
        return 0

    if result.get("error", False):
        log.error(result["error"]["msg"])
        return 1

    for diff in result["diff"]:
        print(prettyDiffEntry(diff))

    return 0

def prettyDiffEntry(diff):
    """Generate nice diff entry string.

    :param diff: Difference entry dict
    :type diff: dict
    :returns: Nice string
    """
    def change(diff):
        if diff["old"] and diff["new"]:
            return "Changed"
        elif diff["new"] and not diff["old"]:
            return "Added"
        elif diff["old"] and not diff["new"]:
            return "Removed"
        else:
            return "Unknown"

    def name(diff):
        if diff["old"]:
            return diff["old"].keys()[0]
        elif diff["new"]:
            return diff["new"].keys()[0]
        else:
            return "Unknown"

    def details(diff):
        if change(diff) == "Changed":
            if name(diff) == "Description":
                return '"%s" -> "%s"' % (diff["old"][name(diff)], diff["old"][name(diff)])
            elif name(diff) == "Version":
                return "%s -> %s" % (diff["old"][name(diff)], diff["old"][name(diff)])
            elif name(diff) in ["Module", "Package"]:
                return "%s %s -> %s" % (diff["old"][name(diff)]["name"], diff["old"][name(diff)]["version"],
                                        diff["new"][name(diff)]["version"])
            else:
                return "Unknown"
        elif change(diff) == "Added":
            return " ".join([diff["new"][k] for k in diff["new"]])
        elif change(diff) == "Removed":
            return " ".join([diff["old"][k] for k in diff["old"]])

    return change(diff) + " " + name(diff) + " " + details(diff)

def recipes_save(socket_path, api_version, args, show_json=False):
    """Save the recipe to a TOML file

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    recipes save <recipe,...>        Save the recipe to a file, <recipe-name>.toml
    """
    for recipe in argify(args):
        api_route = client.api_url(api_version, "/recipes/info/%s?format=toml" % recipe)
        recipe_toml = client.get_url_raw(socket_path, api_route)
        open(toml_filename(recipe), "w").write(recipe_toml)

    return 0

def recipes_delete(socket_path, api_version, args, show_json=False):
    """Delete a recipe from the server

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    delete <recipe>          Delete a recipe from the server
    """
    api_route = client.api_url(api_version, "/recipes/delete/%s" % args[0])
    result = client.delete_url_json(socket_path, api_route)

    return handle_api_result(result, show_json)

def recipes_depsolve(socket_path, api_version, args, show_json=False):
    """Display the packages needed to install the recipe

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    recipes depsolve <recipe,...>    Display the packages needed to install the recipe.
    """
    api_route = client.api_url(api_version, "/recipes/depsolve/%s" % (",".join(argify(args))))
    result = client.get_url_json(socket_path, api_route)

    if show_json:
        print(json.dumps(result, indent=4))
        return 0

    for recipe in result["recipes"]:
        if recipe["recipe"].get("version", ""):
            print("Recipe: %s v%s" % (recipe["recipe"]["name"], recipe["recipe"]["version"]))
        else:
            print("Recipe: %s" % (recipe["recipe"]["name"]))
        for dep in recipe["dependencies"]:
            print("    " + packageNEVRA(dep))

    return 0

def packageNEVRA(pkg):
    """Return the package info as a NEVRA

    :param pkg: The package details
    :type pkg: dict
    :returns: name-[epoch:]version-release-arch
    :rtype: str
    """
    if pkg["epoch"]:
        return "%s-%s:%s-%s.%s" % (pkg["name"], pkg["epoch"], pkg["version"], pkg["release"], pkg["arch"])
    else:
        return "%s-%s-%s.%s" % (pkg["name"], pkg["version"], pkg["release"], pkg["arch"])

def recipes_push(socket_path, api_version, args, show_json=False):
    """Push a recipe TOML file to the server, updating the recipe

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    push <recipe>            Push a recipe TOML file to the server.
    """
    api_route = client.api_url(api_version, "/recipes/new")
    rval = 0
    for recipe in argify(args):
        if not os.path.exists(recipe):
            log.error("Missing recipe file: %s", recipe)
            continue
        recipe_toml = open(recipe, "r").read()

        result = client.post_url_toml(socket_path, api_route, recipe_toml)
        if handle_api_result(result, show_json):
            rval = 1

    return rval

def recipes_freeze(socket_path, api_version, args, show_json=False):
    """Handle the recipes freeze commands

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    recipes freeze <recipe,...>      Display the frozen recipe's modules and packages.
    recipes freeze show <recipe,...> Display the frozen recipe in TOML format.
    recipes freeze save <recipe,...> Save the frozen recipe to a file, <recipe-name>.frozen.toml.
    """
    if args[0] == "show":
        return recipes_freeze_show(socket_path, api_version, args[1:], show_json)
    elif args[0] == "save":
        return recipes_freeze_save(socket_path, api_version, args[1:], show_json)

    if len(args) == 0:
        log.error("freeze is missing the recipe name")
        return 1

    api_route = client.api_url(api_version, "/recipes/freeze/%s" % (",".join(argify(args))))
    result = client.get_url_json(socket_path, api_route)

    if show_json:
        print(json.dumps(result, indent=4))
    else:
        for entry in result["recipes"]:
            recipe = entry["recipe"]
            if recipe.get("version", ""):
                print("Recipe: %s v%s" % (recipe["name"], recipe["version"]))
            else:
                print("Recipe: %s" % (recipe["name"]))

            for m in recipe["modules"]:
                print("    %s-%s" % (m["name"], m["version"]))

            for p in recipe["packages"]:
                print("    %s-%s" % (p["name"], p["version"]))

        # Print any errors
        for err in result.get("errors", []):
            log.error("%s: %s", err["recipe"], err["msg"])

    # Return a 1 if there are any errors
    if result.get("errors", []):
        return 1
    else:
        return 0

def recipes_freeze_show(socket_path, api_version, args, show_json=False):
    """Show the frozen recipe in TOML format

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    recipes freeze show <recipe,...> Display the frozen recipe in TOML format.
    """
    if len(args) == 0:
        log.error("freeze show is missing the recipe name")
        return 1

    for recipe in argify(args):
        api_route = client.api_url(api_version, "/recipes/freeze/%s?format=toml" % recipe)
        print(client.get_url_raw(socket_path, api_route))

    return 0

def recipes_freeze_save(socket_path, api_version, args, show_json=False):
    """Save the frozen recipe to a TOML file

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    recipes freeze save <recipe,...> Save the frozen recipe to a file, <recipe-name>.frozen.toml.
    """
    if len(args) == 0:
        log.error("freeze save is missing the recipe name")
        return 1

    for recipe in argify(args):
        api_route = client.api_url(api_version, "/recipes/freeze/%s?format=toml" % recipe)
        recipe_toml = client.get_url_raw(socket_path, api_route)
        open(frozen_toml_filename(recipe), "w").write(recipe_toml)

    return 0

def recipes_tag(socket_path, api_version, args, show_json=False):
    """Tag the most recent recipe commit as a release

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    recipes tag <recipe>             Tag the most recent recipe commit as a release.
    """
    api_route = client.api_url(api_version, "/recipes/tag/%s" % args[0])
    result = client.post_url(socket_path, api_route, "")

    return handle_api_result(result, show_json)

def recipes_undo(socket_path, api_version, args, show_json=False):
    """Undo changes to a recipe

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    recipes undo <recipe> <commit>   Undo changes to a recipe by reverting to the selected commit.
    """
    if len(args) == 0:
        log.error("undo is missing the recipe name and commit hash")
        return 1
    elif len(args) == 1:
        log.error("undo is missing commit hash")
        return 1

    api_route = client.api_url(api_version, "/recipes/undo/%s/%s" % (args[0], args[1]))
    result = client.post_url(socket_path, api_route, "")

    return handle_api_result(result, show_json)

def recipes_workspace(socket_path, api_version, args, show_json=False):
    """Push the recipe TOML to the temporary workspace storage

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param api_version: Version of the API to talk to. eg. "0"
    :type api_version: str
    :param args: List of remaining arguments from the cmdline
    :type args: list of str
    :param show_json: Set to True to show the JSON output instead of the human readable output
    :type show_json: bool

    recipes workspace <recipe>       Push the recipe TOML to the temporary workspace storage.
    """
    api_route = client.api_url(api_version, "/recipes/workspace")
    rval = 0
    for recipe in argify(args):
        if not os.path.exists(recipe):
            log.error("Missing recipe file: %s", recipe)
            continue
        recipe_toml = open(recipe, "r").read()

        result = client.post_url_toml(socket_path, api_route, recipe_toml)
        if show_json:
            print(json.dumps(result, indent=4))
        elif result.get("error", False):
            log.error(result["error"]["msg"])

        # Any errors results in returning a 1, but we continue with the rest first
        if not result.get("status", False):
            rval = 1

    return rval
