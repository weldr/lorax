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

import dnf
import time

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


def pkg_to_project(pkg):
    """Extract the details from a hawkey.Package object

    :param pkgs: hawkey.Package object with package details
    :type pkgs: hawkey.Package
    :returns: A dict with the name, summary, description, and url.
    :rtype: dict

    upstream_vcs is hard-coded to UPSTREAM_VCS
    """
    return {"name":         pkg.name,
            "summary":      pkg.summary,
            "description":  pkg.description,
            "homepage":     pkg.url,
            "upstream_vcs": "UPSTREAM_VCS"}


def pkg_to_project_info(pkg):
    """Extract the details from a hawkey.Package object

    :param pkg: hawkey.Package object with package details
    :type pkg: hawkey.Package
    :returns: A dict with the project details, as well as epoch, release, arch, build_time, changelog, ...
    :rtype: dict

    metadata entries are hard-coded to {}
    """
    build = {"epoch":      pkg.epoch,
             "release":    pkg.release,
             "arch":       pkg.arch,
             "build_time": api_time(pkg.buildtime),
             "changelog":  "CHANGELOG_NEEDED",                  # XXX Not in hawkey.Package
             "build_config_ref": "BUILD_CONFIG_REF",
             "build_env_ref":    "BUILD_ENV_REF",
             "metadata":    {},
             "source":      {"license":    pkg.license,
                             "version":    pkg.version,
                             "source_ref": "SOURCE_REF",
                             "metadata":   {}}}

    return {"name":         pkg.name,
            "summary":      pkg.summary,
            "description":  pkg.description,
            "homepage":     pkg.url,
            "upstream_vcs": "UPSTREAM_VCS",
            "builds":       [build]}


def pkg_to_dep(pkg):
    """Extract the info from a hawkey.Package object

    :param pkg: A hawkey.Package object
    :type pkg: hawkey.Package
    :returns: A dict with name, epoch, version, release, arch
    :rtype: dict
    """
    return {"name":     pkg.name,
            "epoch":    pkg.epoch,
            "version":  pkg.version,
            "release":  pkg.release,
            "arch":     pkg.arch}


def proj_to_module(proj):
    """Extract the name from a project_info dict

    :param pkg: dict with package details
    :type pkg: dict
    :returns: A dict with name, and group_type
    :rtype: dict

    group_type is hard-coded to "rpm"
    """
    return {"name": proj["name"],
            "group_type": "rpm"}


def dep_evra(dep):
    """Return the epoch:version-release.arch for the dep

    :param dep: dependency dict
    :type dep: dict
    :returns: epoch:version-release.arch
    :rtype: str
    """
    if dep["epoch"] == 0:
        return dep["version"]+"-"+dep["release"]+"."+dep["arch"]
    else:
        return str(dep["epoch"])+":"+dep["version"]+"-"+dep["release"]+"."+dep["arch"]

def dep_nevra(dep):
    """Return the name-epoch:version-release.arch"""
    return dep["name"]+"-"+dep_evra(dep)


def projects_list(dbo):
    """Return a list of projects

    :param dbo: dnf base object
    :type dbo: dnf.Base
    :returns: List of project info dicts with name, summary, description, homepage, upstream_vcs
    :rtype: list of dicts
    """
    return projects_info(dbo, None)


def projects_info(dbo, project_names):
    """Return details about specific projects

    :param dbo: dnf base object
    :type dbo: dnf.Base
    :param project_names: List of names of projects to get info about
    :type project_names: str
    :returns: List of project info dicts with pkg_to_project as well as epoch, version, release, etc.
    :rtype: list of dicts

    If project_names is None it will return the full list of available packages
    """
    if project_names:
        pkgs = dbo.sack.query().available().filter(name__glob=project_names)
    else:
        pkgs = dbo.sack.query().available()
    return sorted(map(pkg_to_project_info, pkgs), key=lambda p: p["name"].lower())


def projects_depsolve(dbo, project_names):
    """Return the dependencies for a list of projects

    :param dbo: dnf base object
    :type dbo: dnf.Base
    :param project_names: The projects to find the dependencies for
    :type project_names: List of Strings
    :returns: NEVRA's of the project and its dependencies
    :rtype: list of dicts
    """
    # This resets the transaction
    dbo.reset(goal=True)
    for p in project_names:
        try:
            dbo.install(p)
        except dnf.exceptions.MarkingError:
            raise ProjectsError("No match for %s" % p)

    try:
        dbo.resolve()
    except dnf.exceptions.DepsolveError as e:
        raise ProjectsError("There was a problem depsolving %s: %s" % (project_names, str(e)))

    if len(dbo.transaction) == 0:
        raise ProjectsError("No packages installed for %s" % project_names)

    return sorted(map(pkg_to_dep, dbo.transaction.install_set), key=lambda p: p["name"].lower())


def estimate_size(packages, block_size=4096):
    """Estimate the installed size of a package list

    :param packages: The packages to be installed
    :type packages: list of hawkey.Package objects
    :param block_size: The block size to use for rounding up file sizes.
    :type block_size: int
    :returns: The estimated size of installed packages
    :rtype: int

    Estimating actual requirements is difficult without the actual file sizes, which
    dnf doesn't provide access to. So use the file count and block size to estimate
    a minimum size for each package.
    """
    installed_size = 0
    for p in packages:
        installed_size += len(p.files) * block_size
        installed_size += p.installsize
    return installed_size


def projects_depsolve_with_size(dbo, project_names, with_core=True):
    """Return the dependencies and installed size for a list of projects

    :param dbo: dnf base object
    :type dbo: dnf.Base
    :param project_names: The projects to find the dependencies for
    :type project_names: List of Strings
    :returns: installed size and a list of NEVRA's of the project and its dependencies
    :rtype: tuple of (int, list of dicts)
    """
    # This resets the transaction
    dbo.reset(goal=True)
    for p in project_names:
        try:
            dbo.install(p)
        except dnf.exceptions.MarkingError:
            raise ProjectsError("No match for %s" % p)

    if with_core:
        dbo.group_install("core", ['mandatory', 'default', 'optional'])

    try:
        dbo.resolve()
    except dnf.exceptions.DepsolveError as e:
        raise ProjectsError("There was a problem depsolving %s: %s" % (project_names, str(e)))

    if len(dbo.transaction) == 0:
        raise ProjectsError("No packages installed for %s" % project_names)

    installed_size = estimate_size(dbo.transaction.install_set)
    deps = sorted(map(pkg_to_dep, dbo.transaction.install_set), key=lambda p: p["name"].lower())
    return (installed_size, deps)


def modules_list(dbo, module_names):
    """Return a list of modules

    :param dbo: dnf base object
    :type dbo: dnf.Base
    :param offset: Number of modules to skip
    :type limit: int
    :param limit: Maximum number of modules to return
    :type limit: int
    :returns: List of module information and total count
    :rtype: tuple of a list of dicts and an Int

    Modules don't exist in RHEL7 so this only returns projects
    and sets the type to "rpm"

    """
    # TODO - Figure out what to do with this for Fedora 'modules'
    projs = projects_info(dbo, module_names)
    return sorted(map(proj_to_module, projs), key=lambda p: p["name"].lower())


def modules_info(dbo, module_names):
    """Return details about a module, including dependencies

    :param dbo: dnf base object
    :type dbo: dnf.Base
    :param module_names: Names of the modules to get info about
    :type module_names: str
    :returns: List of dicts with module details and dependencies.
    :rtype: list of dicts
    """
    modules = projects_info(dbo, module_names)

    # Add the dependency info to each one
    for module in modules:
        module["dependencies"] = projects_depsolve(dbo, [module["name"]])

    return modules
