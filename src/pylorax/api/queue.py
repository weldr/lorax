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
import multiprocessing as mp
import pytoml as toml
import pwd
import shutil
import subprocess
from subprocess import Popen, PIPE
import time

from pylorax.api.compose import move_compose_results
from pylorax.api.recipes import recipe_from_file
from pylorax.base import DataHolder
from pylorax.creator import run_creator
from pylorax.sysutils import joinpaths

def start_queue_monitor(cfg, uid, gid):
    """Start the queue monitor as a mp process

    :param cfg: Configuration settings
    :type cfg: ComposerConfig
    :param uid: User ID that owns the queue
    :type uid: int
    :param gid: Group ID that owns the queue
    :type gid: int
    :returns: None
    """
    lib_dir = cfg.get("composer", "lib_dir")
    share_dir = cfg.get("composer", "share_dir")
    monitor_cfg = DataHolder(composer_dir=lib_dir, share_dir=share_dir, uid=uid, gid=gid)
    p = mp.Process(target=monitor, args=(monitor_cfg,))
    p.daemon = True
    p.start()

def monitor(cfg):
    """Monitor the queue for new compose requests

    :param cfg: Configuration settings
    :type cfg: DataHolder
    :returns: Does not return

    The queue has 2 subdirectories, new and run. When a compose is ready to be run
    a symlink to the uniquely named results directory should be placed in ./queue/new/

    When the it is ready to be run (it is checked every 30 seconds or after a previous
    compose is finished) the symlink will be moved into ./queue/run/ and a STATUS file
    will be created in the results directory.

    STATUS can contain one of: RUNNING, FINISHED, FAILED

    If the system is restarted while a compose is running it will move any old symlinks
    from ./queue/run/ to ./queue/new/ and rerun them.
    """
    def queue_sort(uuid):
        """Sort the queue entries by their mtime, not their names"""
        return os.stat(joinpaths(cfg.composer_dir, "queue/new", uuid)).st_mtime

    # Move any symlinks in the run queue back to the new queue
    for link in os.listdir(joinpaths(cfg.composer_dir, "queue/run")):
        src = joinpaths(cfg.composer_dir, "queue/run", link)
        dst = joinpaths(cfg.composer_dir, "queue/new", link)
        os.rename(src, dst)
        log.debug("Moved unfinished compose %s back to new state", src)

    while True:
        uuids = sorted(os.listdir(joinpaths(cfg.composer_dir, "queue/new")), key=queue_sort)

        # Pick the oldest and move it into ./run/
        if not uuids:
            # No composes left to process, sleep for a bit
            time.sleep(30)
        else:
            src = joinpaths(cfg.composer_dir, "queue/new", uuids[0])
            dst = joinpaths(cfg.composer_dir, "queue/run", uuids[0])
            try:
                os.rename(src, dst)
            except OSError:
                # The symlink may vanish if uuid_cancel() has been called
                continue

            log.info("Starting new compose: %s", dst)
            open(joinpaths(dst, "STATUS"), "w").write("RUNNING\n")

            try:
                make_compose(cfg, os.path.realpath(dst))
                log.info("Finished building %s, results are in %s", dst, os.path.realpath(dst))
                open(joinpaths(dst, "STATUS"), "w").write("FINISHED\n")
            except Exception:
                import traceback
                log.error("traceback: %s", traceback.format_exc())

# TODO - Write the error message to an ERROR-LOG file to include with the status
#                log.error("Error running compose: %s", e)
                open(joinpaths(dst, "STATUS"), "w").write("FAILED\n")

            os.unlink(dst)

def make_compose(cfg, results_dir):
    """Run anaconda with the final-kickstart.ks from results_dir

    :param cfg: Configuration settings
    :type cfg: DataHolder
    :param results_dir: The directory containing the metadata and results for the build
    :type results_dir: str
    :returns: Nothing
    :raises: May raise various exceptions

    This takes the final-kickstart.ks, and the settings in config.toml and runs Anaconda
    in no-virt mode (directly on the host operating system). Exceptions should be caught
    at the higer level.

    If there is a failure, the build artifacts will be cleaned up, and any logs will be
    moved into logs/anaconda/ and their ownership will be set to the user from the cfg
    object.
    """

    # Check on the ks's presence
    ks_path = joinpaths(results_dir, "final-kickstart.ks")
    if not os.path.exists(ks_path):
        raise RuntimeError("Missing kickstart file at %s" % ks_path)

    # The anaconda logs are copied into ./anaconda/ in this directory
    log_dir = joinpaths(results_dir, "logs/")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Load the compose configuration
    cfg_path = joinpaths(results_dir, "config.toml")
    if not os.path.exists(cfg_path):
        raise RuntimeError("Missing config.toml for %s" % results_dir)
    cfg_dict = toml.loads(open(cfg_path, "r").read())

    # The keys in cfg_dict correspond to the arguments setup in livemedia-creator
    # keys that define what to build should be setup in compose_args, and keys with
    # defaults should be setup here.

    # Make sure that image_name contains no path components
    cfg_dict["image_name"] = os.path.basename(cfg_dict["image_name"])

    # Only support novirt installation, set some other defaults
    cfg_dict["no_virt"] = True
    cfg_dict["disk_image"] = None
    cfg_dict["fs_image"] = None
    cfg_dict["keep_image"] = False
    cfg_dict["domacboot"] = False
    cfg_dict["anaconda_args"] = ""
    cfg_dict["proxy"] = ""
    cfg_dict["armplatform"] = ""
    cfg_dict["squashfs_args"] = None

    cfg_dict["lorax_templates"] = cfg.share_dir
    cfg_dict["tmp"] = "/var/tmp/"
    cfg_dict["dracut_args"] = None                  # Use default args for dracut

    # Compose things in a temporary directory inside the results directory
    cfg_dict["result_dir"] = joinpaths(results_dir, "compose")
    os.makedirs(cfg_dict["result_dir"])

    install_cfg = DataHolder(**cfg_dict)

    # Some kludges for the 99-copy-logs %post, failure in it will crash the build
    for f in ["/tmp/NOSAVE_INPUT_KS", "/tmp/NOSAVE_LOGS"]:
        open(f, "w")

    # Placing a CANCEL file in the results directory will make execWithRedirect send anaconda a SIGTERM
    def cancel_build():
        return os.path.exists(joinpaths(results_dir, "CANCEL"))

    log.debug("cfg  = %s", install_cfg)
    try:
        test_path = joinpaths(results_dir, "TEST")
        if os.path.exists(test_path):
            # Pretend to run the compose
            time.sleep(10)
            try:
                test_mode = int(open(test_path, "r").read())
            except Exception:
                test_mode = 1
            if test_mode == 1:
                raise RuntimeError("TESTING FAILED compose")
            else:
                open(joinpaths(results_dir, install_cfg.image_name), "w").write("TEST IMAGE")
        else:
            run_creator(install_cfg, callback_func=cancel_build)

            # Extract the results of the compose into results_dir and cleanup the compose directory
            move_compose_results(install_cfg, results_dir)
    finally:
        # Make sure that everything under the results directory is owned by the user
        user = pwd.getpwuid(cfg.uid).pw_name
        group = grp.getgrgid(cfg.gid).gr_name
        log.debug("Install finished, chowning results to %s:%s", user, group)
        subprocess.call(["chown", "-R", "%s:%s" % (user, group), results_dir])

def get_compose_type(results_dir):
    """Return the type of composition.

    :param results_dir: The directory containing the metadata and results for the build
    :type results_dir: str
    :returns: The type of compose (eg. 'tar')
    :rtype: str
    :raises: RuntimeError if no kickstart template can be found.
    """
    # Should only be 2 kickstarts, the final-kickstart.ks and the template
    t = [os.path.basename(ks)[:-3] for ks in glob(joinpaths(results_dir, "*.ks"))
                                   if "final-kickstart" not in ks]
    if len(t) != 1:
        raise RuntimeError("Cannot find ks template for build %s" % os.path.basename(results_dir))
    return t[0]

def compose_detail(results_dir):
    """Return details about the build.

    :param results_dir: The directory containing the metadata and results for the build
    :type results_dir: str
    :returns: A dictionary with details about the compose
    :rtype: dict
    :raises: IOError if it cannot read the directory, STATUS, or recipe file.

    The following details are included in the dict:

    * id - The uuid of the comoposition
    * queue_status - The final status of the composition (FINISHED or FAILED)
    * timestamp - The time of the last status change
    * compose_type - The type of output generated (tar, iso, etc.)
    * recipe - Recipe name
    * version - Recipe version
    """
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
    """Return details about what is in the queue.

    :param cfg: Configuration settings
    :type cfg: ComposerConfig
    :returns: A list of the new composes, and a list of the running composes
    :rtype: dict

    This returns a dict with 2 lists. "new" is the list of uuids that are waiting to be built,
    and "run" has the uuids that are being built (currently limited to 1 at a time).
    """
    queue_dir = joinpaths(cfg.get("composer", "lib_dir"), "queue")
    new_queue = [os.path.realpath(p) for p in glob(joinpaths(queue_dir, "new/*"))]
    run_queue = [os.path.realpath(p) for p in glob(joinpaths(queue_dir, "run/*"))]

    new_details = []
    for n in new_queue:
        try:
            d = compose_detail(n)
        except IOError:
            continue
        new_details.append(d)

    run_details = []
    for r in run_queue:
        try:
            d = compose_detail(r)
        except IOError:
            continue
        run_details.append(r)

    return {
        "new": new_details,
        "run": run_details
    }

def uuid_status(cfg, uuid):
    """Return the details of a specific UUID compose

    :param cfg: Configuration settings
    :type cfg: ComposerConfig
    :param uuid: The UUID of the build
    :type uuid: str
    :returns: Details about the build
    :rtype: dict or None

    Returns the same dict as `compose_details()`
    """
    uuid_dir = joinpaths(cfg.get("composer", "lib_dir"), "results", uuid)
    try:
        return compose_detail(uuid_dir)
    except IOError:
        return None

def build_status(cfg, status_filter=None):
    """Return the details of finished or failed builds

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

        try:
            status = open(joinpaths(build, "STATUS"), "r").read().strip()
            if status in status_filter:
                results.append(compose_detail(build))
        except IOError:
            pass
    return results

def uuid_cancel(cfg, uuid):
    """Cancel a build and delete its results

    :param cfg: Configuration settings
    :type cfg: ComposerConfig
    :param uuid: The UUID of the build
    :type uuid: str
    :returns: True if it was canceled and deleted
    :rtype: bool

    Only call this if the build status is WAITING or RUNNING
    """
    # This status can change (and probably will) while it is in the middle of doing this:
    # It can move from WAITING -> RUNNING or it can move from RUNNING -> FINISHED|FAILED

    # If it is in WAITING remove the symlink and then check to make sure it didn't show up
    # in RUNNING
    queue_dir = joinpaths(cfg.get("composer", "lib_dir"), "queue")
    uuid_new = joinpaths(queue_dir, "new", uuid)
    if os.path.exists(uuid_new):
        try:
            os.unlink(uuid_new)
        except OSError:
            # The symlink may vanish if the queue monitor started the build
            pass
        uuid_run = joinpaths(queue_dir, "run", uuid)
        if not os.path.exists(uuid_run):
            # Successfully removed it before the build started
            return uuid_delete(cfg, uuid)

    # Tell the build to stop running
    cancel_path = joinpaths(cfg.get("composer", "lib_dir"), "results", uuid, "CANCEL")
    open(cancel_path, "w").write("\n")

    # Wait for status to move to FAILED
    started = time.time()
    while True:
        status = uuid_status(cfg, uuid)
        if status is None or status["queue_status"] == "FAILED":
            break

        # Is this taking too long? Exit anyway and try to cleanup.
        if time.time() > started + (10 * 60):
            log.error("Failed to cancel the build of %s", uuid)
            break

        time.sleep(5)

    # Remove the partial results
    uuid_delete(cfg, uuid)

def uuid_delete(cfg, uuid):
    """Delete all of the results from a compose

    :param cfg: Configuration settings
    :type cfg: ComposerConfig
    :param uuid: The UUID of the build
    :type uuid: str
    :returns: True if it was deleted
    :rtype: bool
    :raises: This will raise an error if the delete failed
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
    :raises: RuntimeError if there was a problem

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
    status_path = joinpaths(uuid_dir, "STATUS")
    if not os.path.exists(status_path):
        raise RuntimeError("Missing status for %s" % uuid)
    status = open(status_path).read().strip()

    commit_path = joinpaths(uuid_dir, "COMMIT")
    if not os.path.exists(commit_path):
        raise RuntimeError("Missing commit hash for %s" % uuid)
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
    :raises: RuntimeError if there was a problem (eg. missing config file)

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
    :raises: RuntimeError if there was a problem (eg. invalid uuid, missing config file)
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

def uuid_log(cfg, uuid, size=1024):
    """Return `size` kbytes from the end of the anaconda.log

    :param cfg: Configuration settings
    :type cfg: ComposerConfig
    :param uuid: The UUID of the build
    :type uuid: str
    :param size: Number of kbytes to read. Default is 1024
    :type size: int
    :returns: Up to `size` kbytes from the end of the log
    :rtype: str
    :raises: RuntimeError if there was a problem (eg. no log file available)

    This function tries to return lines from the end of the log, it will
    attempt to start on a line boundry, and may return less than `size` kbytes.
    """
    uuid_dir = joinpaths(cfg.get("composer", "lib_dir"), "results", uuid)
    if not os.path.exists(uuid_dir):
        raise RuntimeError("%s is not a valid build_id" % uuid)

    # While a build is running the logs will be in /tmp/anaconda.log and when it
    # has finished they will be in the results directory
    status = uuid_status(cfg, uuid)
    if status is None:
        raise RuntimeError("Status is missing for %s" % uuid)

    if status["queue_status"] == "RUNNING":
        log_path = "/tmp/anaconda.log"
    else:
        log_path = joinpaths(uuid_dir, "logs", "anaconda", "anaconda.log")
    if not os.path.exists(log_path):
        raise RuntimeError("No anaconda.log available.")

    with open(log_path, "r") as f:
        f.seek(0, 2)
        end = f.tell()
        if end < 1024 * size:
            f.seek(0, 0)
        else:
            f.seek(end - (1024 * size))
        # Find the start of the next line and return the rest
        f.readline()
        return f.read()
