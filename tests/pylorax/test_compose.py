#
# Copyright (C) 2018 Red Hat, Inc.
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
from StringIO import StringIO
import unittest

from pylorax.api.compose import add_customizations
from pylorax.api.recipes import recipe_from_toml

BASE_RECIPE = """name = "test-cases"
description = "Used for testing"
version = "0.0.1"

"""

HOSTNAME = BASE_RECIPE + """[customizations]
hostname = "testhostname"
"""

SSHKEY = BASE_RECIPE + """[[customizations.sshkey]]
user = "root"
key = "ROOT SSH KEY"
"""

USER = BASE_RECIPE + """[[customizations.user]]
name = "tester"
"""

USER_KEY = """
key = "A SSH KEY FOR TESTER"
"""

USER_DESC = """
description = "a test user account"
"""

USER_CRYPT = """
password = "$6$CHO2$3rN8eviE2t50lmVyBYihTgVRHcaecmeCk31LeOUleVK/R/aeWVHVZDi26zAH.o0ywBKH9Tc0/wm7sW/q39uyd1"
"""

USER_PLAIN = """
password = "plainpassword"
"""

USER_HOME = """
home = "/opt/users/tester/"
"""

USER_SHELL = """
shell = "/usr/bin/zsh"
"""

USER_UID = """
uid = 1013
"""

USER_GID = """
gid = 4242
"""

USER_GROUPS = """
groups = ["wheel", "users"]
"""

USER_ALL = USER + USER_KEY + USER_DESC + USER_CRYPT + USER_HOME + USER_SHELL + USER_UID + USER_GID

GROUP = BASE_RECIPE + """[[customizations.group]]
name = "testgroup"
"""

GROUP_GID = GROUP + """
gid = 1011
"""

USER_GROUP = USER + """[[customizations.group]]
name = "tester"
"""

KS_USER_ALL = '''sshkey --user tester "A SSH KEY FOR TESTER"
user --name tester --homedir /opt/users/tester/ --iscrypted --password "$6$CHO2$3rN8eviE2t50lmVyBYihTgVRHcaecmeCk31LeOUleVK/R/aeWVHVZDi26zAH.o0ywBKH9Tc0/wm7sW/q39uyd1" --shell /usr/bin/zsh --uid 1013 --gid 4242 --gecos "a test user account"
'''

class CustomizationsTestCase(unittest.TestCase):
    def assertCustomization(self, test, result):
        r = recipe_from_toml(test)
        f = StringIO()
        add_customizations(f, r)
        self.assertTrue(result in f.getvalue(), f.getvalue())

    def assertNotCustomization(self, test, result):
        r = recipe_from_toml(test)
        f = StringIO()
        add_customizations(f, r)
        self.assertTrue(result not in f.getvalue(), f.getvalue())

    def test_set_hostname(self):
        """Test setting the hostname"""
        self.assertCustomization(HOSTNAME, "network --hostname=testhostname")

    def test_set_sshkey(self):
        """Test setting sshkey without user"""
        self.assertCustomization(SSHKEY, 'sshkey --user root "ROOT SSH KEY"')

    def test_sshkey_only(self):
        """Test adding a sshkey to an existing user account"""
        self.assertCustomization(USER + USER_KEY, 'sshkey --user tester "A SSH KEY FOR TESTER"')

    def test_create_user(self):
        """Test creating a user with no options"""
        self.assertCustomization(USER, "user --name tester")

    def test_create_user_desc(self):
        """Test creating a user with a description"""
        self.assertCustomization(USER + USER_DESC, '--gecos "a test user account"')

    def test_create_user_crypt(self):
        """Test creating a user with a pre-crypted password"""
        self.assertCustomization(USER + USER_CRYPT, '--password "$6$CHO2$3r')

    def test_create_user_plain(self):
        """Test creating a user with a plaintext password"""
        self.assertCustomization(USER + USER_PLAIN, '--password "plainpassword"')

    def test_create_user_home(self):
        """Test creating user with a home directory"""
        self.assertCustomization(USER + USER_HOME, "--homedir /opt/users/tester/")

    def test_create_user_shell(self):
        """Test creating user with shell set"""
        self.assertCustomization(USER + USER_SHELL, "--shell /usr/bin/zsh")

    def test_create_user_uid(self):
        """Test creating user with uid set"""
        self.assertCustomization(USER + USER_UID, "--uid 1013")

    def test_create_user_gid(self):
        """Test creating user with gid set"""
        self.assertCustomization(USER + USER_GID, "--gid 4242")

    def test_create_user_groups(self):
        """Test creating user with group membership"""
        self.assertCustomization(USER + USER_GROUPS, "--groups wheel,users")

    def test_user_same_group(self):
        """Test creating a group with the same name as a user"""

        # Creating a group with the same name should skip the group creation
        self.assertCustomization(USER_GROUP, "user --name tester")
        self.assertNotCustomization(USER_GROUP, "group --name tester")

    def test_create_user_all(self):
        """Test creating user with all settings"""
        r = recipe_from_toml(USER_ALL)
        f = StringIO()
        add_customizations(f, r)
        self.assertEqual(KS_USER_ALL, f.getvalue())

    def test_create_group(self):
        """Test creating group without gid set"""
        self.assertCustomization(GROUP, "group --name testgroup")

    def test_create_group_gid(self):
        """Test creating group with gid set"""
        self.assertCustomization(GROUP_GID, "group --name testgroup --gid 1011")

