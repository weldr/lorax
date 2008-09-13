#
# pylorax treeinfo module
# Install image and tree support data generation tool -- Python module.
#
# Copyright (C) 2007, 2008  Red Hat, Inc.
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
#            Will Woods <wwoods@redhat.com>
#

import os
import time
import ConfigParser

# Write out the .treeinfo file
def write(family=None, version=None, arch=None, outdir=None, variant='',
          discnum=None, totaldiscs=None, packagedir='', allDiscs=True):
    """write(family=None, version=None, arch=None, outdir=None,
             [variant='', discnum=None, totaldiscs=None, packagedir=''])

    Write the .treeinfo file to the specified directory (outdir).

    Required parameters:
        family       String specifying the family.
        version      String specifying the version number.
        arch         String specifying the architecture.
        outdir       Directory to write .treeinfo to (must exist).

    Optional parameters may be specified:
        variant      Defaults to an empty string, but can be any string.
        discnum      Defaults to '1', but you can specify an integer.
        totaldiscs   Defaults to '1', but you can specify an integer.
        packagedir   Directory where packages are located.
        allDiscs     Boolean stating all discs are in one tree (default: True)

    Returns True on success, False on failure.

    """

    if family is None or arch is None or outdir is None:
        return False

    if not os.path.isdir(outdir):
        return False

    data = { "timestamp": float(time.time()),
             "family": family,
             "variant": variant,
             "version": version,
             "arch": arch,
             "discnum": "1",
             "totaldiscs": "1",
             "packagedir": packagedir,
             "outfile": None }

    outfile = "%s/.treeinfo" % (outdir,)
    section = 'general'

    c = ConfigParser.ConfigParser()
    c.add_section(section)

    if not allDiscs:
        if discnum is not None:
            data["discnum"] = str(discnum)

        if totaldiscs is not None:
            data["totaldiscs"] = str(totaldiscs)

    try:
        f = open(outfile, "w")

        for key, value in data.items():
            c.set(section, key, value)

        c.write(f)
        f.close()
    except:
        return False

    return True
