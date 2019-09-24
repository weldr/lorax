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

from composer.cli.blueprints import blueprints_cmd
from composer.cli.modules import modules_cmd
from composer.cli.projects import projects_cmd
from composer.cli.compose import compose_cmd
from composer.cli.sources import sources_cmd
from composer.cli.status import status_cmd
from composer.cli.upload import upload_cmd
from composer.cli.providers import providers_cmd

command_map = {
    "blueprints": blueprints_cmd,
    "modules":    modules_cmd,
    "projects":   projects_cmd,
    "compose":    compose_cmd,
    "sources":    sources_cmd,
    "status":     status_cmd,
    "upload":     upload_cmd,
    "providers":  providers_cmd
    }


def main(opts):
    """ Main program execution

    :param opts: Cmdline arguments
    :type opts: argparse.Namespace
    """

    # Making sure opts.args is not empty (thus, has a command and subcommand)
    # is already handled in src/bin/composer-cli.
    if opts.args[0] not in command_map:
        log.error("Unknown command %s", opts.args[0])
        return 1
    else:
        try:
            return command_map[opts.args[0]](opts)
        except Exception as e:
            log.error(str(e))
            return 1
