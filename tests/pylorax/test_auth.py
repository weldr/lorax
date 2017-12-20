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
import tempfile
import unittest

import pylorax.api.auth as auth
from pylorax.api.config import configure
from pylorax.api.server import server

class AuthTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # Minimal setup, since it is only testing functions in auth, not the API Server
        repo_dir = tempfile.mkdtemp(prefix="lorax.test.repo.")
        server.config["COMPOSER_CFG"] = configure(root_dir=repo_dir, test_config=True)

        # Disable authentication for these tests
        server.config["COMPOSER_CFG"].set("composer", "auth", "0")
        server.config['TESTING'] = True
        self.server = server

        # Initialize JWT
        auth.setup_jwt(server)

        # No extra headers to send
        self.jwt_header = {}

    @classmethod
    def tearDownClass(self):
        pass

    def test_user_allowed(self):
        """Test user_allowed function with conf [users] section"""
        with self.server.test_request_context():
            self.assertEqual(auth.user_allowed("root"), True)
            self.assertEqual(auth.user_allowed("nonuser"), False)

            self.server.config["COMPOSER_CFG"].set("users", "newuser", "1")
            self.assertEqual(auth.user_allowed("newuser"), True)

    def test_jwt_test_auth(self):
        """Test the jwt test auth function"""
        with self.server.test_request_context():
            self.assertEqual(type(auth.jwt_test_auth("testuser", "goodpassword")), type(auth.User("testuser")))
            self.assertEqual(auth.jwt_test_auth("testuser", "badpassword"), None)
            self.assertEqual(auth.jwt_test_auth("nouser", "badpassword"), None)

    def test_auth_enabled(self):
        """Test auth_enabled function"""
        with self.server.test_request_context():
            self.assertEqual(auth.auth_enabled(), False)
            self.server.config["COMPOSER_CFG"].set("composer", "auth", "1")
            self.assertEqual(auth.auth_enabled(), True)
