#
# Copyright (C) 2019 Red Hat, Inc.
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

from glob import glob
import os
import re
import stat

import toml


def resolve_provider(ucfg, provider_name):
    """Get information about the specified provider as defined in that
    provider's `provider.toml`, including the provider's display name and
    settings.

    At a minimum, each setting has a display name (that likely
    differs from its snake_case name), a type, and a saved value. Currently,
    there are two types of settings: string and boolean. String settings can
    optionally have a "placeholder" value for use on the front end and a
    "regex" for making sure that a value follows an expected pattern.

    :param ucfg: upload config
    :type ucfg: object
    :param provider_name: the name of the provider to look for
    :type provider_name: str
    :raises: RuntimeError when the provider couldn't be found
    :returns: the provider
    :rtype: dict
    """
    path = os.path.join(ucfg["providers_dir"], provider_name, "provider.toml")
    try:
        with open(path) as provider_file:
            provider = toml.load(provider_file)
    except OSError as error:
        raise RuntimeError(f'Couldn\'t find provider "{provider_name}"!') from error
    saved_settings = load_settings(ucfg, provider_name)
    for setting, info in provider["settings-info"].items():
        info["saved"] = saved_settings[setting] if setting in saved_settings else ""
    return provider


def resolve_playbook_path(ucfg, provider_name):
    """Given a provider's name, return the path to its playbook

    :param ucfg: upload config
    :type ucfg: object
    :param provider_name: the name of the provider to find the playbook for
    :type provider_name: str
    :raises: RuntimeError when the provider couldn't be found
    :returns: the path to the playbook
    :rtype: str
    """
    path = os.path.join(ucfg["providers_dir"], provider_name, "playbook.yaml")
    if not os.path.isfile(path):
        raise RuntimeError(f'Couldn\'t find playbook for "{provider_name}"!')
    return path


def list_providers(ucfg):
    """List the names of the available upload providers

    :param ucfg: upload config
    :type ucfg: object
    :returns: a list of all available provider_names
    :rtype: list of str
    """
    paths = glob(os.path.join(ucfg["providers_dir"], "*"))
    return [os.path.basename(path) for path in paths]


def _get_settings_path(ucfg, provider_name, write=False):
    directory = ucfg["settings_dir"]

    # create the upload_queue directory if it doesn't exist
    os.makedirs(directory, exist_ok=True)

    path = os.path.join(directory, f"{provider_name}.toml")
    if write and not os.path.isfile(path):
        open(path, "a").close()
    if os.path.exists(path):
        # make sure settings files aren't readable by others, as they will contain
        # sensitive credentials
        current = stat.S_IMODE(os.lstat(path).st_mode)
        os.chmod(path, current & ~stat.S_IROTH)
    return path


def validate_settings(ucfg, provider_name, settings, image_name=None):
    """Raise a ValueError if any settings are invalid

    :param ucfg: upload config
    :type ucfg: object
    :param provider_name: the name of the provider to validate the settings
    against
    :type provider_name: str
    :param settings: the settings to validate
    :type settings: dict
    :param image_name: optionally check whether an image_name is valid
    :type image_name: str
    :raises: ValueError when the passed settings are invalid
    :raises: RuntimeError when provider_name can't be found
    """
    if image_name == "":
        raise ValueError("Image name cannot be empty!")
    type_map = {"string": str, "boolean": bool}
    settings_info = resolve_provider(ucfg, provider_name)["settings-info"]
    for key, value in settings.items():
        if key not in settings_info:
            raise ValueError(f'Received unexpected setting: "{key}"!')
        setting_type = settings_info[key]["type"]
        correct_type = type_map[setting_type]
        if not isinstance(value, correct_type):
            raise ValueError(
                f'Expected a {correct_type} for "{key}", received a {type(value)}!'
            )
        if setting_type == "string" and "regex" in settings_info[key]:
            if not re.match(settings_info[key]["regex"], value):
                raise ValueError(f'Value "{value}" is invalid for setting "{key}"!')


def load_settings(ucfg, provider_name):
    """Load saved settings for a provider

    :param ucfg: upload config
    :type ucfg: object
    :param provider_name: the name of the cloud provider, e.g. "azure"
    :type provider_name: str
    :returns: the saved settings for that provider, or {} if no settings are
    saved
    :rtype: dict
    """
    path = _get_settings_path(ucfg, provider_name, write=False)
    if os.path.isfile(path):
        with open(path) as settings_file:
            return toml.load(settings_file)
    return {}


def save_settings(ucfg, provider_name, settings):
    """Save (and overwrite) settings for a given provider

    :param ucfg: upload config
    :type ucfg: object
    :param provider_name: the name of the cloud provider, e.g. "azure"
    :type provider_name: str
    :param settings: settings to save for that provider
    :type settings: dict
    :raises: ValueError when passed invalid settings
    """
    validate_settings(ucfg, provider_name, settings, image_name=None)
    settings_path = _get_settings_path(ucfg, provider_name, write=True)
    with open(settings_path, "w") as settings_file:
        toml.dump(settings, settings_file)
