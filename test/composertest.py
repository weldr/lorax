#!/usr/bin/python3

from __future__ import print_function

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


class ComposerTestCase(unittest.TestCase):
    image = testvm.DEFAULT_IMAGE
    sit = False

    def __init__(self, methodName='runTest'):
        super(ComposerTestCase, self).__init__(methodName=methodName)
        # by default run() does this and defaultTestResult()
        # always creates new object which is local for the .run() method
        self.ci_result = self.defaultTestResult()

    def run(self, result=None):
        # so we override run() and use an object attribute which we can
        # reference later in tearDown() and extract the errors from
        super(ComposerTestCase, self).run(result=self.ci_result)

    def setUp(self):
        self.network = testvm.VirtNetwork(0)
        self.machine = testvm.VirtMachine(self.image, networking=self.network.host(), memory_mb=2048)

        print("Starting virtual machine '%s'" % self.image)
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
        r = subprocess.call(self.ssh_command + curl_command, stdout=open(os.devnull, 'w'))
        self.assertEqual(r.returncode, 0)

    def tearDown(self):
        # `errors` is a list of tuples (method, error)
        errors = list(e[1] for e in self.ci_result.errors if e[1])

        if errors and self.sit:
            for e in errors:
                print_exception(*e)

            print()
            print(" ".join(self.ssh_command))
            input("Press RETURN to continue...")

        self.machine.stop()

    def execute(self, command):
        """Execute a command on the test machine."""
        return subprocess.call(self.ssh_command + command)

    def runCliTest(self, script):
        execute_params = ["CLI=/usr/bin/composer-cli",
                          "TEST=" + self.id(),
                          "PACKAGE=composer-cli",
                          "/tests/test_cli.sh", script]
        if self.sit:
            execute_params.insert(0, "COMPOSER_TEST_FAIL_FAST=1")

        r = self.execute(execute_params)
        self.assertEqual(r.returncode, 0)


def print_tests(tests):
    for test in tests:
        if isinstance(test, unittest.TestSuite):
            print_tests(test)
        # I don't know how this is used when running the tests
        # (maybe not used from what it looks like) so not sure how to refactor it
        # elif isinstance(test, unittest.loader._FailedTest):
        #    name = test.id().replace("unittest.loader._FailedTest.", "")
        #    print("Error: '%s' does not match a test" % name, file=sys.stderr)
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
