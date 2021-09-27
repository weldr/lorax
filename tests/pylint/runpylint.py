#!/usr/bin/python3

import sys

from pocketlint import FalsePositive, PocketLintConfig, PocketLinter
import pylint

class LoraxLintConfig(PocketLintConfig):
    def __init__(self):
        PocketLintConfig.__init__(self)

        self.falsePositives = [ FalsePositive(r"Module 'pylorax' has no 'version' member"),
                                FalsePositive(r"Catching too general exception Exception"),
                                # See https://bugzilla.redhat.com/show_bug.cgi?id=1739167
                                FalsePositive(r"Module 'rpm' has no '.*' member"),
                                FalsePositive(r"raise-missing-from"),
                                FalsePositive(r"redundant-u-string-prefix"),
                                FalsePositive(r"unspecified-encoding"),
                              ]

    @property
    def pylintPlugins(self):
        retval = super(LoraxLintConfig, self).pylintPlugins
        # Not using threads so we can skip this
        retval.remove("pocketlint.checkers.environ")
        # No markup used
        retval.remove("pocketlint.checkers.markup")
        return retval

    @property
    def ignoreNames(self):
        return { "bots", "rpmbuild" }

    @property
    def extraArgs(self):
        return ["--extension-pkg-whitelist=rpm"]

    @property
    def disabledOptions(self):
        retval = super(LoraxLintConfig, self).disabledOptions

        # Remove messages that are no longer supported in py3
        for msg in ["W0110", "W0141", "W0142", "I0012"]:
            try:
                retval.remove(msg)
            except ValueError:
                pass
        return retval

if __name__ == "__main__":
    print("INFO: Using pylint v%s" % pylint.__version__)
    conf = LoraxLintConfig()
    linter = PocketLinter(conf)
    rc = linter.run()
    sys.exit(rc)
