#
# Copyright (C) 2018  Red Hat, Inc.
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

from pylorax.dnfbase import get_dnf_base_object
from pylorax.ltmpl import LoraxTemplate, LoraxTemplateRunner
from pylorax.ltmpl import brace_expand, split_and_expand, rglob, rexists
from pylorax.sysutils import joinpaths

class TemplateFunctionsTestCase(unittest.TestCase):
    def test_brace_expand(self):
        """Test expanding braces"""
        self.assertEqual(list(brace_expand("foo")), ["foo"])
        self.assertEqual(list(brace_expand("${foo}")), ["${foo}"])
        self.assertEqual(list(brace_expand("${foo,bar}")), ["$foo", "$bar"])
        self.assertEqual(list(brace_expand("foo {one,two,three,four}")), ["foo one", "foo two", "foo three", "foo four"])

    def test_split_and_expand(self):
        """Test splitting lines and expanding braces"""
        self.assertEqual(list(split_and_expand("foo bar")), ["foo", "bar"])
        self.assertEqual(list(split_and_expand("foo bar-{one,two}")), ["foo", "bar-one", "bar-two"])
        self.assertEqual(list(split_and_expand("foo 'bar {one,two}'")), ["foo", "bar one", "bar two"])
        self.assertEqual(list(split_and_expand('foo "bar {one,two}"')), ["foo", "bar one", "bar two"])

    def test_rglob(self):
        """Test rglob function"""
        self.assertEqual(list(rglob("chmod*tmpl", "./tests/pylorax/templates", fatal=False)), ["chmod-cmd.tmpl"])
        self.assertEqual(list(rglob("einstein", "./tests/pylorax/blueprints", fatal=False)), [])
        with self.assertRaises(IOError):
            list(rglob("einstein", "./tests/pylorax/blueprints", fatal=True))

    def test_rexists(self):
        """Test rexists function"""
        self.assertTrue(rexists("chmod*tmpl", "./tests/pylorax/templates"))
        self.assertFalse(rexists("einstein", "./tests/pylorax/templates"))

class LoraxTemplateTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.templates = LoraxTemplate(["./tests/pylorax/templates/"])

    def test_parse_missing_quote(self):
        """Test parsing a template with missing quote"""
        with self.assertRaises(Exception):
            self.templates.parse("parse-missing-quote.tmpl", {"basearch": "x86_64"})

    def test_parse_template_x86_64(self):
        """Test LoraxTemplate.parse() with basearch set to x86_64"""
        commands = self.templates.parse("parse-test.tmpl", {"basearch": "x86_64"})
        self.assertEqual(commands, [['installpkg', 'common-package'],
                                    ['installpkg', 'foo-one', 'foo-two'],
                                    ['installpkg', 'not-s390x-package'],
                                    ['run_pkg_transaction']])

    def test_parse_template_s390x(self):
        """Test LoraxTemplate.parse() with basearch set to s390x"""
        commands = self.templates.parse("parse-test.tmpl", {"basearch": "s390x"})
        self.assertEqual(commands, [['installpkg', 'common-package'],
                                    ['installpkg', 'foo-one', 'foo-two'],
                                    ['run_pkg_transaction']])

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

def makeFakeRPM(repo_dir, name, epoch, version, release, files=None):
    """Make a fake rpm file in repo_dir"""
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
    with in_tempdir("lorax-test-rpms."):
        p.make()
        rpmfile = p.get_built_rpm(expectedArch)
        shutil.move(rpmfile, repo_dir)

class LoraxTemplateRunnerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # Create 2 repositories with rpmfluff
        self.repo1_dir = tempfile.mkdtemp(prefix="lorax.test.repo.")
        makeFakeRPM(self.repo1_dir, "anaconda-core", 0, "0.0.1", "1")
        makeFakeRPM(self.repo1_dir, "exact", 0, "1.3.17", "1")
        makeFakeRPM(self.repo1_dir, "fake-milhouse", 0, "1.0.0", "1")
        makeFakeRPM(self.repo1_dir, "fake-bart", 2, "1.13.0", "6")
        makeFakeRPM(self.repo1_dir, "fake-homer", 0, "0.4.0", "2")
        makeFakeRPM(self.repo1_dir, "lots-of-files", 0, "0.1.1", "1",
                    ["/lorax-files/file-one.txt",
                     "/lorax-files/file-two.txt",
                     "/lorax-files/file-three.txt"])
        makeFakeRPM(self.repo1_dir, "known-path", 0, "0.1.8", "1", ["/known-path/file-one.txt"])
        os.system("createrepo_c " + self.repo1_dir)

        self.repo2_dir = tempfile.mkdtemp(prefix="lorax.test.repo.")
        makeFakeRPM(self.repo2_dir, "fake-milhouse", 0, "1.3.0", "1")
        makeFakeRPM(self.repo2_dir, "fake-lisa", 0, "1.2.0", "1")
        os.system("createrepo_c " + self.repo2_dir)

        self.repo3_dir = tempfile.mkdtemp(prefix="lorax.test.debug.repo.")
        makeFakeRPM(self.repo3_dir, "fake-marge", 0, "2.3.0", "1", ["/fake-marge/file-one.txt"])
        makeFakeRPM(self.repo3_dir, "fake-marge-debuginfo", 0, "2.3.0", "1", ["/fake-marge/file-one-debuginfo.txt"])
        os.system("createrepo_c " + self.repo3_dir)

        # Get a dbo with just these repos

        # Setup a template runner
        self.root_dir = tempfile.mkdtemp(prefix="lorax.test.repo.")
        sources = ["file://"+self.repo1_dir, "file://"+self.repo2_dir, "file://"+self.repo3_dir]
        self.dnfbase = get_dnf_base_object(self.root_dir, sources,
                                           enablerepos=[], disablerepos=[])

        self.runner = LoraxTemplateRunner(inroot=self.root_dir,
                                          outroot=self.root_dir,
                                          dbo=self.dnfbase,
                                          templatedir="./tests/pylorax/templates")

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.repo1_dir)
        shutil.rmtree(self.repo2_dir)
        shutil.rmtree(self.root_dir)

    def test_00_runner_multi_repo(self):
        """Test installing packages with updates in a 2nd repo"""
        # If this does not raise an error it means that:
        #   Installing a named package works (anaconda-core)
        #   Installing a pinned package works (exact-1.3.17)
        #   Installing a globbed set of package names from multiple repos works
        #   removepkg removes a package's files
        #   removefrom removes some, but not all, of a package's files
        #
        # These all need to be done in one template because run_pkg_transaction can only run once
        self.runner.run("install-test.tmpl")
        self.runner.run("install-remove-test.tmpl")
        self.assertFalse(os.path.exists(joinpaths(self.root_dir, "/known-path/file-one.txt")))
        self.assertTrue(os.path.exists(joinpaths(self.root_dir, "/lorax-files/file-one.txt")))
        self.assertFalse(os.path.exists(joinpaths(self.root_dir, "/lorax-files/file-two.txt")))

        # Check the debug log
        self.assertTrue(os.path.exists(joinpaths(self.root_dir, "/root/debug-pkgs.log")))

    def test_install_file(self):
        """Test append, and install template commands"""
        self.runner.run("install-cmd.tmpl")
        self.assertTrue(os.path.exists(joinpaths(self.root_dir, "/etc/lorax-test")))
        with open(joinpaths(self.root_dir, "/etc/lorax-test")) as f:
            data = f.read()
        self.assertEqual(data, "TESTING LORAX TEMPLATES\n")
        self.assertTrue(os.path.exists(joinpaths(self.root_dir, "/etc/lorax-test-dest")))

    def test_installimg(self):
        """Test installimg template command"""
        self.runner.run("installimg-cmd.tmpl")
        self.assertTrue(os.path.exists(joinpaths(self.root_dir, "images/product.img")))

    def test_mkdir(self):
        """Test mkdir template command"""
        self.runner.run("mkdir-cmd.tmpl")
        self.assertTrue(os.path.isdir(joinpaths(self.root_dir, "/etc/lorax-mkdir")))

    def test_replace(self):
        """Test append, and replace template command"""
        self.runner.run("replace-cmd.tmpl")
        self.assertTrue(os.path.exists(joinpaths(self.root_dir, "/etc/lorax-replace")))
        with open(joinpaths(self.root_dir, "/etc/lorax-replace")) as f:
            data = f.read()
        self.assertEqual(data, "Running 1.2.3 for lorax\n")

    def test_treeinfo(self):
        """Test treeinfo template command"""
        self.runner.run("treeinfo-cmd.tmpl")
        self.assertEqual(self.runner.results.treeinfo["images"]["boot.iso"], "images/boot.iso")

    def test_installkernel(self):
        """Test installkernel template command"""
        self.runner.run("installkernel-cmd.tmpl")
        self.assertTrue(os.path.exists(joinpaths(self.root_dir, "/kernels/vmlinuz")))
        self.assertEqual(self.runner.results.treeinfo["images"]["kernel"], "/kernels/vmlinuz")

    def test_installinitrd(self):
        """Test installinitrd template command"""
        self.runner.run("installinitrd-cmd.tmpl")
        self.assertTrue(os.path.exists(joinpaths(self.root_dir, "/kernels/initrd.img")))
        self.assertEqual(self.runner.results.treeinfo["images"]["initrd"], "/kernels/initrd.img")

    def test_installupgradeinitrd(self):
        """Test installupgraedinitrd template command"""
        self.runner.run("installupgradeinitrd-cmd.tmpl")
        self.assertTrue(os.path.exists(joinpaths(self.root_dir, "/kernels/upgrade.img")))
        self.assertEqual(self.runner.results.treeinfo["images"]["upgrade"], "/kernels/upgrade.img")

    def test_hardlink(self):
        """Test hardlink template command"""
        self.runner.run("hardlink-cmd.tmpl")
        self.assertTrue(os.path.exists(joinpaths(self.root_dir, "/linked-file")))
        self.assertTrue(os.path.exists(joinpaths(self.root_dir, "/lorax-dir/lorax-file")))

    def test_symlink(self):
        """Test symlink template command"""
        self.runner.run("symlink-cmd.tmpl")
        self.assertTrue(os.path.islink(joinpaths(self.root_dir, "/symlinked-file")))

    def test_copy(self):
        """Test copy template command"""
        self.runner.run("copy-cmd.tmpl")
        self.assertTrue(os.path.exists(joinpaths(self.root_dir, "/copied-file")))

    def test_move(self):
        """Test move template command"""
        self.runner.run("move-cmd.tmpl")
        self.assertFalse(os.path.exists(joinpaths(self.root_dir, "/lorax-file")))
        self.assertTrue(os.path.exists(joinpaths(self.root_dir, "/moved-file")))

    def test_remove(self):
        """Test remove template command"""
        self.runner.run("remove-cmd.tmpl")
        self.assertFalse(os.path.exists(joinpaths(self.root_dir, "/lorax-file")))

    def test_chmod(self):
        """Test chmod template command"""
        self.runner.run("chmod-cmd.tmpl")
        self.assertEqual(os.stat(joinpaths(self.root_dir, "/lorax-file")).st_mode, 0o100641)

    def test_runcmd(self):
        """Test runcmd template command"""
        self.runner.run("runcmd-cmd.tmpl", root=self.root_dir)
        self.assertTrue(os.path.exists(joinpaths(self.root_dir, "/lorax-runcmd")))

    def test_removekmod(self):
        """Test removekmod template command"""
        self.runner.run("removekmod-cmd.tmpl")
        self.assertTrue(os.path.exists(joinpaths(self.root_dir, "/lib/modules/1.2.3/kernel/drivers/video/bar1.ko")))
        self.assertFalse(os.path.exists(joinpaths(self.root_dir, "/lib/modules/1.2.3/kernel/drivers/video/bar2.ko")))
        self.assertFalse(os.path.exists(joinpaths(self.root_dir, "/lib/modules/1.2.3/kernel/sound/foo1.ko")))
        self.assertFalse(os.path.exists(joinpaths(self.root_dir, "/lib/modules/1.2.3/kernel/sound/foo2.ko")))

    def test_createaddrsize(self):
        """Test createaddrsize template command"""
        self.runner.run("createaddrsize-cmd.tmpl", root=self.root_dir)
        self.assertTrue(os.path.exists(joinpaths(self.root_dir, "/initrd.addrsize")))

    def test_systemctl(self):
        """Test systemctl template command"""
        self.runner.run("systemctl-cmd.tmpl")
        self.assertTrue(os.path.islink(joinpaths(self.root_dir, "/etc/systemd/system/multi-user.target.wants/foo.service")))

    def test_bad_template(self):
        """Test parsing a bad template"""
        with self.assertRaises(Exception):
            self.runner.run("bad-template.tmpl")

    def test_unknown_cmd(self):
        """Test a template with an unknown command"""
        with self.assertRaises(ValueError):
            self.runner.run("unknown-cmd.tmpl")
