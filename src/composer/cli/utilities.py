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
log = logging.getLogger("composer")

import json

def argify(args):
    """Take a list of human args and return a list with each item

    :param args: list of strings with possible commas and spaces
    :type args: list of str
    :returns: List of all the items
    :rtype: list of str

    Examples:

    ["one,two", "three", ",four", ",five,"] returns ["one", "two", "three", "four", "five"]
    """
    return filter(lambda i: i, [arg for entry in args for arg in entry.split(",")])

def toml_filename(blueprint_name):
    """Convert a blueprint name into a filename.toml

    :param blueprint_name: The blueprint's name
    :type blueprint_name: str
    :returns: The blueprint name with ' ' converted to - and .toml appended
    :rtype: str
    """
    return blueprint_name.replace(" ", "-") + ".toml"

def frozen_toml_filename(blueprint_name):
    """Convert a blueprint name into a filename.toml

    :param blueprint_name: The blueprint's name
    :type blueprint_name: str
    :returns: The blueprint name with ' ' converted to - and .toml appended
    :rtype: str
    """
    return blueprint_name.replace(" ", "-") + ".frozen.toml"

def handle_api_result(result, show_json=False):
    """Log any errors, return the correct value

    :param result: JSON result from the http query
    :type result: dict
    :rtype: tuple
    :returns: (rc, should_exit_now)

    Return the correct rc for the program (0 or 1), and whether or
    not to continue processing the results.
    """
    if show_json:
        print(json.dumps(result, indent=4))
    else:
        for err in result.get("errors", []):
            log.error(err["msg"])

    # What's the rc? If status is present, use that
    # If not, use length of errors
    if "status" in result:
        rc = bool(not result["status"])
    else:
        rc = bool(len(result.get("errors", [])) > 0)

    # Caller should return if showing json, or status was present and False
    exit_now = show_json or ("status" in result and rc)
    return (rc, exit_now)

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
