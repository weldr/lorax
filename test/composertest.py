#!/usr/bin/python3

import cockpittest
import subprocess

class ComposerTestCase(cockpittest.TestCase):
    def setUp(self):
        super(ComposerTestCase, self).setUp()

        print("Waiting for lorax-composer to become ready...")
        curl_command = ["curl", "--max-time", "360",
                                "--silent",
                                "--unix-socket", "/run/weldr/api.socket",
                                "http://localhost/api/status"]
        r = self.execute(curl_command, stdout=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0)


    def runCliTest(self, script):
        extra_env = []
        if self.sit:
            extra_env.append("COMPOSER_TEST_FAIL_FAST=1")

        r = self.execute(["CLI=/usr/bin/composer-cli",
                          "TEST=" + self.id(),
                          "PACKAGE=composer-cli",
                          *extra_env,
                          "/tests/test_cli.sh", script])
        self.assertEqual(r.returncode, 0)
