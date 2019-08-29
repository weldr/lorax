#
# Copyright (C) 2019 Red Hat, Inc.
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

import lifted.config
from lifted.providers import list_providers
from lifted.queue import _write_callback, create_upload, get_all_uploads, get_upload, get_uploads
from lifted.queue import ready_upload, reset_upload, cancel_upload
import pylorax.api.config

from tests.lifted.profiles import test_profiles

class QueueTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.root_dir = tempfile.mkdtemp(prefix="lifted.test.")
        self.config = pylorax.api.config.configure(root_dir=self.root_dir, test_config=True)
        self.config.set("composer", "share_dir", os.path.realpath("./share/"))
        lifted.config.configure(self.config)

        self.upload_uuids = []

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.root_dir)

    # This should run first, it writes uploads to the queue directory
    def test_00_create_upload(self):
        """Test creating an upload for each provider"""
        for p in list_providers(self.config["upload"]):
            print(p)
            upload = create_upload(self.config["upload"], p, "test-image", test_profiles[p][1])
            summary = upload.summary()
            self.assertEqual(summary["provider_name"], p)
            self.assertEqual(summary["image_name"], "test-image")
            self.assertTrue(summary["status"], "WAITING")

            self.upload_uuids.append(summary["uuid"])
        self.assertTrue(len(self.upload_uuids) > 0)
        self.assertTrue(len(self.upload_uuids), len(list_providers(self.config["upload"])))

    def test_01_get_all_uploads(self):
        """Test listing all the uploads"""
        uploads = get_all_uploads(self.config["upload"])
        # Should be one upload per provider
        providers = sorted([u.provider_name for u in uploads])
        self.assertEqual(providers, list_providers(self.config["upload"]))

    def test_02_get_upload(self):
        """Test listing specific uploads by uuid"""
        for uuid in self.upload_uuids:
            upload = get_upload(self.config["upload"], uuid)
            self.assertTrue(upload.uuid, uuid)

    def test_02_get_upload_error(self):
        """Test listing an unknown upload uuid"""
        with self.assertRaises(RuntimeError):
            get_upload(self.config["upload"], "not-a-valid-uuid")

    def test_03_get_uploads(self):
        """Test listing multiple uploads by uuid"""
        uploads = get_uploads(self.config["upload"], self.upload_uuids)
        uuids = sorted([u.uuid for u in uploads])
        self.assertTrue(uuids, sorted(self.upload_uuids))

    def test_04_ready_upload(self):
        """Test ready_upload"""
        ready_upload(self.config["upload"], self.upload_uuids[0], "image-test-path")
        upload = get_upload(self.config["upload"], self.upload_uuids[0])
        self.assertEqual(upload.image_path, "image-test-path")

    def test_05_reset_upload(self):
        """Test reset_upload"""
        # Set the status to FAILED so it can be reset
        upload = get_upload(self.config["upload"], self.upload_uuids[0])
        upload.set_status("FAILED", _write_callback(self.config["upload"]))

        reset_upload(self.config["upload"], self.upload_uuids[0])
        upload = get_upload(self.config["upload"], self.upload_uuids[0])
        self.assertEqual(upload.status, "READY")

    def test_06_reset_upload_error(self):
        """Test reset_upload raising an error"""
        with self.assertRaises(RuntimeError):
            reset_upload(self.config["upload"], self.upload_uuids[0])

    def test_07_cancel_upload(self):
        """Test cancel_upload"""
        cancel_upload(self.config["upload"], self.upload_uuids[0])
        upload = get_upload(self.config["upload"], self.upload_uuids[0])
        self.assertEqual(upload.status, "CANCELLED")

    def test_08_cancel_upload_error(self):
        """Test cancel_upload raises an error"""
        # Set the status to CANCELED to make sure the cancel will fail
        upload = get_upload(self.config["upload"], self.upload_uuids[0])
        upload.set_status("CANCELLED", _write_callback(self.config["upload"]))

        with self.assertRaises(RuntimeError):
            cancel_upload(self.config["upload"], self.upload_uuids[0])

    # TODO test execute
