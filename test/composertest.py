#!/usr/bin/python3

import argparse
import os
import subprocess
import sys
import unittest

# import Cockpit's machinery for test VMs and its browser test API
sys.path.append(os.path.join(os.path.dirname(__file__), "../bots/machine"))
import testvm # pylint: disable=import-error


def print_exception(etype, value, tb):
    import traceback

    # only include relevant lines
    limit = 0
    while tb and '__unittest' in tb.tb_frame.f_globals:
        limit += 1
        tb = tb.tb_next

    traceback.print_exception(etype, value, tb, limit=limit)


class VirtMachineTestCase(unittest.TestCase):
    sit = False
    network = None
    machine = None
    ssh_command = None

    def setUpTestMachine(self, image, identity_file=None):
        self.network = testvm.VirtNetwork(0)
        # default overlay directory is not big enough to hold the large composed trees; thus put overlay into /var/tmp/
        self.machine = testvm.VirtMachine(image, networking=self.network.host(),
                                          cpus=2, memory_mb=2048,
                                          overlay_dir="/var/tmp",
                                          identity_file=identity_file)

        print("Starting virtual machine '{}'".format(image))
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

    def tearDownTestMachine(self):
        if os.environ.get('TEST_ATTACHMENTS'):
            self.machine.download_dir('/var/log/tests', os.environ.get('TEST_ATTACHMENTS'))

        # Peek into internal data structure, because there's no way to get the
        # TestResult at this point. `errors` is a list of tuples (method, error)
        errors = list(e[1] for e in self._outcome.errors if e[1])

        if errors and self.sit:
            for e in errors:
                print_exception(*e)

            print()
            print(" ".join(self.ssh_command))
            input("Press RETURN to continue...")

        self.machine.stop()

    def execute(self, command, **args):
        """Execute a command on the test machine.

        **args and return value are the same as those for subprocess.run().
        """
        return subprocess.run(self.ssh_command + command, **args)


class ComposerTestCase(VirtMachineTestCase):
    def setUp(self):
        self.setUpTestMachine(testvm.DEFAULT_IMAGE)

        # Upload the contents of the ./tests/ directory to the machine (it must have beakerlib already installed)
        self.machine.upload(["../tests"], "/")

        print("Waiting for backend to become ready...")
        curl_command = ["curl", "--max-time", "360",
                                "--silent",
                                "--unix-socket", "/run/weldr/api.socket",
                                "http://localhost/api/status"]
        r = subprocess.run(self.ssh_command + curl_command, stdout=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0)

    def tearDown(self):
        self.tearDownVirt()

    def tearDownVirt(self, virt_dir=None, local_dir=None):
        if os.environ.get('TEST_ATTACHMENTS'):
            self.machine.download_dir('/var/log/tests', os.environ.get('TEST_ATTACHMENTS'))

        if virt_dir and local_dir:
            self.machine.download_dir(virt_dir, local_dir)

        self.tearDownTestMachine()
        return local_dir

    def runCliTest(self, script):
        extra_env = ["BACKEND=%s" % os.getenv('BACKEND', 'lorax-composer')]
        if self.sit:
            extra_env.append("COMPOSER_TEST_FAIL_FAST=1")

        r = self.execute(["CLI=/usr/bin/composer-cli",
                          "TEST=" + self.id(),
                          "PACKAGE=composer-cli",
                          *extra_env,
                          "/tests/test_cli.sh", script])
        self.assertEqual(r.returncode, 0)

    def runImageTest(self, script):
        extra_env = []
        if self.sit:
            extra_env.append("COMPOSER_TEST_FAIL_FAST=1")

        r = self.execute(["TEST=" + self.id(),
                          *extra_env,
                          "/tests/test_image.sh", script])
        self.assertEqual(r.returncode, 0)


def print_tests(tests):
    for test in tests:
        if isinstance(test, unittest.TestSuite):
            print_tests(test)
        elif isinstance(test, unittest.loader._FailedTest):
            name = test.id().replace("unittest.loader._FailedTest.", "")
            print(f"Error: '{name}' does not match a test", file=sys.stderr)
        else:
            print(test.id().replace("__main__.", ""))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tests", nargs="*", help="List of tests modules, classes, and methods")
    parser.add_argument("-l", "--list", action="store_true", help="Print the list of tests that would be executed")
    parser.add_argument("-s", "--sit", action="store_true", help="Halt test execution (but keep VM running) when a test fails")
    args = parser.parse_args()

    ComposerTestCase.sit = args.sit

    module = __import__("__main__")
    if args.tests:
        tests = unittest.defaultTestLoader.loadTestsFromNames(args.tests, module)
    else:
        tests = unittest.defaultTestLoader.loadTestsFromModule(module)

    if args.list:
        print_tests(tests)
        return 0

    runner = unittest.TextTestRunner(verbosity=2, failfast=args.sit)
    result = runner.run(tests)

    sys.exit(not result.wasSuccessful())
