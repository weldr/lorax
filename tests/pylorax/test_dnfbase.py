#
# Copyright (C) 2018  Red Hat, Inc.
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
import unittest

import configparser

from pylorax.api.config import configure, make_dnf_dirs
from pylorax.api.dnfbase import get_base_object


class DnfbaseNoSystemReposTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="lorax.test.dnfbase.")
        conf_file = os.path.join(self.tmp_dir, 'test.conf')
        open(conf_file, 'w').write("""[composer]
# releasever different from the current default
releasever = 6
[dnf]
proxy = https://proxy.example.com
sslverify = False
[repos]
use_system_repos = False
""")

        # will read the above configuration
        config = configure(conf_file=conf_file, root_dir=self.tmp_dir)
        make_dnf_dirs(config)

        # will read composer config and store a dnf config file
        self.dbo = get_base_object(config)

        # will read the stored dnf config file
        self.dnfconf = configparser.ConfigParser()
        self.dnfconf.read([config.get("composer", "dnf_conf")])

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.tmp_dir)

    def test_stores_dnf_proxy_from_composer_config(self):
        self.assertEqual('https://proxy.example.com', self.dnfconf.get('main', 'proxy'))

    def test_disables_sslverify_if_composer_disables_it(self):
        self.assertEqual(False, self.dnfconf.getboolean('main', 'sslverify'))

    def test_sets_releasever_from_composer(self):
        self.assertEqual('6', self.dbo.conf.releasever)

    def test_doesnt_use_system_repos(self):
        # no other repos defined for this test
        self.assertEqual({}, self.dbo.repos)


class DnfbaseSystemReposTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="lorax.test.dnfbase.")

        # will read the above configuration
        config = configure(root_dir=self.tmp_dir)
        make_dnf_dirs(config)

        # will read composer config and store a dnf config file
        self.dbo = get_base_object(config)

        # will read the stored dnf config file
        self.dnfconf = configparser.ConfigParser()
        self.dnfconf.read([config.get("composer", "dnf_conf")])

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.tmp_dir)

    def test_uses_system_repos(self):
        # no other repos defined for this test
        self.assertTrue(len(self.dbo.repos) > 0)


class CreateDnfDirsTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="lorax.test.dnfbase.")

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.tmp_dir)

    def test_creates_missing_dnf_root_directory(self):
        config = configure(test_config=True, root_dir=self.tmp_dir)

        # will create the above directory if missing
        make_dnf_dirs(config)

        self.assertTrue(os.path.exists(self.tmp_dir + '/var/tmp/composer/dnf/root'))
