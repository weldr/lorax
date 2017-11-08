#
# Copyright (C) 2017  Red Hat, Inc.
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
from flask import jsonify, request

# Use pykickstart to calculate disk image size
from pykickstart.parser import KickstartParser
from pykickstart.version import makeVersion, RHEL7

from pylorax.api.crossdomain import crossdomain
from pylorax.api.recipes import list_branch_files
from pylorax.creator import DRACUT_DEFAULT, mount_boot_part_over_root
from pylorax.creator import make_appliance, make_image, make_livecd, make_live_images
from pylorax.creator import make_runtime, make_squashfs
from pylorax.imgutils import copytree
from pylorax.imgutils import Mount, PartitionMount, umount
from pylorax.installer import InstallError
from pylorax.sysutils import joinpaths

# The API functions don't actually get called by any code here
# pylint: disable=unused-variable

# no-virt mode doesn't need libvirt, so make it optional
try:
    import libvirt
except ImportError:
    libvirt = None

def v0_api(api):
    """ Setup v0 of the API server"""
    @api.route("/api/v0/status")
    @crossdomain(origin="*")
    def v0_status():
        return jsonify(build="devel", api="0", db_version="0", schema_version="0", db_supported=False)

    @api.route("/api/v0/recipes/list")
    @crossdomain(origin="*")
    def v0_recipes_list():
        """List the available recipes on a branch."""
        try:
            limit = int(request.args.get("limit", "20"))
            offset = int(request.args.get("offset", "0"))
        except ValueError:
            # TODO return an error
            pass

        with api.config["GITLOCK"].lock:
            recipes = map(lambda f: f[:-5], list_branch_files(api.config["GITLOCK"].repo, "master"))
        return jsonify(recipes=recipes, limit=limit, offset=offset, total=len(recipes))
