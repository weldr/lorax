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


def yaps_to_project(yaps):
    """Extract the details from a YumAvailablePackageSqlite object"""
    return {"name":         yaps.name,
            "summary":      yaps.summary,
            "description":  yaps.description,
            "homepage":     yaps.url,
            "upstream_vcs": "UPSTREAM_VCS"}


def projects_list(yb):
    """Return a list of projects

    :param yb: yum base object
    :type yb: YumBase
    :returns: List of project information
    :rtype: List of Dicts

    name, summary, dfescription, homepage, upstream_vcs
    """
    ybl = yb.doPackageLists(pkgnarrow="available", showdups=False)
    return sorted(map(yaps_to_project, ybl.available), key=lambda p: p["name"].lower())


def projects_info(yb, project_name):
    """Return details about a specific project

    :param yb: yum base object
    :type yb: YumBase
    :param project_name: Name of the project to get info about
    :type project_name: str
    """
    pass


def projects_depsolve(yb, projects):
    """Return the dependencies for a list of projects

    :param yb: yum base object
    :type yb: YumBase
    :param projects: The projects to find the dependencies for
    :type projects: List of Strings
    :returns: ...
    :rtype: ...
    """
    pass


def modules_list(yb, offset, limit):
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


def modules_info(yb, module_name):
    """Return details about a module, including dependencies

    :param yb: yum base object
    :type yb: YumBase
    :param module_name: Name of the module to get info about
    :type module_name: str
    """
    pass
