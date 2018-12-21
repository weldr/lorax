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
from pytoml import TomlError
import shutil
import tempfile
import unittest

import pylorax.api.recipes as recipes
from pylorax.api.compose import add_customizations
from pylorax.sysutils import joinpaths

from pykickstart.parser import KickstartParser
from pykickstart.version import makeVersion

class BasicRecipeTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # Input toml is in .toml and python dict string is in .dict
        input_recipes = [("full-recipe.toml", "full-recipe.dict"),
                         ("minimal.toml", "minimal.dict"),
                         ("modules-only.toml", "modules-only.dict"),
                         ("packages-only.toml", "packages-only.dict"),
                         ("groups-only.toml", "groups-only.dict"),
                         ("custom-base.toml", "custom-base.dict")]
        results_path = "./tests/pylorax/results/"
        self.input_toml = []
        for (recipe_toml, recipe_dict) in input_recipes:
            with open(joinpaths(results_path, recipe_toml)) as f_toml:
                with open(joinpaths(results_path, recipe_dict)) as f_dict:
                    # XXX Warning, can run arbitrary code
                    result_dict = eval(f_dict.read())
                self.input_toml.append((f_toml.read(), result_dict))

        self.old_modules = [recipes.RecipeModule("toml", "2.1"),
                            recipes.RecipeModule("bash", "4.*"),
                            recipes.RecipeModule("httpd", "3.7.*")]
        self.old_packages = [recipes.RecipePackage("python", "2.7.*"),
                             recipes.RecipePackage("parted", "3.2")]
        self.old_groups = [recipes.RecipeGroup("backup-client"),
                           recipes.RecipeGroup("base")]
        self.new_modules = [recipes.RecipeModule("toml", "2.1"),
                            recipes.RecipeModule("httpd", "3.8.*"),
                            recipes.RecipeModule("openssh", "2.8.1")]
        self.new_packages = [recipes.RecipePackage("python", "2.7.*"),
                             recipes.RecipePackage("parted", "3.2"),
                             recipes.RecipePackage("git", "2.13.*")]
        self.new_groups = [recipes.RecipeGroup("console-internet"),
                           recipes.RecipeGroup("base")]
        self.modules_result = [{"new": {"Modules": {"version": "2.8.1", "name": "openssh"}},
                                "old": None},
                               {"new": None,
                                "old": {"Modules": {"name": "bash", "version": "4.*"}}},
                               {"new": {"Modules": {"version": "3.8.*", "name": "httpd"}},
                                "old": {"Modules": {"version": "3.7.*", "name": "httpd"}}}]
        self.packages_result = [{"new": {"Packages": {"name": "git", "version": "2.13.*"}}, "old": None}]
        self.groups_result = [{'new': {'Groups': {'name': 'console-internet'}}, 'old': None},
                              {'new': None, 'old': {'Groups': {'name': 'backup-client'}}}]


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

        with self.assertRaises(recipes.RecipeError):
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
        recipe = recipes.Recipe("test-recipe", "A recipe used for testing", None, None, None, None)
        new_version = recipe.bump_version(None)
        self.assertEqual(new_version, "0.0.1")

        # Original has a version, new does not
        recipe = recipes.Recipe("test-recipe", "A recipe used for testing", None, None, None, None)
        new_version = recipe.bump_version("0.0.1")
        self.assertEqual(new_version, "0.0.2")

        # Original has no version, new does
        recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.0", None, None, None)
        new_version = recipe.bump_version(None)
        self.assertEqual(new_version, "0.1.0")

        # New and Original are the same
        recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.0.1", None, None, None)
        new_version = recipe.bump_version("0.0.1")
        self.assertEqual(new_version, "0.0.2")

        # New is different from Original
        recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", None, None, None)
        new_version = recipe.bump_version("0.0.1")
        self.assertEqual(new_version, "0.1.1")

    def find_name_test(self):
        """Test the find_name function"""
        test_list = [{"name":"dog"}, {"name":"cat"}, {"name":"squirrel"}]

        self.assertEqual(recipes.find_name("dog", test_list), {"name":"dog"})
        self.assertEqual(recipes.find_name("cat", test_list), {"name":"cat"})
        self.assertEqual(recipes.find_name("squirrel", test_list), {"name":"squirrel"})

        self.assertIsNone(recipes.find_name("alien", test_list))

    def diff_items_test(self):
        """Test the diff_items function"""
        self.assertEqual(recipes.diff_items("Modules", self.old_modules, self.new_modules), self.modules_result)
        self.assertEqual(recipes.diff_items("Packages", self.old_packages, self.new_packages), self.packages_result)
        self.assertEqual(recipes.diff_items("Groups", self.old_groups, self.new_groups), self.groups_result)

    def recipe_diff_test(self):
        """Test the recipe_diff function"""
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", self.old_modules, self.old_packages, [])
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", self.new_modules, self.new_packages, [])
        result = [{'new': {'Version': '0.3.1'}, 'old': {'Version': '0.1.1'}},
                  {'new': {'Module': {'name': 'openssh', 'version': '2.8.1'}}, 'old': None},
                  {'new': None, 'old': {'Module': {'name': 'bash', 'version': '4.*'}}},
                  {'new': {'Module': {'name': 'httpd', 'version': '3.8.*'}},
                   'old': {'Module': {'name': 'httpd', 'version': '3.7.*'}}},
                  {'new': {'Package': {'name': 'git', 'version': '2.13.*'}}, 'old': None}]
        self.assertEqual(recipes.recipe_diff(old_recipe, new_recipe), result)

class GitRecipesTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.repo_dir = tempfile.mkdtemp(prefix="lorax.test.repo.")
        self.repo = recipes.open_or_create_repo(self.repo_dir)

        self.results_path = "./tests/pylorax/results/"
        self.examples_path = "./tests/pylorax/blueprints/"
        self.new_recipe = os.path.join(self.examples_path, 'python-testing.toml')

    @classmethod
    def tearDownClass(self):
        if self.repo is not None:
            del self.repo
        shutil.rmtree(self.repo_dir)

    def tearDown(self):
        if os.path.exists(self.new_recipe):
            os.remove(self.new_recipe)

    def _create_another_recipe(self):
        open(self.new_recipe, 'w').write("""name = "python-testing"
description = "A recipe used during testing."
version = "0.0.1"

[[packages]]
name = "python"
version = "2.7.*"
""")

    def test_01_repo_creation(self):
        """Test that creating the repository succeeded"""
        self.assertNotEqual(self.repo, None)

    def test_02_commit_recipe(self):
        """Test committing a Recipe object"""
        recipe = recipes.Recipe("test-recipe", "A recipe used for testing", None, None, None, None)
        oid = recipes.commit_recipe(self.repo, "master", recipe)
        self.assertNotEqual(oid, None)

    def test_03_list_recipe(self):
        """Test listing recipe commits"""
        commits = recipes.list_commits(self.repo, "master", "test-recipe.toml")
        self.assertEqual(len(commits), 1, "Wrong number of commits.")
        self.assertEqual(commits[0].message, "Recipe test-recipe, version 0.0.1 saved.")
        self.assertNotEqual(commits[0].timestamp, None, "Timestamp is None")
        self.assertEqual(len(commits[0].commit), 40, "Commit hash isn't 40 characters")
        self.assertEqual(commits[0].revision, None, "revision is not None")

    def test_03_list_commits_commit_time_val_error(self):
        """Test listing recipe commits which raise CommitTimeValError"""
        with mock.patch('pylorax.api.recipes.GLib.DateTime.to_timeval', return_value=False):
            commits = recipes.list_commits(self.repo, "master", "test-recipe.toml")
        self.assertEqual(len(commits), 0, "Wrong number of commits.")

    def test_04_commit_recipe_file(self):
        """Test committing a TOML file"""
        recipe_path = joinpaths(self.results_path, "full-recipe.toml")
        oid = recipes.commit_recipe_file(self.repo, "master", recipe_path)
        self.assertNotEqual(oid, None)

        commits = recipes.list_commits(self.repo, "master", "http-server.toml")
        self.assertEqual(len(commits), 1, "Wrong number of commits: %s" % commits)

    def test_04_commit_recipe_file_handles_internal_ioerror(self):
        """Test committing a TOML raises RecipeFileError on internal IOError"""
        recipe_path = joinpaths(self.results_path, "non-existing-file.toml")
        with self.assertRaises(recipes.RecipeFileError):
            recipes.commit_recipe_file(self.repo, "master", recipe_path)

    def test_05_commit_toml_dir(self):
        """Test committing a directory of TOML files"""
        # first verify that the newly created file isn't present
        old_commits = recipes.list_commits(self.repo, "master", "python-testing.toml")
        self.assertEqual(len(old_commits), 0, "Wrong number of commits: %s" % old_commits)

        # then create it and commit the entire directory
        self._create_another_recipe()
        recipes.commit_recipe_directory(self.repo, "master", self.examples_path)

        # verify that the newly created file is already in the repository
        new_commits = recipes.list_commits(self.repo, "master", "python-testing.toml")
        self.assertEqual(len(new_commits), 1, "Wrong number of commits: %s" % new_commits)
        # again make sure new_commits != old_commits
        self.assertGreater(len(new_commits), len(old_commits),
                           "New commits shoud differ from old commits")

    def test_05_commit_recipe_directory_handling_internal_exceptions(self):
        """Test committing a directory of TOML files while handling internal exceptions"""
        # first verify that the newly created file isn't present
        old_commits = recipes.list_commits(self.repo, "master", "python-testing.toml")
        self.assertEqual(len(old_commits), 0, "Wrong number of commits: %s" % old_commits)

        # then create it and commit the entire directory
        self._create_another_recipe()

        # try to commit while raising RecipeFileError
        with mock.patch('pylorax.api.recipes.commit_recipe_file', side_effect=recipes.RecipeFileError('TESTING')):
            recipes.commit_recipe_directory(self.repo, "master", self.examples_path)

        # try to commit while raising TomlError
        with mock.patch('pylorax.api.recipes.commit_recipe_file', side_effect=TomlError('TESTING', 0, 0, '__test__')):
            recipes.commit_recipe_directory(self.repo, "master", self.examples_path)

        # verify again that the newly created file isn't present b/c we raised an exception
        new_commits = recipes.list_commits(self.repo, "master", "python-testing.toml")
        self.assertEqual(len(new_commits), 0, "Wrong number of commits: %s" % new_commits)

    def test_06_read_recipe(self):
        """Test reading a recipe from a commit"""
        commits = recipes.list_commits(self.repo, "master", "example-http-server.toml")
        self.assertEqual(len(commits), 1, "Wrong number of commits: %s" % commits)

        recipe = recipes.read_recipe_commit(self.repo, "master", "example-http-server")
        self.assertNotEqual(recipe, None)
        self.assertEqual(recipe["name"], "example-http-server")

        # Read by commit id
        recipe = recipes.read_recipe_commit(self.repo, "master", "example-http-server", commits[0].commit)
        self.assertNotEqual(recipe, None)
        self.assertEqual(recipe["name"], "example-http-server")

        # Read the recipe and its commit id
        (commit_id, recipe) = recipes.read_recipe_and_id(self.repo, "master", "example-http-server", commits[0].commit)
        self.assertEqual(commit_id, commits[0].commit)

    def test_07_tag_commit(self):
        """Test tagging the most recent commit of a recipe"""
        result = recipes.tag_file_commit(self.repo, "master", "not-a-file")
        self.assertEqual(result, None)

        result = recipes.tag_recipe_commit(self.repo, "master", "example-http-server")
        self.assertNotEqual(result, None)

        commits = recipes.list_commits(self.repo, "master", "example-http-server.toml")
        self.assertEqual(len(commits), 1, "Wrong number of commits: %s" % commits)
        self.assertEqual(commits[0].revision, 1)

    def test_08_delete_recipe(self):
        """Test deleting a file from a branch"""
        oid = recipes.delete_recipe(self.repo, "master", "example-http-server")
        self.assertNotEqual(oid, None)

        master_files = recipes.list_branch_files(self.repo, "master")
        self.assertEqual("example-http-server.toml" in master_files, False)

    def test_09_revert_commit(self):
        """Test reverting a file on a branch"""
        commits = recipes.list_commits(self.repo, "master", "example-http-server.toml")
        revert_to = commits[0].commit
        oid = recipes.revert_recipe(self.repo, "master", "example-http-server", revert_to)
        self.assertNotEqual(oid, None)

        commits = recipes.list_commits(self.repo, "master", "example-http-server.toml")
        self.assertEqual(len(commits), 2, "Wrong number of commits: %s" % commits)
        self.assertEqual(commits[0].message, "example-http-server.toml reverted to commit %s" % revert_to)

    def test_10_tag_new_commit(self):
        """Test tagging a newer commit of a recipe"""
        recipe = recipes.read_recipe_commit(self.repo, "master", "example-http-server")
        recipe["description"] = "A modified description"
        oid = recipes.commit_recipe(self.repo, "master", recipe)
        self.assertNotEqual(oid, None)

        # Tag the new commit
        result = recipes.tag_recipe_commit(self.repo, "master", "example-http-server")
        self.assertNotEqual(result, None)

        commits = recipes.list_commits(self.repo, "master", "example-http-server.toml")
        self.assertEqual(len(commits), 3, "Wrong number of commits: %s" % commits)
        self.assertEqual(commits[0].revision, 2)


class ExistingGitRepoRecipesTest(GitRecipesTest):
    @classmethod
    def setUpClass(self):
        # will initialize the git repository in the parent class
        super(ExistingGitRepoRecipesTest, self).setUpClass()

        # reopen the repository again so that tests are executed
        # against the existing repo one more time.
        self.repo = recipes.open_or_create_repo(self.repo_dir)


class GetRevisionFromTagTests(unittest.TestCase):
    def test_01_valid_tag(self):
        revision = recipes.get_revision_from_tag('branch/filename/r123')
        self.assertEqual(123, revision)

    def test_02_invalid_tag_not_a_number(self):
        revision = recipes.get_revision_from_tag('branch/filename/rABC')
        self.assertIsNone(revision)

    def test_02_invalid_tag_missing_revision_string(self):
        revision = recipes.get_revision_from_tag('branch/filename/mybranch')
        self.assertIsNone(revision)

class CustomizationsTests(unittest.TestCase):
    @staticmethod
    def _blueprint_to_ks(blueprint_data):
        recipe_obj = recipes.recipe_from_toml(blueprint_data)
        ks = KickstartParser(makeVersion())

        # write out the customization data, and parse the resulting kickstart
        with tempfile.NamedTemporaryFile(prefix="lorax.test.customizations", mode="w") as f:
            add_customizations(f, recipe_obj)
            f.flush()
            ks.readKickstart(f.name)

        return ks

    @staticmethod
    def _find_user(ks, username):
        for user in ks.handler.user.userList:
            if user.name == username:
                return user
        else:
            return None

    @staticmethod
    def _find_sshkey(ks, username):
        for key in ks.handler.sshkey.sshUserList:
            if key.username == username:
                return key
        else:
            return None

    @staticmethod
    def _find_group(ks, groupname):
        for group in ks.handler.group.groupList:
            if group.name == groupname:
                return group
        else:
            return None

    def test_hostname(self):
        blueprint_data = """name = "test-hostname"
description = "test recipe"
version = "0.0.1"

[customizations]
hostname = "testy.example.com"
"""
        ks = self._blueprint_to_ks(blueprint_data)
        self.assertEqual(ks.handler.network.hostname, "testy.example.com")

    def test_hostname_list(self):
        """Test that the hostname still works when using [[customizations]] instead of [customizations]"""

        blueprint_data = """name = "test-hostname-list"
description = "test recipe"
version = "0.0.1"

[[customizations]]
hostname = "testy.example.com"
"""
        ks = self._blueprint_to_ks(blueprint_data)
        self.assertEqual(ks.handler.network.hostname, "testy.example.com")

    def test_user(self):
        blueprint_data = """name = "test-user"
description = "test recipe"
version = "0.0.1"

[[customizations.user]]
name = "admin"
description = "Widget admin account"
password = "$6$CHO2$3rN8eviE2t50lmVyBYihTgVRHcaecmeCk31LeOUleVK/R/aeWVHVZDi26zAH.o0ywBKH9Tc0/wm7sW/q39uyd1"
home = "/srv/widget/"
shell = "/usr/bin/bash"
groups = ["widget", "users", "students"]
uid = 1200

[[customizations.user]]
name = "bart"
key = "SSH KEY FOR BART"
groups = ["students"]
"""

        ks = self._blueprint_to_ks(blueprint_data)

        admin = self._find_user(ks, "admin")
        self.assertIsNotNone(admin)
        self.assertEqual(admin.name, "admin")
        self.assertEqual(admin.password, "$6$CHO2$3rN8eviE2t50lmVyBYihTgVRHcaecmeCk31LeOUleVK/R/aeWVHVZDi26zAH.o0ywBKH9Tc0/wm7sW/q39uyd1")
        self.assertEqual(admin.homedir, "/srv/widget/")
        self.assertEqual(admin.shell, "/usr/bin/bash")
        # order is unimportant, so use a set instead of comparing lists directly
        self.assertEqual(set(admin.groups), {"widget", "users", "students"})
        self.assertEqual(admin.uid, 1200)

        bart = self._find_user(ks, "bart")
        self.assertIsNotNone(bart)
        self.assertEqual(bart.name, "bart")
        self.assertEqual(bart.groups, ["students"])

        bartkey = self._find_sshkey(ks, "bart")
        self.assertIsNotNone(bartkey)
        self.assertEqual(bartkey.username, "bart")
        self.assertEqual(bartkey.key, "SSH KEY FOR BART")

    def test_group(self):
        blueprint_data = """name = "test-group"
description = "test recipe"
version = "0.0.1"

[[customizations.group]]
name = "widget"

[[customizations.group]]
name = "students"
"""

        ks = self._blueprint_to_ks(blueprint_data)

        widget = self._find_group(ks, "widget")
        self.assertIsNotNone(widget)

        students = self._find_group(ks, "students")
        self.assertIsNotNone(students)

    def test_full(self):
        blueprint_data = """name = "custom-base"
description = "A base system with customizations"
version = "0.0.1"
modules = []
groups = []

[[packages]]
name = "bash"
version = "4.4.*"

[[customizations]]
hostname = "custom-base"

[[customizations.sshkey]]
user = "root"
key = "ssh-rsa"

[[customizations.user]]
name = "widget"
description = "Widget process user account"
home = "/srv/widget/"
shell = "/usr/bin/false"
groups = ["dialout", "users"]

[[customizations.user]]
name = "admin"
description = "Widget admin account"
password = ""
home = "/srv/widget/"
shell = "/usr/bin/bash"
groups = ["widget", "users", "students"]
uid = 1200

[[customizations.user]]
name = "plain"
password = "password"

[[customizations.user]]
name = "bart"
key = ""
groups = ["students"]

[[customizations.group]]
name = "widget"

[[customizations.group]]
name = "students"
"""
        ks = self._blueprint_to_ks(blueprint_data)

        self.assertEqual(ks.handler.network.hostname, "custom-base")

        rootkey = self._find_sshkey(ks, "root")
        self.assertIsNotNone(rootkey)
        self.assertEqual(rootkey.username, "root")
        self.assertEqual(rootkey.key, "ssh-rsa")

        widget = self._find_user(ks, "widget")
        self.assertIsNotNone(widget)
        self.assertEqual(widget.name, "widget")
        self.assertEqual(widget.homedir, "/srv/widget/")
        self.assertEqual(widget.shell, "/usr/bin/false")
        self.assertEqual(set(widget.groups), {"dialout", "users"})

        admin = self._find_user(ks, "admin")
        self.assertIsNotNone(admin)
        self.assertEqual(admin.name, "admin")
        self.assertEqual(admin.password, "")
        self.assertEqual(admin.homedir, "/srv/widget/")
        self.assertEqual(admin.shell, "/usr/bin/bash")
        self.assertEqual(set(admin.groups), {"widget", "users", "students"})
        self.assertEqual(admin.uid, 1200)

        plain = self._find_user(ks, "plain")
        self.assertIsNotNone(plain)
        self.assertEqual(plain.name, "plain")
        self.assertEqual(plain.password, "password")

        # widget does not appear as a separate group line, since a widget
        # group is created for the widget user
        widgetGroup = self._find_group(ks, "widget")
        self.assertIsNone(widgetGroup)

        studentsGroup = self._find_group(ks, "students")
        self.assertIsNotNone(studentsGroup)
        self.assertEqual(studentsGroup.name, "students")
