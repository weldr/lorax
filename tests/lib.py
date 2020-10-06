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
import os
import sys
from contextlib import contextmanager
import magic
from io import StringIO
import shutil
import subprocess
import tempfile

@contextmanager
def captured_output():
    new_out, new_err = StringIO(), StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = new_out, new_err
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout, sys.stderr = old_out, old_err

def get_file_magic(filename):
    """Get the file type details using libmagic

    Returns "" on failure or a string containing the description of the file
    """
    details = ""
    try:
        ms = magic.open(magic.NONE)
        ms.load()
        details = ms.file(filename)
    finally:
        ms.close()
    return details

def create_git_repo():
    """Create a git repo in a tmpdir

    Call this from setUpClass()

    This returns the following fields:
    * repodir - the directory holding the repository
    * test_results - A dict with information to use for the tests
    * first_commit - hash of the first commit
    """
    repodir = tempfile.mkdtemp(prefix="git-rpm-test.")
    # Create a local git repo in a temporary directory, populate it with files.
    cmd = ["git", "init", repodir]
    subprocess.check_call(cmd)

    oldcwd = os.getcwd()
    os.chdir(repodir)
    cmd = ["git", "config", "user.email", "test@testing.localhost"]
    subprocess.check_call(cmd)

    # Hold the expected file paths for the tests
    test_results = {"first": [], "second": [], "branch": []}
    # Add some files
    results_path = "./tests/pylorax/results/"
    for f in ["full-recipe.toml", "minimal.toml", "modules-only.toml"]:
        shutil.copy2(os.path.join(oldcwd, results_path, f), repodir)
        test_results["first"].append(f)

    cmd = ["git", "add", "*.toml"]
    subprocess.check_call(cmd)
    cmd = ["git", "commit", "-m", "first files"]
    subprocess.check_call(cmd)
    cmd = ["git", "tag", "v1.0.0"]
    subprocess.check_call(cmd)

    # Get the commit hash
    cmd = ["git", "log", "--pretty=%H"]
    first_commit = subprocess.check_output(cmd).decode("UTF-8").strip()

    # 2nd commit adds to 1st commit
    test_results["second"] = test_results["first"].copy()

    # Add some more files
    os.makedirs(os.path.join(repodir, "only-bps/"))
    for f in ["packages-only.toml", "groups-only.toml"]:
        shutil.copy2(os.path.join(oldcwd, results_path, f), os.path.join(repodir, "only-bps/"))
        test_results["second"].append(os.path.join("only-bps/", f))

    # Add a dotfile as well
    with open(os.path.join(repodir, "only-bps/.bpsrc"), "w") as f:
        f.write("dotfile test\n")
    test_results["second"].append("only-bps/.bpsrc")
    test_results["second"] = sorted(test_results["second"])

    cmd = ["git", "add", "*.toml", "only-bps/.bpsrc"]
    subprocess.check_call(cmd)
    cmd = ["git", "commit", "-m", "second files"]
    subprocess.check_call(cmd)
    cmd = ["git", "tag", "v1.1.0"]
    subprocess.check_call(cmd)

    # Make a branch for some other files
    cmd = ["git", "checkout", "-b", "custom-branch"]
    subprocess.check_call(cmd)

    # 3nd commit adds to 2nd commit
    test_results["branch"] = test_results["second"].copy()

    # Add some files to the new branch
    for f in ["custom-base.toml", "repos-git.toml"]:
        shutil.copy2(os.path.join(oldcwd, results_path, f), repodir)
        test_results["branch"].append(f)
    test_results["branch"] = sorted(test_results["branch"])

    cmd = ["git", "add", "*.toml"]
    subprocess.check_call(cmd)
    cmd = ["git", "commit", "-m", "branch files"]
    subprocess.check_call(cmd)

    os.chdir(oldcwd)

    return (repodir, test_results, first_commit)
