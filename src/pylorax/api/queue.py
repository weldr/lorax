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
""" Functions to monitor compose queue and run anaconda"""
import logging
log = logging.getLogger("pylorax")

import os
import grp
from glob import glob
import pytoml as toml
import pwd
import shutil
import subprocess
from subprocess import Popen, PIPE
import time
from pykickstart.version import makeVersion, RHEL7
from pykickstart.parser import KickstartParser

from pylorax.api.recipes import recipe_from_file
from pylorax.base import DataHolder
from pylorax.installer import novirt_install
from pylorax.sysutils import joinpaths

# TODO needs a quit queue to cleanly manage quitting
def monitor(cfg, cancel_q):
    """ Monitor the queue for new compose requests

    The queue has 2 subdirectories, new and run. When a compose is ready to be run
    a symlink to the uniquely named results directory should be placed in ./queue/new/

    When the it is ready to be run (it is checked every 30 seconds or after a previous
    compose is finished) the symlink will be moved into ./queue/run/ and a STATUS file
    will be created in the results directory.

    STATUS can contain one of: RUNNING, FINISHED, FAILED

    If the system is restarted while a compose is running it will move any old symlinks
    from ./queue/run/ to ./queue/new/ and rerun them.
    """
    def queue_sort(job):
        """Sort the queue entries by their mtime, not their names"""
        return os.stat(joinpaths(cfg.composer_dir, "queue/new", job)).st_mtime

    # Move any symlinks in the run queue back to the new queue
    for link in os.listdir(joinpaths(cfg.composer_dir, "queue/run")):
        src = joinpaths(cfg.composer_dir, "queue/run", link)
        dst = joinpaths(cfg.composer_dir, "queue/new", link)
        os.rename(src, dst)
        log.debug("Moved unfinished compose %s back to new state", src)

    while True:
        jobs = sorted(os.listdir(joinpaths(cfg.composer_dir, "queue/new")), key=queue_sort)

        # Pick the oldest and move it into ./run/
        if not jobs:
            # No composes left to process, sleep for a bit
            time.sleep(30)
        else:
            src = joinpaths(cfg.composer_dir, "queue/new", jobs[0])
            dst = joinpaths(cfg.composer_dir, "queue/run", jobs[0])
            os.rename(src, dst)
            log.info("Starting new compose: %s", dst)
            open(joinpaths(dst, "STATUS"), "w").write("RUNNING\n")

            try:
                make_compose(cfg, os.path.realpath(dst))
                log.info("Finished building %s, results are in %s", dst, os.path.realpath(dst))
                open(joinpaths(dst, "STATUS"), "w").write("FINISHED\n")
            except Exception as e:
                log.error("Error running compose: %s", e)
                open(joinpaths(dst, "STATUS"), "w").write("FAILED\n")
            os.unlink(dst)

def make_compose(cfg, results_dir):
    """Run anaconda with the final-kickstart.ks from results_dir"""

    # Check on the ks's presense
    ks_path = joinpaths(results_dir, "final-kickstart.ks")
    if not os.path.exists(ks_path):
        raise RuntimeError("Missing kickstart file at %s" % ks_path)

    # The anaconda logs are copied into ./anaconda/ in this directory
    log_dir = joinpaths(results_dir, "logs/")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    ks_version = makeVersion(RHEL7)
    ks = KickstartParser(ks_version, errorsAreFatal=False, missingIncludeIsFatal=False)
    ks.readKickstart(ks_path)
    repo_url = ks.handler.method.url

    # Load the compose configuration
    cfg_path = joinpaths(results_dir, "config.toml")
    if not os.path.exists(cfg_path):
        raise RuntimeError("Missing config.toml for %s" % results_dir)
    cfg_dict = toml.loads(open(cfg_path, "r").read())

    install_cfg = DataHolder(**cfg_dict)

    # Some kludges for the 99-copy-logs %post, failure in it will crash the build
    for f in ["/tmp/NOSAVE_INPUT_KS", "/tmp/NOSAVE_LOGS"]:
        open(f, "w")

    log.debug("repo_url = %s, cfg  = %s", repo_url, install_cfg)
    novirt_install(install_cfg, joinpaths(results_dir, install_cfg.image_name), None, repo_url)

    # Make sure that everything under the results directory is owned by the user
    user = pwd.getpwuid(cfg.uid).pw_name
    group = grp.getgrgid(cfg.gid).gr_name
    log.debug("Install finished, chowning results to %s:%s", user, group)
    subprocess.call(["chown", "-R", "%s:%s" % (user, group), results_dir])

def get_compose_type(results_dir):
    """ Return the type of composition.

    """
    # Should only be 2 kickstarts, the final-kickstart.ks and the template
    t = [os.path.basename(ks)[:-3] for ks in glob(joinpaths(results_dir, "*.ks"))
                                   if "final-kickstart" not in ks]
    if len(t) != 1:
        raise RuntimeError("Cannot find ks template for build %s" % os.path.basename(results_dir))
    return t[0]

def compose_detail(results_dir):
    """ Return details about the build."""

    # Just in case it went away
    if not os.path.exists(results_dir):
        return {}

    build_id = os.path.basename(os.path.abspath(results_dir))
    status = open(joinpaths(results_dir, "STATUS")).read().strip()
    mtime = os.stat(joinpaths(results_dir, "STATUS")).st_mtime
    recipe = recipe_from_file(joinpaths(results_dir, "recipe.toml"))

    compose_type = get_compose_type(results_dir)

    return {"id":           build_id,
            "queue_status": status,
            "timestamp":    mtime,
            "compose_type": compose_type,
            "recipe":       recipe["name"],
            "version":      recipe["version"]
            }

def queue_status(cfg):
    """ Return details about what is in the queue."""
    queue_dir = joinpaths(cfg.get("composer", "lib_dir"), "queue")
    new_queue = [os.path.realpath(p) for p in glob(joinpaths(queue_dir, "new/*"))]
    run_queue = [os.path.realpath(p) for p in glob(joinpaths(queue_dir, "run/*"))]

    return {
        "new":  [compose_detail(n) for n in new_queue],
        "run":  [compose_detail(r) for r in run_queue]
    }

def uuid_status(cfg, uuid):
    """Return the details of a specific UUID compose

    :param cfg: Configuration settings
    :type cfg: ComposerConfig
    :param uuid: The UUID of the build
    :type uuid: str
    :returns: Details about the build
    :rtype: dict or None
    """
    uuid_dir = joinpaths(cfg.get("composer", "lib_dir"), "results", uuid)
    if os.path.exists(uuid_dir):
        return compose_detail(uuid_dir)
    else:
        return None

def build_status(cfg, status_filter=None):
    """ Return the details of finished or failed builds

    :param cfg: Configuration settings
    :type cfg: ComposerConfig
    :param status_filter: What builds to return. None == all, "FINISHED", or "FAILED"
    :type status_filter: str
    :returns: A list of the build details (from compose_details)
    :rtype: list of dicts

    This returns a list of build details for each of the matching builds on the
    system. It does not return the status of builds that have not been finished.
    Use queue_status() for those.
    """
    if status_filter:
        status_filter = [status_filter]
    else:
        status_filter = ["FINISHED", "FAILED"]

    results = []
    result_dir = joinpaths(cfg.get("composer", "lib_dir"), "results")
    for build in glob(result_dir + "/*"):
        log.debug("Checking status of build %s", build)

        status = open(joinpaths(build, "STATUS"), "r").read().strip()
        if status in status_filter:
            results.append(compose_detail(build))
    return results

def uuid_delete(cfg, uuid):
    """Delete all of the results from a compose

    :param cfg: Configuration settings
    :type cfg: ComposerConfig
    :param uuid: The UUID of the build
    :type uuid: str
    :returns: True if it was deleted
    :rtype: bool
    """
    uuid_dir = joinpaths(cfg.get("composer", "lib_dir"), "results", uuid)
    if not uuid_dir or len(uuid_dir) < 10:
        raise RuntimeError("Directory length is too short: %s" % uuid_dir)
    shutil.rmtree(uuid_dir)
    return True

def uuid_info(cfg, uuid):
    """Return information about the composition

    :param cfg: Configuration settings
    :type cfg: ComposerConfig
    :param uuid: The UUID of the build
    :type uuid: str
    :returns: dictionary of information about the composition
    :rtype: dict

    This will return a dict with the following fields populated:

    * id - The uuid of the comoposition
    * config - containing the configuration settings used to run Anaconda
    * recipe - The depsolved recipe used to generate the kickstart
    * commit - The (local) git commit hash for the recipe used
    * deps - The NEVRA of all of the dependencies used in the composition
    * compose_type - The type of output generated (tar, iso, etc.)
    * queue_status - The final status of the composition (FINISHED or FAILED)
    """
    uuid_dir = joinpaths(cfg.get("composer", "lib_dir"), "results", uuid)
    if not os.path.exists(uuid_dir):
        raise RuntimeError("%s is not a valid build_id" % uuid)

    # Load the compose configuration
    cfg_path = joinpaths(uuid_dir, "config.toml")
    if not os.path.exists(cfg_path):
        raise RuntimeError("Missing config.toml for %s" % uuid)
    cfg_dict = toml.loads(open(cfg_path, "r").read())

    frozen_path = joinpaths(uuid_dir, "frozen.toml")
    if not os.path.exists(frozen_path):
        raise RuntimeError("Missing frozen.toml for %s" % uuid)
    frozen_dict = toml.loads(open(frozen_path, "r").read())

    deps_path = joinpaths(uuid_dir, "deps.toml")
    if not os.path.exists(deps_path):
        raise RuntimeError("Missing deps.toml for %s" % uuid)
    deps_dict = toml.loads(open(deps_path, "r").read())

    compose_type = get_compose_type(uuid_dir)
    status = open(joinpaths(uuid_dir, "STATUS")).read().strip()

    commit_path = joinpaths(uuid_dir, "COMMIT")
    commit_id = open(commit_path, "r").read().strip()

    return {"id":           uuid,
            "config":       cfg_dict,
            "recipe":       frozen_dict,
            "commit":       commit_id,
            "deps":         deps_dict,
            "compose_type": compose_type,
            "queue_status": status
    }

def uuid_tar(cfg, uuid, metadata=False, image=False, logs=False):
    """Return a tar of the build data

    :param cfg: Configuration settings
    :type cfg: ComposerConfig
    :param uuid: The UUID of the build
    :type uuid: str
    :param metadata: Set to true to include all the metadata needed to reproduce the build
    :type metadata: bool
    :param image: Set to true to include the output image
    :type image: bool
    :param logs: Set to true to include the logs from the build
    :type logs: bool
    :returns: A stream of bytes from tar
    :rtype: A generator

    This yields an uncompressed tar's data to the caller. It includes
    the selected data to the caller by returning the Popen stdout from the tar process.
    """
    uuid_dir = joinpaths(cfg.get("composer", "lib_dir"), "results", uuid)
    if not os.path.exists(uuid_dir):
        raise RuntimeError("%s is not a valid build_id" % uuid)

    # Load the compose configuration
    cfg_path = joinpaths(uuid_dir, "config.toml")
    if not os.path.exists(cfg_path):
        raise RuntimeError("Missing config.toml for %s" % uuid)
    cfg_dict = toml.loads(open(cfg_path, "r").read())
    image_name = cfg_dict["image_name"]

    def include_file(f):
        if f.endswith("/logs"):
            return logs
        if f.endswith(image_name):
            return image
        return metadata
    filenames = [os.path.basename(f) for f in glob(joinpaths(uuid_dir, "*")) if include_file(f)]

    tar = Popen(["tar", "-C", uuid_dir, "-cf-"] + filenames, stdout=PIPE)
    return tar.stdout

def uuid_image(cfg, uuid):
    """Return the filename and full path of the build's image file

    :param cfg: Configuration settings
    :type cfg: ComposerConfig
    :param uuid: The UUID of the build
    :type uuid: str
    :returns: The image filename and full path
    :rtype: tuple of strings
    """
    uuid_dir = joinpaths(cfg.get("composer", "lib_dir"), "results", uuid)
    if not os.path.exists(uuid_dir):
        raise RuntimeError("%s is not a valid build_id" % uuid)

    # Load the compose configuration
    cfg_path = joinpaths(uuid_dir, "config.toml")
    if not os.path.exists(cfg_path):
        raise RuntimeError("Missing config.toml for %s" % uuid)
    cfg_dict = toml.loads(open(cfg_path, "r").read())
    image_name = cfg_dict["image_name"]

    return (image_name, joinpaths(uuid_dir, image_name))
