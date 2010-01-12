#
# __init__.py
# function for loading action modules
#
# Copyright (C) 2009  Red Hat, Inc.
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
# Red Hat Author(s):  Martin Gracik <mgracik@redhat.com>
#

import sys
import os


def get_map():
    actions = {}

    root, actions_dir = os.path.split(os.path.dirname(__file__))

    sys.path.insert(0, root)

    modules = set()
    for filename in os.listdir(os.path.join(root, actions_dir)):
        if filename.endswith(".py") and not filename == "__init__.py":
            basename, extension = os.path.splitext(filename)
            modules.add(os.path.join(actions_dir, basename).replace("/", "."))

    for module in modules:
        imported = __import__(module, globals(), locals(), [module], -1)

        commands = getattr(imported, "COMMANDS", {})
        for command, classname in commands.items():
            actions[command] = getattr(imported, classname)

    sys.path.pop(0)

    return actions
