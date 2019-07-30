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
program_log = logging.getLogger("program")
dnf_log = logging.getLogger("dnf")

import os
import grp
from glob import glob
import multiprocessing as mp
import pwd
import shutil
import subprocess
from subprocess import Popen, PIPE
import time

from pylorax import find_templates
from pylorax.api.compose import move_compose_results
from pylorax.api.recipes import recipe_from_file
from pylorax.api.timestamp import TS_CREATED, TS_STARTED, TS_FINISHED, write_timestamp, timestamp_dict
import pylorax.api.toml as toml
from pylorax.base import DataHolder
from pylorax.creator import run_creator
from pylorax.sysutils import joinpaths, read_tail

from lifted.queue import create_upload, get_uploads, ready_upload, delete_upload

def check_queues(cfg):
    """Check to make sure the new and run queue symlinks are correct

    :param cfg: Configuration settings
    :type cfg: DataHolder

    Also check all of the existing results and make sure any with WAITING
    set in STATUS have a symlink in queue/new/
    """
    # Remove broken symlinks from the new and run queues
    queue_symlinks = glob(joinpaths(cfg.composer_dir, "queue/new/*")) + \
                     glob(joinpaths(cfg.composer_dir, "queue/run/*"))
    for link in queue_symlinks:
        if not os.path.isdir(os.path.realpath(link)):
            log.info("Removing broken symlink %s", link)
            os.unlink(link)

    # Write FAILED to the STATUS of any run queue symlinks and remove them
    for link in glob(joinpaths(cfg.composer_dir, "queue/run/*")):
        log.info("Setting build %s to FAILED, and removing symlink from queue/run/", os.path.basename(link))
        open(joinpaths(link, "STATUS"), "w").write("FAILED\n")
        os.unlink(link)

    # Check results STATUS messages
    # - If STATUS is missing, set it to FAILED
    # - RUNNING should be changed to FAILED
    # - WAITING should have a symlink in the new queue
    for link in glob(joinpaths(cfg.composer_dir, "results/*")):
        if not os.path.exists(joinpaths(link, "STATUS")):
            open(joinpaths(link, "STATUS"), "w").write("FAILED\n")
            continue

        status = open(joinpaths(link, "STATUS")).read().strip()
        if status == "RUNNING":
            log.info("Setting build %s to FAILED", os.path.basename(link))
            open(joinpaths(link, "STATUS"), "w").write("FAILED\n")
        elif status == "WAITING":
            if not os.path.islink(joinpaths(cfg.composer_dir, "queue/new/", os.path.basename(link))):
                log.info("Creating missing symlink to new build %s", os.path.basename(link))
                os.symlink(link, joinpaths(cfg.composer_dir, "queue/new/", os.path.basename(link)))

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
    tmp = cfg.get("composer", "tmp")
    monitor_cfg = DataHolder(cfg=cfg, composer_dir=lib_dir, share_dir=share_dir, uid=uid, gid=gid, tmp=tmp)
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

    STATUS can contain one of: WAITING, RUNNING, FINISHED, FAILED

    If the system is restarted while a compose is running it will move any old symlinks
    from ./queue/run/ to ./queue/new/ and rerun them.
    """
    def queue_sort(uuid):
        """Sort the queue entries by their mtime, not their names"""
        return os.stat(joinpaths(cfg.composer_dir, "queue/new", uuid)).st_mtime

    check_queues(cfg)
    while True:
        uuids = sorted(os.listdir(joinpaths(cfg.composer_dir, "queue/new")), key=queue_sort)

        # Pick the oldest and move it into ./run/
        if not uuids:
            # No composes left to process, sleep for a bit
            time.sleep(5)
        else:
            src = joinpaths(cfg.composer_dir, "queue/new", uuids[0])
            dst = joinpaths(cfg.composer_dir, "queue/run", uuids[0])
            try:
                os.rename(src, dst)
            except OSError:
                # The symlink may vanish if uuid_cancel() has been called
                continue

            # The anaconda logs are also copied into ./anaconda/ in this directory
            os.makedirs(joinpaths(dst, "logs"), exist_ok=True)

            def open_handler(loggers, file_name):
                handler = logging.FileHandler(joinpaths(dst, "logs", file_name))
                handler.setLevel(logging.DEBUG)
                handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
                for logger in loggers:
                    logger.addHandler(handler)
                return (handler, loggers)

            loggers = (((log, program_log, dnf_log), "combined.log"),
                       ((log,), "composer.log"),
                       ((program_log,), "program.log"),
                       ((dnf_log,), "dnf.log"))
            handlers = [open_handler(loggers, file_name) for loggers, file_name in loggers]

            log.info("Starting new compose: %s", dst)
            open(joinpaths(dst, "STATUS"), "w").write("RUNNING\n")

            try:
                make_compose(cfg, os.path.realpath(dst))
                log.info("Finished building %s, results are in %s", dst, os.path.realpath(dst))
                open(joinpaths(dst, "STATUS"), "w").write("FINISHED\n")
                write_timestamp(dst, TS_FINISHED)

                upload_cfg = cfg.cfg["upload"]
                for upload in get_uploads(upload_cfg, uuid_get_uploads(cfg.cfg, uuids[0])):
                    log.info("Readying upload %s", upload.uuid)
                    uuid_ready_upload(cfg.cfg, uuids[0], upload.uuid)
            except Exception:
                import traceback
                log.error("traceback: %s", traceback.format_exc())

# TODO - Write the error message to an ERROR-LOG file to include with the status
#                log.error("Error running compose: %s", e)
                open(joinpaths(dst, "STATUS"), "w").write("FAILED\n")
                write_timestamp(dst, TS_FINISHED)
            finally:
                for handler, loggers in handlers:
                    for logger in loggers:
                        logger.removeHandler(handler)
                    handler.close()

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

    cfg_dict["lorax_templates"] = find_templates(cfg.share_dir)
    cfg_dict["tmp"] = cfg.tmp
    cfg_dict["dracut_args"] = None                  # Use default args for dracut

    # TODO How to support other arches?
    cfg_dict["arch"] = None

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
        write_timestamp(results_dir, TS_STARTED)
        if os.path.exists(test_path):
            # Pretend to run the compose
            time.sleep(5)
            try:
                test_mode = int(open(test_path, "r").read())
            except Exception:
                test_mode = 1
            if test_mode == 1:
                raise RuntimeError("TESTING FAILED compose")
            else:
                open(joinpaths(results_dir, install_cfg.image_name), "w").write("TEST IMAGE")
        else:
            run_creator(install_cfg, cancel_func=cancel_build)

            # Extract the results of the compose into results_dir and cleanup the compose directory
            move_compose_results(install_cfg, results_dir)
    finally:
        # Make sure any remaining temporary directories are removed (eg. if there was an exception)
        for d in glob(joinpaths(cfg.tmp, "lmc-*")):
            if os.path.isdir(d):
                shutil.rmtree(d)
            elif os.path.isfile(d):
                os.unlink(d)

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

def compose_detail(cfg, results_dir):
    """Return details about the build.

    :param results_dir: The directory containing the metadata and results for the build
    :type results_dir: str
    :returns: A dictionary with details about the compose
    :rtype: dict
    :raises: IOError if it cannot read the directory, STATUS, or blueprint file.

    The following details are included in the dict:

    * id - The uuid of the comoposition
    * queue_status - The final status of the composition (FINISHED or FAILED)
    * compose_type - The type of output generated (tar, iso, etc.)
    * blueprint - Blueprint name
    * version - Blueprint version
    * image_size - Size of the image, if finished. 0 otherwise.

    Various timestamps are also included in the dict.  These are all Unix UTC timestamps.
    It is possible for these timestamps to not always exist, in which case they will be
    None in Python (or null in JSON).  The following timestamps are included:

    * job_created - When the user submitted the compose
    * job_started - Anaconda started running
    * job_finished - Job entered FINISHED or FAILED state
    """
    build_id = os.path.basename(os.path.abspath(results_dir))
    status = open(joinpaths(results_dir, "STATUS")).read().strip()
    blueprint = recipe_from_file(joinpaths(results_dir, "blueprint.toml"))

    compose_type = get_compose_type(results_dir)

    image_path = get_image_name(results_dir)[1]
    if status == "FINISHED" and os.path.exists(image_path):
        image_size = os.stat(image_path).st_size
    else:
        image_size = 0

    times = timestamp_dict(results_dir)

    upload_uuids = uuid_get_uploads(cfg, build_id)
    summaries = [upload.summary() for upload in get_uploads(cfg["upload"], upload_uuids)]

    return {"id":           build_id,
            "queue_status": status,
            "job_created":  times.get(TS_CREATED),
            "job_started":  times.get(TS_STARTED),
            "job_finished": times.get(TS_FINISHED),
            "compose_type": compose_type,
            "blueprint":    blueprint["name"],
            "version":      blueprint["version"],
            "image_size":   image_size,
            "uploads":      summaries,
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
            d = compose_detail(cfg, n)
        except IOError:
            continue
        new_details.append(d)

    run_details = []
    for r in run_queue:
        try:
            d = compose_detail(cfg, r)
        except IOError:
            continue
        run_details.append(d)

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
        return compose_detail(cfg, uuid_dir)
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
                results.append(compose_detail(cfg, build))
        except IOError:
            pass
    return results

def _upload_list_path(cfg, uuid):
    results_dir = joinpaths(cfg.get("composer", "lib_dir"), "results", uuid)
    if not os.path.isdir(results_dir):
        raise RuntimeError(f'"{uuid}" is not a valid build uuid!')
    return joinpaths(results_dir, "UPLOADS")

def get_type_provider(compose_type):
    return {
        "qcow2": "openstack",
        "vhd": "azure",
        "vmdk": "vsphere",
    }[compose_type]

def uuid_schedule_upload(cfg, uuid, image_name, settings):
    status = uuid_status(cfg, uuid)
    if status is None:
        raise RuntimeError(f'"{uuid}" is not a valid build uuid!')
    provider_name = get_type_provider(status["compose_type"])

    upload = create_upload(cfg["upload"], provider_name, image_name, settings)
    uuid_add_upload(cfg, uuid, upload.uuid)
    return upload.uuid

def uuid_get_uploads(cfg, uuid):
    try:
        with open(_upload_list_path(cfg, uuid)) as uploads_file:
            return frozenset(uploads_file.read().split())
    except FileNotFoundError:
        return frozenset()

def uuid_add_upload(cfg, uuid, upload_uuid):
    if upload_uuid not in uuid_get_uploads(cfg, uuid):
        with open(_upload_list_path(cfg, uuid), "a") as uploads_file:
            print(upload_uuid, file=uploads_file)
        status = uuid_status(cfg, uuid)
        if status and status["queue_status"] == "FINISHED":
            uuid_ready_upload(cfg, uuid, upload_uuid)

def uuid_remove_upload(cfg, uuid, upload_uuid):
    uploads = uuid_get_uploads(cfg, uuid) - frozenset((upload_uuid,))
    with open(_upload_list_path(cfg, uuid), "w") as uploads_file:
        for upload in uploads:
            print(upload, file=uploads_file)

def uuid_ready_upload(cfg, uuid, upload_uuid):
    status = uuid_status(cfg, uuid)
    if not status:
        raise RuntimeError(f"{uuid} is not a valid build id!")
    if status["queue_status"] != "FINISHED":
        raise RuntimeError(f"Build {uuid} is not finished!")
    _, image_path = uuid_image(cfg, uuid)
    ready_upload(cfg["upload"], upload_uuid, image_path)

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
    cancel_path = joinpaths(cfg.get("composer", "lib_dir"), "results", uuid, "CANCEL")
    if os.path.exists(cancel_path):
        log.info("Cancel has already been requested for %s", uuid)
        return False

    # This status can change (and probably will) while it is in the middle of doing this:
    # It can move from WAITING -> RUNNING or it can move from RUNNING -> FINISHED|FAILED

    # If it is in WAITING remove the symlink and then check to make sure it didn't show up
    # in the run queue
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
            # Make sure the build is still in the waiting state
            status = uuid_status(cfg, uuid)
            if status is None or status["queue_status"] == "WAITING":
                # Successfully removed it before the build started
                return uuid_delete(cfg, uuid)

    # At this point the build has probably started. Write to the CANCEL file.
    open(cancel_path, "w").write("\n")

    # Wait for status to move to FAILED or FINISHED
    started = time.time()
    while True:
        status = uuid_status(cfg, uuid)
        if status is None or status["queue_status"] == "FAILED":
            break
        elif status is not None and status["queue_status"] == "FINISHED":
            # The build finished successfully, no point in deleting it now
            return False

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

    for upload in get_uploads(cfg["upload"], uuid_get_uploads(cfg, uuid)):
        delete_upload(cfg["upload"], upload.uuid)

    shutil.rmtree(uuid_dir)
    return True

def uuid_info(cfg, uuid):
    """Return information about the composition

    :param cfg: Configuration settings
    :type cfg: ComposerConfig
    :param uuid: The UUID of the build
    :type uuid: str
    :returns: dictionary of information about the composition or None
    :rtype: dict
    :raises: RuntimeError if there was a problem

    This will return a dict with the following fields populated:

    * id - The uuid of the comoposition
    * config - containing the configuration settings used to run Anaconda
    * blueprint - The depsolved blueprint used to generate the kickstart
    * commit - The (local) git commit hash for the blueprint used
    * deps - The NEVRA of all of the dependencies used in the composition
    * compose_type - The type of output generated (tar, iso, etc.)
    * queue_status - The final status of the composition (FINISHED or FAILED)
    """
    uuid_dir = joinpaths(cfg.get("composer", "lib_dir"), "results", uuid)
    if not os.path.exists(uuid_dir):
        return None

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

    details = compose_detail(cfg, uuid_dir)

    commit_path = joinpaths(uuid_dir, "COMMIT")
    if not os.path.exists(commit_path):
        raise RuntimeError("Missing commit hash for %s" % uuid)
    commit_id = open(commit_path, "r").read().strip()

    upload_uuids = uuid_get_uploads(cfg, uuid)
    summaries = [upload.summary() for upload in get_uploads(cfg["upload"], upload_uuids)]

    return {"id":           uuid,
            "config":       cfg_dict,
            "blueprint":    frozen_dict,
            "commit":       commit_id,
            "deps":         deps_dict,
            "compose_type": details["compose_type"],
            "queue_status": details["queue_status"],
            "image_size":   details["image_size"],
            "uploads":      summaries,
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
    return get_image_name(uuid_dir)

def get_image_name(uuid_dir):
    """Return the filename and full path of the build's image file

    :param uuid: The UUID of the build
    :type uuid: str
    :returns: The image filename and full path
    :rtype: tuple of strings
    :raises: RuntimeError if there was a problem (eg. invalid uuid, missing config file)
    """
    uuid = os.path.basename(os.path.abspath(uuid_dir))
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
    """Return `size` KiB from the end of the most currently relevant log for a
    given compose

    :param cfg: Configuration settings
    :type cfg: ComposerConfig
    :param uuid: The UUID of the build
    :type uuid: str
    :param size: Number of KiB to read. Default is 1024
    :type size: int
    :returns: Up to `size` KiB from the end of the log
    :rtype: str
    :raises: RuntimeError if there was a problem (eg. no log file available)

    This function will return the end of either the anaconda log, the packaging
    log, or the combined composer logs, depending on the progress of the
    compose. It tries to return lines from the end of the log, it will attempt
    to start on a line boundary, and it may return less than `size` kbytes.
    """
    uuid_dir = joinpaths(cfg.get("composer", "lib_dir"), "results", uuid)
    if not os.path.exists(uuid_dir):
        raise RuntimeError("%s is not a valid build_id" % uuid)

    # While a build is running the logs will be in /tmp/anaconda.log and when it
    # has finished they will be in the results directory
    status = uuid_status(cfg, uuid)
    if status is None:
        raise RuntimeError("Status is missing for %s" % uuid)

    def get_log_path():
        # Try to return the most relevant log at any given time during the
        # compose. If the compose is not running, return the composer log.
        anaconda_log = "/tmp/anaconda.log"
        packaging_log = "/tmp/packaging.log"
        combined_log = joinpaths(uuid_dir, "logs", "combined.log")
        if status["queue_status"] != "RUNNING" or not os.path.isfile(anaconda_log):
            return combined_log
        if not os.path.isfile(packaging_log):
            return anaconda_log
        try:
            anaconda_mtime = os.stat(anaconda_log).st_mtime
            packaging_mtime = os.stat(packaging_log).st_mtime
            # If the packaging log exists and its last message is at least 15
            # seconds newer than the anaconda log, return the packaging log.
            if packaging_mtime > anaconda_mtime + 15:
                return packaging_log
            return anaconda_log
        except OSError:
            # Return the combined log if anaconda_log or packaging_log disappear
            return combined_log
    try:
        tail = read_tail(get_log_path(), size)
    except OSError as e:
        raise RuntimeError("No log available.") from e
    return tail
