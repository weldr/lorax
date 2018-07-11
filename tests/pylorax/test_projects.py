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
from glob import glob
import os
import mock
import time
import shutil
import tempfile
import unittest

from yum.Errors import YumBaseError

from pylorax.sysutils import joinpaths
from pylorax.api.config import configure, make_yum_dirs
from pylorax.api.projects import api_time, api_changelog, yaps_to_project, yaps_to_project_info
from pylorax.api.projects import tm_to_dep, yaps_to_module, projects_list, projects_info, projects_depsolve
from pylorax.api.projects import modules_list, modules_info, ProjectsError, dep_evra, dep_nevra
from pylorax.api.projects import repo_to_source, get_repo_sources, delete_repo_source, source_to_repo
from pylorax.api.projects import yum_repo_to_file_repo
from pylorax.api.yumbase import get_base_object


class Yaps(object):
    """Test class for yaps tests"""
    name = "name"
    summary = "summary"
    description = "description"
    url = "url"
    epoch = 1
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
    epoch = 1
    version = "version"
    release = "release"
    arch = "arch"


class ProjectsTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="lorax.test.repo.")
        self.config = configure(root_dir=self.tmp_dir, test_config=True)
        make_yum_dirs(self.config)
        self.yb = get_base_object(self.config)
        os.environ["TZ"] = "UTC"
        time.tzset()

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.tmp_dir)

    def test_api_time(self):
        self.assertEqual(api_time(499222800), "1985-10-27T01:00:00")

    def test_api_changelog(self):
        self.assertEqual(api_changelog([[0,1,"Heavy!"], [0, 1, "Light!"]]), "Heavy!")

    def test_api_changelog_empty_list(self):
        self.assertEqual(api_changelog([]), '')

    def test_api_changelog_missing_text_entry(self):
        self.assertEqual(api_changelog([('now', 'atodorov')]), '')

    def test_yaps_to_project(self):
        result = {"name":"name",
                  "summary":"summary",
                  "description":"description",
                  "homepage":"url",
                  "upstream_vcs":"UPSTREAM_VCS"}

        y = Yaps()
        self.assertEqual(yaps_to_project(y), result)

    def test_yaps_to_project_info(self):
        build = {"epoch":1,
                 "release":"release",
                 "arch":"arch",
                 "build_time":"1985-10-27T01:00:00",
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
                  "epoch":1,
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
               "epoch": 0,
               "name": "basesystem",
               "release": "7.el7",
               "version": "10.0"}
        self.assertEqual(dep_evra(dep), "10.0-7.el7.noarch")

    def test_dep_evra_with_epoch_not_zero(self):
        dep = {"arch": "x86_64",
               "epoch": 2,
               "name": "tog-pegasus-libs",
               "release": "3.el7",
               "version": "2.14.1"}
        self.assertEqual(dep_evra(dep), "2:2.14.1-3.el7.x86_64")

    def test_dep_nevra(self):
        dep = {"arch": "noarch",
               "epoch": 0,
               "name": "basesystem",
               "release": "7.el7",
               "version": "10.0"}
        self.assertEqual(dep_nevra(dep), "basesystem-10.0-7.el7.noarch")

    def test_projects_list(self):
        projects = projects_list(self.yb)
        self.assertEqual(len(projects) > 10, True)

    def test_projects_list_yum_raises_exception(self):
        with self.assertRaises(ProjectsError):
            with mock.patch.object(self.yb, 'doPackageLists', side_effect=YumBaseError('TESTING')):
                projects_list(self.yb)

    def test_projects_info(self):
        projects = projects_info(self.yb, ["bash"])

        self.assertEqual(projects[0]["name"], "bash")
        self.assertEqual(projects[0]["builds"][0]["source"]["license"], "GPLv3+")

    def test_projects_info_yum_raises_exception(self):
        with self.assertRaises(ProjectsError):
            with mock.patch.object(self.yb, 'doPackageLists', side_effect=YumBaseError('TESTING')):
                projects_info(self.yb, ["bash"])

    def test_projects_depsolve(self):
        deps = projects_depsolve(self.yb, [("bash", "*.*")], [])
        self.assertTrue(len(deps) > 3)
        self.assertTrue("basesystem" in [dep["name"] for dep in deps])

    def test_projects_depsolve_version(self):
        """Test that depsolving with a partial wildcard version works"""
        deps = projects_depsolve(self.yb, [("bash", "4.*")], [])
        self.assertEqual(deps[1]["name"], "bash")

        deps = projects_depsolve(self.yb, [("bash", "4.2.*")], [])
        self.assertEqual(deps[1]["name"], "bash")

    def test_projects_depsolve_oldversion(self):
        """Test that depsolving a specific non-existant version fails"""
        with self.assertRaises(ProjectsError):
            deps = projects_depsolve(self.yb, [("bash", "1.0.0")], [])
            self.assertEqual(deps[1]["name"], "bash")

    def test_projects_depsolve_fail(self):
        with self.assertRaises(ProjectsError):
            projects_depsolve(self.yb, [("nada-package", "*.*")], [])

    def test_modules_list(self):
        modules = modules_list(self.yb, None)

        self.assertEqual(len(modules) > 10, True)
        self.assertEqual(modules[0]["group_type"], "rpm")

        modules = modules_list(self.yb, ["g*"])
        self.assertEqual(modules[0]["name"].startswith("g"), True)

    def test_modules_list_yum_raises_exception(self):
        with self.assertRaises(ProjectsError):
            with mock.patch.object(self.yb, 'doPackageLists', side_effect=YumBaseError('TESTING')):
                modules_list(self.yb, None)

    def test_modules_info(self):
        modules = modules_info(self.yb, ["bash"])

        print(modules)
        self.assertTrue(len(modules) > 0)
        self.assertTrue(len(modules[0]["dependencies"]) > 3)
        self.assertEqual(modules[0]["name"], "bash")
        self.assertTrue("basesystem" in [dep["name"] for dep in modules[0]["dependencies"]])

    def test_modules_info_yum_raises_exception(self):
        with self.assertRaises(ProjectsError):
            with mock.patch.object(self.yb, 'doPackageLists', side_effect=YumBaseError('TESTING')):
                modules_info(self.yb, ["bash"])

    def test_groups_depsolve(self):
        deps = projects_depsolve(self.yb, [], ["base"])
        names = [grp["name"] for grp in deps]
        self.assertTrue("acl" in names)                 # mandatory package
        self.assertTrue("bash-completion" in names)     # default package
        self.assertFalse("gpm" in names)                # optional package


class ConfigureTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="lorax.test.configure.")
        self.conf_file = os.path.join(self.tmp_dir, 'test.conf')
        open(self.conf_file, 'w').write("[composer]\ncache_dir = /tmp/cache-test")

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.tmp_dir)

    def test_configure_reads_existing_file(self):
        config = configure(conf_file=self.conf_file)
        self.assertEqual(config.get('composer', 'cache_dir'), '/tmp/cache-test')

    def test_configure_reads_non_existing_file(self):
        config = configure(conf_file=self.conf_file + '.non-existing')
        self.assertEqual(config.get('composer', 'cache_dir'), '/var/tmp/composer/cache')

class FakeRepoBaseUrl(object):
    id = "fake-repo-baseurl"
    baseurl = ["https://fake-repo.base.url"]
    metalink = ""
    mirrorlist = ""
    proxy = ""
    sslverify = True
    gpgcheck = True
    gpgkey = []

def fakerepo_baseurl():
    return {
        "check_gpg": True,
        "check_ssl": True,
        "name": "fake-repo-baseurl",
        "system": False,
        "type": "yum-baseurl",
        "url": "https://fake-repo.base.url"
    }

def fakerepo_baseurl_str():
    return """[fake-repo-baseurl]
baseurl = https://fake-repo.base.url
sslverify = True
gpgcheck = True
"""

class FakeSystemRepo(object):
    id = "fake-system-repo"
    baseurl = ["https://fake-repo.base.url"]
    metalink = ""
    mirrorlist = ""
    proxy = ""
    sslverify = True
    gpgcheck = True
    gpgkey = []

def fakesystem_repo():
    return {
        "check_gpg": True,
        "check_ssl": True,
        "name": "fake-system-repo",
        "system": True,
        "type": "yum-baseurl",
        "url": "https://fake-repo.base.url"
    }

class FakeRepoMetalink(object):
    id = "fake-repo-metalink"
    baseurl = []
    metalink = "https://fake-repo.metalink"
    proxy = ""
    sslverify = True
    gpgcheck = True
    gpgkey = []

def fakerepo_metalink():
    return {
        "check_gpg": True,
        "check_ssl": True,
        "name": "fake-repo-metalink",
        "system": False,
        "type": "yum-metalink",
        "url": "https://fake-repo.metalink"
    }

def fakerepo_metalink_str():
    return """[fake-repo-metalink]
metalink = https://fake-repo.metalink
sslverify = True
gpgcheck = True
"""

class FakeRepoMirrorlist(object):
    id = "fake-repo-mirrorlist"
    baseurl = []
    metalink = ""
    mirrorlist = "https://fake-repo.mirrorlist"
    proxy = ""
    sslverify = True
    gpgcheck = True
    gpgkey = []

def fakerepo_mirrorlist():
    return {
        "check_gpg": True,
        "check_ssl": True,
        "name": "fake-repo-mirrorlist",
        "system": False,
        "type": "yum-mirrorlist",
        "url": "https://fake-repo.mirrorlist"
    }

def fakerepo_mirrorlist_str():
    return """[fake-repo-mirrorlist]
mirrorlist = https://fake-repo.mirrorlist
sslverify = True
gpgcheck = True
"""

class FakeRepoProxy(object):
    id = "fake-repo-proxy"
    baseurl = ["https://fake-repo.base.url"]
    metalink = ""
    mirrorlist = ""
    proxy = "https://fake-repo.proxy"
    sslverify = True
    gpgcheck = True
    gpgkey = []

def fakerepo_proxy():
    return {
        "check_gpg": True,
        "check_ssl": True,
        "name": "fake-repo-proxy",
        "proxy": "https://fake-repo.proxy",
        "system": False,
        "type": "yum-baseurl",
        "url": "https://fake-repo.base.url"
    }

def fakerepo_proxy_str():
    return """[fake-repo-proxy]
baseurl = https://fake-repo.base.url
proxy = https://fake-repo.proxy
sslverify = True
gpgcheck = True
"""

class FakeRepoGPGKey(object):
    id = "fake-repo-gpgkey"
    baseurl = ["https://fake-repo.base.url"]
    metalink = ""
    mirrorlist = ""
    proxy = ""
    sslverify = True
    gpgcheck = True
    gpgkey = ["https://fake-repo.gpgkey"]

def fakerepo_gpgkey():
    return {
        "check_gpg": True,
        "check_ssl": True,
        "gpgkey_urls": [
            "https://fake-repo.gpgkey"
        ],
        "name": "fake-repo-gpgkey",
        "system": False,
        "type": "yum-baseurl",
        "url": "https://fake-repo.base.url"
    }

def fakerepo_gpgkey_str():
    return """[fake-repo-gpgkey]
baseurl = https://fake-repo.base.url
sslverify = True
gpgcheck = True
gpgkey = https://fake-repo.gpgkey
"""

def yum_to_file(d):
    """Test function to convert a source to a dict and then to a yum repo string"""
    return yum_repo_to_file_repo(source_to_repo(d))

class SourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="lorax.test.repo.")
        for f in glob("./tests/pylorax/repos/*.repo"):
            shutil.copy2(f, self.tmp_dir)

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.tmp_dir)

    def test_repo_to_source_baseurl(self):
        """Test a repo with a baseurl"""
        self.assertEqual(repo_to_source(FakeRepoBaseUrl(), False), fakerepo_baseurl())

    def test_system_repo(self):
        """Test a system repo with a baseurl"""
        self.assertEqual(repo_to_source(FakeSystemRepo(), True), fakesystem_repo())

    def test_repo_to_source_metalink(self):
        """Test a repo with a metalink"""
        self.assertEqual(repo_to_source(FakeRepoMetalink(), False), fakerepo_metalink())

    def test_repo_to_source_mirrorlist(self):
        """Test a repo with a mirrorlist"""
        self.assertEqual(repo_to_source(FakeRepoMirrorlist(), False), fakerepo_mirrorlist())

    def test_repo_to_source_proxy(self):
        """Test a repo with a proxy"""
        self.assertEqual(repo_to_source(FakeRepoProxy(), False), fakerepo_proxy())

    def test_repo_to_source_gpgkey(self):
        """Test a repo with a GPG key"""
        self.assertEqual(repo_to_source(FakeRepoGPGKey(), False), fakerepo_gpgkey())

    def test_get_repo_sources(self):
        """Test getting a list of sources from a repo directory"""
        sources = get_repo_sources(joinpaths(self.tmp_dir, "*.repo"))
        self.assertTrue("lorax-1" in sources)
        self.assertTrue("lorax-2" in sources)

    def test_delete_source_multiple(self):
        """Test deleting a source from a repo file with multiple entries"""
        delete_repo_source(joinpaths(self.tmp_dir, "*.repo"), "lorax-3")
        sources = get_repo_sources(joinpaths(self.tmp_dir, "*.repo"))
        self.assertTrue("lorax-3" not in sources)

    def test_delete_source_single(self):
        """Test deleting a source from a repo with only 1 entry"""
        delete_repo_source(joinpaths(self.tmp_dir, "*.repo"), "single-repo")
        sources = get_repo_sources(joinpaths(self.tmp_dir, "*.repo"))
        self.assertTrue("single-repo" not in sources)
        self.assertTrue(not os.path.exists(joinpaths(self.tmp_dir, "single.repo")))

    def test_delete_source_other(self):
        """Test deleting a source from a repo that doesn't match the source name"""
        with self.assertRaises(ProjectsError):
            delete_repo_source(joinpaths(self.tmp_dir, "*.repo"), "unknown-source")
        sources = get_repo_sources(joinpaths(self.tmp_dir, "*.repo"))
        self.assertTrue("lorax-1" in sources)
        self.assertTrue("lorax-2" in sources)
        self.assertTrue("lorax-4" in sources)
        self.assertTrue("other-repo" in sources)

    def test_source_to_repo_baseurl(self):
        """Test creating a yum.yumRepo.YumRepository with a baseurl"""
        repo = source_to_repo(fakerepo_baseurl())
        self.assertEqual(repo["baseurl"][0], fakerepo_baseurl()["url"])

    def test_source_to_repo_metalink(self):
        """Test creating a yum.yumRepo.YumRepository with a metalink"""
        repo = source_to_repo(fakerepo_metalink())
        self.assertEqual(repo["metalink"], fakerepo_metalink()["url"])

    def test_source_to_repo_mirrorlist(self):
        """Test creating a yum.yumRepo.YumRepository with a mirrorlist"""
        repo = source_to_repo(fakerepo_mirrorlist())
        self.assertEqual(repo["mirrorlist"], fakerepo_mirrorlist()["url"])

    def test_source_to_repo_proxy(self):
        """Test creating a yum.yumRepo.YumRepository with a proxy"""
        repo = source_to_repo(fakerepo_proxy())
        self.assertEqual(repo["proxy"], fakerepo_proxy()["proxy"])

    def test_source_to_repo_gpgkey(self):
        """Test creating a yum.yumRepo.YumRepository with a proxy"""
        repo = source_to_repo(fakerepo_gpgkey())
        self.assertEqual(repo["gpgkey"], fakerepo_gpgkey()["gpgkey_urls"])

    def test_drtfr_baseurl(self):
        """Test creating a yum .repo file from a baseurl Repo object"""
        self.assertEqual(yum_to_file(fakerepo_baseurl()), fakerepo_baseurl_str())

    def test_drtfr_metalink(self):
        """Test creating a yum .repo file from a metalink Repo object"""
        self.assertEqual(yum_to_file(fakerepo_metalink()), fakerepo_metalink_str())

    def test_drtfr_mirrorlist(self):
        """Test creating a yum .repo file from a mirrorlist Repo object"""
        self.assertEqual(yum_to_file(fakerepo_mirrorlist()), fakerepo_mirrorlist_str())

    def test_drtfr_proxy(self):
        """Test creating a yum .repo file from a baseurl Repo object with proxy"""
        self.assertEqual(yum_to_file(fakerepo_proxy()), fakerepo_proxy_str())

    def test_drtfr_gpgkey(self):
        """Test creating a yum .repo file from a baseurl Repo object with gpgkey"""
        self.assertEqual(yum_to_file(fakerepo_gpgkey()), fakerepo_gpgkey_str())
