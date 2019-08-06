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
""" API utility functions
"""
from pylorax.api.recipes import RecipeError, RecipeFileError, read_recipe_commit

def take_limits(iterable, offset, limit):
    """ Apply offset and limit to an iterable object

    :param iterable: The object to limit
    :type iterable: iter
    :param offset: The number of items to skip
    :type offset: int
    :param limit: The total number of items to return
    :type limit: int
    :returns: A subset of the iterable
    """
    return iterable[offset:][:limit]

def blueprint_exists(api, branch, blueprint_name):
    """Return True if the blueprint exists

    :param api: flask object
    :type api: Flask
    :param branch: Branch name
    :type branch: str
    :param recipe_name: Recipe name to read
    :type recipe_name: str
    """
    try:
        with api.config["GITLOCK"].lock:
            read_recipe_commit(api.config["GITLOCK"].repo, branch, blueprint_name)

        return True
    except (RecipeError, RecipeFileError):
        return False
