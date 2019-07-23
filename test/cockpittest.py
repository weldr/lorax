#!/usr/bin/python3

import argparse
import os
import subprocess
import sys
import traceback
import unittest

# import Cockpit's machinery for test VMs and its browser test API
sys.path.append(os.path.join(os.path.dirname(__file__), "../bots/machine"))
import testvm # pylint: disable=import-error


def print_exception(etype, value, tb):
    # only include relevant lines
    limit = 0
    while tb and '__unittest' in tb.tb_frame.f_globals:
        limit += 1
        tb = tb.tb_next

    traceback.print_exception(etype, value, tb, limit=limit)


class TestCase(unittest.TestCase):
    image = testvm.DEFAULT_IMAGE
    sit = False

    def setUp(self):
        self.network = testvm.VirtNetwork(0)
        self.machine = testvm.VirtMachine(self.image, networking=self.network.host(), memory_mb=2048)

        print("Starting virtual machine '{}'".format(self.image))
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

    def tearDown(self):
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

    def runTest(self, cli, package, runner, script):
        """Run the test script"""
        extra_env = ["CLI=" + cli,
                     "TEST=" + self.id(),
                     "PACKAGE=" + package]
        if self.sit:
            extra_env.append("COMPOSER_TEST_FAIL_FAST=1")

        return self.execute([*extra_env, runner, script])


class TestResult(unittest.TestResult):
    def name(self, test):
        name = test.id().replace("__main__.", "")
        if test.shortDescription():
            name += ": " + test.shortDescription()
        return name

    def startTest(self, test):
        super().startTest(test)

        print("# ----------------------------------------------------------------------")
        print("# ", self.name(test))
        print("", flush=True)

    def stopTest(self, test):
        print(flush=True)

    def addSuccess(self, test):
        super().addSuccess(test)
        print("ok {} {}".format(self.testsRun, self.name(test)))

    def addError(self, test, err):
        super().addError(test, err)
        traceback.print_exception(*err, file=sys.stdout)
        print("not ok {} {}".format(self.testsRun, self.name(test)))

    def addFailure(self, test, err):
        super().addError(test, err)
        traceback.print_exception(*err, file=sys.stdout)
        print("not ok {} {}".format(self.testsRun, self.name(test)))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        print("ok {} {} # SKIP {}".format(self.testsRun, self.name(test), reason))

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        print("ok {} {}".format(self.testsRun, self.name(test)))

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        print("not ok {} {}".format(self.testsRun, self.name(test)))


class TestRunner(object):
    """A test runner that (in combination with TestResult) outputs
    results in a way that cockpit's log.html can read and format them.
    """

    def __init__(self, failfast=False):
        self.failfast = failfast

    def run(self, testable):
        result = TestResult()
        result.failfast = self.failfast
        result.startTestRun()
        count = testable.countTestCases()
        print("1.." + str(count))
        try:
            testable(result)
        finally:
            result.stopTestRun()
        return result


def print_tests(tests):
    for test in tests:
        if isinstance(test, unittest.TestSuite):
            print_tests(test)
        elif isinstance(test, unittest.loader._FailedTest):
            name = test.id().replace("unittest.loader._FailedTest.", "")
            print("Error: '{}' does not match a test".format(name), file=sys.stderr)
        else:
            print(test.id().replace("__main__.", ""))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tests", nargs="*", help="List of tests modules, classes, and methods")
    parser.add_argument("-l", "--list", action="store_true", help="Print the list of tests that would be executed")
    parser.add_argument("-s", "--sit", action="store_true", help="Halt test execution (but keep VM running) when a test fails")
    args = parser.parse_args()

    TestCase.sit = args.sit

    module = __import__("__main__")
    if args.tests:
        tests = unittest.defaultTestLoader.loadTestsFromNames(args.tests, module)
    else:
        tests = unittest.defaultTestLoader.loadTestsFromModule(module)

    if args.list:
        print_tests(tests)
        return 0

    runner = TestRunner(failfast=args.sit)
    result = runner.run(tests)

    if tests.countTestCases() != result.testsRun:
        print("Error: unexpected number of tests were run", file=sys.stderr)
        sys.exit(1)

    sys.exit(not result.wasSuccessful())
