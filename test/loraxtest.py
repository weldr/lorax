#!/usr/bin/python3

import cockpittest

class LoraxTestCase(cockpittest.TestCase):
    def runLoraxTest(self, script=""):
        r = self.runTest("/usr/sbin/lorax", "lorax", "/tests/test_lorax.sh", script)
        self.assertEqual(r.returncode, 0)
