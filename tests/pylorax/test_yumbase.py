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

from pylorax.api.config import configure, make_yum_dirs
from pylorax.api.yumbase import get_base_object


class YumbaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="lorax.test.yumbase.")
        conf_file = os.path.join(self.tmp_dir, 'test.conf')
        open(conf_file, 'w').write("""[composer]
# releasever different from the current default
releasever = 6
[yum]
proxy = https://proxy.example.com
sslverify = False
[repos]
use_system_repos = False
""")

        # will read the above configuration
        config = configure(conf_file=conf_file, root_dir=self.tmp_dir)
        make_yum_dirs(config)

        # will read composer config and store a yum config file
        self.yb = get_base_object(config)

        # will read the stored yum config file
        self.yumconf = configparser.ConfigParser()
        self.yumconf.read([config.get("composer", "yum_conf")])

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.tmp_dir)

    def test_stores_yum_proxy_from_composer_config(self):
        self.assertEqual('https://proxy.example.com', self.yumconf.get('main', 'proxy'))

    def test_disables_sslverify_if_composer_disables_it(self):
        self.assertEqual('0', self.yumconf.get('main', 'sslverify'))

    def test_sets_releasever_from_composer(self):
        self.assertEqual('6', self.yb.conf.yumvar['releasever'])

    def test_doesnt_use_system_repos(self):
        # no other repos defined for this test
        self.assertEqual({}, self.yb._repos.repos)


class CreateYumDirsTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="lorax.test.yumbase.")

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.tmp_dir)

    def test_creates_missing_yum_root_directory(self):
        config = configure(test_config=True, root_dir=self.tmp_dir)

        # will create the above directory if missing
        make_yum_dirs(config)
        _ = get_base_object(config)

        self.assertTrue(os.path.exists(self.tmp_dir + '/var/tmp/composer/yum/root'))
