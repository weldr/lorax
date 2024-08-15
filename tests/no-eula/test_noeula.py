import unittest

# Make sure that redhat-release-eula was removed after copying over lorax-templates-rhel
class NoEULATestCase(unittest.TestCase):
    def test_noeula(self):
        """Make sure redhat-release-eula is not in runtime-install.tmpl"""
        with open("./share/templates.d/99-generic/runtime-install.tmpl") as f:
            for line in f.readlines():
                self.assertTrue("redhat-release-eula" not in line,
                                "Remove redhat-release-eula from runtime-install.tmpl")
