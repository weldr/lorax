# Copyright (C) 2019 Red Hat, Inc.
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
""" Clone a git repository and package it as an rpm

This module contains functions for cloning a git repo, creating a tar archive of
the selected commit, branch, or tag, and packaging the files into an rpm that will
be installed by anaconda when creating the image.
"""
import logging
log = logging.getLogger("lorax-composer")

import os
from rpmfluff import SimpleRpmBuild
import shutil
import subprocess
import tempfile
import time


def get_repo_description(gitRepo):
    """ Return a description including the git repo and reference

    :param gitRepo: A dict with the repository details
    :type gitRepo: dict
    :returns: A string with the git repo url and reference
    :rtype: str
    """
    return "Created from %s, reference '%s', on %s" % (gitRepo["repo"], gitRepo["ref"], time.ctime())

class GitArchiveTarball:
    """Create a git archive of the selected git repo and reference"""
    def __init__(self, gitRepo):
        self._gitRepo = gitRepo
        self.sourceName = self._gitRepo["rpmname"]+".tar.xz"

    def write_file(self, sourcesDir):
        """ Create the tar archive

        :param sourcesDir: Path to use for creating the archive
        :type sourcesDir: str

        This clones the git repository and creates a git archive from the specified reference.
        The result is in RPMNAME.tar.xz under the sourcesDir
        """
        # Clone the repository into a temporary location
        cmd = ["git", "clone", self._gitRepo["repo"], os.path.join(sourcesDir, "gitrepo")]
        log.debug(cmd)
        subprocess.check_call(cmd)

        oldcwd = os.getcwd()
        try:
            os.chdir(os.path.join(sourcesDir, "gitrepo"))

            # Configure archive to create a .tar.xz
            cmd = ["git", "config", "tar.tar.xz.command", "xz -c"]
            log.debug(cmd)
            subprocess.check_call(cmd)

            cmd = ["git", "archive", "--prefix", self._gitRepo["rpmname"] + "/", "-o", os.path.join(sourcesDir, self.sourceName), self._gitRepo["ref"]]
            log.debug(cmd)
            subprocess.check_call(cmd)
        finally:
            # Cleanup even if there was an error
            os.chdir(oldcwd)
            shutil.rmtree(os.path.join(sourcesDir, "gitrepo"))

class GitRpmBuild(SimpleRpmBuild):
    """Build an rpm containing files from a git repository"""
    def __init__(self, *args, **kwargs):
        self._base_dir = None
        super().__init__(*args, **kwargs)

    def check(self):
        raise NotImplementedError

    def get_base_dir(self):
        """Place all the files under a temporary directory + rpmbuild/
        """
        if not self._base_dir:
            self._base_dir = tempfile.mkdtemp(prefix="lorax-git-rpm.")
        return os.path.join(self._base_dir, "rpmbuild")

    def cleanup_tmpdir(self):
        """Remove the temporary directory and all of its contents
        """
        if len(self._base_dir) < 5:
            raise RuntimeError("Invalid base_dir: %s" % self.get_base_dir())

        shutil.rmtree(self._base_dir)

    def clean(self):
        """Remove the base directory from inside the tmpdir"""
        if len(self.get_base_dir()) < 5:
            raise RuntimeError("Invalid base_dir: %s" % self.get_base_dir())
        shutil.rmtree(self.get_base_dir(), ignore_errors=True)

    def add_git_tarball(self, gitRepo):
        """Add a tar archive of a git repository to the rpm

        :param gitRepo: A dict with the repository details
        :type gitRepo: dict

        This populates the rpm with the URL of the git repository, the summary
        describing the repo, the description of the repository and reference used,
        and sets up the rpm to install the archive contents into the destination
        path.
        """
        self.addUrl(gitRepo["repo"])
        self.add_summary(gitRepo["summary"])
        self.add_description(get_repo_description(gitRepo))
        self.addLicense("Unknown")
        sourceIndex = self.add_source(GitArchiveTarball(gitRepo))
        self.section_build += "tar -xvf %s\n" % self.sources[sourceIndex].sourceName
        dest = os.path.normpath(gitRepo["destination"])
        self.create_parent_dirs(dest)
        self.section_install += "cp -r %s $RPM_BUILD_ROOT/%s\n" % (gitRepo["rpmname"], dest)
        sub = self.get_subpackage(None)
        sub.section_files += "%s/" % dest

def make_git_rpm(gitRepo, dest):
    """ Create an rpm from the specified git repo

    :param gitRepo: A dict with the repository details
    :type gitRepo: dict

    This will clone the git repository, create an archive of the selected reference,
    and build an rpm that will install the files from the repository under the destination
    directory. The gitRepo dict should have the following fields::

        rpmname: "server-config"
        rpmversion: "1.0"
        rpmrelease: "1"
        summary: "Setup files for server deployment"
        repo: "PATH OF GIT REPO TO CLONE"
        ref: "v1.0"
        destination: "/opt/server/"

    * rpmname: Name of the rpm to create, also used as the prefix name in the tar archive
    * rpmversion: Version of the rpm, eg. "1.0.0"
    * rpmrelease: Release of the rpm, eg. "1"
    * summary: Summary string for the rpm
    * repo: URL of the get repo to clone and create the archive from
    * ref: Git reference to check out. eg. origin/branch-name, git tag, or git commit hash
    * destination: Path to install the / of the git repo at when installing the rpm
    """
    gitRpm = GitRpmBuild(gitRepo["rpmname"], gitRepo["rpmversion"], gitRepo["rpmrelease"], ["noarch"])
    try:
        gitRpm.add_git_tarball(gitRepo)
        gitRpm.do_make()
        rpmfile = gitRpm.get_built_rpm("noarch")
        shutil.move(rpmfile, dest)
    except Exception as e:
        log.error("Creating git repo rpm: %s", e)
        raise RuntimeError("Creating git repo rpm: %s" % e)
    finally:
        gitRpm.cleanup_tmpdir()

    return os.path.basename(rpmfile)
