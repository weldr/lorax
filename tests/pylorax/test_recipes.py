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
from pytoml import TomlError
import shutil
import tempfile
import unittest

import pylorax.api.recipes as recipes
from pylorax.sysutils import joinpaths

class BasicRecipeTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # Input toml is in .toml and python dict string is in .dict
        input_recipes = [("full-recipe.toml", "full-recipe.dict"),
                         ("minimal.toml", "minimal.dict"),
                         ("modules-only.toml", "modules-only.dict"),
                         ("packages-only.toml", "packages-only.dict")]
        results_path = "./tests/pylorax/results/"
        self.input_toml = []
        for (recipe_toml, recipe_dict) in input_recipes:
            with open(joinpaths(results_path, recipe_toml)) as f_toml:
                with open(joinpaths(results_path, recipe_dict)) as f_dict:
                    # XXX Warning, can run arbitrary code
                    result_dict = eval(f_dict.read())
                self.input_toml.append((f_toml.read(), result_dict))

    @classmethod
    def tearDownClass(self):
        pass

    def toml_to_recipe_test(self):
        """Test converting the TOML string to a Recipe object"""
        for (toml_str, recipe_dict) in self.input_toml:
            result = recipes.recipe_from_toml(toml_str)
            self.assertEqual(result, recipe_dict)

    def toml_to_recipe_fail_test(self):
        """Test trying to convert a non-TOML string to a Recipe"""
        with self.assertRaises(TomlError):
            recipes.recipe_from_toml("This is not a TOML string\n")

        with self.assertRaises(recipes.RecipeTOMLError):
            recipes.recipe_from_toml('name = "a failed toml string"\n')

    def recipe_to_toml_test(self):
        """Test converting a Recipe object to a TOML string"""
        # In order to avoid problems from matching strings we convert to TOML and
        # then back so compare the Recipes.
        for (toml_str, _recipe_dict) in self.input_toml:
            # This is tested in toml_to_recipe
            recipe_1 = recipes.recipe_from_toml(toml_str)
            # Convert the Recipe to TOML and then back to a Recipe
            toml_2 = recipe_1.toml()
            recipe_2 = recipes.recipe_from_toml(toml_2)
            self.assertEqual(recipe_1, recipe_2)

    def recipe_bump_version_test(self):
        """Test the Recipe's version bump function"""

        # Neither have a version
        recipe = recipes.Recipe("test-recipe", "A recipe used for testing", None, None, None)
        new_version = recipe.bump_version(None)
        self.assertEqual(new_version, "0.0.1")

        # Original has a version, new does not
        recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.0.1", None, None)
        new_version = recipe.bump_version(None)
        self.assertEqual(new_version, "0.0.2")

        # Original has no version, new does
        recipe = recipes.Recipe("test-recipe", "A recipe used for testing", None, None, None)
        new_version = recipe.bump_version("0.1.0")
        self.assertEqual(new_version, "0.1.0")

        # New and Original are the same
        recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.0.1", None, None)
        new_version = recipe.bump_version("0.0.1")
        self.assertEqual(new_version, "0.0.2")

        # New is different from Original
        recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.0.1", None, None)
        new_version = recipe.bump_version("0.1.1")
        self.assertEqual(new_version, "0.1.1")


class GitRecipesTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.repo_dir = tempfile.mkdtemp(prefix="lorax.test.repo.")
        self.repo = recipes.open_or_create_repo(self.repo_dir)

        self.results_path = "./tests/pylorax/results/"
        self.examples_path = "./tests/pylorax/recipes/"

    @classmethod
    def tearDownClass(self):
        if self.repo is not None:
            del self.repo
        shutil.rmtree(self.repo_dir)

    def test_01_repo_creation(self):
        """Test that creating the repository succeeded"""
        self.assertNotEqual(self.repo, None)

    def test_02_commit_recipe(self):
        """Test committing a Recipe object"""
        recipe = recipes.Recipe("test-recipe", "A recipe used for testing", None, None, None)
        oid = recipes.commit_recipe(self.repo, "master", recipe, "0.1.0")
        self.assertNotEqual(oid, None)

    def test_03_list_recipe(self):
        """Test listing recipe commits"""
        commits = recipes.list_commits(self.repo, "master", "test-recipe.toml")
        self.assertEqual(len(commits), 1, "Wrong number of commits.")
        self.assertEqual(commits[0].message, "Recipe test-recipe, version 0.1.0 saved.")
        self.assertNotEqual(commits[0].timestamp, None, "Timestamp is None")
        self.assertEqual(len(commits[0].commit), 40, "Commit hash isn't 40 characters")
        self.assertEqual(commits[0].revision, None, "revision is not None")

    def test_04_commit_toml_file(self):
        """Test committing a TOML file"""
        recipe_path = joinpaths(self.results_path, "full-recipe.toml")
        oid = recipes.commit_recipe_file(self.repo, "master", recipe_path)
        self.assertNotEqual(oid, None)

        commits = recipes.list_commits(self.repo, "master", "http-server.toml")
        self.assertEqual(len(commits), 1, "Wrong number of commits: %s" % commits)

    def test_05_commit_toml_dir(self):
        """Test committing a directory of TOML files"""
        # It worked if it doesn't raise errors
        recipes.commit_recipe_directory(self.repo, "master", self.examples_path)

    def test_06_read_recipe(self):
        """Test reading a recipe from a commit"""
        commits = recipes.list_commits(self.repo, "master", "http-server.toml")
        self.assertEqual(len(commits), 1, "Wrong number of commits: %s" % commits)

        recipe = recipes.read_recipe_commit(self.repo, "master", "http-server.toml")
        self.assertNotEqual(recipe, None)
        self.assertEqual(recipe["name"], "http-server")

        # Read by commit id
        recipe = recipes.read_recipe_commit(self.repo, "master", "http-server.toml", commits[0].commit)
        self.assertNotEqual(recipe, None)
        self.assertEqual(recipe["name"], "http-server")

    def test_07_tag_commit(self):
        """Test tagging the most recent commit of a recipe"""
        result = recipes.tag_file_commit(self.repo, "master", "not-a-file")
        self.assertEqual(result, None)

        result = recipes.tag_file_commit(self.repo, "master", "http-server.toml")
        self.assertNotEqual(result, None)

        commits = recipes.list_commits(self.repo, "master", "http-server.toml")
        self.assertEqual(len(commits), 1, "Wrong number of commits: %s" % commits)
        self.assertEqual(commits[0].revision, 1)

    def test_08_delete_recipe(self):
        """Test deleting a file from a branch"""
        oid = recipes.delete_file(self.repo, "master", "http-server.toml")
        self.assertNotEqual(oid, None)

        master_files = recipes.list_branch_files(self.repo, "master")
        self.assertEqual("http-server.toml" in master_files, False)

    def test_09_revert_commit(self):
        """Test reverting a file on a branch"""
        commits = recipes.list_commits(self.repo, "master", "http-server.toml")
        revert_to = commits[0].commit
        oid = recipes.revert_file(self.repo, "master", "http-server.toml", revert_to)
        self.assertNotEqual(oid, None)

        commits = recipes.list_commits(self.repo, "master", "http-server.toml")
        self.assertEqual(len(commits), 2, "Wrong number of commits: %s" % commits)
        self.assertEqual(commits[0].message, "Recipe http-server.toml reverted to commit %s" % revert_to)

    def test_10_tag_new_commit(self):
        """Test tagging a newer commit of a recipe"""
        recipe = recipes.read_recipe_commit(self.repo, "master", "http-server.toml")
        recipe["description"] = "A modified description"
        oid = recipes.commit_recipe(self.repo, "master", recipe, "0.1.0")
        self.assertNotEqual(oid, None)

        # Tag the new commit
        result = recipes.tag_file_commit(self.repo, "master", "http-server.toml")
        self.assertNotEqual(result, None)

        commits = recipes.list_commits(self.repo, "master", "http-server.toml")
        self.assertEqual(len(commits), 3, "Wrong number of commits: %s" % commits)
        self.assertEqual(commits[0].revision, 2)
