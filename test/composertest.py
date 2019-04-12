#!/usr/bin/python3

import os
import subprocess
import sys
import unittest

# import Cockpit's machinery for test VMs and its browser test API
sys.path.append(os.path.join(os.path.dirname(__file__), "../bots/machine"))
import testvm # pylint: disable=import-error


class ComposerTestCase(unittest.TestCase):
    image = testvm.DEFAULT_IMAGE

    def setUp(self):
        network = testvm.VirtNetwork(0)
        self.machine = testvm.VirtMachine(self.image, networking=network.host(), memory_mb=2048)

        print(f"Starting virtual machine '{self.image}'")
        self.machine.start()
        self.machine.wait_boot()

        # run a command to force starting the SSH master
        self.machine.execute("uptime")

        self.ssh_command = ["ssh", "-o", "ControlPath=" + self.machine.ssh_master,
                                   "-p", self.machine.ssh_port,
                                   self.machine.ssh_user + "@" + self.machine.ssh_address]

        print("Machine is up. Connect to it via:")
        print(" ".join(self.ssh_command))
        print()

        print("Waiting for lorax-composer to become ready...")
        curl_command = ["curl", "--max-time", "360",
                                "--silent",
                                "--unix-socket", "/run/weldr/api.socket",
                                "http://localhost/api/status"]
        r = subprocess.run(self.ssh_command + curl_command, stdout=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0)

    def tearDown(self):
        self.machine.stop()

    def execute(self, command, **args):
        """Execute a command on the test machine.

        **args and return value are the same as those for subprocess.run().
        """
        return subprocess.run(self.ssh_command + command, **args)

    def runCliTest(self, script):
        r = self.execute(["CLI=/usr/bin/composer-cli", "TEST=" + self.id(), "/tests/test_cli.sh", script])
        self.assertEqual(r.returncode, 0)


def main():
    unittest.main(verbosity=2)
