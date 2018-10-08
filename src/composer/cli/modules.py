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

from composer import http_client as client
from composer.cli.help import modules_help
from composer.cli.utilities import handle_api_result

def modules_cmd(opts):
    """Process modules commands

    :param opts: Cmdline arguments
    :type opts: argparse.Namespace
    :returns: Value to return from sys.exit()
    :rtype: int
    """
    if opts.args[1] == "help" or opts.args[1] == "--help":
        print(modules_help)
        return 0
    elif opts.args[1] != "list":
        log.error("Unknown modules command: %s", opts.args[1])
        return 1

    api_route = client.api_url(opts.api_version, "/modules/list")
    result = client.get_url_json_unlimited(opts.socket, api_route)
    (rc, exit_now) = handle_api_result(result, opts.json)
    if exit_now:
        return rc

    # "list" should output a plain list of identifiers, one per line.
    print("\n".join(r["name"] for r in result["modules"]))

    return rc
