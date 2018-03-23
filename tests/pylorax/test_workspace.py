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
import mock
import shutil
import tempfile
import unittest

import pylorax.api.recipes as recipes
from pylorax.api.workspace import workspace_dir, workspace_read, workspace_write, workspace_delete
from pylorax.sysutils import joinpaths

class WorkspaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.repo_dir = tempfile.mkdtemp(prefix="lorax.test.repo.")
        self.repo = recipes.open_or_create_repo(self.repo_dir)

        self.results_path = "./tests/pylorax/results/"
        self.examples_path = "./tests/pylorax/recipes/"

        recipe_path = joinpaths(self.examples_path, "http-server.toml")
        f = open(recipe_path, 'rb')
        self.example_recipe = recipes.recipe_from_toml(f.read())

    @classmethod
    def tearDownClass(self):
        if self.repo is not None:
            del self.repo
        shutil.rmtree(self.repo_dir)

    def test_01_repo_creation(self):
        """Test that creating the repository succeeded"""
        self.assertNotEqual(self.repo, None)

    def test_02_workspace_dir(self):
        """Test the workspace_dir function"""
        ws_dir = workspace_dir(self.repo, "master")
        self.assertEqual(ws_dir, joinpaths(self.repo_dir, "git", "workspace", "master"))

    def test_03_workspace_write(self):
        """Test the workspace_write function"""
        # Use an example recipe
        workspace_write(self.repo, "master", self.example_recipe)

        # The file should have ended up here
        ws_recipe_path = joinpaths(self.repo_dir, "git", "workspace", "master", "http-server.toml")
        self.assertEqual(os.path.exists(ws_recipe_path), True)

    def test_04_workspace_read(self):
        """Test the workspace_read function"""
        # The recipe was written by the workspace_write test. Read it and compare with the source recipe.
        recipe = workspace_read(self.repo, "master", "http-server")
        self.assertEqual(self.example_recipe, recipe)

    def test_04_workspace_read_ioerror(self):
        """Test the workspace_read function dealing with internal IOError"""
        # The recipe was written by the workspace_write test.
        with self.assertRaises(recipes.RecipeFileError):
            with mock.patch('pylorax.api.workspace.recipe_from_toml', side_effect=IOError('TESTING')):
                workspace_read(self.repo, "master", "http-server")

    def test_05_workspace_delete(self):
        """Test the workspace_delete function"""
        ws_recipe_path = joinpaths(self.repo_dir, "git", "workspace", "master", "http-server.toml")

        self.assertEqual(os.path.exists(ws_recipe_path), True)
        workspace_delete(self.repo, "master", "http-server")
        self.assertEqual(os.path.exists(ws_recipe_path), False)

    def test_05_workspace_delete_non_existing(self):
        """Test the workspace_delete function"""
        ws_recipe_path = joinpaths(self.repo_dir, "git", "workspace", "master", "non-existing.toml")

        workspace_delete(self.repo, "master", "non-existing")
        self.assertFalse(os.path.exists(ws_recipe_path))
