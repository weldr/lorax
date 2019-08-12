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

import toml

class TomlError(toml.TomlDecodeError):
    pass

def loads(s):
    if isinstance(s, bytes):
        s = s.decode('utf-8')
    try:
        return toml.loads(s)
    except toml.TomlDecodeError as e:
        raise TomlError(e.msg, e.doc, e.pos)

def dumps(o):
    # strip the result, because `toml.dumps` adds a lot of newlines
    return toml.dumps(o, encoder=toml.TomlEncoder(dict)).strip()

def load(file):
    try:
        return toml.load(file)
    except toml.TomlDecodeError as e:
        raise TomlError(e.msg, e.doc, e.pos)

def dump(o, file):
    return toml.dump(o, file)
