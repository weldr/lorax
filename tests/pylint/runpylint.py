#!/usr/bin/python3

import sys

from pocketlint import FalsePositive, PocketLintConfig, PocketLinter

class LoraxLintConfig(PocketLintConfig):
    def __init__(self):
        PocketLintConfig.__init__(self)

        self.falsePositives = [ FalsePositive(r"No name 'version' in module 'pylorax'"),
                                FalsePositive(r"Module 'pylorax' has no 'version' member"),
                                FalsePositive(r"Instance of 'int' has no .* member"),
                                FalsePositive(r"ImageMinimizer.remove_rpm.runCallback: Unused argument .*")
                              ]

    @property
    def pylintPlugins(self):
        retval = super(LoraxLintConfig, self).pylintPlugins
        # Not using threads so we can skip these
        retval.remove("pocketlint.checkers.environ")
        retval.remove("pocketlint.checkers.eintr")
        # No markup used
        retval.remove("pocketlint.checkers.markup")
        return retval

if __name__ == "__main__":
    conf = LoraxLintConfig()
    linter = PocketLinter(conf)
    rc = linter.run()
    sys.exit(rc)
