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
""" Setup for composing an image

Adding New Output Types
-----------------------

The new output type must add a kickstart template to ./share/composer/ where the
name of the kickstart (without the trailing .ks) matches the entry in compose_args.

The kickstart should not have any url or repo entries, these will be added at build
time. The %packages section should be the last thing, and while it can contain mandatory
packages required by the output type, it should not have the trailing %end because the
package NEVRAs will be appended to it at build time.

compose_args should have a name matching the kickstart, and it should set the novirt_install
parameters needed to generate the desired output. Other types should be set to False.

"""
import logging
log = logging.getLogger("lorax-composer")

import os
from glob import glob
from math import ceil
import pytoml as toml
import shutil
from uuid import uuid4

from pyanaconda.simpleconfig import SimpleConfigFile

# Use pykickstart to calculate disk image size
from pykickstart.parser import KickstartParser
from pykickstart.version import makeVersion, RHEL7

from pylorax.api.projects import projects_depsolve, projects_depsolve_with_size, dep_nevra
from pylorax.api.projects import ProjectsError
from pylorax.api.recipes import read_recipe_and_id
from pylorax.api.timestamp import TS_CREATED, write_timestamp
from pylorax.imgutils import default_image_name
from pylorax.sysutils import joinpaths


def test_templates(yb, share_dir):
    """ Try depsolving each of the the templates and report any errors

    :param yb: yum base object
    :type yb: YumBase
    :returns: List of template types and errors
    :rtype: List of errors

    Return a list of templates and errors encountered or an empty list
    """
    template_errors = []
    for compose_type in compose_types(share_dir):
        # Read the kickstart template for this type
        ks_template_path = joinpaths(share_dir, "composer", compose_type) + ".ks"
        ks_template = open(ks_template_path, "r").read()

        # How much space will the packages in the default template take?
        ks_version = makeVersion(RHEL7)
        ks = KickstartParser(ks_version, errorsAreFatal=False, missingIncludeIsFatal=False)
        ks.readKickstartFromString(ks_template+"\n%end\n")
        pkgs = [(name, "*") for name in ks.handler.packages.packageList]
        grps = [grp.name for grp in ks.handler.packages.groupList]
        try:
            _ = projects_depsolve(yb, pkgs, grps)
        except ProjectsError as e:
            template_errors.append("Error depsolving %s: %s" % (compose_type, str(e)))

    return template_errors

def repo_to_ks(r, url="url"):
    """ Return a kickstart line with the correct args.

    Set url to "baseurl" if it is a repo, leave it as "url" for the installation url.
    """
    cmd = ""
    if url == "url":
        if not r.urls:
            raise RuntimeError("Cannot find a base url for %s" % r.name)

        # url is passed to Anaconda on the cmdline with --repo, so it cannot support a mirror
        # If a mirror is setup yum will return the list of mirrors in .urls
        # So just use the first one.
        cmd += '--%s="%s" ' % (url, r.urls[0])
    elif r.metalink:
        # XXX Total Hack
        # RHEL7 kickstart doesn't support metalink. If the url has 'metalink' in it, rewrite it as 'mirrorlist'
        if "metalink" in r.metalink:
            log.info("RHEL7 does not support metalink, translating to mirrorlist")
            cmd += '--mirrorlist="%s" ' % r.metalink.replace("metalink", "mirrorlist")
        else:
            log.error("Could not convert metalink to mirrorlist. %s", r.metalink)
            raise RuntimeError("Cannot convert metalink to mirrorlist: %s" % r.metalink)
    elif r.mirrorlist:
        cmd += '--mirrorlist="%s" ' % r.mirrorlist
    elif r.baseurl:
        cmd += '--%s="%s" ' % (url, r.baseurl[0])
    else:
        raise RuntimeError("Repo has no baseurl or mirror")

    if r.proxy:
        cmd += '--proxy="%s" ' % r.proxy

    if not r.sslverify:
        cmd += '--noverifyssl'

    return cmd


def write_ks_root(f, user):
    """ Write kickstart root password and sshkey entry

    :param f: kickstart file object
    :type f: open file object
    :param user: A blueprint user dictionary
    :type user: dict

    If the entry contains a ssh key, use sshkey to write it
    If it contains password, use rootpw to set it

    root cannot be used with the user command. So only key and password are supported
    for root.
    """
    # ssh key uses the sshkey kickstart command
    if "key" in user:
        f.write('sshkey --user %s "%s"\n' % (user["name"], user["key"]))

    if "password" in user:
        if any(user["password"].startswith(prefix) for prefix in ["$2b$", "$6$", "$5$"]):
            log.debug("Detected pre-crypted password")
            f.write('rootpw --iscrypted "%s"\n' % user["password"])
        else:
            log.debug("Detected plaintext password")
            f.write('rootpw --plaintext "%s"\n' % user["password"])

def write_ks_user(f, user):
    """ Write kickstart user and sshkey entry

    :param f: kickstart file object
    :type f: open file object
    :param user: A blueprint user dictionary
    :type user: dict

    If the entry contains a ssh key, use sshkey to write it
    All of the user fields are optional, except name, write out a kickstart user entry
    with whatever options are relevant.
    """
    # ssh key uses the sshkey kickstart command
    if "key" in user:
        f.write('sshkey --user %s "%s"\n' % (user["name"], user["key"]))

    # Write out the user kickstart command, much of it is optional
    f.write("user --name %s" % user["name"])
    if "home" in user:
        f.write(" --homedir %s" % user["home"])

    if "password" in user:
        if any(user["password"].startswith(prefix) for prefix in ["$2b$", "$6$", "$5$"]):
            log.debug("Detected pre-crypted password")
            f.write(" --iscrypted")
        else:
            log.debug("Detected plaintext password")
            f.write(" --plaintext")

        f.write(" --password \"%s\"" % user["password"])

    if "shell" in user:
        f.write(" --shell %s" % user["shell"])

    if "uid" in user:
        f.write(" --uid %d" % int(user["uid"]))

    if "gid" in user:
        f.write(" --gid %d" % int(user["gid"]))

    if "description" in user:
        f.write(" --gecos \"%s\"" % user["description"])

    if "groups" in user:
        f.write(" --groups %s" % ",".join(user["groups"]))

    f.write("\n")


def write_ks_group(f, group):
    """ Write kickstart group entry

    :param f: kickstart file object
    :type f: open file object
    :param group: A blueprint group dictionary
    :type user: dict

    gid is optional
    """
    if "name" not in group:
        raise RuntimeError("group entry requires a name")

    f.write("group --name %s" % group["name"])
    if "gid" in group:
        f.write(" --gid %d" % int(group["gid"]))

    f.write("\n")


def add_customizations(f, recipe):
    """ Add customizations to the kickstart file

    :param f: kickstart file object
    :type f: open file object
    :param recipe:
    :type recipe: Recipe object
    :returns: None
    :raises: RuntimeError if there was a problem writing to the kickstart
    """
    if "customizations" not in recipe:
        return
    customizations = recipe["customizations"]

    if "hostname" in customizations:
        f.write("network --hostname=%s\n" % customizations["hostname"])

    # TODO - remove this, should use user section to define this
    if "sshkey" in customizations:
        # This is a list of entries
        for sshkey in customizations["sshkey"]:
            if "user" not in sshkey or "key" not in sshkey:
                log.error("%s is incorrect, skipping", sshkey)
                continue
            f.write('sshkey --user %s "%s"\n' % (sshkey["user"], sshkey["key"]))

    # Creating a user also creates a group. Make a list of the names for later
    user_groups = []
    if "user" in customizations:
        # only name is required, everything else is optional
        for user in customizations["user"]:
            if "name" not in user:
                raise RuntimeError("user entry requires a name")

            # root is special, cannot use normal user command for it
            if user["name"] == "root":
                write_ks_root(f, user)
                continue

            write_ks_user(f, user)
            user_groups.append(user["name"])

    if "group" in customizations:
        for group in customizations["group"]:
            if group["name"] not in user_groups:
                write_ks_group(f, group)
            else:
                log.warning("Skipping group %s, already created by user", group["name"])

def start_build(cfg, yumlock, gitlock, branch, recipe_name, compose_type, test_mode=0):
    """ Start the build

    :param cfg: Configuration object
    :type cfg: ComposerConfig
    :param yumlock: Lock and YumBase for depsolving
    :type yumlock: YumLock
    :param recipe: The recipe to build
    :type recipe: str
    :param compose_type: The type of output to create from the recipe
    :type compose_type: str
    :returns: Unique ID for the build that can be used to track its status
    :rtype: str
    """
    share_dir = cfg.get("composer", "share_dir")
    lib_dir = cfg.get("composer", "lib_dir")

    # Make sure compose_type is valid
    if compose_type not in compose_types(share_dir):
        raise RuntimeError("Invalid compose type (%s), must be one of %s" % (compose_type, compose_types(share_dir)))

    with gitlock.lock:
        (commit_id, recipe) = read_recipe_and_id(gitlock.repo, branch, recipe_name)

    # Combine modules and packages and depsolve the list
    module_nver = recipe.module_nver
    package_nver = recipe.package_nver
    projects = sorted(set(module_nver+package_nver), key=lambda p: p[0].lower())
    deps = []
    try:
        with yumlock.lock:
            (installed_size, deps) = projects_depsolve_with_size(yumlock.yb, projects, recipe.group_names, with_core=False)
    except ProjectsError as e:
        log.error("start_build depsolve: %s", str(e))
        raise RuntimeError("Problem depsolving %s: %s" % (recipe["name"], str(e)))

    # Read the kickstart template for this type
    ks_template_path = joinpaths(share_dir, "composer", compose_type) + ".ks"
    ks_template = open(ks_template_path, "r").read()

    # How much space will the packages in the default template take?
    ks_version = makeVersion(RHEL7)
    ks = KickstartParser(ks_version, errorsAreFatal=False, missingIncludeIsFatal=False)
    ks.readKickstartFromString(ks_template+"\n%end\n")
    pkgs = [(name, "*") for name in ks.handler.packages.packageList]
    grps = [grp.name for grp in ks.handler.packages.groupList]
    try:
        with yumlock.lock:
            (template_size, _) = projects_depsolve_with_size(yumlock.yb, pkgs, grps,
                                                             with_core=not ks.handler.packages.nocore)
    except ProjectsError as e:
        log.error("start_build depsolve: %s", str(e))
        raise RuntimeError("Problem depsolving %s: %s" % (recipe["name"], str(e)))
    log.debug("installed_size = %d, template_size=%d", installed_size, template_size)

    # Minimum LMC disk size is 1GiB, and anaconda bumps the estimated size up by 35% (which doesn't always work).
    installed_size = max(1024**3, int((installed_size+template_size) * 1.4))
    log.debug("/ partition size = %d", installed_size)

    # Create the results directory
    build_id = str(uuid4())
    results_dir = joinpaths(lib_dir, "results", build_id)
    os.makedirs(results_dir)

    # Write the recipe commit hash
    commit_path = joinpaths(results_dir, "COMMIT")
    with open(commit_path, "w") as f:
        f.write(commit_id)

    # Write the original recipe
    recipe_path = joinpaths(results_dir, "blueprint.toml")
    with open(recipe_path, "w") as f:
        f.write(recipe.toml())

    # Write the frozen recipe
    frozen_recipe = recipe.freeze(deps)
    recipe_path = joinpaths(results_dir, "frozen.toml")
    with open(recipe_path, "w") as f:
        f.write(frozen_recipe.toml())

    # Write out the dependencies to the results dir
    deps_path = joinpaths(results_dir, "deps.toml")
    with open(deps_path, "w") as f:
        f.write(toml.dumps({"packages":deps}).encode("UTF-8"))

    # Save a copy of the original kickstart
    shutil.copy(ks_template_path, results_dir)

    with yumlock.lock:
        repos = yumlock.yb.repos.listEnabled()
    if not repos:
        raise RuntimeError("No enabled repos, canceling build.")

    # Create the final kickstart with repos and package list
    ks_path = joinpaths(results_dir, "final-kickstart.ks")
    with open(ks_path, "w") as f:
        ks_url = repo_to_ks(repos[0], "url")
        log.debug("url = %s", ks_url)
        f.write('url %s\n' % ks_url)
        for idx, r in enumerate(repos[1:]):
            ks_repo = repo_to_ks(r, "baseurl")
            log.debug("repo composer-%s = %s", idx, ks_repo)
            f.write('repo --name="composer-%s" %s\n' % (idx, ks_repo))

        # Setup the disk for booting
        # TODO Add GPT and UEFI boot support
        f.write('clearpart --all\n')

        # Write the root partition and it's size in MB (rounded up)
        f.write('part / --fstype="ext4" --size=%d\n' % ceil(installed_size / 1024**2))

        f.write(ks_template)

        for d in deps:
            f.write(dep_nevra(d)+"\n")
        f.write("%end\n")

        add_customizations(f, recipe)

    # Setup the config to pass to novirt_install
    log_dir = joinpaths(results_dir, "logs/")
    cfg_args = compose_args(compose_type)

    # Get the title, project, and release version from the host
    if not os.path.exists("/etc/os-release"):
        log.error("/etc/os-release is missing, cannot determine product or release version")
    os_release = SimpleConfigFile("/etc/os-release")
    os_release.read()

    log.debug("os_release = %s", os_release)

    cfg_args["title"] = os_release.get("PRETTY_NAME")
    cfg_args["project"] = os_release.get("NAME")
    cfg_args["releasever"] = os_release.get("VERSION_ID")
    cfg_args["volid"] = ""

    cfg_args.update({
        "compression":      "xz",
        "compress_args":    [],
        "ks":               [ks_path],
        "project":          "Red Hat Enterprise Linux",
        "releasever":       "7",
        "logfile":          log_dir
    })
    with open(joinpaths(results_dir, "config.toml"), "w") as f:
        f.write(toml.dumps(cfg_args).encode("UTF-8"))

    # Set the initial status
    open(joinpaths(results_dir, "STATUS"), "w").write("WAITING")

    # Set the test mode, if requested
    if test_mode > 0:
        open(joinpaths(results_dir, "TEST"), "w").write("%s" % test_mode)

    write_timestamp(results_dir, TS_CREATED)
    log.info("Adding %s (%s %s) to compose queue", build_id, recipe["name"], compose_type)
    os.symlink(results_dir, joinpaths(lib_dir, "queue/new/", build_id))

    return build_id

# Supported output types
def compose_types(share_dir):
    r""" Returns a list of the supported output types

    The output types come from the kickstart names in /usr/share/lorax/composer/\*ks
    """
    return sorted([os.path.basename(ks)[:-3] for ks in glob(joinpaths(share_dir, "composer/*.ks"))])

def compose_args(compose_type):
    """ Returns the settings to pass to novirt_install for the compose type

    :param compose_type: The type of compose to create, from `compose_types()`
    :type compose_type: str

    This will return a dict of options that match the ArgumentParser options for livemedia-creator.
    These are the ones the define the type of output, it's filename, etc.
    Other options will be filled in by `make_compose()`
    """
    _MAP = {"tar":              {"make_iso":                False,
                                 "make_disk":               False,
                                 "make_fsimage":            False,
                                 "make_appliance":          False,
                                 "make_ami":                False,
                                 "make_tar":                True,
                                 "make_pxe_live":           False,
                                 "make_ostree_live":        False,
                                 "ostree":                  False,
                                 "live_rootfs_keep_size":   False,
                                 "live_rootfs_size":        0,
                                 "qcow2":                   False,
                                 "qcow2_args":              [],
                                 "image_name":              default_image_name("xz", "root.tar"),
                                 "image_only":              True,
                                 "app_name":                None,
                                 "app_template":            None,
                                 "app_file":                None
                                },
            "live-iso":         {"make_iso":                True,
                                 "make_disk":               False,
                                 "make_fsimage":            False,
                                 "make_appliance":          False,
                                 "make_ami":                False,
                                 "make_tar":                False,
                                 "make_pxe_live":           False,
                                 "make_ostree_live":        False,
                                 "ostree":                  False,
                                 "live_rootfs_keep_size":   False,
                                 "live_rootfs_size":        0,
                                 "qcow2":                   False,
                                 "qcow2_args":              [],
                                 "image_name":              "live.iso",
                                 "fs_label":                "Anaconda",     # Live booting may expect this to be 'Anaconda'
                                 "image_only":              False,
                                 "app_name":                None,
                                 "app_template":            None,
                                 "app_file":                None
                                },
            "partitioned-disk": {"make_iso":                False,
                                 "make_disk":               True,
                                 "make_fsimage":            False,
                                 "make_appliance":          False,
                                 "make_ami":                False,
                                 "make_tar":                False,
                                 "make_pxe_live":           False,
                                 "make_ostree_live":        False,
                                  "ostree":                  False,
                                 "live_rootfs_keep_size":   False,
                                 "live_rootfs_size":        0,
                                 "qcow2":                   False,
                                 "qcow2_args":              [],
                                 "image_name":              "disk.img",
                                 "fs_label":                "",
                                 "image_only":              True,
                                 "app_name":                None,
                                 "app_template":            None,
                                 "app_file":                None
                                },
            "qcow2":            {"make_iso":                False,
                                 "make_disk":               True,
                                 "make_fsimage":            False,
                                 "make_appliance":          False,
                                 "make_ami":                False,
                                 "make_tar":                False,
                                 "make_pxe_live":           False,
                                 "make_ostree_live":        False,
                                  "ostree":                  False,
                                 "live_rootfs_keep_size":   False,
                                 "live_rootfs_size":        0,
                                 "qcow2":                   True,
                                 "qcow2_args":              [],
                                 "image_name":              "disk.qcow2",
                                 "fs_label":                "",
                                 "image_only":              True,
                                 "app_name":                None,
                                 "app_template":            None,
                                 "app_file":                None
                                },
            "ext4-filesystem":  {"make_iso":                False,
                                 "make_disk":               False,
                                 "make_fsimage":            True,
                                 "make_appliance":          False,
                                 "make_ami":                False,
                                 "make_tar":                False,
                                 "make_pxe_live":           False,
                                 "make_ostree_live":        False,
                                 "ostree":                  False,
                                 "live_rootfs_keep_size":   False,
                                 "live_rootfs_size":        0,
                                 "qcow2":                   False,
                                 "qcow2_args":              [],
                                 "image_name":              "filesystem.img",
                                 "fs_label":                "",
                                 "image_only":              True,
                                 "app_name":                None,
                                 "app_template":            None,
                                 "app_file":                None
                                },
            }
    return _MAP[compose_type]

def move_compose_results(cfg, results_dir):
    """Move the final image to the results_dir and cleanup the unneeded compose files

    :param cfg: Build configuration
    :type cfg: DataHolder
    :param results_dir: Directory to put the results into
    :type results_dir: str
    """
    if cfg["make_tar"]:
        shutil.move(joinpaths(cfg["result_dir"], cfg["image_name"]), results_dir)
    elif cfg["make_iso"]:
        # Output from live iso is always a boot.iso under images/, move and rename it
        shutil.move(joinpaths(cfg["result_dir"], "images/boot.iso"), joinpaths(results_dir, cfg["image_name"]))
    elif cfg["make_disk"] or cfg["make_fsimage"]:
        shutil.move(joinpaths(cfg["result_dir"], cfg["image_name"]), joinpaths(results_dir, cfg["image_name"]))


    # Cleanup the compose directory, but only if it looks like a compose directory
    if os.path.basename(cfg["result_dir"]) == "compose":
        shutil.rmtree(cfg["result_dir"])
    else:
        log.error("Incorrect compose directory, not cleaning up")
