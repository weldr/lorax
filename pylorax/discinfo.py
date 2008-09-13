#
# pylorax discinfo module
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

import os
import time

# Write out the .discinfo file
def write(release=None, arch=None, outdir=None, disc=None):
    """write(release=None, arch=None, outdir=None, [disc=None])

    Write the .discinfo file to the specified directory (outdir).
    The release string is specified as release and the architecture
    is specified as arch.  If disc is specified, it will be written
    as the disc number, otherwise 0 is written for the disc number.

    The release, arch, and outdir parameters are all required.

    """

    if release is None or arch is None or outdir is None:
        return False

    if not os.path.isdir(outdir):
        return False

    outfile = "%s/.discinfo" % (outdir,)

    try:
        f = open(outfile, "w")
        f.write("%s\n", time.time())
        f.write("%s\n", release)
        f.write("%s\n", arch)

        if disc is not None:
            f.write("%d\n", disc)
        else:
            f.write("0\n")

        f.close()
    except:
        return False

    return True
