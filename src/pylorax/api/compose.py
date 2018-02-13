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
import pytoml as toml
import shutil
from uuid import uuid4

from pylorax.api.projects import projects_depsolve, dep_nevra
from pylorax.api.projects import ProjectsError
from pylorax.api.recipes import read_recipe_and_id
from pylorax.imgutils import default_image_name
from pylorax.sysutils import joinpaths


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
    # TODO include the version/glob in the depsolving
    module_names = map(lambda m: m["name"], recipe["modules"] or [])
    package_names = map(lambda p: p["name"], recipe["packages"] or [])
    projects = sorted(set(module_names+package_names), key=lambda n: n.lower())
    deps = []
    try:
        with yumlock.lock:
            deps = projects_depsolve(yumlock.yb, projects)
    except ProjectsError as e:
        log.error("start_build depsolve: %s", str(e))
        raise RuntimeError("Problem depsolving %s: %s" % (recipe["name"], str(e)))

    # Create the results directory
    build_id = str(uuid4())
    results_dir = joinpaths(lib_dir, "results", build_id)
    os.makedirs(results_dir)

    # Write the recipe commit hash
    commit_path = joinpaths(results_dir, "COMMIT")
    with open(commit_path, "w") as f:
        f.write(commit_id)

    # Write the original recipe
    recipe_path = joinpaths(results_dir, "recipe.toml")
    with open(recipe_path, "w") as f:
        f.write(recipe.toml())

    # Write the frozen recipe
    frozen_recipe = recipe.freeze(deps)
    recipe_path = joinpaths(results_dir, "frozen.toml")
    with open(recipe_path, "w") as f:
        f.write(frozen_recipe.toml())

    # Read the kickstart template for this type and copy it into the results
    ks_template_path = joinpaths(share_dir, "composer", compose_type) + ".ks"
    shutil.copy(ks_template_path, results_dir)
    ks_template = open(ks_template_path, "r").read()

    # Write out the dependencies to the results dir
    deps_path = joinpaths(results_dir, "deps.toml")
    with open(deps_path, "w") as f:
        f.write(toml.dumps({"packages":deps}).encode("UTF-8"))

    # Create the final kickstart with repos and package list
    ks_path = joinpaths(results_dir, "final-kickstart.ks")
    with open(ks_path, "w") as f:
        with yumlock.lock:
            repos = yumlock.yb.repos.listEnabled()
        if not repos:
            raise RuntimeError("No enabled repos, canceling build.")

        ks_url = repo_to_ks(repos[0], "url")
        log.debug("url = %s", ks_url)
        f.write('url %s\n' % ks_url)
        for idx, r in enumerate(repos[1:]):
            ks_repo = repo_to_ks(r, "baseurl")
            log.debug("repo composer-%s = %s", idx, ks_repo)
            f.write('repo --name="composer-%s" %s\n' % (idx, ks_repo))

        f.write(ks_template)

        for d in deps:
            f.write(dep_nevra(d)+"\n")

        f.write("%end\n")

    # Setup the config to pass to novirt_install
    log_dir = joinpaths(results_dir, "logs/")
    cfg_args = compose_args(compose_type)
    cfg_args.update({
        "compression":      "xz",
        #"compress_args":    ["-9"],
        "compress_args":    [],
        "ks":               [ks_path],
        "anaconda_args":    "",
        "proxy":            "",
        "armplatform":      "",

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

    log.info("Adding %s with recipe %s output type %s to compose queue", build_id, recipe["name"], compose_type)
    os.symlink(results_dir, joinpaths(lib_dir, "queue/new/", build_id))

    return build_id

# Supported output types
def compose_types(share_dir):
    """ Returns a list of the supported output types

    The output types come from the kickstart names in /usr/share/lorax/composer/*ks
    """
    return [os.path.basename(ks)[:-3] for ks in glob(joinpaths(share_dir, "composer/*.ks"))]

def compose_args(compose_type):
    """ Returns the settings to pass to novirt_install for the compose type"""
    _MAP = {"tar": {"make_tar":     True,
                    "make_iso":     False,
                    "make_fsimage": False,
                    "qcow2":        False,
                    "image_name":   default_image_name("xz", "root.tar")},
                    }

    return _MAP[compose_type]
