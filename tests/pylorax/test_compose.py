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
from io import StringIO
import unittest

from pylorax.api.compose import add_customizations, compose_types
from pylorax.api.compose import bootloader_append, customize_ks_template
from pylorax.api.recipes import recipe_from_toml
from pylorax.sysutils import joinpaths

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

ROOT_USER = BASE_RECIPE + """[[customizations.user]]
name = "root"
"""

USER_KEY = """
key = "A SSH KEY FOR THE USER"
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

KS_USER_ALL = '''sshkey --user tester "A SSH KEY FOR THE USER"
user --name tester --homedir /opt/users/tester/ --iscrypted --password "$6$CHO2$3rN8eviE2t50lmVyBYihTgVRHcaecmeCk31LeOUleVK/R/aeWVHVZDi26zAH.o0ywBKH9Tc0/wm7sW/q39uyd1" --shell /usr/bin/zsh --uid 1013 --gid 4242 --gecos "a test user account"
rootpw --lock
'''

# ROOT TESTS
ROOT_CRYPT = ROOT_USER + USER_CRYPT
ROOT_PLAIN = ROOT_USER + USER_PLAIN
ROOT_CRYPT_KEY = ROOT_USER + USER_CRYPT + USER_KEY
ROOT_PLAIN_KEY = ROOT_USER + USER_PLAIN + USER_KEY
ROOT_KEY = ROOT_USER + USER_KEY

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

    def test_no_customizations(self):
        """Test not setting any customizations"""
        self.assertCustomization(BASE_RECIPE, "rootpw --lock")

    def test_set_hostname(self):
        """Test setting the hostname"""
        self.assertCustomization(HOSTNAME, "network --hostname=testhostname")
        self.assertCustomization(HOSTNAME, "rootpw --lock")

    def test_set_sshkey(self):
        """Test setting sshkey without user"""
        self.assertCustomization(SSHKEY, 'sshkey --user root "ROOT SSH KEY"')

    def test_sshkey_only(self):
        """Test adding a sshkey to an existing user account"""
        self.assertCustomization(USER + USER_KEY, 'sshkey --user tester "A SSH KEY FOR THE USER"')
        self.assertCustomization(USER + USER_KEY, "rootpw --lock")

    def test_create_user(self):
        """Test creating a user with no options"""
        self.assertCustomization(USER, "user --name tester")
        self.assertCustomization(USER, "rootpw --lock")

    def test_create_user_desc(self):
        """Test creating a user with a description"""
        self.assertCustomization(USER + USER_DESC, '--gecos "a test user account"')
        self.assertCustomization(USER + USER_DESC, "rootpw --lock")

    def test_create_user_crypt(self):
        """Test creating a user with a pre-crypted password"""
        self.assertCustomization(USER + USER_CRYPT, '--password "$6$CHO2$3r')
        self.assertCustomization(USER + USER_CRYPT, "rootpw --lock")

    def test_create_user_plain(self):
        """Test creating a user with a plaintext password"""
        self.assertCustomization(USER + USER_PLAIN, '--password "plainpassword"')
        self.assertCustomization(USER + USER_PLAIN, "rootpw --lock")

    def test_create_user_home(self):
        """Test creating user with a home directory"""
        self.assertCustomization(USER + USER_HOME, "--homedir /opt/users/tester/")
        self.assertCustomization(USER + USER_HOME, "rootpw --lock")

    def test_create_user_shell(self):
        """Test creating user with shell set"""
        self.assertCustomization(USER + USER_SHELL, "--shell /usr/bin/zsh")
        self.assertCustomization(USER + USER_SHELL, "rootpw --lock")

    def test_create_user_uid(self):
        """Test creating user with uid set"""
        self.assertCustomization(USER + USER_UID, "--uid 1013")
        self.assertCustomization(USER + USER_UID, "rootpw --lock")

    def test_create_user_gid(self):
        """Test creating user with gid set"""
        self.assertCustomization(USER + USER_GID, "--gid 4242")
        self.assertCustomization(USER + USER_GID, "rootpw --lock")

    def test_create_user_groups(self):
        """Test creating user with group membership"""
        self.assertCustomization(USER + USER_GROUPS, "--groups wheel,users")
        self.assertCustomization(USER + USER_GROUPS, "rootpw --lock")

    def test_user_same_group(self):
        """Test creating a group with the same name as a user"""

        # Creating a group with the same name should skip the group creation
        self.assertCustomization(USER_GROUP, "user --name tester")
        self.assertNotCustomization(USER_GROUP, "group --name tester")
        self.assertCustomization(USER_GROUP, "rootpw --lock")

    def test_create_user_all(self):
        """Test creating user with all settings"""
        r = recipe_from_toml(USER_ALL)
        f = StringIO()
        add_customizations(f, r)
        self.assertEqual(KS_USER_ALL, f.getvalue())

    def test_create_group(self):
        """Test creating group without gid set"""
        self.assertCustomization(GROUP, "group --name testgroup")
        self.assertCustomization(GROUP, "rootpw --lock")

    def test_create_group_gid(self):
        """Test creating group with gid set"""
        self.assertCustomization(GROUP_GID, "group --name testgroup --gid 1011")
        self.assertCustomization(GROUP_GID, "rootpw --lock")

    def test_root_crypt(self):
        self.assertCustomization(ROOT_CRYPT, 'rootpw --iscrypted "$6$CHO2$3r')
        self.assertNotCustomization(ROOT_CRYPT, "rootpw --lock")

    def test_root_plain(self):
        self.assertCustomization(ROOT_PLAIN, 'rootpw --plaintext "plainpassword"')
        self.assertNotCustomization(ROOT_PLAIN, "rootpw --lock")

    def test_root_crypt_key(self):
        self.assertCustomization(ROOT_CRYPT_KEY, 'rootpw --iscrypted "$6$CHO2$3r')
        self.assertCustomization(ROOT_CRYPT_KEY, 'sshkey --user root "A SSH KEY FOR THE USER"')
        self.assertNotCustomization(ROOT_CRYPT_KEY, "rootpw --lock")

    def test_root_plain_key(self):
        self.assertCustomization(ROOT_PLAIN_KEY, 'rootpw --plaintext "plainpassword"')
        self.assertCustomization(ROOT_PLAIN_KEY, 'sshkey --user root "A SSH KEY FOR THE USER"')
        self.assertNotCustomization(ROOT_PLAIN_KEY, "rootpw --lock")

    def test_bootloader_append(self):
        """Test bootloader_append function"""

        self.assertEqual(bootloader_append("", "nosmt=force"), 'bootloader --append="nosmt=force" --location=none')
        self.assertEqual(bootloader_append("", "nosmt=force console=ttyS0,115200n8"),
                         'bootloader --append="nosmt=force console=ttyS0,115200n8" --location=none')
        self.assertEqual(bootloader_append("bootloader --location=none", "nosmt=force"),
                         'bootloader --append="nosmt=force" --location=none')
        self.assertEqual(bootloader_append("bootloader --location=none", "console=ttyS0,115200n8 nosmt=force"),
                         'bootloader --append="console=ttyS0,115200n8 nosmt=force" --location=none')
        self.assertEqual(bootloader_append('bootloader --append="no_timer_check console=ttyS0,115200n8" --location=mbr', "nosmt=force"),
                         'bootloader --append="no_timer_check console=ttyS0,115200n8 nosmt=force" --location=mbr')
        self.assertEqual(bootloader_append('bootloader --append="console=tty1" --location=mbr --password="BADPASSWORD"', "nosmt=force"),
                         'bootloader --append="console=tty1 nosmt=force" --location=mbr --password="BADPASSWORD"')

    def _checkBootloader(self, result, append_str):
        """Find the bootloader line and make sure append_str is in it"""

        for line in result.splitlines():
            if line.startswith("bootloader") and append_str in line:
                return True
        return False

    def test_customize_ks_template(self):
        """Test that [customizations.kernel] works correctly"""
        blueprint_data = """name = "test-kernel"
description = "test recipe"
version = "0.0.1"

[customizations.kernel]
append="nosmt=force"
"""
        recipe = recipe_from_toml(blueprint_data)

        # Test against a kickstart without bootloader
        result = customize_ks_template("firewall --enabled\n", recipe)
        self.assertTrue(self._checkBootloader(result, "nosmt=force"))

        # Test against all of the available templates
        share_dir = "./share/"
        errors = []
        for compose_type in compose_types(share_dir):
            # Read the kickstart template for this type
            ks_template_path = joinpaths(share_dir, "composer", compose_type) + ".ks"
            ks_template = open(ks_template_path, "r").read()
            result = customize_ks_template(ks_template, recipe)
            if not self._checkBootloader(result, "nosmt=force"):
                errors.append(("compose_type %s failed" % compose_type, result))

        # Print the bad results
        for e, r in errors:
            print("%s:\n%s\n\n" % (e, r))

        self.assertEqual(errors, [])
