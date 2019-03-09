#
# Copyright (C) 2019  Red Hat, Inc.
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
import os
import pytoml as toml
import rpm
import shutil
import stat
import subprocess
import tarfile
import tempfile
import unittest

from pylorax.api.gitrpm import GitArchiveTarball, GitRpmBuild, make_git_rpm, create_gitrpm_repo
from pylorax.sysutils import joinpaths

def _setup_git_repo(self):
    """Setup a git repo in a tmpdir, storing details into self

    Call this from setUpClass()
    """
    self.repodir = tempfile.mkdtemp(prefix="git-rpm-test.")
    # Create a local git repo in a temporary directory, populate it with files.
    cmd = ["git", "init", self.repodir]
    subprocess.check_call(cmd)

    oldcwd = os.getcwd()
    os.chdir(self.repodir)
    cmd = ["git", "config", "user.email", "test@testing.localhost"]
    subprocess.check_call(cmd)

    # Hold the expected file paths for the tests
    self.test_results = {"first": [], "second": [], "branch": []}
    # Add some files
    results_path = "./tests/pylorax/results/"
    for f in ["full-recipe.toml", "minimal.toml", "modules-only.toml"]:
        shutil.copy2(os.path.join(oldcwd, results_path, f), self.repodir)
        self.test_results["first"].append(f)

    cmd = ["git", "add", "*.toml"]
    subprocess.check_call(cmd)
    cmd = ["git", "commit", "-m", "first files"]
    subprocess.check_call(cmd)
    cmd = ["git", "tag", "v1.0.0"]
    subprocess.check_call(cmd)

    # Get the commit hash
    cmd = ["git", "log", "--pretty=%H"]
    self.first_commit = subprocess.check_output(cmd).decode("UTF-8").strip()

    # 2nd commit adds to 1st commit
    self.test_results["second"] = self.test_results["first"].copy()

    # Add some more files
    os.makedirs(os.path.join(self.repodir, "only-bps/"))
    for f in ["packages-only.toml", "groups-only.toml"]:
        shutil.copy2(os.path.join(oldcwd, results_path, f), os.path.join(self.repodir, "only-bps/"))
        self.test_results["second"].append(os.path.join("only-bps/", f))
    self.test_results["second"] = sorted(self.test_results["second"])

    cmd = ["git", "add", "*.toml"]
    subprocess.check_call(cmd)
    cmd = ["git", "commit", "-m", "second files"]
    subprocess.check_call(cmd)
    cmd = ["git", "tag", "v1.1.0"]
    subprocess.check_call(cmd)

    # Make a branch for some other files
    cmd = ["git", "checkout", "-b", "custom-branch"]
    subprocess.check_call(cmd)

    # 3nd commit adds to 2nd commit
    self.test_results["branch"] = self.test_results["second"].copy()

    # Add some files to the new branch
    for f in ["custom-base.toml", "repos-git.toml"]:
        shutil.copy2(os.path.join(oldcwd, results_path, f), self.repodir)
        self.test_results["branch"].append(f)
    self.test_results["branch"] = sorted(self.test_results["branch"])

    cmd = ["git", "add", "*.toml"]
    subprocess.check_call(cmd)
    cmd = ["git", "commit", "-m", "branch files"]
    subprocess.check_call(cmd)

    os.chdir(oldcwd)


class GitArchiveTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.repodir = None
        self.first_commit = None
        self.test_results = {}

        _setup_git_repo(self)

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.repodir)

    def _check_tar(self, archive, prefix, test_name):
        """Check the file list of the created archive against the expected list in self.test_results"""
        try:
            tardir = tempfile.mkdtemp(prefix="git-rpm-test.")
            archive.write_file(tardir)
            tarpath = os.path.join(tardir, archive.sourceName)

            # Archive is in rpmdir + archive.sourceName
            self.assertTrue(os.path.exists(tarpath))

            # Examine contents of the tarfile
            tar = tarfile.open(tarpath, "r")
            files = sorted(i.name for i in tar if i.isreg())
            self.assertEqual(files, [os.path.join(prefix, f) for f in self.test_results[test_name]])
            tar.close()
        finally:
            shutil.rmtree(tardir)

    def git_branch_test(self):
        """Test creating an archive from a git branch"""
        git_repo = toml.loads("""
            [[repos.git]]
            rpmname="git-rpm-test"
            rpmversion="1.0.0"
            rpmrelease="1"
            summary="Testing the git rpm code"
            repo="file://%s"
            ref="origin/custom-branch"
            destination="/srv/testing-rpm/"
        """ % self.repodir)
        archive = GitArchiveTarball(git_repo["repos"]["git"][0])
        self._check_tar(archive, "git-rpm-test/", "branch")

    def git_commit_test(self):
        """Test creating an archive from a git commit hash"""
        git_repo = toml.loads("""
            [[repos.git]]
            rpmname="git-rpm-test"
            rpmversion="1.0.0"
            rpmrelease="1"
            summary="Testing the git rpm code"
            repo="file://%s"
            ref="%s"
            destination="/srv/testing-rpm/"
        """ % (self.repodir, self.first_commit))
        archive = GitArchiveTarball(git_repo["repos"]["git"][0])
        self._check_tar(archive, "git-rpm-test/", "first")

    def git_tag_test(self):
        """Test creating an archive from a git tag"""
        git_repo = toml.loads("""
            [[repos.git]]
            rpmname="git-rpm-test"
            rpmversion="1.0.0"
            rpmrelease="1"
            summary="Testing the git rpm code"
            repo="file://%s"
            ref="v1.1.0"
            destination="/srv/testing-rpm/"
        """ % (self.repodir))
        archive = GitArchiveTarball(git_repo["repos"]["git"][0])
        self._check_tar(archive, "git-rpm-test/", "second")

    def git_fail_repo_test(self):
        """Test creating an archive from a bad url"""
        git_repo = toml.loads("""
            [[repos.git]]
            rpmname="git-rpm-test"
            rpmversion="1.0.0"
            rpmrelease="1"
            summary="Testing the git rpm code"
            repo="file://%s"
            ref="v1.1.0"
            destination="/srv/testing-rpm/"
        """ % ("/tmp/no-repo-here/"))
        with self.assertRaises(RuntimeError):
            archive = GitArchiveTarball(git_repo["repos"]["git"][0])
            self._check_tar(archive, "git-rpm-test/", None)

    def git_fail_ref_test(self):
        """Test creating an archive from a bad ref"""
        git_repo = toml.loads("""
            [[repos.git]]
            rpmname="git-rpm-test"
            rpmversion="1.0.0"
            rpmrelease="1"
            summary="Testing the git rpm code"
            repo="file://%s"
            ref="0297617d7b8baa263a69ae7dc901bbbcefd0eaa4"
            destination="/srv/testing-rpm/"
        """ % (self.repodir))
        with self.assertRaises(RuntimeError):
            archive = GitArchiveTarball(git_repo["repos"]["git"][0])
            self._check_tar(archive, "git-rpm-test/", None)


class GitRpmTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.repodir = None
        self.first_commit = None
        self.test_results = {}

        _setup_git_repo(self)

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.repodir)

    def _check_rpm(self, repo, rpm_dir, rpm_file, test_name):
        """Check the contents of the rpm against the expected test results
        """
        ts = rpm.TransactionSet()
        fd = os.open(os.path.join(rpm_dir, rpm_file), os.O_RDONLY)
        hdr = ts.hdrFromFdno(fd)
        os.close(fd)

        self.assertEqual(hdr[rpm.RPMTAG_NAME].decode("UTF-8"), repo["rpmname"])
        self.assertEqual(hdr[rpm.RPMTAG_VERSION].decode("UTF-8"), repo["rpmversion"])
        self.assertEqual(hdr[rpm.RPMTAG_RELEASE].decode("UTF-8"), repo["rpmrelease"])
        self.assertEqual(hdr[rpm.RPMTAG_URL].decode("UTF-8"), repo["repo"])

        files = sorted(f.name for f in rpm.files(hdr) if stat.S_ISREG(f.mode))
        self.assertEqual(files, [os.path.join(repo["destination"], f) for f in self.test_results[test_name]])

    def git_branch_test(self):
        """Test creating an rpm from a git branch"""
        git_repo = toml.loads("""
            [[repos.git]]
            rpmname="git-rpm-test"
            rpmversion="1.0.0"
            rpmrelease="1"
            summary="Testing the git rpm code"
            repo="file://%s"
            ref="origin/custom-branch"
            destination="/srv/testing-rpm/"
        """ % self.repodir)
        try:
            rpm_dir = tempfile.mkdtemp(prefix="git-rpm-test.")
            rpm_file = make_git_rpm(git_repo["repos"]["git"][0], rpm_dir)
            self._check_rpm(git_repo["repos"]["git"][0], rpm_dir, rpm_file, "branch")
        finally:
            shutil.rmtree(rpm_dir)

    def git_commit_test(self):
        """Test creating an rpm from a git commit hash"""
        git_repo = toml.loads("""
            [[repos.git]]
            rpmname="git-rpm-test"
            rpmversion="1.0.0"
            rpmrelease="1"
            summary="Testing the git rpm code"
            repo="file://%s"
            ref="%s"
            destination="/srv/testing-rpm/"
        """ % (self.repodir, self.first_commit))
        try:
            rpm_dir = tempfile.mkdtemp(prefix="git-rpm-test.")
            rpm_file = make_git_rpm(git_repo["repos"]["git"][0], rpm_dir)
            self._check_rpm(git_repo["repos"]["git"][0], rpm_dir, rpm_file, "first")
        finally:
            shutil.rmtree(rpm_dir)

    def git_tag_test(self):
        """Test creating an rpm from a git tag"""
        git_repo = toml.loads("""
            [[repos.git]]
            rpmname="git-rpm-test"
            rpmversion="1.0.0"
            rpmrelease="1"
            summary="Testing the git rpm code"
            repo="file://%s"
            ref="v1.1.0"
            destination="/srv/testing-rpm/"
        """ % (self.repodir))
        try:
            rpm_dir = tempfile.mkdtemp(prefix="git-rpm-test.")
            rpm_file = make_git_rpm(git_repo["repos"]["git"][0], rpm_dir)
            self._check_rpm(git_repo["repos"]["git"][0], rpm_dir, rpm_file, "second")
        finally:
            shutil.rmtree(rpm_dir)

    def gitrpm_repo_test(self):
        """Test creating a dnf repo of the git rpms"""
        recipe = toml.loads("""
            [[repos.git]]
            rpmname="repo-test-alpha"
            rpmversion="1.1.0"
            rpmrelease="1"
            summary="Testing the git rpm code"
            repo="file://%s"
            ref="v1.1.0"
            destination="/srv/testing-alpha/"

            [[repos.git]]
            rpmname="repo-test-beta"
            rpmversion="1.0.0"
            rpmrelease="1"
            summary="Testing the git rpm code"
            repo="file://%s"
            ref="v1.0.0"
            destination="/srv/testing-beta/"
        """ % (self.repodir, self.repodir))
        try:
            temp_dir = tempfile.mkdtemp(prefix="git-rpm-test.")
            repo_dir = create_gitrpm_repo(temp_dir, recipe)

            self.assertTrue(len(repo_dir) > 0)
            self.assertTrue(os.path.exists(joinpaths(repo_dir, "repo-test-alpha-1.1.0-1.noarch.rpm")))
            self.assertTrue(os.path.exists(joinpaths(repo_dir, "repo-test-beta-1.0.0-1.noarch.rpm")))

        finally:
            shutil.rmtree(temp_dir)


class GitRpmBuildTest(unittest.TestCase):
    def get_base_dir_test(self):
        """Make sure base_dir is created"""
        gitRpm = GitRpmBuild("rpmtest", "1.0.0", "1", ["noarch"])
        base_dir = gitRpm.get_base_dir()
        self.assertTrue("lorax-git-rpm" in base_dir)
        gitRpm.cleanup_tmpdir()

    def short_base_dir_test(self):
        """Make sure cleanup of an unusually short base_dir fails"""
        gitRpm = GitRpmBuild("rpmtest", "1.0.0", "1", ["noarch"])
        gitRpm._base_dir = "/aa/"
        with self.assertRaises(RuntimeError):
            gitRpm.cleanup_tmpdir()
