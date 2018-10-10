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
import configparser
import grp
import os
import pwd

from pylorax.sysutils import joinpaths

class ComposerConfig(configparser.SafeConfigParser):
    def get_default(self, section, option, default):
        try:
            return self.get(section, option)
        except configparser.Error:
            return default


def configure(conf_file="/etc/lorax/composer.conf", root_dir="/", test_config=False):
    """lorax-composer configuration

    :param conf_file: Path to the config file overriding the default settings
    :type conf_file: str
    :param root_dir: Directory to prepend to paths, defaults to /
    :type root_dir: str
    :param test_config: Set to True to skip reading conf_file
    :type test_config: bool
    """
    conf = ComposerConfig()

    # set defaults
    conf.add_section("composer")
    conf.set("composer", "share_dir", os.path.realpath(joinpaths(root_dir, "/usr/share/lorax/")))
    conf.set("composer", "lib_dir", os.path.realpath(joinpaths(root_dir, "/var/lib/lorax/composer/")))
    conf.set("composer", "repo_dir", os.path.realpath(joinpaths(root_dir, "/var/lib/lorax/composer/repos.d/")))
    conf.set("composer", "dnf_conf", os.path.realpath(joinpaths(root_dir, "/var/tmp/composer/dnf.conf")))
    conf.set("composer", "dnf_root", os.path.realpath(joinpaths(root_dir, "/var/tmp/composer/dnf/root/")))
    conf.set("composer", "cache_dir", os.path.realpath(joinpaths(root_dir, "/var/tmp/composer/cache/")))
    conf.set("composer", "tmp", os.path.realpath(joinpaths(root_dir, "/var/tmp/")))

    conf.add_section("users")
    conf.set("users", "root", "1")

    # Enable all available repo files by default
    conf.add_section("repos")
    conf.set("repos", "use_system_repos", "1")
    conf.set("repos", "enabled", "*")

    conf.add_section("dnf")

    if not test_config:
        # read the config file
        if os.path.isfile(conf_file):
            conf.read(conf_file)

    return conf

def make_owned_dir(p_dir, uid, gid):
    """Make a directory and its parents, setting owner and group

    :param p_dir: path to directory to create
    :type p_dir: string
    :param uid: uid of owner
    :type uid: int
    :param gid: gid of owner
    :type gid: int
    :returns: list of errors
    :rtype: list of str

    Check to make sure it does not have o+rw permissions and that it is owned by uid:gid
    """
    errors = []
    if not os.path.isdir(p_dir):
        # Make sure no o+rw permissions are set
        orig_umask = os.umask(0o006)
        os.makedirs(p_dir, 0o771)
        os.chown(p_dir, uid, gid)
        os.umask(orig_umask)
    else:
        p_stat = os.stat(p_dir)
        if p_stat.st_mode & 0o006 != 0:
            errors.append("Incorrect permissions on %s, no o+rw permissions are allowed." % p_dir)

        if p_stat.st_gid != gid or p_stat.st_uid != 0:
            gr_name = grp.getgrgid(gid).gr_name
            u_name = pwd.getpwuid(uid)
            errors.append("%s should be owned by %s:%s" % (p_dir, u_name, gr_name))

    return errors

def make_dnf_dirs(conf, uid, gid):
    """Make any missing dnf directories owned by user:group

    :param conf: The configuration to use
    :type conf: ComposerConfig
    :param uid: uid of owner
    :type uid: int
    :param gid: gid of owner
    :type gid: int
    :returns: list of errors
    :rtype: list of str
    """
    errors = []
    for p in ["dnf_conf", "repo_dir", "cache_dir", "dnf_root"]:
        p_dir = os.path.abspath(conf.get("composer", p))
        if p == "dnf_conf":
            p_dir = os.path.dirname(p_dir)
        errors.extend(make_owned_dir(p_dir, uid, gid))

def make_queue_dirs(conf, gid):
    """Make any missing queue directories

    :param conf: The configuration to use
    :type conf: ComposerConfig
    :param gid: Group ID that has access to the queue directories
    :type gid: int
    :returns: list of errors
    :rtype: list of str
    """
    errors = []
    lib_dir = conf.get("composer", "lib_dir")
    for p in ["queue/run", "queue/new", "results"]:
        p_dir = joinpaths(lib_dir, p)
        errors.extend(make_owned_dir(p_dir, 0, gid))
    return errors
