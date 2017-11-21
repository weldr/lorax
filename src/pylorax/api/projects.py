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

from yum.Errors import YumBaseError

TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


class ProjectsError(Exception):
    pass


def api_time(t):
    """Convert time since epoch to a string

    :param t: Seconds since epoch
    :type t: int
    :returns: Time string
    :rtype: str
    """
    return time.strftime(TIME_FORMAT, time.localtime(t))


def api_changelog(changelog):
    """Convert the changelog to a string

    :param changelog: A list of time, author, string tuples.
    :type changelog: tuple
    :returns: The most recent changelog text or ""
    :rtype: str

    This returns only the most recent changelog entry.
    """
    try:
        entry = changelog[0][2]
    except IndexError:
        entry = ""
    return entry


def yaps_to_project(yaps):
    """Extract the details from a YumAvailablePackageSqlite object

    :param yaps: Yum object with package details
    :type yaps: YumAvailablePackageSqlite
    :returns: A dict with the name, summary, description, and url.
    :rtype: dict

    upstream_vcs is hard-coded to UPSTREAM_VCS
    """
    return {"name":         yaps.name,
            "summary":      yaps.summary,
            "description":  yaps.description,
            "homepage":     yaps.url,
            "upstream_vcs": "UPSTREAM_VCS"}


def yaps_to_project_info(yaps):
    """Extract the details from a YumAvailablePackageSqlite object

    :param yaps: Yum object with package details
    :type yaps: YumAvailablePackageSqlite
    :returns: A dict with the project details, as well as epoch, release, arch, build_time, changelog, ...
    :rtype: dict

    metadata entries are hard-coded to {}
    """
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
    """Extract the info from a TransactionMember object

    :param tm: A Yum transaction object
    :type tm: TransactionMember
    :returns: A dict with name, epoch, version, release, arch
    :rtype: dict
    """
    return {"name":     tm.name,
            "epoch":    tm.epoch,
            "version":  tm.version,
            "release":  tm.release,
            "arch":     tm.arch}


def yaps_to_module(yaps):
    """Extract the name from a YumAvailablePackageSqlite object

    :param yaps: Yum object with package details
    :type yaps: YumAvailablePackageSqlite
    :returns: A dict with name, and group_type
    :rtype: dict

    group_type is hard-coded to "rpm"
    """
    return {"name": yaps.name,
            "group_type": "rpm"}


def projects_list(yb):
    """Return a list of projects

    :param yb: yum base object
    :type yb: YumBase
    :returns: List of project info dicts with name, summary, description, homepage, upstream_vcs
    :rtype: list of dicts
    """
    try:
        ybl = yb.doPackageLists(pkgnarrow="available", showdups=False)
    except YumBaseError as e:
        raise ProjectsError("There was a problem listing projects: %s", str(e))
    return sorted(map(yaps_to_project, ybl.available), key=lambda p: p["name"].lower())


def projects_info(yb, project_names):
    """Return details about specific projects

    :param yb: yum base object
    :type yb: YumBase
    :param project_names: List of names of projects to get info about
    :type project_names: str
    :returns: List of project info dicts with yaps_to_project as well as epoch, version, release, etc.
    :rtype: list of dicts
    """
    try:
        ybl = yb.doPackageLists(pkgnarrow="available", patterns=project_names, showdups=False)
    except YumBaseError as e:
        raise ProjectsError("There was a problem with info for %s: %s" % (project_names, str(e)))
    return sorted(map(yaps_to_project_info, ybl.available), key=lambda p: p["name"].lower())


def projects_depsolve(yb, project_names):
    """Return the dependencies for a list of projects

    :param yb: yum base object
    :type yb: YumBase
    :param project_names: The projects to find the dependencies for
    :type project_names: List of Strings
    :returns: NEVRA's of the project and its dependencies
    :rtype: list of dicts
    """
    try:
        # This resets the transaction
        yb.closeRpmDB()
        for p in project_names:
            yb.install(pattern=p)
        (rc, msg) = yb.buildTransaction()
        if rc not in [1,2]:
            raise ProjectsError("There was a problem depsolving %s: %s" % (project_names, msg))
        yb.tsInfo.makelists()
    except YumBaseError as e:
        raise ProjectsError("There was a problem depsolving %s: %s" % (project_names, str(e)))
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
    :rtype: tuple of a list of dicts and an Int

    Modules don't exist in RHEL7 so this only returns projects
    and sets the type to "rpm"
    """
    try:
        ybl = yb.doPackageLists(pkgnarrow="available", showdups=False)
    except YumBaseError as e:
        raise ProjectsError("There was a problem listing modules: %s" % str(e))
    return sorted(map(yaps_to_module, ybl.available), key=lambda p: p["name"].lower())


def modules_info(yb, module_names):
    """Return details about a module, including dependencies

    :param yb: yum base object
    :type yb: YumBase
    :param module_names: Names of the modules to get info about
    :type module_names: str
    :returns: List of dicts with module details and dependencies.
    :rtype: list of dicts
    """
    try:
        # Get the info about each module
        ybl = yb.doPackageLists(pkgnarrow="available", patterns=module_names, showdups=False)
    except YumBaseError as e:
        raise ProjectsError("There was a problem with info for %s: %s" % (module_names, str(e)))

    modules = sorted(map(yaps_to_project, ybl.available), key=lambda p: p["name"].lower())
    # Add the dependency info to each one
    for module in modules:
        module["dependencies"] = projects_depsolve(yb, [module["name"]])

    return modules
