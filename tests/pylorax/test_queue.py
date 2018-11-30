#
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
import os
import shutil
import tempfile
import unittest
from uuid import uuid4

from pylorax.api.config import configure, make_queue_dirs
from pylorax.api.queue import check_queues
from pylorax.base import DataHolder
from pylorax.sysutils import joinpaths


class QueueTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.maxDiff = None
        self.config = dict()

        repo_dir = tempfile.mkdtemp(prefix="lorax.test.repo.")
        self.config["REPO_DIR"] = repo_dir

        self.config["COMPOSER_CFG"] = configure(root_dir=repo_dir, test_config=True)
        os.makedirs(joinpaths(self.config["COMPOSER_CFG"].get("composer", "share_dir"), "composer"))
        errors = make_queue_dirs(self.config["COMPOSER_CFG"], os.getgid())
        if errors:
            raise RuntimeError("\n".join(errors))

        lib_dir = self.config["COMPOSER_CFG"].get("composer", "lib_dir")
        share_dir = self.config["COMPOSER_CFG"].get("composer", "share_dir")
        tmp = self.config["COMPOSER_CFG"].get("composer", "tmp")
        self.monitor_cfg = DataHolder(composer_dir=lib_dir, share_dir=share_dir, uid=0, gid=0, tmp=tmp)

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.config["REPO_DIR"])

    def test_broken_run_symlinks(self):
        """Put a broken symlink into queue/run and make sure it is removed"""
        uuid = str(uuid4())
        os.symlink(joinpaths(self.monitor_cfg.composer_dir, "results", uuid),
                   joinpaths(self.monitor_cfg.composer_dir, "queue/run", uuid))
        self.assertTrue(os.path.islink(joinpaths(self.monitor_cfg.composer_dir, "queue/run", uuid)))
        check_queues(self.monitor_cfg)
        self.assertFalse(os.path.islink(joinpaths(self.monitor_cfg.composer_dir, "queue/run", uuid)))

    def test_broken_new_symlinks(self):
        """Put a broken symlink into queue/new and make sure it is removed"""
        uuid = str(uuid4())
        os.symlink(joinpaths(self.monitor_cfg.composer_dir, "results", uuid),
                   joinpaths(self.monitor_cfg.composer_dir, "queue/new", uuid))
        self.assertTrue(os.path.islink(joinpaths(self.monitor_cfg.composer_dir, "queue/new", uuid)))
        check_queues(self.monitor_cfg)
        self.assertFalse(os.path.islink(joinpaths(self.monitor_cfg.composer_dir, "queue/new", uuid)))

    def test_stale_run_symlink(self):
        """Put a valid symlink in run, make sure it is set to FAILED and removed"""
        uuid = str(uuid4())
        os.makedirs(joinpaths(self.monitor_cfg.composer_dir, "results", uuid))
        os.symlink(joinpaths(self.monitor_cfg.composer_dir, "results", uuid),
                   joinpaths(self.monitor_cfg.composer_dir, "queue/run", uuid))
        self.assertTrue(os.path.islink(joinpaths(self.monitor_cfg.composer_dir, "queue/run", uuid)))
        check_queues(self.monitor_cfg)
        self.assertFalse(os.path.islink(joinpaths(self.monitor_cfg.composer_dir, "queue/run", uuid)))
        status = open(joinpaths(self.monitor_cfg.composer_dir, "results", uuid, "STATUS")).read().strip()
        self.assertEqual(status, "FAILED")

    def test_missing_status(self):
        """Create a results dir w/o STATUS and confirm it is set to FAILED"""
        uuid = str(uuid4())
        os.makedirs(joinpaths(self.monitor_cfg.composer_dir, "results", uuid))
        check_queues(self.monitor_cfg)
        status = open(joinpaths(self.monitor_cfg.composer_dir, "results", uuid, "STATUS")).read().strip()
        self.assertEqual(status, "FAILED")

    def test_running_status(self):
        """Create a results dir with STATUS set to RUNNING and confirm it is set to FAILED"""
        uuid = str(uuid4())
        os.makedirs(joinpaths(self.monitor_cfg.composer_dir, "results", uuid))
        open(joinpaths(self.monitor_cfg.composer_dir, "results", uuid, "STATUS"), "w").write("RUNNING\n")
        check_queues(self.monitor_cfg)
        status = open(joinpaths(self.monitor_cfg.composer_dir, "results", uuid, "STATUS")).read().strip()
        self.assertEqual(status, "FAILED")

    def test_missing_new_symlink(self):
        """Create a results dir with STATUS set to WAITING and confirm a symlink is created in queue/new"""
        uuid = str(uuid4())
        os.makedirs(joinpaths(self.monitor_cfg.composer_dir, "results", uuid))
        open(joinpaths(self.monitor_cfg.composer_dir, "results", uuid, "STATUS"), "w").write("WAITING\n")
        check_queues(self.monitor_cfg)
        status = open(joinpaths(self.monitor_cfg.composer_dir, "results", uuid, "STATUS")).read().strip()
        self.assertEqual(status, "WAITING")
        self.assertTrue(os.path.islink(joinpaths(self.monitor_cfg.composer_dir, "queue/new", uuid)))
