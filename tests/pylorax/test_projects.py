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
import shutil
import tempfile
import unittest

from pylorax.api.config import configure
from pylorax.api.projects import api_time, api_changelog, yaps_to_project, yaps_to_project_info
from pylorax.api.projects import tm_to_dep, yaps_to_module, projects_list, projects_info, projects_depsolve
from pylorax.api.projects import modules_list, modules_info, ProjectsError, dep_evra
from pylorax.api.yumbase import get_base_object


class Yaps(object):
    """Test class for yaps tests"""
    name = "name"
    summary = "summary"
    description = "description"
    url = "url"
    epoch = "epoch"
    release = "release"
    arch = "arch"
    buildtime = 499222800
    license = "license"
    version = "version"

    def returnChangelog(self):
        return [[0,1,"Heavy!"]]


class TM(object):
    """Test class for tm test"""
    name = "name"
    epoch = "epoch"
    version = "version"
    release = "release"
    arch = "arch"


class ProjectsTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="lorax.test.repo.")
        self.config = configure(root_dir=self.tmp_dir, test_config=True)
        self.yb = get_base_object(self.config)

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.tmp_dir)

    def test_api_time(self):
        self.assertEqual(api_time(499222800), "1985-10-26T21:00:00")

    def test_api_changelog(self):
        self.assertEqual(api_changelog([[0,1,"Heavy!"]]), "Heavy!")

    def test_yaps_to_project(self):
        result = {"name":"name",
                  "summary":"summary",
                  "description":"description",
                  "homepage":"url",
                  "upstream_vcs":"UPSTREAM_VCS"}

        y = Yaps()
        self.assertEqual(yaps_to_project(y), result)

    def test_yaps_to_project_info(self):
        build = {"epoch":"epoch",
                 "release":"release",
                 "arch":"arch",
                 "build_time":"1985-10-26T21:00:00",
                 "changelog":"Heavy!",
                 "build_config_ref": "BUILD_CONFIG_REF",
                 "build_env_ref":    "BUILD_ENV_REF",
                 "metadata":    {},
                 "source":      {"license":"license",
                                 "version":"version",
                                 "source_ref": "SOURCE_REF",
                                 "metadata":   {}}}

        result = {"name":"name",
                  "summary":"summary",
                  "description":"description",
                  "homepage":"url",
                  "upstream_vcs":"UPSTREAM_VCS",
                  "builds": [build]}

        y = Yaps()
        self.assertEqual(yaps_to_project_info(y), result)

    def test_tm_to_dep(self):
        result = {"name":"name",
                  "epoch":"epoch",
                  "version":"version",
                  "release":"release",
                  "arch":"arch"}

        tm = TM()
        self.assertEqual(tm_to_dep(tm), result)

    def test_yaps_to_module(self):
        result = {"name":"name",
                  "group_type":"rpm"}

        y = Yaps()
        self.assertEqual(yaps_to_module(y), result)

    def test_dep_evra(self):
        dep = {"arch": "noarch",
               "epoch": "0",
               "name": "basesystem",
               "release": "7.el7",
               "version": "10.0"}
        self.assertEqual(dep_evra(dep), "10.0-7.el7.noarch")

    def test_projects_list(self):
        projects = projects_list(self.yb)
        self.assertEqual(len(projects) > 10, True)

    def test_projects_info(self):
        projects = projects_info(self.yb, ["bash"])

        self.assertEqual(projects[0]["name"], "bash")
        self.assertEqual(projects[0]["builds"][0]["source"]["license"], "GPLv3+")

    def test_projects_depsolve(self):
        deps = projects_depsolve(self.yb, ["bash"])

        self.assertEqual(deps[0]["name"], "basesystem")

    def test_projects_depsolve_fail(self):
        with self.assertRaises(ProjectsError):
            projects_depsolve(self.yb, ["nada-package"])

    def test_modules_list(self):
        modules = modules_list(self.yb)

        self.assertEqual(len(modules) > 10, True)
        self.assertEqual(modules[0]["group_type"], "rpm")

    def test_modules_info(self):
        modules = modules_info(self.yb, ["bash"])

        print(modules)
        self.assertEqual(modules[0]["name"], "bash")
        self.assertEqual(modules[0]["dependencies"][0]["name"], "basesystem")
