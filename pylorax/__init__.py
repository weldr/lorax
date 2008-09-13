#
# pylorax
# Install image and tree support data generation tool -- Python module.
#
# Copyright (C) 2008  Red Hat, Inc.
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
# Author(s): David Cantrell <dcantrell@redhat.com>
#

version = (0, 1)

__all__ = ['discinfo', 'treeinfo']

import os
import shutil
import tempfile

import discinfo
import treeinfo

def show_version(prog):
    """show_version(prog)

    Display program name (prog) and version number.  If prog is an empty
    string or None, use the value 'pylorax'.

    """

    if prog is None or prog == '':
        prog = 'pylorax'

    print "%s version %d.%d" % (prog, version[0], version[1],)

def collectRepos(args):
    """collectRepos(args)

    Get the main repo (the first one) and then build a list of all remaining
    repos in the list.  Sanitize each repo URL for proper yum syntax.

    """

    if args is None or args == []:
        return '', []

    repolist = []
    for repospec in args:
        if repospec.startswith('/'):
            repolist.append("file://%s" % (repospec,))
        elif repospec.startswith('http://') or repospec.startswith('ftp://'):
            repolist.append(repospec)

    repo = repolist[0]
    extrarepos = []

    if len(repolist) > 1:
        for extra in repolist[1:]:
            extrarepos.append(extra)

    return repo, extrarepos

def initializeDirs(output):
    """initializeDirs(output)

    Create directories used for image generation.  The only required
    parameter is the main output directory specified by the user.

    """

    if not os.path.isdir(output):
        os.makedirs(output, mode=0755)

    tmpdir = tempfile.gettempdir()
    buildinstdir = tempfile.mkdtemp('XXXXXX', 'buildinstall.tree.', tmpdir)
    treedir = tempfile.mkdtemp('XXXXXX', 'treedir.', tmpdir)
    cachedir = tempfile.mkdtemp('XXXXXX', 'yumcache.', tmpdir)

    return buildinstdir, treedir, cachedir

def writeYumConf(cachedir=None, repo=None, extrarepos=[], mirrorlist=[]):
    """writeYumConf(cachedir=None, repo=None, [extrarepos=[], mirrorlist=[]])

    Generate a temporary yum.conf file for image generation.  The required
    parameters are the cachedir that yum should use and the main repo to use.

    Optional parameters are a list of extra repositories to add to the
    yum.conf file.  The mirrorlist parameter is a list of yum mirrorlists
    that should be added to the yum.conf file.

    Returns the path to the temporary yum.conf file on success, None of failure.
    """

    if cachedir is None or repo is None:
        return None

    tmpdir = tempfile.gettempdir()
    (f, yumconf) = tempfile.mkstemp('XXXXXX', 'yum.conf', tmpdir)

    f.write("[main]\n")
    f.write("cachedir=%s\n" % (cachedir,))
    f.write("keepcache=0\n")
    f.write("gpgcheck=0\n")
    f.write("plugins=0\n")
    f.write("reposdir=\n")
    f.write("tsflags=nodocs\n\n")
    f.write("[anacondarepo]\n")
    f.write("name=anaconda repo\n")
    f.write("baseurl=%s\n" % (repo,))
    f.write("enabled=1\n\n")

    if extrarepos != []:
        n = 1
        for extra in extrarepos:
            f.write("[anaconda-extrarepo-%d]\n" % (n,))
            f.write("name=anaconda extra repo %d\n" % (n,))
            f.write("baseurl=%s\n" % (extra,))
            f.write("enabled=1\n")
            n += 1

    if mirrorlist != []:
        n = 1
        for mirror in mirrorlist:
            f.write("[anaconda-mirrorlistrepo-%d]\n" % (n,))
            f.write("name=anaconda mirrorlist repo %d\n" % (n,))
            f.write("mirrorlist=%s\n" % (extra,))
            f.write("enabled=1\n")
            n += 1

    f.close()
    return yumconf

def cleanup(trash=[]):
    """cleanup(trash)

    Given a list of things to remove, cleanup() will remove them if it can.
    Never fails, just tries to remove things and returns regardless of
    failures removing things.

    """

    if trash is []:
        return

    for item in trash:
        if os.path.isdir(item):
           shutil.rmtree(item, ignore_errors=True)
        else:
           os.unlink(item)

    return
