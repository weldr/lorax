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

import pylorax.api.toml as toml


def _get_profile_path(ucfg, provider_name, profile, exists=True):
    """Helper to return the directory and path for a provider's profile file

    :param ucfg: upload config
    :type ucfg: object
    :param provider_name: the name of the cloud provider, e.g. "azure"
    :type provider_name: str
    :param profile: the name of the profile to save
    :type profile: str != ""
    :returns: Full path of the profile .toml file
    :rtype: str
    :raises: ValueError when passed invalid settings or an invalid profile name
    :raises: RuntimeError when the provider or profile couldn't be found
    """
    # Make sure no path elements are present
    profile = os.path.basename(profile)
    provider_name = os.path.basename(provider_name)
    if not profile:
        raise ValueError("Profile name cannot be empty!")
    if not provider_name:
        raise ValueError("Provider name cannot be empty!")

    directory = os.path.join(ucfg["settings_dir"], provider_name)
    # create the settings directory if it doesn't exist
    os.makedirs(directory, exist_ok=True)

    path = os.path.join(directory, f"{profile}.toml")
    if exists and not os.path.isfile(path):
        raise RuntimeError(f'Couldn\'t find profile "{profile}"!')

    return os.path.abspath(path)

def resolve_provider(ucfg, provider_name):
    """Get information about the specified provider as defined in that
    provider's `provider.toml`, including the provider's display name and expected
    settings.

    At a minimum, each setting has a display name (that likely differs from its
    snake_case name) and a type. Currently, there are two types of settings:
    string and boolean. String settings can optionally have a "placeholder"
    value for use on the front end and a "regex" for making sure that a value
    follows an expected pattern.

    :param ucfg: upload config
    :type ucfg: object
    :param provider_name: the name of the provider to look for
    :type provider_name: str
    :raises: RuntimeError when the provider couldn't be found
    :returns: the provider
    :rtype: dict
    """
    # Make sure no path elements are present
    provider_name = os.path.basename(provider_name)
    path = os.path.join(ucfg["providers_dir"], provider_name, "provider.toml")
    try:
        with open(path) as provider_file:
            provider = toml.load(provider_file)
    except OSError as error:
        raise RuntimeError(f'Couldn\'t find provider "{provider_name}"!') from error

    return provider


def load_profiles(ucfg, provider_name):
    """Return all settings profiles associated with a provider

    :param ucfg: upload config
    :type ucfg: object
    :param provider_name: name a provider to find profiles for
    :type provider_name: str
    :returns: a dict of settings dicts, keyed by profile name
    :rtype: dict
    """
    # Make sure no path elements are present
    provider_name = os.path.basename(provider_name)

    def load_path(path):
        with open(path) as file:
            return toml.load(file)

    def get_name(path):
        return os.path.splitext(os.path.basename(path))[0]

    paths = glob(os.path.join(ucfg["settings_dir"], provider_name, "*"))
    return {get_name(path): load_path(path) for path in paths}


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
    # Make sure no path elements are present
    provider_name = os.path.basename(provider_name)

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
    return sorted(os.path.basename(path) for path in paths)


def validate_settings(ucfg, provider_name, settings, image_name=None):
    """Raise a ValueError if any settings are invalid

    :param ucfg: upload config
    :type ucfg: object
    :param provider_name: the name of the provider to validate the settings against
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


def save_settings(ucfg, provider_name, profile, settings):
    """Save (and overwrite) settings for a given provider

    :param ucfg: upload config
    :type ucfg: object
    :param provider_name: the name of the cloud provider, e.g. "azure"
    :type provider_name: str
    :param profile: the name of the profile to save
    :type profile: str != ""
    :param settings: settings to save for that provider
    :type settings: dict
    :raises: ValueError when passed invalid settings or an invalid profile name
    """
    path = _get_profile_path(ucfg, provider_name, profile, exists=False)
    validate_settings(ucfg, provider_name, settings, image_name=None)

    # touch the TOML file if it doesn't exist
    if not os.path.isfile(path):
        open(path, "a").close()

    # make sure settings files aren't readable by others, as they will contain
    # sensitive credentials
    current = stat.S_IMODE(os.lstat(path).st_mode)
    os.chmod(path, current & ~stat.S_IROTH)

    with open(path, "w") as settings_file:
        toml.dump(settings, settings_file)

def load_settings(ucfg, provider_name, profile):
    """Load settings for a provider's profile

    :param ucfg: upload config
    :type ucfg: object
    :param provider_name: the name of the cloud provider, e.g. "azure"
    :type provider_name: str
    :param profile: the name of the profile to save
    :type profile: str != ""
    :returns: The profile settings for the selected provider
    :rtype: dict
    :raises: ValueError when passed invalid settings or an invalid profile name
    :raises: RuntimeError when the provider or profile couldn't be found
    :raises: ValueError when the passed settings are invalid

    This also calls validate_settings on the loaded settings, potentially
    raising an error if the saved settings are invalid.
    """
    path = _get_profile_path(ucfg, provider_name, profile)

    with open(path) as file:
        settings = toml.load(file)
    validate_settings(ucfg, provider_name, settings)
    return settings

def delete_profile(ucfg, provider_name, profile):
    """Delete a provider's profile settings file

    :param ucfg: upload config
    :type ucfg: object
    :param provider_name: the name of the cloud provider, e.g. "azure"
    :type provider_name: str
    :param profile: the name of the profile to save
    :type profile: str != ""
    :raises: ValueError when passed invalid settings or an invalid profile name
    :raises: RuntimeError when the provider or profile couldn't be found
    """
    path = _get_profile_path(ucfg, provider_name, profile)

    if os.path.exists(path):
        os.unlink(path)
