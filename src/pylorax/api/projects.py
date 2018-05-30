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

import os
from ConfigParser import ConfigParser
import yum
from glob import glob
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
    build = {"epoch":      int(yaps.epoch),
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
            "epoch":    int(tm.epoch),
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
        raise ProjectsError("There was a problem listing projects: %s" % str(e))
    finally:
        yb.closeRpmDB()
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
    finally:
        yb.closeRpmDB()
    return sorted(map(yaps_to_project_info, ybl.available), key=lambda p: p["name"].lower())


def projects_depsolve(yb, projects):
    """Return the dependencies for a list of projects

    :param yb: yum base object
    :type yb: YumBase
    :param projects: The projects and version globs to find the dependencies for
    :type projects: List of tuples
    :returns: NEVRA's of the project and its dependencies
    :rtype: list of dicts
    :raises: ProjectsError if there was a problem installing something
    """
    try:
        # This resets the transaction
        yb.closeRpmDB()
        for name, version in projects:
            if not version:
                version = "*"
            yb.install(pattern="%s-%s" % (name, version))
        (rc, msg) = yb.buildTransaction()
        if rc not in [0, 1, 2]:
            raise ProjectsError("There was a problem depsolving %s: %s" % (projects, msg))
        yb.tsInfo.makelists()
        deps = sorted(map(tm_to_dep, yb.tsInfo.installed + yb.tsInfo.depinstalled), key=lambda p: p["name"].lower())
    except YumBaseError as e:
        raise ProjectsError("There was a problem depsolving %s: %s" % (projects, str(e)))
    finally:
        yb.closeRpmDB()
    return deps

def estimate_size(packages, block_size=4096):
    """Estimate the installed size of a package list

    :param packages: The packages to be installed
    :type packages: list of TransactionMember objects
    :param block_size: The block size to use for rounding up file sizes.
    :type block_size: int
    :returns: The estimated size of installed packages
    :rtype: int

    Estimating actual requirements is difficult without the actual file sizes, which
    yum doesn't provide access to. So use the file count and block size to estimate
    a minimum size for each package.
    """
    installed_size = 0
    for p in packages:
        installed_size += len(p.po.filelist) * block_size
        installed_size += p.po.installedsize
    return installed_size

def projects_depsolve_with_size(yb, projects, with_core=True):
    """Return the dependencies and installed size for a list of projects

    :param yb: yum base object
    :type yb: YumBase
    :param projects: The projects and version globs to find the dependencies for
    :type projects: List of tuples
    :returns: installed size and a list of NEVRA's of the project and its dependencies
    :rtype: tuple of (int, list of dicts)
    :raises: ProjectsError if there was a problem installing something
    """
    try:
        # This resets the transaction
        yb.closeRpmDB()
        for name, version in projects:
            if not version:
                version = "*"
            yb.install(pattern="%s-%s" % (name, version))
        if with_core:
            yb.selectGroup("core", group_package_types=['mandatory', 'default', 'optional'])
        (rc, msg) = yb.buildTransaction()
        if rc not in [0, 1, 2]:
            raise ProjectsError("There was a problem depsolving %s: %s" % (projects, msg))
        yb.tsInfo.makelists()
        installed_size = estimate_size(yb.tsInfo.installed + yb.tsInfo.depinstalled)
        deps = sorted(map(tm_to_dep, yb.tsInfo.installed + yb.tsInfo.depinstalled), key=lambda p: p["name"].lower())
    except YumBaseError as e:
        raise ProjectsError("There was a problem depsolving %s: %s" % (projects, str(e)))
    finally:
        yb.closeRpmDB()
    return (installed_size, deps)

def modules_list(yb, module_names):
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
        ybl = yb.doPackageLists(pkgnarrow="available", patterns=module_names, showdups=False)
    except YumBaseError as e:
        raise ProjectsError("There was a problem listing modules: %s" % str(e))
    finally:
        yb.closeRpmDB()
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
    finally:
        yb.closeRpmDB()

    modules = sorted(map(yaps_to_project, ybl.available), key=lambda p: p["name"].lower())
    # Add the dependency info to each one
    for module in modules:
        module["dependencies"] = projects_depsolve(yb, [(module["name"], "*")])

    return modules

def repo_to_source(repo, system_source):
    """Return a Weldr Source dict created from the YumRepository

    :param repo: Yum Repository
    :type repo: yum.yumRepo.YumRepository
    :param system_source: True if this source is an immutable system source
    :type system_source: bool
    :returns: A dict with Weldr Source fields filled in
    :rtype: dict

    Example::

        {
          "check_gpg": true,
          "check_ssl": true,
          "gpgkey_url": [
            "file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-28-x86_64"
          ],
          "name": "fedora",
          "proxy": "http://proxy.brianlane.com:8123",
          "system": true
          "type": "yum-metalink",
          "url": "https://mirrors.fedoraproject.org/metalink?repo=fedora-28&arch=x86_64"
        }

    """
    source = {"name": repo.id, "system": system_source}
    if repo.baseurl:
        source["url"] = repo.baseurl[0]
        source["type"] = "yum-baseurl"
    elif repo.metalink:
        source["url"] = repo.metalink
        source["type"] = "yum-metalink"
    elif repo.mirrorlist:
        source["url"] = repo.mirrorlist
        source["type"] = "yum-mirrorlist"
    else:
        raise RuntimeError("Repo has no baseurl, metalink, or mirrorlist")

    # proxy is optional
    if repo.proxy:
        source["proxy"] = repo.proxy

    if not repo.sslverify:
        source["check_ssl"] = False
    else:
        source["check_ssl"] = True

    if not repo.gpgcheck:
        source["check_gpg"] = False
    else:
        source["check_gpg"] = True

    if repo.gpgkey:
        source["gpgkey_urls"] = repo.gpgkey

    return source

def source_to_repo(source):
    """Return a yum YumRepository object created from a source dict

    :param source: A Weldr source dict
    :type source: dict
    :returns: A yum YumRepository object
    :rtype: yum.yumRepo.YumRepository

    Example::

        {
          "check_gpg": True,
          "check_ssl": True,
          "gpgkey_urls": [
            "file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-28-x86_64"
          ],
          "name": "fedora",
          "proxy": "http://proxy.brianlane.com:8123",
          "system": True
          "type": "yum-metalink",
          "url": "https://mirrors.fedoraproject.org/metalink?repo=fedora-28&arch=x86_64"
        }

    """
    repo = yum.yumRepo.YumRepository(source["name"])
    # This will allow errors to be raised so we can catch them
    # without this they are logged, but the repo is silently disabled
    repo.skip_if_unavailable = False

    if source["type"] == "yum-baseurl":
        repo.baseurl = [source["url"]]
    elif source["type"] == "yum-metalink":
        repo.metalink = source["url"]
    elif source["type"] == "yum-mirrorlist":
        repo.mirrorlist = source["url"]

    if "proxy" in source:
        repo.proxy = source["proxy"]

    if source["check_ssl"]:
        repo.sslverify = True
    else:
        repo.sslverify = False

    if source["check_gpg"]:
        repo.gpgcheck = True
    else:
        repo.gpgcheck = False

    if "gpgkey_urls" in source:
        repo.gpgkey = source["gpgkey_urls"]

    repo.enable()

    return repo

def get_source_ids(source_path):
    """Return a list of the source ids in a file

    :param source_path: Full path and filename of the source (yum repo) file
    :type source_path: str
    :returns: A list of source id strings
    :rtype: list of str
    """
    if not os.path.exists(source_path):
        return []

    cfg = ConfigParser()
    cfg.read(source_path)
    return cfg.sections()

def get_repo_sources(source_glob):
    """Return a list of sources from a directory of yum repositories

    :param source_glob: A glob to use to match the source files, including full path
    :type source_glob: str
    :returns: A list of the source ids in all of the matching files
    :rtype: list of str
    """
    sources = []
    for f in glob(source_glob):
        sources.extend(get_source_ids(f))
    return sources

def delete_repo_source(source_glob, source_name):
    """Delete a source from a repo file

    :param source_glob: A glob of the repo sources to search
    :type source_glob: str
    :returns: None
    :raises: ProjectsError if there was a problem

    A repo file may have multiple sources in it, delete only the selected source.
    If it is the last one in the file, delete the file.

    WARNING: This will delete ANY source, the caller needs to ensure that a system
    source_name isn't passed to it.
    """
    found = False
    for f in glob(source_glob):
        try:
            cfg = ConfigParser()
            cfg.read(f)
            if source_name in cfg.sections():
                found = True
                cfg.remove_section(source_name)
                # If there are other sections, rewrite the file without the deleted one
                if len(cfg.sections()) > 0:
                    with open(f, "w") as cfg_file:
                        cfg.write(cfg_file)
                else:
                    # No sections left, just delete the file
                    os.unlink(f)
        except Exception as e:
            raise ProjectsError("Problem deleting repo source %s: %s" % (source_name, str(e)))
    if not found:
        raise ProjectsError("source %s not found" % source_name)
