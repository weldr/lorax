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
import shutil
import tempfile
from threading import Lock
import unittest

from flask import json
import pytoml as toml
from pylorax.api.config import configure, make_yum_dirs
from pylorax.api.recipes import open_or_create_repo, commit_recipe_directory
from pylorax.api.server import server, GitLock, YumLock
from pylorax.api.yumbase import get_base_object
from pylorax.sysutils import joinpaths

class ServerTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(self):
        repo_dir = tempfile.mkdtemp(prefix="lorax.test.repo.")
        server.config["REPO_DIR"] = repo_dir
        repo = open_or_create_repo(server.config["REPO_DIR"])
        server.config["GITLOCK"] = GitLock(repo=repo, lock=Lock(), dir=repo_dir)

        server.config["COMPOSER_CFG"] = configure(root_dir=repo_dir, test_config=True)
        make_yum_dirs(server.config["COMPOSER_CFG"])
        yb = get_base_object(server.config["COMPOSER_CFG"])
        server.config["YUMLOCK"] = YumLock(yb=yb, lock=Lock())

        server.config['TESTING'] = True
        self.server = server.test_client()

        self.examples_path = "./tests/pylorax/recipes/"

        # Import the example recipes
        commit_recipe_directory(server.config["GITLOCK"].repo, "master", self.examples_path)

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(server.config["REPO_DIR"])

    def test_00_hello(self):
        """Test /"""
        resp = self.server.get("/")
        self.assertEqual(resp.data, 'Hello, World!')

    def test_01_status(self):
        """Test the /api/v0/status route"""
        status_dict = {"build":"devel", "api":"0", "db_version":"0", "schema_version":"0", "db_supported":False}
        resp = self.server.get("/api/v0/status")
        data = json.loads(resp.data)
        self.assertEqual(data, status_dict)

    def test_02_recipes_list(self):
        """Test the /api/v0/recipes/list route"""
        list_dict = {"recipes":["atlas", "development", "glusterfs", "http-server", "jboss", "kubernetes"],
                     "limit":20, "offset":0, "total":6}
        resp = self.server.get("/api/v0/recipes/list")
        data = json.loads(resp.data)
        self.assertEqual(data, list_dict)

    def test_03_recipes_info(self):
        """Test the /api/v0/recipes/info route"""
        info_dict_1 = {"changes":[{"changed":False, "name":"http-server"}],
                       "errors":[],
                       "recipes":[{"description":"An example http server with PHP and MySQL support.",
                                   "modules":[{"name":"httpd", "version":"2.4.*"},
                                              {"name":"mod_auth_kerb", "version":"5.4"},
                                              {"name":"mod_ssl", "version":"2.4.*"},
                                              {"name":"php", "version":"5.4.*"},
                                              {"name": "php-mysql", "version":"5.4.*"}],
                                   "name":"http-server",
                                   "packages": [{"name":"openssh-server", "version": "6.6.*"},
                                                {"name": "rsync", "version": "3.0.*"},
                                                {"name": "tmux", "version": "2.2"}],
                                   "version": "0.0.1"}]}
        resp = self.server.get("/api/v0/recipes/info/http-server")
        data = json.loads(resp.data)
        self.assertEqual(data, info_dict_1)

        info_dict_2 = {"changes":[{"changed":False, "name":"glusterfs"},
                                  {"changed":False, "name":"http-server"}],
                       "errors":[],
                       "recipes":[{"description": "An example GlusterFS server with samba",
                                   "modules":[{"name":"glusterfs", "version":"3.7.*"},
                                              {"name":"glusterfs-cli", "version":"3.7.*"}],
                                   "name":"glusterfs",
                                   "packages":[{"name":"samba", "version":"4.2.*"}],
                                   "version": "0.0.1"},
                                  {"description":"An example http server with PHP and MySQL support.",
                                   "modules":[{"name":"httpd", "version":"2.4.*"},
                                              {"name":"mod_auth_kerb", "version":"5.4"},
                                              {"name":"mod_ssl", "version":"2.4.*"},
                                              {"name":"php", "version":"5.4.*"},
                                              {"name": "php-mysql", "version":"5.4.*"}],
                                   "name":"http-server",
                                   "packages": [{"name":"openssh-server", "version": "6.6.*"},
                                                {"name": "rsync", "version": "3.0.*"},
                                                {"name": "tmux", "version": "2.2"}],
                                   "version": "0.0.1"},
                                 ]}
        resp = self.server.get("/api/v0/recipes/info/http-server,glusterfs")
        data = json.loads(resp.data)
        self.assertEqual(data, info_dict_2)

        info_dict_3 = {"changes":[],
                "errors":[{"recipe":"missing-recipe", "msg":"No commits for missing-recipe.toml on the master branch."}],
                       "recipes":[]
                      }
        resp = self.server.get("/api/v0/recipes/info/missing-recipe")
        data = json.loads(resp.data)
        self.assertEqual(data, info_dict_3)

    def test_04_recipes_changes(self):
        """Test the /api/v0/recipes/changes route"""
        resp = self.server.get("/api/v0/recipes/changes/http-server")
        data = json.loads(resp.data)

        # Can't compare a whole dict since commit hash and timestamps will change.
        # Should have 1 commit (for now), with a matching message.
        self.assertEqual(data["limit"], 20)
        self.assertEqual(data["offset"], 0)
        self.assertEqual(len(data["errors"]), 0)
        self.assertEqual(len(data["recipes"]), 1)
        self.assertEqual(data["recipes"][0]["name"], "http-server")
        self.assertEqual(len(data["recipes"][0]["changes"]), 1)

    def test_05_recipes_new_json(self):
        """Test the /api/v0/recipes/new route with json recipe"""
        test_recipe = {"description": "An example GlusterFS server with samba",
                       "name":"glusterfs",
                       "version": "0.2.0",
                       "modules":[{"name":"glusterfs", "version":"3.7.*"},
                                  {"name":"glusterfs-cli", "version":"3.7.*"}],
                       "packages":[{"name":"samba", "version":"4.2.*"},
                                   {"name":"tmux", "version":"2.2"}]}

        resp = self.server.post("/api/v0/recipes/new",
                                data=json.dumps(test_recipe),
                                content_type="application/json")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        resp = self.server.get("/api/v0/recipes/info/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        recipes = data.get("recipes")
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0], test_recipe)

    def test_06_recipes_new_toml(self):
        """Test the /api/v0/recipes/new route with toml recipe"""
        test_recipe = open(joinpaths(self.examples_path, "glusterfs.toml"), "rb").read()
        resp = self.server.post("/api/v0/recipes/new",
                                data=test_recipe,
                                content_type="text/x-toml")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        resp = self.server.get("/api/v0/recipes/info/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        recipes = data.get("recipes")
        self.assertEqual(len(recipes), 1)

        # Returned recipe has had its version bumped to 0.2.1
        test_recipe = toml.loads(test_recipe)
        test_recipe["version"] = "0.2.1"

        self.assertEqual(recipes[0], test_recipe)

    def test_07_recipes_ws_json(self):
        """Test the /api/v0/recipes/workspace route with json recipe"""
        test_recipe = {"description": "An example GlusterFS server with samba, ws version",
                       "name":"glusterfs",
                       "version": "0.3.0",
                       "modules":[{"name":"glusterfs", "version":"3.7.*"},
                                  {"name":"glusterfs-cli", "version":"3.7.*"}],
                       "packages":[{"name":"samba", "version":"4.2.*"},
                                   {"name":"tmux", "version":"2.2"}]}

        resp = self.server.post("/api/v0/recipes/workspace",
                                data=json.dumps(test_recipe),
                                content_type="application/json")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        resp = self.server.get("/api/v0/recipes/info/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        recipes = data.get("recipes")
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0], test_recipe)
        changes = data.get("changes")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0], {"name":"glusterfs", "changed":True})

    def test_08_recipes_ws_toml(self):
        """Test the /api/v0/recipes/workspace route with toml recipe"""
        test_recipe = {"description": "An example GlusterFS server with samba, ws version",
                       "name":"glusterfs",
                       "version": "0.4.0",
                       "modules":[{"name":"glusterfs", "version":"3.7.*"},
                                  {"name":"glusterfs-cli", "version":"3.7.*"}],
                       "packages":[{"name":"samba", "version":"4.2.*"},
                                   {"name":"tmux", "version":"2.2"}]}

        resp = self.server.post("/api/v0/recipes/workspace",
                                data=json.dumps(test_recipe),
                                content_type="application/json")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        resp = self.server.get("/api/v0/recipes/info/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        recipes = data.get("recipes")
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0], test_recipe)
        changes = data.get("changes")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0], {"name":"glusterfs", "changed":True})

    def test_09_recipes_ws_delete(self):
        """Test DELETE /api/v0/recipes/workspace/<recipe_name>"""
        # Write to the workspace first, just use the test_recipes_ws_json test for this
        self.test_07_recipes_ws_json()

        # Delete it
        resp = self.server.delete("/api/v0/recipes/workspace/glusterfs")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        # Make sure it isn't the workspace copy and that changed is False
        resp = self.server.get("/api/v0/recipes/info/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        recipes = data.get("recipes")
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0]["version"], "0.2.1")
        changes = data.get("changes")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0], {"name":"glusterfs", "changed":False})

    def test_10_recipes_delete(self):
        """Test DELETE /api/v0/recipes/delete/<recipe_name>"""
        resp = self.server.delete("/api/v0/recipes/delete/glusterfs")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        # Make sure glusterfs is no longer in the list of recipes
        resp = self.server.get("/api/v0/recipes/list")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        recipes = data.get("recipes")
        self.assertEqual("glusterfs" in recipes, False)

    def test_11_recipes_undo(self):
        """Test POST /api/v0/recipes/undo/<recipe_name/<commit>"""
        resp = self.server.get("/api/v0/recipes/changes/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)

        # Revert it to the first commit
        recipes = data.get("recipes")
        self.assertNotEqual(recipes, None)
        changes = recipes[0].get("changes")
        self.assertEqual(len(changes) > 1, True)

        # Revert it to the first commit
        commit = changes[-1]["commit"]
        resp = self.server.post("/api/v0/recipes/undo/glusterfs/%s" % commit)
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        resp = self.server.get("/api/v0/recipes/changes/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)

        recipes = data.get("recipes")
        self.assertNotEqual(recipes, None)
        changes = recipes[0].get("changes")
        self.assertEqual(len(changes) > 1, True)

        expected_msg = "Recipe glusterfs.toml reverted to commit %s" % commit
        self.assertEqual(changes[0]["message"], expected_msg)

    def test_12_recipes_tag(self):
        """Test POST /api/v0/recipes/tag/<recipe_name>"""
        resp = self.server.post("/api/v0/recipes/tag/glusterfs")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        resp = self.server.get("/api/v0/recipes/changes/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)

        # Revert it to the first commit
        recipes = data.get("recipes")
        self.assertNotEqual(recipes, None)
        changes = recipes[0].get("changes")
        self.assertEqual(len(changes) > 1, True)
        self.assertEqual(changes[0]["revision"], 1)

    def test_13_recipes_diff(self):
        """Test /api/v0/recipes/diff/<recipe_name>/<from_commit>/<to_commit>"""
        resp = self.server.get("/api/v0/recipes/changes/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        recipes = data.get("recipes")
        self.assertNotEqual(recipes, None)
        changes = recipes[0].get("changes")
        self.assertEqual(len(changes) >= 2, True)

        from_commit = changes[1].get("commit")
        self.assertNotEqual(from_commit, None)
        to_commit = changes[0].get("commit")
        self.assertNotEqual(to_commit, None)

        # Get the differences between the two commits
        resp = self.server.get("/api/v0/recipes/diff/glusterfs/%s/%s" % (from_commit, to_commit))
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data, {"diff": [{"new": {"Version": "0.0.1"}, "old": {"Version": "0.2.1"}}]})

        # Write to the workspace and check the diff
        test_recipe = {"description": "An example GlusterFS server with samba, ws version",
                       "name":"glusterfs",
                       "version": "0.3.0",
                       "modules":[{"name":"glusterfs", "version":"3.7.*"},
                                  {"name":"glusterfs-cli", "version":"3.7.*"}],
                       "packages":[{"name":"samba", "version":"4.2.*"},
                                   {"name":"tmux", "version":"2.2"}]}

        resp = self.server.post("/api/v0/recipes/workspace",
                                data=json.dumps(test_recipe),
                                content_type="application/json")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        # Get the differences between the newest commit and the workspace
        resp = self.server.get("/api/v0/recipes/diff/glusterfs/NEWEST/WORKSPACE")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        print(data)
        result = {"diff": [{"new": {"Description": "An example GlusterFS server with samba, ws version"},
                             "old": {"Description": "An example GlusterFS server with samba"}},
                            {"new": {"Version": "0.3.0"},
                             "old": {"Version": "0.0.1"}},
                            {"new": {"Package": {"version": "2.2", "name": "tmux"}},
                             "old": None}]}
        self.assertEqual(data, result)

    def test_14_recipes_depsolve(self):
        """Test /api/v0/recipes/depsolve/<recipe_names>"""
        resp = self.server.get("/api/v0/recipes/depsolve/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        recipes = data.get("recipes")
        self.assertNotEqual(recipes, None)
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0]["recipe"]["name"], "glusterfs")
        self.assertEqual(len(recipes[0]["dependencies"]) > 10, True)
        self.assertFalse(data.get("errors"))

    def test_14_recipes_depsolve_empty(self):
        """Test /api/v0/recipes/depsolve/<recipe_names> on empty recipe"""
        test_recipe = {"description": "An empty recipe",
                       "name":"void",
                       "version": "0.1.0"}
        resp = self.server.post("/api/v0/recipes/new",
                                data=json.dumps(test_recipe),
                                content_type="application/json")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        resp = self.server.get("/api/v0/recipes/depsolve/void")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        recipes = data.get("recipes")
        self.assertNotEqual(recipes, None)
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0]["recipe"]["name"], "void")
        self.assertEqual(recipes[0]["recipe"]["packages"], [])
        self.assertEqual(recipes[0]["recipe"]["modules"], [])
        self.assertEqual(recipes[0]["dependencies"], [])
        self.assertFalse(data.get("errors"))

    def test_15_recipes_freeze(self):
        """Test /api/v0/recipes/freeze/<recipe_names>"""
        resp = self.server.get("/api/v0/recipes/freeze/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        recipes = data.get("recipes")
        self.assertNotEqual(recipes, None)
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0]["recipe"]["name"], "glusterfs")
        evra = recipes[0]["recipe"]["modules"][0]["version"]
        self.assertEqual(len(evra) > 10, True)

    def test_projects_list(self):
        """Test /api/v0/projects/list"""
        resp = self.server.get("/api/v0/projects/list")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        projects = data.get("projects")
        self.assertEqual(len(projects) > 10, True)

    def test_projects_info(self):
        """Test /api/v0/projects/info/<project_names>"""
        resp = self.server.get("/api/v0/projects/info/bash")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        projects = data.get("projects")
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["name"], "bash")
        self.assertEqual(projects[0]["builds"][0]["source"]["license"], "GPLv3+")

    def test_projects_depsolve(self):
        """Test /api/v0/projects/depsolve/<project_names>"""
        resp = self.server.get("/api/v0/projects/depsolve/bash")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        deps = data.get("projects")
        self.assertEqual(len(deps) > 10, True)
        self.assertEqual(deps[0]["name"], "basesystem")

    def test_modules_list(self):
        """Test /api/v0/modules/list"""
        resp = self.server.get("/api/v0/modules/list")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        print(data)
        modules = data.get("modules")
        self.assertEqual(len(modules) > 10, True)
        self.assertEqual(modules[0]["group_type"], "rpm")

        resp = self.server.get("/api/v0/modules/list/d*")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        print(data)
        modules = data.get("modules")
        self.assertEqual(len(modules) > 0, True)
        self.assertEqual(modules[0]["name"].startswith("d"), True)

    def test_modules_info(self):
        """Test /api/v0/modules/info"""
        resp = self.server.get("/api/v0/modules/info/bash")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        modules = data.get("modules")
        self.assertEqual(len(modules), 1)
        self.assertEqual(modules[0]["name"], "bash")
        self.assertEqual(modules[0]["dependencies"][0]["name"], "basesystem")

    def test_recipe_new_branch(self):
        """Test the /api/v0/recipes/new route with a new branch"""
        test_recipe = {"description": "An example GlusterFS server with samba",
                       "name":"glusterfs",
                       "version": "0.2.0",
                       "modules":[{"name":"glusterfs", "version":"3.7.*"},
                                  {"name":"glusterfs-cli", "version":"3.7.*"}],
                       "packages":[{"name":"samba", "version":"4.2.*"},
                                   {"name":"tmux", "version":"2.2"}]}

        resp = self.server.post("/api/v0/recipes/new?branch=test",
                                data=json.dumps(test_recipe),
                                content_type="application/json")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        resp = self.server.get("/api/v0/recipes/info/glusterfs?branch=test")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        recipes = data.get("recipes")
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0], test_recipe)

    def test_api_docs(self):
        """Test the /api/docs/"""
        resp = self.server.get("/api/docs/")
        doc_str = open(os.path.abspath(joinpaths(os.path.dirname(__file__), "../../docs/html/index.html"))).read()
        self.assertEqual(doc_str, resp.data)

    def test_api_docs_with_existing_path(self):
        """Test the /api/docs/modules.html"""
        resp = self.server.get("/api/docs/modules.html")
        doc_str = open(os.path.abspath(joinpaths(os.path.dirname(__file__), "../../docs/html/modules.html"))).read()
        self.assertEqual(doc_str, resp.data)
