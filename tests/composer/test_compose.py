#
# Copyright (C) 2020  Red Hat, Inc.
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
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
import json
import shutil
from socketserver import UnixStreamServer
import threading

import tempfile
import unittest

from composer import http_client as client
import composer.cli as cli
from composer.cli.cmdline import composer_cli_parser

# Use a GLOBAL record the request data for use in the test
# because there is no way to access the request handler class from the test methods
LAST_REQUEST = {}

# Test data for upload profile
PROFILE_TOML = """
provider = "aws"

[settings]
aws_access_key = "AWS Access Key"
aws_bucket = "AWS Bucket"
aws_region = "AWS Region"
aws_secret_key = "AWS Secret Key"
"""

class MyUnixServer(UnixStreamServer):
    def get_request(self):
        """There is no client address for Unix Domain Sockets, so return the server address"""
        req, _ = self.socket.accept()
        return (req, self.server_address)


class APIHTTPHandler(BaseHTTPRequestHandler):
    STATUS = {}

    def log_request(self, code='-', size='-'):
        # Don't log requests
        return

    def send_json_response(self, status, d):
        """Send a 200 with a JSON body"""
        body = json.dumps(d).encode("UTF-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_api_status_dict(self):
        self.send_json_response(HTTPStatus.OK, self.STATUS)

    def send_api_status(self, status=True, errors=None):
        if status:
            self.send_json_response(HTTPStatus.OK, {"status": True})
        else:
            self.send_json_response(HTTPStatus.BAD_REQUEST,
                    {"status": False, "errors": [{"id": "0", "msg": "Test Framework"}]})

    def save_request(self):
        global LAST_REQUEST
        LAST_REQUEST = {
                "command": self.command,
                "path": self.path,
                "headers": self.headers,
                "body": "",
        }
        try:
            length = int(self.headers.get('content-length'))
            LAST_REQUEST["body"] = self.rfile.read(length)
        except (ValueError, TypeError):
            pass
        print("%s" % LAST_REQUEST)

    def do_GET(self):
        self.save_request()
        if self.path == "/api/status":
            self.send_api_status_dict()

    def do_POST(self):
        # Need to check for /api/status and send the correct response
        self.save_request()
        self.send_api_status(True)


class LoraxAPIv0HTTPHandler(APIHTTPHandler):
    STATUS = {
        "api": "0",
        "backend": "lorax-composer",
        "build": "devel",
        "db_supported": True,
        "db_version": "0",
        "msgs": [],
        "schema_version": "0"
    }


class LoraxAPIv1HTTPHandler(APIHTTPHandler):
    STATUS = {
        "api": "1",
        "backend": "lorax-composer",
        "build": "devel",
        "db_supported": True,
        "db_version": "0",
        "msgs": [],
        "schema_version": "0"
    }


class OsBuildAPIv0HTTPHandler(APIHTTPHandler):
    STATUS = {
        "api": "0",
        "backend": "osbuild-composer",
        "build": "devel",
        "db_supported": True,
        "db_version": "0",
        "msgs": [],
        "schema_version": "0"
    }


class OsBuildAPIv1HTTPHandler(APIHTTPHandler):
    STATUS = {
        "api": "1",
        "backend": "osbuild-composer",
        "build": "devel",
        "db_supported": True,
        "db_version": "0",
        "msgs": [],
        "schema_version": "0"
    }


class ComposeTestCase(unittest.TestCase):
    def run_args(self, args):
        global LAST_REQUEST
        LAST_REQUEST = {}
        p = composer_cli_parser()
        opts = p.parse_args(args)
        cli.main(opts)
        return LAST_REQUEST


class ComposeLoraxV0TestCase(ComposeTestCase):
    @classmethod
    def setUpClass(self):
        self.tmpdir = tempfile.mkdtemp(prefix="composer-cli.test.")
        self.socket = self.tmpdir + "/api.socket"
        self.server = MyUnixServer(self.socket, LoraxAPIv0HTTPHandler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()

    @classmethod
    def tearDownClass(self):
        self.server.shutdown()
        self.thread.join(10)
        shutil.rmtree(self.tmpdir)

    def test_status(self):
        """Make sure the mock status response is working"""
        global LAST_REQUEST
        LAST_REQUEST = {}
        result = client.get_url_json(self.socket, "/api/status")
        self.assertTrue("path" in LAST_REQUEST)
        self.assertEqual(LAST_REQUEST["path"], "/api/status")
        self.assertEqual(result, LoraxAPIv0HTTPHandler.STATUS)

    def test_compose_start_plain(self):
        result = self.run_args(["--socket", self.socket, "--api", "0", "compose", "start", "http-server", "qcow2"])
        self.assertTrue(result is not None)
        self.assertTrue("body" in result)
        self.assertGreater(len(result["body"]), 0)
        jd = json.loads(result["body"])
        self.assertEqual(jd, {"blueprint_name": "http-server", "compose_type": "qcow2", "branch": "master"})


class ComposeLoraxV1TestCase(ComposeTestCase):
    @classmethod
    def setUpClass(self):
        self.tmpdir = tempfile.mkdtemp(prefix="composer-cli.test.")
        self.socket = self.tmpdir + "api.socket"
        self.server = MyUnixServer(self.socket, LoraxAPIv1HTTPHandler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()

    @classmethod
    def tearDownClass(self):
        self.server.shutdown()
        self.thread.join(10)
        shutil.rmtree(self.tmpdir)

    def test_status(self):
        """Make sure the mock status response is working"""
        global LAST_REQUEST
        LAST_REQUEST = {}
        result = client.get_url_json(self.socket, "/api/status")
        self.assertTrue("path" in LAST_REQUEST)
        self.assertEqual(LAST_REQUEST["path"], "/api/status")
        self.assertEqual(result, LoraxAPIv1HTTPHandler.STATUS)

    def test_compose_start_plain(self):
        result = self.run_args(["--socket", self.socket, "--api", "1", "compose", "start", "http-server", "qcow2"])
        self.assertTrue(result is not None)
        self.assertTrue("body" in result)
        self.assertGreater(len(result["body"]), 0)
        jd = json.loads(result["body"])
        self.assertEqual(jd, {"blueprint_name": "http-server", "compose_type": "qcow2", "branch": "master"})

    def test_compose_start_upload(self):
        with tempfile.NamedTemporaryFile(prefix="composer-cli.test.") as f:
            f.write(PROFILE_TOML.encode("UTF-8"))
            f.seek(0)
            result = self.run_args(["--socket", self.socket, "--api", "1", "compose", "start", "http-server", "qcow2", "httpimage", f.name])
            self.assertTrue(result is not None)
            self.assertTrue("body" in result)
            self.assertGreater(len(result["body"]), 0)
            jd = json.loads(result["body"])
            self.assertEqual(jd, {"blueprint_name": "http-server", "compose_type": "qcow2", "branch": "master",
                "upload": {"image_name": "httpimage", "provider": "aws",
                "settings": {"aws_access_key": "AWS Access Key", "aws_bucket": "AWS Bucket", "aws_region": "AWS Region", "aws_secret_key": "AWS Secret Key"}}})

    def test_compose_start_provider(self):
        result = self.run_args(["--socket", self.socket, "--api", "1", "compose", "start", "http-server", "qcow2", "httpimage", "aws", "production"])
        self.assertTrue(result is not None)
        self.assertTrue("body" in result)
        self.assertGreater(len(result["body"]), 0)
        jd = json.loads(result["body"])
        self.assertEqual(jd, {"blueprint_name": "http-server", "compose_type": "qcow2", "branch": "master",
            "upload": {"image_name": "httpimage", "profile": "production", "provider": "aws"}})

class ComposeOsBuildV0TestCase(ComposeTestCase):
    @classmethod
    def setUpClass(self):
        self.tmpdir = tempfile.mkdtemp(prefix="composer-cli.test.")
        self.socket = self.tmpdir + "api.socket"
        self.server = MyUnixServer(self.socket, OsBuildAPIv0HTTPHandler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()

    @classmethod
    def tearDownClass(self):
        self.server.shutdown()
        self.thread.join(10)
        shutil.rmtree(self.tmpdir)

    def test_status(self):
        """Make sure the mock status response is working"""
        global LAST_REQUEST
        LAST_REQUEST = {}
        result = client.get_url_json(self.socket, "/api/status")
        self.assertTrue("path" in LAST_REQUEST)
        self.assertEqual(LAST_REQUEST["path"], "/api/status")
        self.assertEqual(result, OsBuildAPIv0HTTPHandler.STATUS)

    def test_compose_start_plain(self):
        result = self.run_args(["--socket", self.socket, "--api", "0", "compose", "start", "http-server", "qcow2"])
        self.assertTrue(result is not None)
        self.assertTrue("body" in result)
        self.assertGreater(len(result["body"]), 0)
        jd = json.loads(result["body"])
        self.assertEqual(jd, {"blueprint_name": "http-server", "compose_type": "qcow2", "branch": "master"})

class ComposeOsBuildV1TestCase(ComposeTestCase):
    @classmethod
    def setUpClass(self):
        self.tmpdir = tempfile.mkdtemp(prefix="composer-cli.test.")
        self.socket = self.tmpdir + "api.socket"
        self.server = MyUnixServer(self.socket, OsBuildAPIv1HTTPHandler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()

    @classmethod
    def tearDownClass(self):
        self.server.shutdown()
        self.thread.join(10)
        shutil.rmtree(self.tmpdir)

    def test_status(self):
        """Make sure the mock status response is working"""
        global LAST_REQUEST
        LAST_REQUEST = {}
        result = client.get_url_json(self.socket, "/api/status")
        self.assertTrue("path" in LAST_REQUEST)
        self.assertEqual(LAST_REQUEST["path"], "/api/status")
        self.assertEqual(result, OsBuildAPIv1HTTPHandler.STATUS)

    def test_compose_start_plain(self):
        result = self.run_args(["--socket", self.socket, "--api", "1", "compose", "start", "http-server", "qcow2"])
        self.assertTrue(result is not None)
        self.assertTrue("body" in result)
        self.assertGreater(len(result["body"]), 0)
        jd = json.loads(result["body"])
        self.assertEqual(jd, {"blueprint_name": "http-server", "compose_type": "qcow2", "branch": "master"})

    def test_compose_start_upload(self):
        with tempfile.NamedTemporaryFile(prefix="composer-cli.test.") as f:
            f.write(PROFILE_TOML.encode("UTF-8"))
            f.seek(0)
            result = self.run_args(["--socket", self.socket, "--api", "1", "compose", "start", "http-server", "qcow2", "httpimage", f.name])
            self.assertTrue(result is not None)
            self.assertTrue("body" in result)
            self.assertGreater(len(result["body"]), 0)
            jd = json.loads(result["body"])
            self.assertEqual(jd, {"blueprint_name": "http-server", "compose_type": "qcow2", "branch": "master",
                "upload": {"image_name": "httpimage", "provider": "aws",
                "settings": {"aws_access_key": "AWS Access Key", "aws_bucket": "AWS Bucket", "aws_region": "AWS Region", "aws_secret_key": "AWS Secret Key"}}})

    def test_compose_start_plain_size(self):
        result = self.run_args(["--socket", self.socket, "--api", "1", "compose", "start", "--size", "1776", "http-server", "qcow2"])
        self.assertTrue(result is not None)
        self.assertTrue("body" in result)
        self.assertGreater(len(result["body"]), 0)
        jd = json.loads(result["body"])
        self.assertEqual(jd, {"blueprint_name": "http-server", "compose_type": "qcow2", "branch": "master", "size": 1862270976})

    def test_compose_start_size_upload(self):
        with tempfile.NamedTemporaryFile(prefix="composer-cli.test.") as f:
            f.write(PROFILE_TOML.encode("UTF-8"))
            f.seek(0)
            result = self.run_args(["--socket", self.socket, "--api", "1", "compose", "start", "--size", "1791", "http-server", "qcow2", "httpimage", f.name])
            self.assertTrue(result is not None)
            self.assertTrue("body" in result)
            self.assertGreater(len(result["body"]), 0)
            jd = json.loads(result["body"])
            self.assertEqual(jd, {"blueprint_name": "http-server", "compose_type": "qcow2", "branch": "master", "size": 1877999616,
                "upload": {"image_name": "httpimage", "provider": "aws",
                "settings": {"aws_access_key": "AWS Access Key", "aws_bucket": "AWS Bucket", "aws_region": "AWS Region", "aws_secret_key": "AWS Secret Key"}}})

    def test_compose_start_ostree(self):
        result = self.run_args(["--socket", self.socket, "--api", "1", "compose", "start-ostree", "http-server", "fedora-iot-commit", "referenceid", "parenturl"])
        self.assertTrue(result is not None)
        self.assertTrue("body" in result)
        self.assertGreater(len(result["body"]), 0)
        jd = json.loads(result["body"])
        self.assertEqual(jd, {"blueprint_name": "http-server", "compose_type": "fedora-iot-commit", "branch": "master",
            "ostree": {"ref": "referenceid", "parent": "parenturl"}})

    def test_compose_start_ostree_upload(self):
        with tempfile.NamedTemporaryFile(prefix="composer-cli.test.") as f:
            f.write(PROFILE_TOML.encode("UTF-8"))
            f.seek(0)
            result = self.run_args(["--socket", self.socket, "--api", "1", "compose", "start-ostree", "http-server", "fedora-iot-commit", "referenceid", "parenturl", "httpimage", f.name])
            self.assertTrue(result is not None)
            self.assertTrue("body" in result)
            self.assertGreater(len(result["body"]), 0)
            jd = json.loads(result["body"])
            self.assertEqual(jd, {"blueprint_name": "http-server", "compose_type": "fedora-iot-commit", "branch": "master",
                "ostree": {"ref": "referenceid", "parent": "parenturl"},
                "upload": {"image_name": "httpimage", "provider": "aws",
                "settings": {"aws_access_key": "AWS Access Key", "aws_bucket": "AWS Bucket", "aws_region": "AWS Region", "aws_secret_key": "AWS Secret Key"}}})
