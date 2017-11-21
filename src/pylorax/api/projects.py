#
# Copyright (C) 2017  Red Hat, Inc.
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
log = logging.getLogger("lorax-composer")

import time

TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

def api_time(t):
    """Convert time since epoch to a string"""
    return time.strftime(TIME_FORMAT, time.localtime(t))


def api_changelog(changelog):
    """Convert the changelog to a string

    :param changelog: A list of time, author, string tuples.
    :type changelog: tuple
    :returns: The most recent changelog text
    :rtype: str
    """
    try:
        entry = changelog[0][2]
    except IndexError:
        entry = ""
    return entry


def yaps_to_project(yaps):
    """Extract the details from a YumAvailablePackageSqlite object"""
    return {"name":         yaps.name,
            "summary":      yaps.summary,
            "description":  yaps.description,
            "homepage":     yaps.url,
            "upstream_vcs": "UPSTREAM_VCS"}


def yaps_to_project_info(yaps):
    """Extract the details from a YumAvailablePackageSqlite object"""
    build = {"epoch":      yaps.epoch,
             "release":    yaps.release,
             "arch":       yaps.arch,
             "build_time": api_time(yaps.buildtime),
             "changelog":  api_changelog(yaps.returnChangelog()),
             "build_config_ref": "BUILD_CONFIG_REF",
             "build_env_ref":    "BUILD_ENV_REF",
             "metadata":    {},
             "source":      {"license":    yaps.license,
                             "version":    yaps.version,
                             "source_ref": "SOURCE_REF",
                             "metadata":   {}}}

    return {"name":         yaps.name,
            "summary":      yaps.summary,
            "description":  yaps.description,
            "homepage":     yaps.url,
            "upstream_vcs": "UPSTREAM_VCS",
            "builds":       [build]}


def tm_to_dep(tm):
    """Extract the info from a TransactionMember object"""
    return {"name":     tm.name,
            "epoch":    tm.epoch,
            "version":  tm.version,
            "release":  tm.release,
            "arch":     tm.arch}


def projects_list(yb):
    """Return a list of projects

    :param yb: yum base object
    :type yb: YumBase
    :returns: List of project information
    :rtype: List of Dicts

    Returns a list of dicts with these fields:
        name, summary, description, homepage, upstream_vcs
    """
    ybl = yb.doPackageLists(pkgnarrow="available", showdups=False)
    return sorted(map(yaps_to_project, ybl.available), key=lambda p: p["name"].lower())


def projects_info(yb, project_names):
    """Return details about specific projects

    :param yb: yum base object
    :type yb: YumBase
    :param project_names: List of names of projects to get info about
    :type project_names: str
    :returns: List of project details
    :rtype: List of Dicts

    """
    ybl = yb.doPackageLists(pkgnarrow="available", patterns=project_names, showdups=False)
    return sorted(map(yaps_to_project_info, ybl.available), key=lambda p: p["name"].lower())


def projects_depsolve(yb, project_names):
    """Return the dependencies for a list of projects

    :param yb: yum base object
    :type yb: YumBase
    :param project_names: The projects to find the dependencies for
    :type project_names: List of Strings
    :returns: ...
    :rtype: ...
    """
    # TODO - Catch yum tracebacks here

    # This resets the transaction
    yb.closeRpmDB()
    for p in project_names:
        yb.install(pattern=p)
    (rc, msg) = yb.buildTransaction()
    # If rc isn't 2 something went wrong, raise and error
    yb.tsInfo.makelists()
    return sorted(map(tm_to_dep, yb.tsInfo.installed + yb.tsInfo.depinstalled), key=lambda p: p["name"].lower())


def modules_list(yb):
    """Return a list of modules

    :param yb: yum base object
    :type yb: YumBase
    :param offset: Number of modules to skip
    :type limit: int
    :param limit: Maximum number of modules to return
    :type limit: int
    :returns: List of module information and total count
    :rtype: Tuple of a List of Dicts and an Int

    Modules don't exist in RHEL7 so this only returns projects
    and sets the type to "rpm"
    """
    pass


def modules_info(yb, module_names):
    """Return details about a module, including dependencies

    :param yb: yum base object
    :type yb: YumBase
    :param module_names: Names of the modules to get info about
    :type module_names: str
    """
    pass
