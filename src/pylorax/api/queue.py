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
import time
from pykickstart.version import makeVersion, RHEL7
from pykickstart.parser import KickstartParser

from pylorax.base import DataHolder
from pylorax.imgutils import default_image_name
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
        log.debug("jobs = %s", jobs)

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

    # TODO -- This will change based on the type of image requested
    # Configuration to pass to novirt_install
    install_cfg = DataHolder(
                image_name = default_image_name("xz", "root.tar"),
                compression = "xz",
                #compress_args = ["-9"],
                compress_args = [],
                ks = [ks_path],
                anaconda_args = "",
                proxy = "",
                armplatform = "",

                make_tar = True,
                make_iso = False,
                make_fsimage = False,
                fslabel = "",
                qcow2 = False,

                project = "Red Hat Enterprise Linux",
                releasever = "7",

                logfile=log_dir
          )

    # Some kludges for the 99-copy-logs %post, failure in it will crash the build
    for f in ["/tmp/NOSAVE_INPUT_KS", "/tmp/NOSAVE_LOGS"]:
        open(f, "w")

    log.info("repo_url = %s, cfg  = %s", repo_url, install_cfg)
    novirt_install(install_cfg, joinpaths(results_dir, install_cfg.image_name), None, repo_url)
