# Copyright (C) 2018 Red Hat, Inc.
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
log = logging.getLogger("pylorax")

import dnf
import os
import shutil

from pylorax import DEFAULT_PLATFORM_ID
from pylorax.sysutils import flatconfig

def get_dnf_base_object(installroot, sources, mirrorlists=None, repos=None,
                        enablerepos=None, disablerepos=None,
                        tempdir="/var/tmp", proxy=None, releasever="34",
                        cachedir=None, logdir=None, sslverify=True, dnfplugins=None):
    """ Create a dnf Base object and setup the repositories and installroot

        :param string installroot: Full path to the installroot
        :param list sources: List of source repo urls to use for the installation
        :param list enablerepos: List of repo names to enable
        :param list disablerepos: List of repo names to disable
        :param list mirrorlist: List of mirrors to use
        :param string tempdir: Path of temporary directory
        :param string proxy: http proxy to use when fetching packages
        :param string releasever: Release version to pass to dnf
        :param string cachedir: Directory to use for caching packages
        :param bool noverifyssl: Set to True to ignore the CA of ssl certs. eg. use self-signed ssl for https repos.

        If tempdir is not set /var/tmp is used.
        If cachedir is None a dnf.cache directory is created inside tmpdir
    """
    def sanitize_repo(repo):
        """Convert bare paths to file:/// URIs, and silently reject protocols unhandled by yum"""
        if repo.startswith("/"):
            return "file://{0}".format(repo)
        elif any(repo.startswith(p) for p in ('http://', 'https://', 'ftp://', 'file://')):
            return repo
        else:
            return None

    mirrorlists = mirrorlists or []

    # sanitize the repositories
    sources = list(sanitize_repo(r) for r in sources)
    mirrorlists = list(sanitize_repo(r) for r in mirrorlists)

    # remove invalid repositories
    sources = list(r for r in sources if r)
    mirrorlists = list(r for r in mirrorlists if r)

    if not cachedir:
        cachedir = os.path.join(tempdir, "dnf.cache")
    if not os.path.isdir(cachedir):
        os.mkdir(cachedir)

    if not logdir:
        logdir = os.path.join(tempdir, "dnf.logs")
        if not os.path.isdir(logdir):
            os.mkdir(logdir)

    dnfbase = dnf.Base()
    # Enable DNF pluings
    # NOTE: These come from the HOST system's environment
    if dnfplugins:
        if dnfplugins[0] == "*":
            # Enable them all
            dnfbase.init_plugins()
        else:
            # Only enable the listed plugins
            dnfbase.init_plugins(disabled_glob=["*"], enable_plugins=dnfplugins)
    conf = dnfbase.conf
    conf.logdir = logdir
    conf.cachedir = cachedir

    conf.install_weak_deps = False
    conf.releasever = releasever
    conf.installroot = installroot
    conf.prepend_installroot('persistdir')
    # this is a weird 'AppendOption' thing that, when you set it,
    # actually appends. Doing this adds 'nodocs' to the existing list
    # of values, over in libdnf, it does not replace the existing values.
    conf.tsflags = ['nodocs']
    # Log details about the solver
    conf.debug_solver = True

    if proxy:
        conf.proxy = proxy

    if sslverify == False:
        conf.sslverify = False

    # DNF 3.2 needs to have module_platform_id set, otherwise depsolve won't work correctly
    if not os.path.exists("/etc/os-release"):
        log.warning("/etc/os-release is missing, cannot determine platform id, falling back to %s", DEFAULT_PLATFORM_ID)
        platform_id = DEFAULT_PLATFORM_ID
    else:
        os_release = flatconfig("/etc/os-release")
        platform_id = os_release.get("PLATFORM_ID", DEFAULT_PLATFORM_ID)
    log.info("Using %s for module_platform_id", platform_id)
    conf.module_platform_id = platform_id

    # Add .repo files
    if repos:
        reposdir = os.path.join(tempdir, "dnf.repos")
        if not os.path.isdir(reposdir):
            os.mkdir(reposdir)
        for r in repos:
            shutil.copy2(r, reposdir)
        conf.reposdir = [reposdir]
        dnfbase.read_all_repos()

    # add the sources
    for i, r in enumerate(sources):
        if "SRPM" in r or "srpm" in r:
            log.info("Skipping source repo: %s", r)
            continue
        repo_name = "lorax-repo-%d" % i
        repo = dnf.repo.Repo(repo_name, conf)
        repo.baseurl = [r]
        if proxy:
            repo.proxy = proxy
        repo.enable()
        dnfbase.repos.add(repo)
        log.info("Added '%s': %s", repo_name, r)
        log.info("Fetching metadata...")
        try:
            repo.load()
        except dnf.exceptions.RepoError as e:
            log.error("Error fetching metadata for %s: %s", repo_name, e)
            return None

    # add the mirrorlists
    for i, r in enumerate(mirrorlists):
        if "SRPM" in r or "srpm" in r:
            log.info("Skipping source repo: %s", r)
            continue
        repo_name = "lorax-mirrorlist-%d" % i
        repo = dnf.repo.Repo(repo_name, conf)
        repo.mirrorlist = r
        if proxy:
            repo.proxy = proxy
        repo.enable()
        dnfbase.repos.add(repo)
        log.info("Added '%s': %s", repo_name, r)
        log.info("Fetching metadata...")
        try:
            repo.load()
        except dnf.exceptions.RepoError as e:
            log.error("Error fetching metadata for %s: %s", repo_name, e)
            return None

    # Enable repos listed on the cmdline
    for r in enablerepos:
        repolist = dnfbase.repos.get_matching(r)
        if not repolist:
            log.warning("%s is an unknown repo, not enabling it", r)
        else:
            repolist.enable()
            log.info("Enabled repo %s", r)

    # Disable repos listed on the cmdline
    for r in disablerepos:
        repolist = dnfbase.repos.get_matching(r)
        if not repolist:
            log.warning("%s is an unknown repo, not disabling it", r)
        else:
            repolist.disable()
            log.info("Disabled repo %s", r)

    dnfbase.fill_sack(load_system_repo=False)
    dnfbase.read_comps()

    return dnfbase
