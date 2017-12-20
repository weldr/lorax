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
from threading import Lock

from pylorax.api.auth import setup_jwt
from pylorax.api.config import configure
from pylorax.api.recipes import open_or_create_repo, commit_recipe_directory
from pylorax.api.server import server, GitLock, YumLock
from pylorax.api.yumbase import get_base_object

from common import ServerCommon

class ServerTestCase(ServerCommon):
    """Test the server API without authentication"""
    __test__ = True

    @classmethod
    def setUpClass(self):
        repo_dir = tempfile.mkdtemp(prefix="lorax.test.repo.")
        server.config["REPO_DIR"] = repo_dir
        repo = open_or_create_repo(server.config["REPO_DIR"])
        server.config["GITLOCK"] = GitLock(repo=repo, lock=Lock(), dir=repo_dir)

        server.config["COMPOSER_CFG"] = configure(root_dir=repo_dir, test_config=True)

        # Disable authentication for these tests
        server.config["COMPOSER_CFG"].set("composer", "auth", "0")

        yb = get_base_object(server.config["COMPOSER_CFG"])
        server.config["YUMLOCK"] = YumLock(yb=yb, lock=Lock())

        server.config['TESTING'] = True
        self.server = server.test_client()

        self.examples_path = "./tests/pylorax/recipes/"

        # Import the example recipes
        commit_recipe_directory(server.config["GITLOCK"].repo, "master", self.examples_path)

        # Initialize JWT
        setup_jwt(server)

        # No extra headers to send
        self.jwt_header = {}

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(server.config["REPO_DIR"])
