#
# Copyright (C) 2020  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
from contextlib import contextmanager
import os
from rpmfluff import SimpleRpmBuild, SourceFile, expectedArch
import shutil
import tempfile
import unittest

from pylorax import ArchData, DataHolder
from pylorax.dnfbase import get_dnf_base_object
from pylorax.treebuilder import RuntimeBuilder

# TODO Put these into a common test library location
@contextmanager
def in_tempdir(prefix='tmp'):
    """Execute a block of code with chdir in a temporary location"""
    oldcwd = os.getcwd()
    tmpdir = tempfile.mkdtemp(prefix=prefix)
    os.chdir(tmpdir)
    try:
        yield
    finally:
        os.chdir(oldcwd)
        shutil.rmtree(tmpdir)

def makeFakeRPM(repo_dir, name, epoch, version, release, files=None, provides=None):
    """Make a fake rpm file in repo_dir"""
    if provides is None:
        provides = []
    p = SimpleRpmBuild(name, version, release)
    if epoch:
        p.epoch = epoch
    if not files:
        p.add_simple_payload_file_random()
    else:
        # Make a number of fake file entries in the rpm
        for f in files:
            p.add_installed_file(
                installPath = f,
                sourceFile = SourceFile(os.path.basename(f), "THIS IS A FAKE FILE"))
    for c in provides:
        p.add_provides(c)
    with in_tempdir("lorax-test-rpms."):
        p.make()
        rpmfile = p.get_built_rpm(expectedArch)
        shutil.move(rpmfile, repo_dir)


class InstallBrandingTestCase(unittest.TestCase):
    def install_branding(self, repo_dir, variant=None, skip_branding=False):
        """Run the _install_branding and return the names of the installed packages"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as root_dir:
            dbo = get_dnf_base_object(root_dir, ["file://"+repo_dir], enablerepos=[], disablerepos=[])
            self.assertTrue(dbo is not None)

            product = DataHolder(name="Fedora", version="33", release="33",
                                 variant=variant, bugurl="http://none", isfinal=True)
            arch = ArchData(os.uname().machine)
            rb = RuntimeBuilder(product, arch, dbo, skip_branding=skip_branding)
            rb._install_branding()
            dbo.resolve()
            self.assertTrue(dbo.transaction is not None)

            return sorted(p.name for p in dbo.transaction.install_set)

    def test_no_pkgs(self):
        """Test with a repo with no system-release packages"""
        # No system-release packages
        with tempfile.TemporaryDirectory(prefix="lorax.test.repo.") as repo_dir:
            makeFakeRPM(repo_dir, "fake-milhouse", 0, "1.0.0", "1")
            os.system("createrepo_c " + repo_dir)

            pkgs = self.install_branding(repo_dir)
            self.assertEqual(pkgs, [])

    def test_generic_pkg(self):
        """Test with a repo with only a generic-release package"""
        # Only generic-release
        with tempfile.TemporaryDirectory(prefix="lorax.test.repo.") as repo_dir:
            makeFakeRPM(repo_dir, "generic-release", 0, "33", "1", ["/etc/system-release"], ["system-release"])
            os.system("createrepo_c " + repo_dir)

            pkgs = self.install_branding(repo_dir)
            self.assertEqual(pkgs, [])

    def test_two_pkgs(self):
        """Test with a repo with generic-release, and a fedora-release package"""
        # Two system-release packages
        with tempfile.TemporaryDirectory(prefix="lorax.test.repo.") as repo_dir:
            makeFakeRPM(repo_dir, "generic-release", 0, "33", "1", ["/etc/system-release"], ["system-release"])
            makeFakeRPM(repo_dir, "fedora-release", 0, "33", "1", ["/etc/system-release"], ["system-release"])
            makeFakeRPM(repo_dir, "fedora-logos", 0, "33", "1")
            os.system("createrepo_c " + repo_dir)

            pkgs = self.install_branding(repo_dir)
            self.assertEqual(pkgs, ["fedora-logos", "fedora-release"])

            # Test with a variant set, but not available
            pkgs = self.install_branding(repo_dir, variant="workstation")
            self.assertEqual(pkgs, ["fedora-logos", "fedora-release"])

    def test_three_pkgs(self):
        """Test with a repo with generic-release, fedora-release, fedora-release-workstation package"""
        # Three system-release packages, one with a variant suffix
        with tempfile.TemporaryDirectory(prefix="lorax.test.repo.") as repo_dir:
            makeFakeRPM(repo_dir, "generic-release", 0, "33", "1", ["/etc/system-release"], ["system-release"])
            makeFakeRPM(repo_dir, "fedora-release", 0, "33", "1", ["/etc/system-release"], ["system-release"])
            makeFakeRPM(repo_dir, "fedora-logos", 0, "33", "1")
            makeFakeRPM(repo_dir, "fedora-release-workstation", 0, "33", "1", ["/etc/system-release"], ["system-release"])
            os.system("createrepo_c " + repo_dir)

            pkgs = self.install_branding(repo_dir)
            self.assertEqual(pkgs, ["fedora-logos", "fedora-release"])

            # Test with a variant set
            pkgs = self.install_branding(repo_dir, variant="workstation")
            self.assertEqual(pkgs, ["fedora-logos", "fedora-release-workstation"])

            # Test with a variant set, but not available
            pkgs = self.install_branding(repo_dir, variant="server")
            self.assertEqual(pkgs, ["fedora-logos", "fedora-release"])

    def test_skip_branding(self):
        """Test disabled branding"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.repo.") as repo_dir:
            makeFakeRPM(repo_dir, "fedora-release", 0, "33", "1", ["/etc/system-release"], ["system-release"])
            makeFakeRPM(repo_dir, "fedora-logos", 0, "33", "1")
            os.system("createrepo_c " + repo_dir)

            pkgs = self.install_branding(repo_dir, skip_branding=True)
            self.assertEqual(pkgs, [])
