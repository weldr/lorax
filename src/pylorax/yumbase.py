# Copyright (C) 2009-2020  Red Hat, Inc.
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
# Red Hat Author(s):  Martin Gracik <mgracik@redhat.com>
#
# pylint: disable=bad-preconf-access


import ConfigParser
import logging
import os
import yum

def get_yum_base_object(installroot, repositories, mirrorlists=None, repo_files=None,
                        tempdir="/var/tmp", proxy=None, excludepkgs=None,
                        sslverify=True, releasever=None):

    def sanitize_repo(repo):
        """Convert bare paths to file:/// URIs, and silently reject protocols unhandled by yum"""
        if repo.startswith("/"):
            return "file://{0}".format(repo)
        elif any(repo.startswith(p) for p in ('http://', 'https://', 'ftp://', 'file://')):
            return repo
        else:
            return None

    if mirrorlists is None:
        mirrorlists = []
    if repo_files is None:
        repo_files = []
    if excludepkgs is None:
        excludepkgs = []

    # sanitize the repositories
    repositories = map(sanitize_repo, repositories)
    mirrorlists = map(sanitize_repo, mirrorlists)

    # remove invalid repositories
    repositories = filter(bool, repositories)
    mirrorlists = filter(bool, mirrorlists)

    cachedir = os.path.join(tempdir, "yum.cache")
    if not os.path.isdir(cachedir):
        os.mkdir(cachedir)

    yumconf = os.path.join(tempdir, "yum.conf")
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

    if proxy:
        data["proxy"] = proxy

    if sslverify == False:
        data["sslverify"] = "0"

    if excludepkgs:
        data["exclude"] = " ".join(excludepkgs)

    c.add_section(section)
    map(lambda (key, value): c.set(section, key, value), data.items())

    # add the main repository - the first repository from list
    # This list may be empty if using --repo to load .repo files
    if repositories:
        section = "lorax-repo"
        data = {"name": "lorax repo",
                "baseurl": repositories[0],
                "enabled": 1}

        c.add_section(section)
        map(lambda (key, value): c.set(section, key, value), data.items())

    # add the extra repositories
    for n, extra in enumerate(repositories[1:], start=1):
        section = "lorax-extra-repo-{0:d}".format(n)
        data = {"name": "lorax extra repo {0:d}".format(n),
                "baseurl": extra,
                "enabled": 1}

        c.add_section(section)
        map(lambda (key, value): c.set(section, key, value), data.items())

    # add the mirrorlists
    for n, mirror in enumerate(mirrorlists, start=1):
        section = "lorax-mirrorlist-{0:d}".format(n)
        data = {"name": "lorax mirrorlist {0:d}".format(n),
                "mirrorlist": mirror,
                "enabled": 1 }

        c.add_section(section)
        map(lambda (key, value): c.set(section, key, value), data.items())

    # write the yum configuration file
    with open(yumconf, "w") as f:
        c.write(f)

    # create the yum base object
    yb = yum.YumBase()

    yb.preconf.fn = yumconf
    yb.preconf.root = installroot
    if releasever:
        yb.preconf.releasever = releasever

    # Turn on as much yum logging as we can
    yb.preconf.debuglevel = 6
    yb.preconf.errorlevel = 6
    yb.logger.setLevel(logging.DEBUG)
    yb.verbose_logger.setLevel(logging.DEBUG)

    # Add .repo files from the cmdline
    for fn in repo_files:
        if os.path.exists(fn):
            yb.getReposFromConfigFile(fn)

    return yb
