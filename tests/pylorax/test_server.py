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
from configparser import ConfigParser, NoOptionError
from glob import glob
import shutil
import tempfile
import time
from threading import Lock
import unittest

from flask import json
import pytoml as toml
from pylorax.api.config import configure, make_dnf_dirs, make_queue_dirs
from pylorax.api.queue import start_queue_monitor
from pylorax.api.recipes import open_or_create_repo, commit_recipe_directory
from pylorax.api.server import server, GitLock, DNFLock
from pylorax.api.dnfbase import get_base_object
from pylorax.sysutils import joinpaths

def get_system_repo():
    """Get an enabled system repo from /etc/yum.repos.d/*repo

    This will be used for test_projects_source_01_delete_system()
    """
    # The sources delete test needs the name of a system repo, get it from /etc/yum.repos.d/
    for sys_repo in sorted(glob("/etc/yum.repos.d/*repo")):
        cfg = ConfigParser()
        cfg.read(sys_repo)
        for section in cfg.sections():
            try:
                if cfg.get(section, "enabled") == "1":
                    # The API only supports repo filenames, return that.
                    return os.path.basename(sys_repo)[:-5]
            except NoOptionError:
                pass

    # Failed to find one, fall back to using base
    return "base"

class ServerTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(self):
        self.rawhide = False
        self.maxDiff = None

        repo_dir = tempfile.mkdtemp(prefix="lorax.test.repo.")
        server.config["REPO_DIR"] = repo_dir
        repo = open_or_create_repo(server.config["REPO_DIR"])
        server.config["GITLOCK"] = GitLock(repo=repo, lock=Lock(), dir=repo_dir)

        server.config["COMPOSER_CFG"] = configure(root_dir=repo_dir, test_config=True)
        os.makedirs(joinpaths(server.config["COMPOSER_CFG"].get("composer", "share_dir"), "composer"))
        errors = make_queue_dirs(server.config["COMPOSER_CFG"], 0)
        if errors:
            raise RuntimeError("\n".join(errors))

        make_dnf_dirs(server.config["COMPOSER_CFG"])

        # copy over the test dnf repositories
        dnf_repo_dir = server.config["COMPOSER_CFG"].get("composer", "repo_dir")
        for f in glob("./tests/pylorax/repos/*.repo"):
            shutil.copy2(f, dnf_repo_dir)

        # Modify fedora vs. rawhide tests when running on rawhide
        if os.path.exists("/etc/yum.repos.d/fedora-rawhide.repo"):
            self.rawhide = True

        # dnf repo baseurl has to point to an absolute directory, so we use /tmp/lorax-empty-repo/ in the files
        # and create an empty repository
        os.makedirs("/tmp/lorax-empty-repo/")
        os.system("createrepo_c /tmp/lorax-empty-repo/")

        dbo = get_base_object(server.config["COMPOSER_CFG"])
        server.config["DNFLOCK"] = DNFLock(dbo=dbo, lock=Lock())

        # Include a message in /api/status output
        server.config["TEMPLATE_ERRORS"] = ["Test message"]

        server.config['TESTING'] = True
        self.server = server.test_client()
        self.repo_dir = repo_dir

        self.examples_path = "./tests/pylorax/blueprints/"

        # Copy the shared files over to the directory tree we are using
        share_path = "./share/composer/"
        for f in glob(joinpaths(share_path, "*")):
            shutil.copy(f, joinpaths(server.config["COMPOSER_CFG"].get("composer", "share_dir"), "composer"))

        # Import the example blueprints
        commit_recipe_directory(server.config["GITLOCK"].repo, "master", self.examples_path)

        # The sources delete test needs the name of a system repo, get it from /etc/yum.repos.d/
        self.system_repo = get_system_repo()

        start_queue_monitor(server.config["COMPOSER_CFG"], 0, 0)

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(server.config["REPO_DIR"])
        shutil.rmtree("/tmp/lorax-empty-repo/")

    def test_01_status(self):
        """Test the /api/status route"""
        status_fields = ["build", "api", "db_version", "schema_version", "db_supported", "backend", "msgs"]
        resp = self.server.get("/api/status")
        data = json.loads(resp.data)
        # Make sure the fields are present
        self.assertEqual(sorted(data.keys()), sorted(status_fields))

        # Check for test message
        self.assertEqual(data["msgs"], ["Test message"])


    def test_02_blueprints_list(self):
        """Test the /api/v0/blueprints/list route"""
        list_dict = {"blueprints":["atlas", "custom-base", "development", "glusterfs", "http-server",
                     "jboss", "kubernetes"], "limit":20, "offset":0, "total":7}
        resp = self.server.get("/api/v0/blueprints/list")
        data = json.loads(resp.data)
        self.assertEqual(data, list_dict)

    def test_03_blueprints_info_1(self):
        """Test the /api/v0/blueprints/info route with one blueprint"""
        info_dict_1 = {"changes":[{"changed":False, "name":"http-server"}],
                       "errors":[],
                       "blueprints":[{"description":"An example http server with PHP and MySQL support.",
                                   "modules":[{"name":"httpd", "version":"2.4.*"},
                                              {"name":"mod_auth_openid", "version":"0.8"},
                                              {"name":"mod_ssl", "version":"2.4.*"},
                                              {"name":"php", "version":"7.2.4"},
                                              {"name": "php-mysqlnd", "version":"7.2.4"}],
                                   "name":"http-server",
                                   "packages": [{"name":"openssh-server", "version": "7.*"},
                                                {"name": "rsync", "version": "3.1.*"},
                                                {"name": "tmux", "version": "2.7"}],
                                   "groups": [],
                                   "version": "0.0.1"}]}
        resp = self.server.get("/api/v0/blueprints/info/http-server")
        data = json.loads(resp.data)
        self.assertEqual(data, info_dict_1)

    def test_03_blueprints_info_2(self):
        """Test the /api/v0/blueprints/info route with 2 blueprints"""
        info_dict_2 = {"changes":[{"changed":False, "name":"glusterfs"},
                                  {"changed":False, "name":"http-server"}],
                       "errors":[],
                       "blueprints":[{"description": "An example GlusterFS server with samba",
                                   "modules":[{"name":"glusterfs", "version":"4.1.*"},
                                              {"name":"glusterfs-cli", "version":"4.1.*"}],
                                   "name":"glusterfs",
                                   "packages":[{"name":"samba", "version":"4.9.*"}],
                                   "groups": [],
                                   "version": "0.0.1"},
                                  {"description":"An example http server with PHP and MySQL support.",
                                   "modules":[{"name":"httpd", "version":"2.4.*"},
                                              {"name":"mod_auth_openid", "version":"0.8"},
                                              {"name":"mod_ssl", "version":"2.4.*"},
                                              {"name":"php", "version":"7.2.4"},
                                              {"name": "php-mysqlnd", "version":"7.2.4"}],
                                   "name":"http-server",
                                   "packages": [{"name":"openssh-server", "version": "7.*"},
                                                {"name": "rsync", "version": "3.1.*"},
                                                {"name": "tmux", "version": "2.7"}],
                                   "groups": [],
                                   "version": "0.0.1"},
                                 ]}
        resp = self.server.get("/api/v0/blueprints/info/http-server,glusterfs")
        data = json.loads(resp.data)
        self.assertEqual(data, info_dict_2)

    def test_03_blueprints_info_none(self):
        """Test the /api/v0/blueprints/info route with an unknown blueprint"""
        info_dict_3 = {"changes":[],
                       "errors":["missing-blueprint: No commits for missing-blueprint.toml on the master branch."],
                       "blueprints":[]
                      }
        resp = self.server.get("/api/v0/blueprints/info/missing-blueprint")
        data = json.loads(resp.data)
        self.assertEqual(data, info_dict_3)

    def test_04_blueprints_changes(self):
        """Test the /api/v0/blueprints/changes route"""
        resp = self.server.get("/api/v0/blueprints/changes/http-server")
        data = json.loads(resp.data)

        # Can't compare a whole dict since commit hash and timestamps will change.
        # Should have 1 commit (for now), with a matching message.
        self.assertEqual(data["limit"], 20)
        self.assertEqual(data["offset"], 0)
        self.assertEqual(len(data["errors"]), 0)
        self.assertEqual(len(data["blueprints"]), 1)
        self.assertEqual(data["blueprints"][0]["name"], "http-server")
        self.assertEqual(len(data["blueprints"][0]["changes"]), 1)

    def test_04a_blueprints_diff_empty_ws(self):
        """Test the /api/v0/diff/NEWEST/WORKSPACE with empty workspace"""
        resp = self.server.get("/api/v0/blueprints/diff/glusterfs/NEWEST/WORKSPACE")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data, {"diff": []})

    def test_05_blueprints_new_json(self):
        """Test the /api/v0/blueprints/new route with json blueprint"""
        test_blueprint = {"description": "An example GlusterFS server with samba",
                       "name":"glusterfs",
                       "version": "0.2.0",
                       "modules":[{"name":"glusterfs", "version":"4.1.*"},
                                  {"name":"glusterfs-cli", "version":"4.1.*"}],
                       "packages":[{"name":"samba", "version":"4.9.*"},
                                   {"name":"tmux", "version":"2.7"}],
                       "groups": []}

        resp = self.server.post("/api/v0/blueprints/new",
                                data=json.dumps(test_blueprint),
                                content_type="application/json")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        resp = self.server.get("/api/v0/blueprints/info/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        blueprints = data.get("blueprints")
        self.assertEqual(len(blueprints), 1)
        self.assertEqual(blueprints[0], test_blueprint)

    def test_06_blueprints_new_toml(self):
        """Test the /api/v0/blueprints/new route with toml blueprint"""
        test_blueprint = open(joinpaths(self.examples_path, "glusterfs.toml"), "rb").read()
        resp = self.server.post("/api/v0/blueprints/new",
                                data=test_blueprint,
                                content_type="text/x-toml")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        resp = self.server.get("/api/v0/blueprints/info/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        blueprints = data.get("blueprints")
        self.assertEqual(len(blueprints), 1)

        # Returned blueprint has had its version bumped
        test_blueprint = toml.loads(test_blueprint)
        test_blueprint["version"] = "0.2.1"

        # The test_blueprint generated by toml.loads will not have any groups property
        # defined, since there are no groups listed.  However, /api/v0/blueprints/new will
        # return an object with groups=[].  So, add that here to keep the equality test
        # working.
        test_blueprint["groups"] = []

        self.assertEqual(blueprints[0], test_blueprint)

    def test_07_blueprints_ws_json(self):
        """Test the /api/v0/blueprints/workspace route with json blueprint"""
        test_blueprint = {"description": "An example GlusterFS server with samba, ws version",
                       "name":"glusterfs",
                       "version": "0.3.0",
                       "modules":[{"name":"glusterfs", "version":"4.1.*"},
                                  {"name":"glusterfs-cli", "version":"4.1.*"}],
                       "packages":[{"name":"samba", "version":"4.9.*"},
                                   {"name":"tmux", "version":"2.7"}],
                       "groups": []}

        resp = self.server.post("/api/v0/blueprints/workspace",
                                data=json.dumps(test_blueprint),
                                content_type="application/json")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        resp = self.server.get("/api/v0/blueprints/info/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        blueprints = data.get("blueprints")
        self.assertEqual(len(blueprints), 1)
        self.assertEqual(blueprints[0], test_blueprint)
        changes = data.get("changes")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0], {"name":"glusterfs", "changed":True})

    def test_08_blueprints_ws_toml(self):
        """Test the /api/v0/blueprints/workspace route with toml blueprint"""
        test_blueprint = {"description": "An example GlusterFS server with samba, ws version",
                       "name":"glusterfs",
                       "version": "0.4.0",
                       "modules":[{"name":"glusterfs", "version":"4.1.*"},
                                  {"name":"glusterfs-cli", "version":"4.1.*"}],
                       "packages":[{"name":"samba", "version":"4.9.*"},
                                   {"name":"tmux", "version":"2.7"}],
                       "groups": []}

        resp = self.server.post("/api/v0/blueprints/workspace",
                                data=json.dumps(test_blueprint),
                                content_type="application/json")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        resp = self.server.get("/api/v0/blueprints/info/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        blueprints = data.get("blueprints")
        self.assertEqual(len(blueprints), 1)
        self.assertEqual(blueprints[0], test_blueprint)
        changes = data.get("changes")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0], {"name":"glusterfs", "changed":True})

    def test_09_blueprints_ws_delete(self):
        """Test DELETE /api/v0/blueprints/workspace/<blueprint_name>"""
        # Write to the workspace first, just use the test_blueprints_ws_json test for this
        self.test_07_blueprints_ws_json()

        # Delete it
        resp = self.server.delete("/api/v0/blueprints/workspace/glusterfs")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        # Make sure it isn't the workspace copy and that changed is False
        resp = self.server.get("/api/v0/blueprints/info/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        blueprints = data.get("blueprints")
        self.assertEqual(len(blueprints), 1)
        self.assertEqual(blueprints[0]["version"], "0.2.1")
        changes = data.get("changes")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0], {"name":"glusterfs", "changed":False})

    def test_10_blueprints_delete(self):
        """Test DELETE /api/v0/blueprints/delete/<blueprint_name>"""
        resp = self.server.delete("/api/v0/blueprints/delete/glusterfs")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        # Make sure glusterfs is no longer in the list of blueprints
        resp = self.server.get("/api/v0/blueprints/list")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        blueprints = data.get("blueprints")
        self.assertEqual("glusterfs" in blueprints, False)

    def test_11_blueprints_undo(self):
        """Test POST /api/v0/blueprints/undo/<blueprint_name>/<commit>"""
        resp = self.server.get("/api/v0/blueprints/changes/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)

        # Revert it to the first commit
        blueprints = data.get("blueprints")
        self.assertNotEqual(blueprints, None)
        changes = blueprints[0].get("changes")
        self.assertEqual(len(changes) > 1, True)

        # Revert it to the first commit
        commit = changes[-1]["commit"]
        resp = self.server.post("/api/v0/blueprints/undo/glusterfs/%s" % commit)
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        resp = self.server.get("/api/v0/blueprints/changes/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)

        blueprints = data.get("blueprints")
        self.assertNotEqual(blueprints, None)
        changes = blueprints[0].get("changes")
        self.assertEqual(len(changes) > 1, True)

        expected_msg = "glusterfs.toml reverted to commit %s" % commit
        self.assertEqual(changes[0]["message"], expected_msg)

    def test_12_blueprints_tag(self):
        """Test POST /api/v0/blueprints/tag/<blueprint_name>"""
        resp = self.server.post("/api/v0/blueprints/tag/glusterfs")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        resp = self.server.get("/api/v0/blueprints/changes/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)

        # Revert it to the first commit
        blueprints = data.get("blueprints")
        self.assertNotEqual(blueprints, None)
        changes = blueprints[0].get("changes")
        self.assertEqual(len(changes) > 1, True)
        self.assertEqual(changes[0]["revision"], 1)

    def test_13_blueprints_diff(self):
        """Test /api/v0/blueprints/diff/<blueprint_name>/<from_commit>/<to_commit>"""
        resp = self.server.get("/api/v0/blueprints/changes/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        blueprints = data.get("blueprints")
        self.assertNotEqual(blueprints, None)
        changes = blueprints[0].get("changes")
        self.assertEqual(len(changes) >= 2, True)

        from_commit = changes[1].get("commit")
        self.assertNotEqual(from_commit, None)
        to_commit = changes[0].get("commit")
        self.assertNotEqual(to_commit, None)

        print("from: %s" % from_commit)
        print("to: %s" % to_commit)
        print(changes)

        # Get the differences between the two commits
        resp = self.server.get("/api/v0/blueprints/diff/glusterfs/%s/%s" % (from_commit, to_commit))
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data, {"diff": [{"new": {"Version": "0.0.1"}, "old": {"Version": "0.2.1"}}]})

        # Write to the workspace and check the diff
        test_blueprint = {"description": "An example GlusterFS server with samba, ws version",
                       "name":"glusterfs",
                       "version": "0.3.0",
                       "modules":[{"name":"glusterfs", "version":"4.1.*"},
                                  {"name":"glusterfs-cli", "version":"4.1.*"}],
                       "packages":[{"name":"samba", "version":"4.9.*"},
                                   {"name":"tmux", "version":"2.7"}]}

        resp = self.server.post("/api/v0/blueprints/workspace",
                                data=json.dumps(test_blueprint),
                                content_type="application/json")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        # Get the differences between the newest commit and the workspace
        resp = self.server.get("/api/v0/blueprints/diff/glusterfs/NEWEST/WORKSPACE")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        result = {"diff": [{"new": {"Description": "An example GlusterFS server with samba, ws version"},
                             "old": {"Description": "An example GlusterFS server with samba"}},
                            {"new": {"Version": "0.3.0"},
                             "old": {"Version": "0.0.1"}},
                            {"new": {"Package": {"version": "2.7", "name": "tmux"}},
                             "old": None}]}
        self.assertEqual(data, result)

    def test_14_blueprints_depsolve(self):
        """Test /api/v0/blueprints/depsolve/<blueprint_names>"""
        resp = self.server.get("/api/v0/blueprints/depsolve/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        blueprints = data.get("blueprints")
        self.assertNotEqual(blueprints, None)
        self.assertEqual(len(blueprints), 1)
        self.assertEqual(blueprints[0]["blueprint"]["name"], "glusterfs")
        self.assertEqual(len(blueprints[0]["dependencies"]) > 10, True)
        self.assertFalse(data.get("errors"))

    def test_14_blueprints_depsolve_empty(self):
        """Test /api/v0/blueprints/depsolve/<blueprint_names> on empty blueprint"""
        test_blueprint = {"description": "An empty blueprint",
                       "name":"void",
                       "version": "0.1.0"}
        resp = self.server.post("/api/v0/blueprints/new",
                                data=json.dumps(test_blueprint),
                                content_type="application/json")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        resp = self.server.get("/api/v0/blueprints/depsolve/void")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        blueprints = data.get("blueprints")
        self.assertNotEqual(blueprints, None)
        self.assertEqual(len(blueprints), 1)
        self.assertEqual(blueprints[0]["blueprint"]["name"], "void")
        self.assertEqual(blueprints[0]["blueprint"]["packages"], [])
        self.assertEqual(blueprints[0]["blueprint"]["modules"], [])
        self.assertEqual(blueprints[0]["dependencies"], [])
        self.assertFalse(data.get("errors"))

    def test_15_blueprints_freeze(self):
        """Test /api/v0/blueprints/freeze/<blueprint_names>"""
        resp = self.server.get("/api/v0/blueprints/freeze/glusterfs")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        blueprints = data.get("blueprints")
        self.assertNotEqual(blueprints, None)
        self.assertEqual(len(blueprints), 1)
        self.assertTrue(len(blueprints[0]["blueprint"]["modules"]) > 0)
        self.assertEqual(blueprints[0]["blueprint"]["name"], "glusterfs")
        evra = blueprints[0]["blueprint"]["modules"][0]["version"]
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
        self.assertEqual(len(projects) > 0, True)
        self.assertEqual(projects[0]["name"], "bash")
        self.assertEqual(projects[0]["builds"][0]["source"]["license"], "GPLv3+")

    def test_projects_depsolve(self):
        """Test /api/v0/projects/depsolve/<project_names>"""
        resp = self.server.get("/api/v0/projects/depsolve/bash")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        deps = data.get("projects")
        self.assertEqual(len(deps) > 10, True)
        self.assertTrue("basesystem" in [dep["name"] for dep in deps])

    def test_projects_source_00_list(self):
        """Test /api/v0/projects/source/list"""
        resp = self.server.get("/api/v0/projects/source/list")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        if self.rawhide:
            self.assertEqual(data["sources"], ["lorax-1", "lorax-2", "lorax-3", "lorax-4", "other-repo", "rawhide", "single-repo"])
        else:
            self.assertEqual(data["sources"], ["fedora", "lorax-1", "lorax-2", "lorax-3", "lorax-4", "other-repo", "single-repo", "updates"])

    def test_projects_source_00_info(self):
        """Test /api/v0/projects/source/info"""
        resp = self.server.get("/api/v0/projects/source/info/single-repo")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        sources = data["sources"]
        self.assertTrue("single-repo" in sources)

    def test_projects_source_00_new_json(self):
        """Test /api/v0/projects/source/new with a new json source"""
        json_source = open("./tests/pylorax/source/test-repo.json").read()
        self.assertTrue(len(json_source) > 0)
        resp = self.server.post("/api/v0/projects/source/new",
                                data=json_source,
                                content_type="application/json")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        # Is it listed?
        resp = self.server.get("/api/v0/projects/source/list")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        sources = data["sources"]
        self.assertTrue("new-repo-1" in sources)

    def test_projects_source_00_new_toml(self):
        """Test /api/v0/projects/source/new with a new toml source"""
        toml_source = open("./tests/pylorax/source/test-repo.toml").read()
        self.assertTrue(len(toml_source) > 0)
        resp = self.server.post("/api/v0/projects/source/new",
                                data=toml_source,
                                content_type="text/x-toml")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        # Is it listed?
        resp = self.server.get("/api/v0/projects/source/list")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        sources = data["sources"]
        self.assertTrue("new-repo-2" in sources)

    def test_projects_source_00_replace(self):
        """Test /api/v0/projects/source/new with a replacement source"""
        toml_source = open("./tests/pylorax/source/replace-repo.toml").read()
        self.assertTrue(len(toml_source) > 0)
        resp = self.server.post("/api/v0/projects/source/new",
                                data=toml_source,
                                content_type="text/x-toml")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        # Check to see if it was really changed
        resp = self.server.get("/api/v0/projects/source/info/single-repo")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        sources = data["sources"]
        self.assertTrue("single-repo" in sources)
        repo = sources["single-repo"]
        self.assertEqual(repo["check_ssl"], False)
        self.assertTrue("gpgkey_urls" not in repo)

    def test_projects_source_00_bad_url(self):
        """Test /api/v0/projects/source/new with a new source that has an invalid url"""
        toml_source = open("./tests/pylorax/source/bad-repo.toml").read()
        self.assertTrue(len(toml_source) > 0)
        resp = self.server.post("/api/v0/projects/source/new",
                                data=toml_source,
                                content_type="text/x-toml")
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.data)
        self.assertEqual(data["status"], False)

    def test_projects_source_01_delete_system(self):
        """Test /api/v0/projects/source/delete a system source"""
        if self.rawhide:
            resp = self.server.delete("/api/v0/projects/source/delete/rawhide")
        else:
            resp = self.server.delete("/api/v0/projects/source/delete/fedora")
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data["status"], False)

        # Make sure fedora/rawhide is still listed
        resp = self.server.get("/api/v0/projects/source/list")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertTrue(self.system_repo in data["sources"], "%s not in %s" % (self.system_repo, data["sources"]))

    def test_projects_source_02_delete_single(self):
        """Test /api/v0/projects/source/delete a single source"""
        resp = self.server.delete("/api/v0/projects/source/delete/single-repo")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data, {"status":True})

        # Make sure single-repo isn't listed
        resp = self.server.get("/api/v0/projects/source/list")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertTrue("single-repo" not in data["sources"])

    def test_projects_source_03_delete_unknown(self):
        """Test /api/v0/projects/source/delete an unknown source"""
        resp = self.server.delete("/api/v0/projects/source/delete/unknown-repo")
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data["status"], False)

    def test_projects_source_04_delete_multi(self):
        """Test /api/v0/projects/source/delete a source from a file with multiple sources"""
        resp = self.server.delete("/api/v0/projects/source/delete/lorax-3")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data, {"status":True})

        # Make sure single-repo isn't listed
        resp = self.server.get("/api/v0/projects/source/list")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertTrue("lorax-3" not in data["sources"])

    def test_modules_list(self):
        """Test /api/v0/modules/list"""
        resp = self.server.get("/api/v0/modules/list")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        modules = data.get("modules")
        self.assertEqual(len(modules) > 10, True)
        self.assertEqual(modules[0]["group_type"], "rpm")

        resp = self.server.get("/api/v0/modules/list/d*")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        modules = data.get("modules")
        self.assertEqual(len(modules) > 0, True)
        self.assertEqual(modules[0]["name"].startswith("d"), True)

    def test_modules_info(self):
        """Test /api/v0/modules/info"""
        resp = self.server.get("/api/v0/modules/info/bash")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        modules = data.get("modules")
        self.assertEqual(len(modules) > 0, True)
        self.assertEqual(modules[0]["name"], "bash")
        self.assertTrue("basesystem" in [dep["name"] for dep in modules[0]["dependencies"]])

    def test_blueprint_new_branch(self):
        """Test the /api/v0/blueprints/new route with a new branch"""
        test_blueprint = {"description": "An example GlusterFS server with samba",
                       "name":"glusterfs",
                       "version": "0.2.0",
                       "modules":[{"name":"glusterfs", "version":"4.1.*"},
                                  {"name":"glusterfs-cli", "version":"4.1.*"}],
                       "packages":[{"name":"samba", "version":"4.9.*"},
                                   {"name":"tmux", "version":"2.7"}],
                       "groups": []}

        resp = self.server.post("/api/v0/blueprints/new?branch=test",
                                data=json.dumps(test_blueprint),
                                content_type="application/json")
        data = json.loads(resp.data)
        self.assertEqual(data, {"status":True})

        resp = self.server.get("/api/v0/blueprints/info/glusterfs?branch=test")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        blueprints = data.get("blueprints")
        self.assertEqual(len(blueprints), 1)
        self.assertEqual(blueprints[0], test_blueprint)

    def assert_documentation(self, response):
        """
            Assert response containing documentation from /api/doc/ is
            valid *without* comparing to the actual file on disk.
        """
        self.assertEqual(200, response.status_code)
        self.assertTrue(len(response.data) > 1024)
        # look for some well known strings inside the documentation
        self.assertRegex(response.data.decode("utf-8"), r"Lorax [\d.]+ documentation")
        self.assertRegex(response.data.decode("utf-8"), r"Copyright \d+, Red Hat, Inc.")

    def test_api_docs(self):
        """Test the /api/docs/"""
        resp = self.server.get("/api/docs/")
        self.assert_documentation(resp)

    def test_api_docs_with_existing_path(self):
        """Test the /api/docs/modules.html"""
        resp = self.server.get("/api/docs/modules.html")
        self.assert_documentation(resp)

    def wait_for_status(self, uuid, wait_status):
        """Helper function that waits for a status

        :param uuid: UUID of the build to check
        :type uuid: str
        :param wait_status: List of statuses to exit on
        :type wait_status: list of str
        :returns: True if status was found, False if it timed out
        :rtype: bool

        This will time out after 60 seconds
        """
        start = time.time()
        while True:
            resp = self.server.get("/api/v0/compose/info/%s" % uuid)
            data = json.loads(resp.data)
            self.assertNotEqual(data, None)
            queue_status = data.get("queue_status")
            if queue_status in wait_status:
                return True
            if time.time() > start + 60:
                return False
            time.sleep(1)

    def test_compose_01_types(self):
        """Test the /api/v0/compose/types route"""
        resp = self.server.get("/api/v0/compose/types")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual({"name": "tar", "enabled": True} in data["types"], True)

    def test_compose_02_bad_type(self):
        """Test that using an unsupported image type failes"""
        test_compose = {"blueprint_name": "glusterfs",
                        "compose_type": "snakes",
                        "branch": "master"}

        resp = self.server.post("/api/v0/compose?test=1",
                                data=json.dumps(test_compose),
                                content_type="application/json")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data["status"], False, "Failed to fail to start test compose: %s" % data)
        self.assertEqual(data["errors"], ["Invalid compose type (snakes), must be one of ['ext4-filesystem', 'live-iso', 'partitioned-disk', 'qcow2', 'tar']"],
                                         "Failed to get errors: %s" % data)

    def test_compose_03_status_fail(self):
        """Test that requesting a status for a bad uuid is empty"""
        resp = self.server.get("/api/v0/compose/status/NO-UUID-TO-SEE-HERE")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data["uuids"], [], "Failed to get empty result bad uuid: %s" % data)

    def test_compose_04_cancel_fail(self):
        """Test that requesting a cancel for a bad uuid fails."""
        resp = self.server.delete("/api/v0/compose/cancel/NO-UUID-TO-SEE-HERE")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data["status"], False, "Failed to get an error for a bad uuid: %s" % data)
        self.assertEqual(data["errors"], ["NO-UUID-TO-SEE-HERE is not a valid build uuid"], "Failed to get errors: %s" % data)

    def test_compose_05_delete_fail(self):
        """Test that requesting a delete for a bad uuid fails."""
        resp = self.server.delete("/api/v0/compose/delete/NO-UUID-TO-SEE-HERE")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data["errors"], ["no-uuid-to-see-here is not a valid build uuid"],
                         "Failed to get an error for a bad uuid: %s" % data)

    def test_compose_06_info_fail(self):
        """Test that requesting info for a bad uuid fails."""
        resp = self.server.get("/api/v0/compose/info/NO-UUID-TO-SEE-HERE")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data["status"], False, "Failed to get an error for a bad uuid: %s" % data)
        self.assertEqual(data["errors"], ["NO-UUID-TO-SEE-HERE is not a valid build_id"],
                                         "Failed to get errors: %s" % data)

    def test_compose_07_metadata_fail(self):
        """Test that requesting metadata for a bad uuid fails."""
        resp = self.server.get("/api/v0/compose/metadata/NO-UUID-TO-SEE-HERE")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data["status"], False, "Failed to get an error for a bad uuid: %s" % data)
        self.assertEqual(data["errors"], ["NO-UUID-TO-SEE-HERE is not a valid build uuid"],
                                         "Failed to get errors: %s" % data)

    def test_compose_08_results_fail(self):
        """Test that requesting results for a bad uuid fails."""
        resp = self.server.get("/api/v0/compose/results/NO-UUID-TO-SEE-HERE")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data["status"], False, "Failed to get an error for a bad uuid: %s" % data)
        self.assertEqual(data["errors"], ["NO-UUID-TO-SEE-HERE is not a valid build uuid"], "Failed to get errors: %s" % data)

    def test_compose_09_logs_fail(self):
        """Test that requesting logs for a bad uuid fails."""
        resp = self.server.get("/api/v0/compose/logs/NO-UUID-TO-SEE-HERE")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data["status"], False, "Failed to get an error for a bad uuid: %s" % data)
        self.assertEqual(data["errors"], ["NO-UUID-TO-SEE-HERE is not a valid build uuid"],
                                         "Failed to get errors: %s" % data)

    def test_compose_10_log_fail(self):
        """Test that requesting log for a bad uuid fails."""
        resp = self.server.get("/api/v0/compose/log/NO-UUID-TO-SEE-HERE")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data["status"], False, "Failed to get an error for a bad uuid: %s" % data)
        self.assertEqual(data["errors"], ["NO-UUID-TO-SEE-HERE is not a valid build uuid"],
                                         "Failed to get errors: %s" % data)

    def test_compose_11_create_failed(self):
        """Test the /api/v0/compose routes with a failed test compose"""
        test_compose = {"blueprint_name": "glusterfs",
                        "compose_type": "tar",
                        "branch": "master"}

        resp = self.server.post("/api/v0/compose?test=1",
                                data=json.dumps(test_compose),
                                content_type="application/json")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data["status"], True, "Failed to start test compose: %s" % data)

        build_id = data["build_id"]

        # Is it in the queue list (either new or run is fine, based on timing)
        resp = self.server.get("/api/v0/compose/queue")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        ids = [e["id"] for e in data["new"] + data["run"]]
        self.assertEqual(build_id in ids, True, "Failed to add build to the queue")

        # Wait for it to start
        self.assertEqual(self.wait_for_status(build_id, ["RUNNING"]), True, "Failed to start test compose")

        # Wait for it to finish
        self.assertEqual(self.wait_for_status(build_id, ["FAILED"]), True, "Failed to finish test compose")

        resp = self.server.get("/api/v0/compose/info/%s" % build_id)
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data["queue_status"], "FAILED", "Build not in FAILED state")

        # Test the /api/v0/compose/failed route
        resp = self.server.get("/api/v0/compose/failed")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        ids = [e["id"] for e in data["failed"]]
        self.assertEqual(build_id in ids, True, "Failed build not listed by /compose/failed")

        # Test the /api/v0/compose/finished route
        resp = self.server.get("/api/v0/compose/finished")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data["finished"], [], "Finished build not listed by /compose/finished")

        # Test the /api/v0/compose/status/<uuid> route
        resp = self.server.get("/api/v0/compose/status/%s" % build_id)
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        ids = [(e["id"], e["queue_status"]) for e in data["uuids"]]
        self.assertEqual((build_id, "FAILED") in ids, True, "Failed build not listed by /compose/status")

        # Test the /api/v0/compose/cancel/<uuid> route
        resp = self.server.post("/api/v0/compose?test=1",
                                data=json.dumps(test_compose),
                                content_type="application/json")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data["status"], True, "Failed to start test compose: %s" % data)

        cancel_id = data["build_id"]

        # Wait for it to start
        self.assertEqual(self.wait_for_status(cancel_id, ["RUNNING"]), True, "Failed to start test compose")

        # Cancel the build
        resp = self.server.delete("/api/v0/compose/cancel/%s" % cancel_id)
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data["status"], True, "Failed to cancel test compose: %s" % data)

        # Delete the failed build
        # Test the /api/v0/compose/delete/<uuid> route
        resp = self.server.delete("/api/v0/compose/delete/%s" % build_id)
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        ids = [(e["uuid"], e["status"]) for e in data["uuids"]]
        self.assertEqual((build_id, True) in ids, True, "Failed to delete test compose: %s" % data)

        # Make sure the failed list is empty
        resp = self.server.get("/api/v0/compose/failed")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data["failed"], [], "Failed to delete the failed build: %s" % data)

    def test_compose_12_create_finished(self):
        """Test the /api/v0/compose routes with a finished test compose"""
        test_compose = {"blueprint_name": "custom-base",
                        "compose_type": "tar",
                        "branch": "master"}

        resp = self.server.post("/api/v0/compose?test=2",
                                data=json.dumps(test_compose),
                                content_type="application/json")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data["status"], True, "Failed to start test compose: %s" % data)

        build_id = data["build_id"]

        # Is it in the queue list (either new or run is fine, based on timing)
        resp = self.server.get("/api/v0/compose/queue")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        ids = [e["id"] for e in data["new"] + data["run"]]
        self.assertEqual(build_id in ids, True, "Failed to add build to the queue")

        # Wait for it to start
        self.assertEqual(self.wait_for_status(build_id, ["RUNNING"]), True, "Failed to start test compose")

        # Wait for it to finish
        self.assertEqual(self.wait_for_status(build_id, ["FINISHED"]), True, "Failed to finish test compose")

        resp = self.server.get("/api/v0/compose/info/%s" % build_id)
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data["queue_status"], "FINISHED", "Build not in FINISHED state")

        # Test the /api/v0/compose/finished route
        resp = self.server.get("/api/v0/compose/finished")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        ids = [e["id"] for e in data["finished"]]
        self.assertEqual(build_id in ids, True, "Finished build not listed by /compose/finished")

        # Test the /api/v0/compose/failed route
        resp = self.server.get("/api/v0/compose/failed")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data["failed"], [], "Failed build not listed by /compose/failed")

        # Test the /api/v0/compose/status/<uuid> route
        resp = self.server.get("/api/v0/compose/status/%s" % build_id)
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        ids = [(e["id"], e["queue_status"]) for e in data["uuids"]]
        self.assertEqual((build_id, "FINISHED") in ids, True, "Finished build not listed by /compose/status")

        # Test the /api/v0/compose/metadata/<uuid> route
        resp = self.server.get("/api/v0/compose/metadata/%s" % build_id)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data) > 1024, True)

        # Test the /api/v0/compose/results/<uuid> route
        resp = self.server.get("/api/v0/compose/results/%s" % build_id)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data) > 1024, True)

        # Test the /api/v0/compose/image/<uuid> route
        resp = self.server.get("/api/v0/compose/image/%s" % build_id)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data) > 0, True)
        self.assertEqual(resp.data, b"TEST IMAGE")

        # Examine the final-kickstart.ks for the customizations
        # A bit kludgy since it examines the filesystem directly, but that's better than unpacking the metadata
        final_ks = open(joinpaths(self.repo_dir, "var/lib/lorax/composer/results/", build_id, "final-kickstart.ks")).read()

        # Check for the expected customizations in the kickstart
        self.assertTrue("network --hostname=" in final_ks)
        self.assertTrue("sshkey --user root" in final_ks)

        # Delete the finished build
        # Test the /api/v0/compose/delete/<uuid> route
        resp = self.server.delete("/api/v0/compose/delete/%s" % build_id)
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        ids = [(e["uuid"], e["status"]) for e in data["uuids"]]
        self.assertEqual((build_id, True) in ids, True, "Failed to delete test compose: %s" % data)

        # Make sure the finished list is empty
        resp = self.server.get("/api/v0/compose/finished")
        data = json.loads(resp.data)
        self.assertNotEqual(data, None)
        self.assertEqual(data["finished"], [], "Failed to delete the failed build: %s" % data)
