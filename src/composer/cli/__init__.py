#
# composer-cli
#
# Copyright (C) 2018-2019 Red Hat, Inc.
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

from composer import http_client as client
from composer.cli.blueprints import blueprints_cmd
from composer.cli.modules import modules_cmd
from composer.cli.projects import projects_cmd
from composer.cli.compose import compose_cmd, compose_cmd_v1
from composer.cli.sources import sources_cmd
from composer.cli.status import status_cmd


def upload_cmd_unavailable(opts):
    print("This command is not supported. You can upload images as part of the compose command")
    return 1

command_map = {
    "0": {
        "blueprints": blueprints_cmd,
        "modules":    modules_cmd,
        "projects":   projects_cmd,
        "compose":    compose_cmd,
        "sources":    sources_cmd,
        "status":     status_cmd
    },
    "1": {
        "blueprints": blueprints_cmd,
        "modules":    modules_cmd,
        "projects":   projects_cmd,
        "compose":    compose_cmd_v1,
        "sources":    sources_cmd,
        "status":     status_cmd,
        "upload":     upload_cmd_unavailable,
        "providers":  upload_cmd_unavailable
    }
}




def main(opts):
    """ Main program execution

    :param opts: Cmdline arguments
    :type opts: argparse.Namespace
    """
    # Detect and use the API server version if it is supported. Can be overridden by --api cmdline arg
    if opts.api_version is None:
        # Get the API version from the server, some commands are only available with newer releases
        result = client.get_url_json(opts.socket, "/api/status")
        # Get the api version and fall back to 0 if it fails.
        opts.api_version = result.get("api", "0")
        backend = result.get("backend", "unknown")

        if opts.api_version not in command_map:
            # If the server supports a newer version than composer-cli pick the highest version it does support
            # The server may not support this, but the command will handle the failure and output the server's error
            latest_version = sorted(command_map.keys())[-1]
            opts.api_version = latest_version
            print(f"WARNING: {backend} backend server supports newer API v{opts.api_version}, falling back to {latest_version}")

    # Making sure opts.args is not empty (thus, has a command and subcommand)
    # is already handled in src/bin/composer-cli.
    if opts.args[0] not in command_map[opts.api_version]:
        log.error("Unknown command %s for API v%s", opts.args[0], opts.api_version)
        return 1
    else:
        try:
            return command_map[opts.api_version][opts.args[0]](opts)
        except Exception as e:
            log.error(str(e))
            return 1
