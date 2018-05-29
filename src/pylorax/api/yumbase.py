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
# pylint: disable=bad-preconf-access

import logging
log = logging.getLogger("lorax-composer")

import ConfigParser
from fnmatch import fnmatchcase
from glob import glob
import os
import yum
# This is a hack to short circuit yum's internal logging
yum.logginglevels._added_handlers = True

from pylorax.sysutils import joinpaths

def get_base_object(conf):
    """Get the Yum object with settings from the config file

    :param conf: configuration object
    :type conf: ComposerParser
    :returns: A Yum base object
    :rtype: YumBase
    """
    cachedir = os.path.abspath(conf.get("composer", "cache_dir"))
    yumconf = os.path.abspath(conf.get("composer", "yum_conf"))
    yumroot = os.path.abspath(conf.get("composer", "yum_root"))
    repodir = os.path.abspath(conf.get("composer", "repo_dir"))

    c = ConfigParser.ConfigParser()

    # add the main section
    section = "main"
    data = {"cachedir": cachedir,
            "keepcache": 0,
            "gpgcheck": 0,
            "plugins": 0,
            "assumeyes": 1,
            "reposdir": "",
            "tsflags": "nodocs"}

    if conf.get_default("yum", "proxy", None):
        data["proxy"] = conf.get("yum", "proxy")

    if conf.has_option("yum", "sslverify") and not conf.getboolean("yum", "sslverify"):
        data["sslverify"] = "0"

    c.add_section(section)
    map(lambda (key, value): c.set(section, key, value), data.items())

    # write the yum configuration file
    with open(yumconf, "w") as f:
        c.write(f)

    # create the yum base object
    yb = yum.YumBase()

    yb.preconf.fn = yumconf

    yb.preconf.root = yumroot
    if not os.path.isdir(yb.preconf.root):
        os.makedirs(yb.preconf.root)

    _releasever = conf.get_default("composer", "releasever", None)
    if not _releasever:
        distroverpkg = ['system-release(releasever)', 'redhat-release']
        # Use yum private function to guess the releasever
        _releasever = yum.config._getsysver("/", distroverpkg)
    log.info("releasever = %s", _releasever)
    yb.preconf.releasever = _releasever

    # Turn on as much yum logging as we can
    yb.preconf.debuglevel = 6
    yb.preconf.errorlevel = 6
    yb.logger.setLevel(logging.DEBUG)
    yb.verbose_logger.setLevel(logging.DEBUG)

    # Gather up all the available repo files, add the ones matching "repos":"enabled" patterns
    enabled_repos = conf.get("repos", "enabled").split(",")
    repo_files = glob(joinpaths(repodir, "*.repo"))
    if not conf.has_option("repos", "use_system_repos") or conf.getboolean("repos", "use_system_repos"):
        repo_files.extend(glob("/etc/yum.repos.d/*.repo"))

    for repo_file in repo_files:
        name = os.path.basename(repo_file)[:-5]
        if any(map(lambda pattern: fnmatchcase(name, pattern), enabled_repos)):     # pylint: disable=cell-var-from-loop
            yb.getReposFromConfigFile(repo_file)

    # Update the metadata from the enabled repos to speed up later operations
    log.info("Updating yum repository metadata")
    update_metadata(yb)

    return yb

def update_metadata(yb):
    """Update the metadata for all the enabled repos

    :param yb: The Yum base object
    :type yb: yum.YumBase
    :returns: None
    :rtype: None
    """
    for r in yb.repos.sort():
        r.metadata_expire = 0
        r.mdpolicy = "group:all"
    yb.doRepoSetup()
    yb.repos.doSetup()
    yb.repos.populateSack(mdtype='all', cacheonly=1)
