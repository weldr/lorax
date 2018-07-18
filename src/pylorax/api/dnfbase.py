#
# Copyright (C) 2017-2018 Red Hat, Inc.
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
# pylint: disable=bad-preconf-access

import logging
log = logging.getLogger("lorax-composer")

import dnf
import dnf.logging
from glob import glob
import os
import shutil


def get_base_object(conf):
    """Get the DNF object with settings from the config file

    :param conf: configuration object
    :type conf: ComposerParser
    :returns: A DNF Base object
    :rtype: dnf.Base
    """
    cachedir = os.path.abspath(conf.get("composer", "cache_dir"))
    dnfconf = os.path.abspath(conf.get("composer", "dnf_conf"))
    dnfroot = os.path.abspath(conf.get("composer", "dnf_root"))
    repodir = os.path.abspath(conf.get("composer", "repo_dir"))

    # Setup the config for the DNF Base object
    dbo = dnf.Base()
    dbc = dbo.conf
# TODO - Handle this
#    dbc.logdir = logdir
    dbc.installroot = dnfroot
    if not os.path.isdir(dnfroot):
        os.makedirs(dnfroot)
    if not os.path.isdir(repodir):
        os.makedirs(repodir)

    dbc.cachedir = cachedir
    dbc.reposdir = [repodir]
    dbc.install_weak_deps = False
    dbc.prepend_installroot('persistdir')
    dbc.tsflags.append('nodocs')

    if conf.get_default("dnf", "proxy", None):
        dbc.proxy = conf.get("dnf", "proxy")

    if conf.has_option("dnf", "sslverify") and not conf.getboolean("dnf", "sslverify"):
        dbc.sslverify = False

    _releasever = conf.get_default("composer", "releasever", None)
    if not _releasever:
        # Use the releasever of the host system
        _releasever = dnf.rpm.detect_releasever("/")
    log.info("releasever = %s", _releasever)
    dbc.releasever = _releasever

    # write the dnf configuration file
    with open(dnfconf, "w") as f:
        f.write(dbc.dump())

    # dnf needs the repos all in one directory, composer uses repodir for this
    # if system repos are supposed to be used, copy them into repodir, overwriting any previous copies
    if not conf.has_option("repos", "use_system_repos") or conf.getboolean("repos", "use_system_repos"):
        for repo_file in glob("/etc/yum.repos.d/*.repo"):
            shutil.copy2(repo_file, repodir)
    dbo.read_all_repos()

    # Update the metadata from the enabled repos to speed up later operations
    log.info("Updating repository metadata")
    try:
        dbo.fill_sack(load_system_repo=False)
        dbo.read_comps()
    except dnf.exceptions.Error as e:
        log.error("Failed to update metadata: %s", str(e))
        raise RuntimeError("Fetching metadata failed: %s" % str(e))

    return dbo
