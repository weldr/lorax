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
import os

from pylorax.api.recipes import recipe_filename, recipe_from_toml, RecipeFileError
from pylorax.sysutils import joinpaths


def workspace_dir(repo, branch):
    """Create the workspace's path from a Repository and branch

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :returns: The path to the branch's workspace directory
    :rtype: str

    """
    repo_path = repo.get_location().get_path()
    return joinpaths(repo_path, "workspace", branch)


def workspace_read(repo, branch, recipe_name):
    """Read a Recipe from the branch's workspace

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param recipe_name: The name of the recipe
    :type recipe_name: str
    :returns: The workspace copy of the recipe, or None if it doesn't exist
    :rtype: Recipe or None
    :raises: RecipeFileError
    """
    ws_dir = workspace_dir(repo, branch)
    if not os.path.isdir(ws_dir):
        os.makedirs(ws_dir)
    filename = joinpaths(ws_dir, recipe_filename(recipe_name))
    if not os.path.exists(filename):
        return None
    try:
        f = open(filename, 'rb')
        recipe = recipe_from_toml(f.read().decode("UTF-8"))
    except IOError:
        raise RecipeFileError
    return recipe


def workspace_write(repo, branch, recipe):
    """Write a recipe to the workspace

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param recipe: The recipe to write to the workspace
    :type recipe: Recipe
    :returns: None
    :raises: IO related errors
    """
    ws_dir = workspace_dir(repo, branch)
    if not os.path.isdir(ws_dir):
        os.makedirs(ws_dir)
    filename = joinpaths(ws_dir, recipe.filename)
    open(filename, 'wb').write(recipe.toml().encode("UTF-8"))


def workspace_delete(repo, branch, recipe_name):
    """Delete the recipe from the workspace

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param recipe_name: The name of the recipe
    :type recipe_name: str
    :returns: None
    :raises: IO related errors
    """
    ws_dir = workspace_dir(repo, branch)
    filename = joinpaths(ws_dir, recipe_filename(recipe_name))
    if os.path.exists(filename):
        os.unlink(filename)
