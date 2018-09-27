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
from threading import Lock
import time
import yum
from yum.Errors import YumBaseError

# This is a hack to short circuit yum's internal logging
yum.logginglevels._added_handlers = True

from pylorax.sysutils import joinpaths

class YumLock(object):
    """Hold the YumBase object and a Lock to control access to it.

    self.yb is a property that returns the YumBase object, but it *may* change
    from one call to the next if the upstream repositories have changed.
    """
    def __init__(self, conf, expire_secs=6*60*60):
        self._conf = conf
        self._lock = Lock()
        self.yb = get_base_object(self._conf)
        self._expire_secs = expire_secs
        self._expire_time = time.time() + self._expire_secs

    @property
    def lock(self):
        """Check for repo updates (using expiration time) and return the lock

        If the repository has been updated, tear down the old YumBase and
        create a new one. This is the only way to force yum to use the new
        metadata.
        """
        if time.time() > self._expire_time:
            return self.lock_check
        return self._lock

    @property
    def lock_check(self):
        """Force a check for repo updates and return the lock

        If the repository has been updated, tear down the old YumBase and
        create a new one. This is the only way to force yum to use the new
        metadata.

        Use this method sparingly, it removes the repodata and downloads a new copy every time.
        """
        self._expire_time = time.time() + self._expire_secs
        if self._haveReposChanged():
            self._destroyYb()
            self.yb = get_base_object(self._conf)
        return self._lock

    def _destroyYb(self):
        # Do our best to get yum to let go of all the things...
        self.yb.pkgSack.dropCachedData()
        for s in self.yb.pkgSack.sacks.values():
            s.close()
            del s
        del self.yb.pkgSack
        self.yb.closeRpmDB()
        del self.yb.tsInfo
        del self.yb.ts
        self.yb.close()
        del self.yb

    def _haveReposChanged(self):
        """Return True if the repo has new metadata"""
        # This is a total kludge, yum doesn't really expect to deal with things changing while the
        # object is is use.
        try:
            before = [(r.id, r.repoXML.checksums["sha256"]) for r in sorted(self.yb.repos.listEnabled())]
            for r in sorted(self.yb.repos.listEnabled()):
                r.metadata_expire = 0
                del r.repoXML
            after = [(r.id, r.repoXML.checksums["sha256"]) for r in sorted(self.yb.repos.listEnabled())]
            return before != after
        except Exception:
            return False

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
    try:
        yb.doRepoSetup()
        yb.repos.doSetup()
        yb.repos.populateSack(mdtype='all', cacheonly=0)
    except YumBaseError as e:
        log.error("Failed to update metadata: %s", str(e))
        raise RuntimeError("Fetching metadata failed: %s" % str(e))
