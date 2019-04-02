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
import sys
from contextlib import contextmanager
import magic
from io import StringIO

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

def this_is_rhel():
    """Check to see if the tests are running on RHEL
    """
    release = open("/etc/system-release", "r").read()
    return "Red Hat Enterprise Linux" in release
