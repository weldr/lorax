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
from pylorax.sysutils import joinpaths

def configure(conf):
    """Add lifted settings to the configuration

    :param conf: configuration object
    :type conf: ComposerConfig
    :returns: None

    This uses the composer.share_dir and composer.lib_dir as the base
    directories for the settings.
    """
    share_dir = conf.get("composer", "share_dir")
    lib_dir = conf.get("composer", "lib_dir")

    conf.add_section("upload")
    conf.set("upload", "providers_dir", joinpaths(share_dir, "/lifted/providers/"))
    conf.set("upload", "queue_dir", joinpaths(lib_dir, "/upload/queue/"))
    conf.set("upload", "settings_dir", joinpaths(lib_dir, "/upload/settings/"))
