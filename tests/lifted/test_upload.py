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
from lifted.providers import list_providers, resolve_playbook_path, validate_settings
from lifted.upload import Upload
import pylorax.api.config

from tests.lifted.profiles import test_profiles

# Helper function for creating Upload object
def create_upload(ucfg, provider_name, image_name, settings, status=None, callback=None):
    validate_settings(ucfg, provider_name, settings, image_name)
    return Upload(
        provider_name=provider_name,
        playbook_path=resolve_playbook_path(ucfg, provider_name),
        image_name=image_name,
        settings=settings,
        status=status,
        status_callback=callback,
    )


class UploadTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.root_dir = tempfile.mkdtemp(prefix="lifted.test.")
        self.config = pylorax.api.config.configure(root_dir=self.root_dir, test_config=True)
        self.config.set("composer", "share_dir", os.path.realpath("./share/"))
        lifted.config.configure(self.config)

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.root_dir)

    def test_new_upload(self):
        for p in list_providers(self.config["upload"]):
            print(p)
            upload = create_upload(self.config["upload"], p, "test-image", test_profiles[p][1], status="READY")
            summary = upload.summary()
            self.assertEqual(summary["provider_name"], p)
            self.assertEqual(summary["image_name"], "test-image")
            self.assertTrue(summary["status"], "WAITING")

    def test_serializable(self):
        for p in list_providers(self.config["upload"]):
            print(p)
            upload = create_upload(self.config["upload"], p, "test-image", test_profiles[p][1], status="READY")
            self.assertEqual(upload.serializable()["settings"], test_profiles[p][1])
            self.assertEqual(upload.serializable()["status"], "READY")

    def test_summary(self):
        for p in list_providers(self.config["upload"]):
            print(p)
            upload = create_upload(self.config["upload"], p, "test-image", test_profiles[p][1], status="READY")
            self.assertEqual(upload.summary()["settings"], test_profiles[p][1])
            self.assertEqual(upload.summary()["status"], "READY")

    def test_set_status(self):
        for p in list_providers(self.config["upload"]):
            print(p)
            upload = create_upload(self.config["upload"], p, "test-image", test_profiles[p][1], status="READY")
            self.assertEqual(upload.summary()["status"], "READY")
            upload.set_status("WAITING")
            self.assertEqual(upload.summary()["status"], "WAITING")

    def test_ready(self):
        for p in list_providers(self.config["upload"]):
            print(p)
            upload = create_upload(self.config["upload"], p, "test-image", test_profiles[p][1], status="WAITING")
            self.assertEqual(upload.summary()["status"], "WAITING")
            upload.ready("test-image-path", status_callback=None)
            summary = upload.summary()
            self.assertEqual(summary["status"], "READY")
            self.assertEqual(summary["image_path"], "test-image-path")

    def test_reset(self):
        for p in list_providers(self.config["upload"]):
            print(p)
            upload = create_upload(self.config["upload"], p, "test-image", test_profiles[p][1], status="CANCELLED")
            upload.ready("test-image-path", status_callback=None)
            upload.reset(status_callback=None)
            self.assertEqual(upload.status, "READY")

    def test_reset_errors(self):
        for p in list_providers(self.config["upload"]):
            print(p)
            upload = create_upload(self.config["upload"], p, "test-image", test_profiles[p][1], status="WAITING")
            with self.assertRaises(RuntimeError):
                upload.reset(status_callback=None)

            upload = create_upload(self.config["upload"], p, "test-image", test_profiles[p][1], status="CANCELLED")
            with self.assertRaises(RuntimeError):
                upload.reset(status_callback=None)

    def test_cancel(self):
        for p in list_providers(self.config["upload"]):
            print(p)
            upload = create_upload(self.config["upload"], p, "test-image", test_profiles[p][1], status="WAITING")
            upload.cancel()
            self.assertEqual(upload.status, "CANCELLED")

    def test_cancel_error(self):
        for p in list_providers(self.config["upload"]):
            print(p)
            upload = create_upload(self.config["upload"], p, "test-image", test_profiles[p][1], status="CANCELLED")
            with self.assertRaises(RuntimeError):
                upload.cancel()
