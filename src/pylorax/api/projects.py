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

from configparser import ConfigParser
import dnf
from glob import glob
import os
import time

from pylorax.api.bisect import insort_left

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


def pkg_to_build(pkg):
    """Extract the build details from a hawkey.Package object

    :param pkg: hawkey.Package object with package details
    :type pkg: hawkey.Package
    :returns: A dict with the build details, epoch, release, arch, build_time, changelog, ...
    :rtype: dict

    metadata entries are hard-coded to {}

    Note that this only returns the build dict, it does not include the name, description, etc.
    """
    return {"epoch":      pkg.epoch,
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


def pkg_to_project_info(pkg):
    """Extract the details from a hawkey.Package object

    :param pkg: hawkey.Package object with package details
    :type pkg: hawkey.Package
    :returns: A dict with the project details, as well as epoch, release, arch, build_time, changelog, ...
    :rtype: dict

    metadata entries are hard-coded to {}
    """
    return {"name":         pkg.name,
            "summary":      pkg.summary,
            "description":  pkg.description,
            "homepage":     pkg.url,
            "upstream_vcs": "UPSTREAM_VCS",
            "builds":       [pkg_to_build(pkg)]}


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

    # iterate over pkgs
    # - if pkg.name isn't in the results yet, add pkg_to_project_info in sorted position
    # - if pkg.name is already in results, get its builds. If the build for pkg is different
    #   in any way (version, arch, etc.) add it to the entry's builds list. If it is the same,
    #   skip it.
    results = []
    results_names = {}
    for p in pkgs:
        if p.name.lower() not in results_names:
            idx = insort_left(results, pkg_to_project_info(p), key=lambda p: p["name"].lower())
            results_names[p.name.lower()] = idx
        else:
            build = pkg_to_build(p)
            if build not in results[results_names[p.name.lower()]]["builds"]:
                results[results_names[p.name.lower()]]["builds"].append(build)

    return results

def _depsolve(dbo, projects, groups):
    """Add projects to a new transaction

    :param dbo: dnf base object
    :type dbo: dnf.Base
    :param projects: The projects and version globs to find the dependencies for
    :type projects: List of tuples
    :param groups: The groups to include in dependency solving
    :type groups: List of str
    :returns: None
    :rtype: None
    :raises: ProjectsError if there was a problem installing something
    """
    # This resets the transaction and updates the cache.
    # It is important that the cache always be synchronized because Anaconda will grab its own copy
    # and if that is different the NEVRAs will not match and the build will fail.
    dbo.reset(goal=True)
    install_errors = []
    for name in groups:
        try:
            dbo.group_install(name, ["mandatory", "default"])
        except dnf.exceptions.MarkingError as e:
            install_errors.append(("Group %s" % (name), str(e)))

    for name, version in projects:
        # Find the best package matching the name + version glob
        # dnf can return multiple packages if it is in more than 1 repository
        query = dbo.sack.query().filterm(provides__glob=name)
        if version:
            query.filterm(version__glob=version)

        query.filterm(latest=1)
        if not query:
            install_errors.append(("%s-%s" % (name, version), "No match"))
            continue
        sltr = dnf.selector.Selector(dbo.sack).set(pkg=query)

        # NOTE: dnf says in near future there will be a "goal" attribute of Base class
        #       so yes, we're using a 'private' attribute here on purpose and with permission.
        dbo._goal.install(select=sltr, optional=False)

    if install_errors:
        raise ProjectsError("The following package(s) had problems: %s" % ",".join(["%s (%s)" % (pattern, err) for pattern, err in install_errors]))

def projects_depsolve(dbo, projects, groups):
    """Return the dependencies for a list of projects

    :param dbo: dnf base object
    :type dbo: dnf.Base
    :param projects: The projects to find the dependencies for
    :type projects: List of Strings
    :param groups: The groups to include in dependency solving
    :type groups: List of str
    :returns: NEVRA's of the project and its dependencies
    :rtype: list of dicts
    :raises: ProjectsError if there was a problem installing something
    """
    _depsolve(dbo, projects, groups)

    try:
        dbo.resolve()
    except dnf.exceptions.DepsolveError as e:
        raise ProjectsError("There was a problem depsolving %s: %s" % (projects, str(e)))

    if len(dbo.transaction) == 0:
        return []

    return sorted(map(pkg_to_dep, dbo.transaction.install_set), key=lambda p: p["name"].lower())


def estimate_size(packages, block_size=6144):
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


def projects_depsolve_with_size(dbo, projects, groups, with_core=True):
    """Return the dependencies and installed size for a list of projects

    :param dbo: dnf base object
    :type dbo: dnf.Base
    :param project_names: The projects to find the dependencies for
    :type project_names: List of Strings
    :param groups: The groups to include in dependency solving
    :type groups: List of str
    :returns: installed size and a list of NEVRA's of the project and its dependencies
    :rtype: tuple of (int, list of dicts)
    :raises: ProjectsError if there was a problem installing something
    """
    _depsolve(dbo, projects, groups)

    if with_core:
        dbo.group_install("core", ['mandatory', 'default', 'optional'])

    try:
        dbo.resolve()
    except dnf.exceptions.DepsolveError as e:
        raise ProjectsError("There was a problem depsolving %s: %s" % (projects, str(e)))

    if len(dbo.transaction) == 0:
        return (0, [])

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
    projs = _unique_dicts(projects_info(dbo, module_names), key=lambda p: p["name"].lower())
    return list(map(proj_to_module, projs))

def _unique_dicts(lst, key):
    """Return a new list of dicts, only including one match of key(d)

    :param lst: list of dicts
    :type lst: list
    :param key: key function to match lst entries
    :type key: function
    :returns: list of the unique lst entries
    :rtype: list

    Uses key(d) to test for duplicates in the returned list, creating a
    list of unique return values.
    """
    result = []
    result_keys = []
    for d in lst:
        if key(d) not in result_keys:
            result.append(d)
            result_keys.append(key(d))
    return result

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
        module["dependencies"] = projects_depsolve(dbo, [(module["name"], "*.*")], [])

    return modules

def dnf_repo_to_file_repo(repo):
    """Return a string representation of a DNF Repo object suitable for writing to a .repo file

    :param repo: DNF Repository
    :type repo: dnf.RepoDict
    :returns: A string
    :rtype: str

    The DNF Repo.dump() function does not produce a string that can be used as a dnf .repo file,
    it ouputs baseurl and gpgkey as python lists which DNF cannot read. So do this manually with
    only the attributes we care about.
    """
    repo_str = "[%s]\nname = %s\n" % (repo.id, repo.name)
    if repo.metalink:
        repo_str += "metalink = %s\n" % repo.metalink
    elif repo.mirrorlist:
        repo_str += "mirrorlist = %s\n" % repo.mirrorlist
    elif repo.baseurl:
        repo_str += "baseurl = %s\n" % repo.baseurl[0]
    else:
        raise RuntimeError("Repo has no baseurl, metalink, or mirrorlist")

    # proxy is optional
    if repo.proxy:
        repo_str += "proxy = %s\n" % repo.proxy

    repo_str += "sslverify = %s\n" % repo.sslverify
    repo_str += "gpgcheck = %s\n" % repo.gpgcheck
    if repo.gpgkey:
        repo_str += "gpgkey = %s\n" % ",".join(repo.gpgkey)

    return repo_str

def repo_to_source(repo, system_source):
    """Return a Weldr Source dict created from the DNF Repository

    :param repo: DNF Repository
    :type repo: dnf.RepoDict
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
        source["gpgkey_urls"] = list(repo.gpgkey)

    return source

def source_to_repo(source, dnf_conf):
    """Return a dnf Repo object created from a source dict

    :param source: A Weldr source dict
    :type source: dict
    :returns: A dnf Repo object
    :rtype: dnf.Repo

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
    repo = dnf.repo.Repo(source["name"], dnf_conf)
    # This will allow errors to be raised so we can catch them
    # without this they are logged, but the repo is silently disabled
    repo.skip_if_unavailable = False

    if source["type"] == "yum-baseurl":
        repo.baseurl = source["url"]
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
        repo.gpgkey = tuple(source["gpgkey_urls"])

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

    cfg = ConfigParser(strict=False)
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
            cfg = ConfigParser(strict=False)
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
