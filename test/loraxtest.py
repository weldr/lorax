#!/usr/bin/python3

import cockpittest

class LoraxTestCase(cockpittest.TestCase):
    def runLoraxTest(self, script=""):
        extra_env = []
        if self.sit:
            extra_env.append("COMPOSER_TEST_FAIL_FAST=1")

        r = self.execute(["CLI=/usr/sbin/lorax",
                          "TEST=" + self.id(),
                          "PACKAGE=lorax",
                          *extra_env,
                          "/tests/test_lorax.sh", script])
        self.assertEqual(r.returncode, 0)
