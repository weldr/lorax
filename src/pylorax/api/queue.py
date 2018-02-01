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
from glob import glob
import pytoml as toml
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

def compose_detail(results_dir):
    """ Return details about the build."""

    # Just in case it went away
    if not os.path.exists(results_dir):
        return {}

    build_id = os.path.basename(os.path.abspath(results_dir))
    status = open(joinpaths(results_dir, "STATUS")).read().strip()
    mtime = os.stat(joinpaths(results_dir, "STATUS")).st_mtime
    recipe = recipe_from_file(joinpaths(results_dir, "recipe.toml"))

    # Should only be 2 kickstarts, the final-kickstart.ks and the template
    types = [os.path.basename(ks)[:-3] for ks in glob(joinpaths(results_dir, "*.ks"))
                                       if "final-kickstart" not in ks]
    if len(types) != 1:
        raise RuntimeError("Cannot find ks template for build %s" % build_id)

    return {"id":       build_id,
            "status":   status,
            "timestamp":mtime,
            "recipe":   recipe["name"],
            "version":  recipe["version"]
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
