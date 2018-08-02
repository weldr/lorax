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

import pytoml as toml
import time

from pylorax.sysutils import joinpaths

TS_CREATED  = "created"
TS_STARTED  = "started"
TS_FINISHED = "finished"

def write_timestamp(destdir, ty):
    path = joinpaths(destdir, "times.toml")

    try:
        contents = toml.loads(open(path, "r").read())
    except IOError:
        contents = toml.loads("")

    if ty == TS_CREATED:
        contents[TS_CREATED] = time.time()
    elif ty == TS_STARTED:
        contents[TS_STARTED] = time.time()
    elif ty == TS_FINISHED:
        contents[TS_FINISHED] = time.time()

    with open(path, "w") as f:
        f.write(toml.dumps(contents).encode("UTF-8"))

def timestamp_dict(destdir):
    path = joinpaths(destdir, "times.toml")

    try:
        return toml.loads(open(path, "r").read())
    except IOError:
        return toml.loads("")
