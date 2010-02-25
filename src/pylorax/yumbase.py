#
# yumbase.py
#
# Copyright (C) 2009  Red Hat, Inc.
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

import os
import ConfigParser

import yum


def get_yum_base_object(installroot, repositories, mirrorlists=[],
                        tempdir="/tmp"):

    def sanitize_repo(repo):
        if repo.startswith("/"):
            return "file://{0}".format(repo)
        elif repo.startswith("http://") or repo.startswith("ftp://"):
            return repo
        else:
            return None

    # sanitize the repositories
    repositories = map(sanitize_repo, repositories)
    mirrorlists = map(sanitize_repo, mirrorlists)

    # remove invalid repositories
    repositories = filter(bool, repositories)
    mirrorlists = filter(bool, mirrorlists)

    #cachedir = os.path.join(tempdir, "yum.cache")
    #if not os.path.isdir(cachedir):
    #    os.mkdir(cachedir)

    yumconf = os.path.join(tempdir, "yum.conf")
    c = ConfigParser.ConfigParser()

    # add the main section
    section = "main"
    data = {#"cachedir": cachedir,
            #"keepcache": 0,
            "gpgcheck": 0,
            "plugins": 0,
            "reposdir": "",
            "tsflags": "nodocs"}

    c.add_section(section)
    map(lambda (key, value): c.set(section, key, value), data.items())

    # add the main repository - the first repository from list
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
    yb._getConfig()

    yb._getRpmDB()
    yb._getRepos()
    yb._getSacks()

    return yb
