#!/usr/bin/python
#
# composer-cli
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
import logging
log = logging.getLogger("composer-cli")

from composer.cli.recipes import recipes_cmd
from composer.cli.modules import modules_cmd
from composer.cli.projects import projects_cmd
from composer.cli.compose import compose_cmd

command_map = {
    "recipes": recipes_cmd,
    "modules": modules_cmd,
    "projects": projects_cmd,
    "compose": compose_cmd
    }


def main(opts):
    """ Main program execution

    :param opts: Cmdline arguments
    :type opts: argparse.Namespace
    """
    if len(opts.args) > 0 and opts.args[0] in command_map:
        return command_map[opts.args[0]](opts)
    elif len(opts.args) == 0:
        log.error("Unknown command: %s", opts.args)
        return 1
    else:
        log.error("Unknown command: %s", opts.args)
        return 1
