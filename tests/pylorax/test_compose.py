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

from pylorax.api.compose import add_customizations, compose_types
from pylorax.api.compose import timezone_cmd, get_timezone_settings
from pylorax.api.compose import lang_cmd, get_languages, keyboard_cmd, get_keyboard_layout
from pylorax.api.compose import get_kernel_append, bootloader_append, customize_ks_template
from pylorax.api.recipes import recipe_from_toml
from pylorax.sysutils import joinpaths

BASE_RECIPE = """name = "test-cases"
description = "Used for testing"
version = "0.0.1"

"""

HOSTNAME = BASE_RECIPE + """[customizations]
hostname = "testhostname"
"""

TIMEZONE = BASE_RECIPE + """[customizations]
timezone = "US/Samoa"
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

    def test_set_hostname(self):
        """Test setting the hostname"""
        self.assertCustomization(HOSTNAME, "network --hostname=testhostname")

    def test_set_sshkey(self):
        """Test setting sshkey without user"""
        self.assertCustomization(SSHKEY, 'sshkey --user root "ROOT SSH KEY"')

    def test_sshkey_only(self):
        """Test adding a sshkey to an existing user account"""
        self.assertCustomization(USER + USER_KEY, 'sshkey --user tester "A SSH KEY FOR THE USER"')

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

    def test_root_crypt(self):
        self.assertCustomization(ROOT_CRYPT, 'rootpw --iscrypted "$6$CHO2$3r')

    def test_root_plain(self):
        self.assertCustomization(ROOT_PLAIN, 'rootpw --plaintext "plainpassword"')

    def test_root_crypt_key(self):
        self.assertCustomization(ROOT_CRYPT_KEY, 'rootpw --iscrypted "$6$CHO2$3r')
        self.assertCustomization(ROOT_CRYPT_KEY, 'sshkey --user root "A SSH KEY FOR THE USER"')

    def test_root_plain_key(self):
        self.assertCustomization(ROOT_PLAIN_KEY, 'rootpw --plaintext "plainpassword"')
        self.assertCustomization(ROOT_PLAIN_KEY, 'sshkey --user root "A SSH KEY FOR THE USER"')
        self.assertNotCustomization(ROOT_PLAIN_KEY, "rootpw --lock")

    def test_get_kernel_append(self):
        """Test get_kernel_append function"""
        blueprint_data = """name = "test-kernel"
description = "test recipe"
version = "0.0.1"
"""
        blueprint2_data = blueprint_data + """
[customizations.kernel]
append="nosmt=force"
"""
        recipe = recipe_from_toml(blueprint_data)
        self.assertEqual(get_kernel_append(recipe), "")

        recipe = recipe_from_toml(blueprint2_data)
        self.assertEqual(get_kernel_append(recipe), "nosmt=force")

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

    def test_get_timezone_settings(self):
        """Test get_timezone_settings function"""
        blueprint_data = """name = "test-kernel"
description = "test recipe"
version = "0.0.1"
"""
        blueprint2_data = blueprint_data + """
[customizations.timezone]
timezone = "US/Samoa"
"""
        blueprint3_data = blueprint_data + """
[customizations.timezone]
ntpservers = ["0.north-america.pool.ntp.org", "1.north-america.pool.ntp.org"]
"""
        blueprint4_data = blueprint_data + """
[customizations.timezone]
timezone = "US/Samoa"
ntpservers = ["0.north-america.pool.ntp.org", "1.north-america.pool.ntp.org"]
"""
        recipe = recipe_from_toml(blueprint_data)
        self.assertEqual(get_timezone_settings(recipe), {})

        recipe = recipe_from_toml(blueprint2_data)
        self.assertEqual(get_timezone_settings(recipe), {"timezone": "US/Samoa"})

        recipe = recipe_from_toml(blueprint3_data)
        self.assertEqual(get_timezone_settings(recipe),
                         {"ntpservers": ["0.north-america.pool.ntp.org", "1.north-america.pool.ntp.org"]})

        recipe = recipe_from_toml(blueprint4_data)
        self.assertEqual(get_timezone_settings(recipe),
                         {"timezone": "US/Samoa",
                          "ntpservers": ["0.north-america.pool.ntp.org", "1.north-america.pool.ntp.org"]})

    def test_timezone_cmd(self):
        """Test timezone_cmd function"""

        self.assertEqual(timezone_cmd("timezone UTC", {}), 'timezone UTC')
        self.assertEqual(timezone_cmd("timezone FOO", {"timezone": "US/Samoa"}),
                         'timezone US/Samoa')
        self.assertEqual(timezone_cmd("timezone FOO",
            {"timezone": "US/Samoa", "ntpservers": ["0.ntp.org", "1.ntp.org"]}),
                         'timezone US/Samoa --ntpservers=0.ntp.org,1.ntp.org')

        self.assertEqual(timezone_cmd("timezone --ntpservers=a,b,c FOO",
            {"timezone": "US/Samoa", "ntpservers": ["0.pool.ntp.org", "1.pool.ntp.org"]}),
                         'timezone US/Samoa --ntpservers=0.pool.ntp.org,1.pool.ntp.org')

    def test_get_languages(self):
        """Test get_languages function"""
        blueprint_data = """name = "test-locale"
description = "test recipe"
version = "0.0.1"
        """
        blueprint2_data = blueprint_data + """
[customizations.locale]
languages = ["en_CA.utf8", "en_HK.utf8"]
"""
        blueprint3_data = blueprint_data + """
[customizations.locale]
keyboard = "de (dvorak)"
languages = ["en_CA.utf8", "en_HK.utf8"]
"""
        recipe = recipe_from_toml(blueprint_data)
        self.assertEqual(get_languages(recipe), [])

        recipe = recipe_from_toml(blueprint2_data)
        self.assertEqual(get_languages(recipe), ["en_CA.utf8", "en_HK.utf8"])

        recipe = recipe_from_toml(blueprint3_data)
        self.assertEqual(get_languages(recipe), ["en_CA.utf8", "en_HK.utf8"])

    def test_lang_cmd(self):
        """Test lang_cmd function"""

        self.assertEqual(lang_cmd("lang en_CA.utf8", {}), 'lang en_CA.utf8')
        self.assertEqual(lang_cmd("lang en_US.utf8", ["en_HK.utf8"]),
                         'lang en_HK.utf8')
        self.assertEqual(lang_cmd("lang en_US.utf8", ["en_CA.utf8", "en_HK.utf8"]),
                         'lang en_CA.utf8 --addsupport=en_HK.utf8')

        self.assertEqual(lang_cmd("lang --addsupport en_US.utf8 en_CA.utf8",
                         ["en_CA.utf8", "en_HK.utf8", "en_GB.utf8"]),
                         'lang en_CA.utf8 --addsupport=en_HK.utf8,en_GB.utf8')

    def test_get_keyboard_layout(self):
        """Test get_keyboard_layout function"""
        blueprint_data = """name = "test-locale"
description = "test recipe"
version = "0.0.1"
        """
        blueprint2_data = blueprint_data + """
[customizations.locale]
keyboard = "de (dvorak)"
"""
        blueprint3_data = blueprint_data + """
[customizations.locale]
keyboard = "de (dvorak)"
languages = ["en_CA.utf8", "en_HK.utf8"]
"""
        recipe = recipe_from_toml(blueprint_data)
        self.assertEqual(get_keyboard_layout(recipe), [])

        recipe = recipe_from_toml(blueprint2_data)
        self.assertEqual(get_keyboard_layout(recipe), "de (dvorak)")

        recipe = recipe_from_toml(blueprint3_data)
        self.assertEqual(get_keyboard_layout(recipe), "de (dvorak)")

    def test_keyboard_cmd(self):
        """Test lang_cmd function"""

        self.assertEqual(keyboard_cmd("keyboard us", {}), "keyboard 'us'")
        self.assertEqual(keyboard_cmd("keyboard us", "de (dvorak)"),
                         "keyboard 'de (dvorak)'")

        self.assertEqual(keyboard_cmd("keyboard --vckeymap=us --xlayouts=us,gb",
                         "de (dvorak)"),
                         "keyboard 'de (dvorak)'")

    def _checkBootloader(self, result, append_str, line_limit=0):
        """Find the bootloader line and make sure append_str is in it"""
        # Optionally check to make sure the change is at the top of the template
        line_num = 0
        for line in result.splitlines():
            if line.startswith("bootloader") and append_str in line:
                if line_limit == 0 or line_num < line_limit:
                    return True
                else:
                    print("FAILED: bootloader not in the first %d lines of the output" % line_limit)
                    return False
            line_num += 1
        return False

    def _checkTimezone(self, result, settings, line_limit=0):
        """Find the timezone line and make sure it is as expected"""
        # Optionally check to make sure the change is at the top of the template
        line_num = 0
        for line in result.splitlines():
            if line.startswith("timezone"):
                if settings["timezone"] in line and all([True for n in settings["ntpservers"] if n in line]):
                    if line_limit == 0 or line_num < line_limit:
                        return True
                    else:
                        print("FAILED: timezone not in the first %d lines of the output" % line_limit)
                        return False
                else:
                    print("FAILED: %s not matching %s" % (settings, line))
            line_num += 1
        return False

    def _checkLang(self, result, locales, line_limit=0):
        """Find the lang line and make sure it is as expected"""
        # Optionally check to make sure the change is at the top of the template
        line_num = 0
        for line in result.splitlines():
            if line.startswith("lang"):
                if all([True for n in locales if n in line]):
                    if line_limit == 0 or line_num < line_limit:
                        return True
                    else:
                        print("FAILED: lang not in the first %d lines of the output" % line_limit)
                        return False
                else:
                    print("FAILED: %s not matching %s" % (locales, line))
            line_num += 1
        return False

    def _checkKeyboard(self, result, layout, line_limit=0):
        """Find the keyboard line and make sure it is as expected"""
        # Optionally check to make sure the change is at the top of the template
        line_num = 0
        for line in result.splitlines():
            if line.startswith("keyboard"):
                if layout in line:
                    if line_limit == 0 or line_num < line_limit:
                        return True
                    else:
                        print("FAILED: keyboard not in the first %d lines of the output" % line_limit)
                        return False
                else:
                    print("FAILED: %s not matching %s" % (layout, line))
            line_num += 1
        return False

    def test_template_defaults(self):
        """Test that customize_ks_template includes defaults correctly"""
        blueprint_data = """name = "test-kernel"
description = "test recipe"
version = "0.0.1"

[[packages]]
name = "lorax"
version = "*"
"""
        recipe = recipe_from_toml(blueprint_data)

        # Make sure that a kickstart with no bootloader and no timezone has them added
        result = customize_ks_template("firewall --enabled\n", recipe)
        print(result)
        self.assertEqual(sum([1 for l in result.splitlines() if l.startswith("bootloader")]), 1)
        self.assertTrue(self._checkBootloader(result, "none", line_limit=2))
        self.assertEqual(sum([1 for l in result.splitlines() if l.startswith("timezone")]), 1)
        self.assertTrue(self._checkTimezone(result, {"timezone": "UTC", "ntpservers": []}, line_limit=2))

        # Make sure that a kickstart with a bootloader, and no timezone has timezone added to the top
        result = customize_ks_template("firewall --enabled\nbootloader --location=mbr\n", recipe)
        print(result)
        self.assertEqual(sum([1 for l in result.splitlines() if l.startswith("bootloader")]), 1)
        self.assertTrue(self._checkBootloader(result, "mbr"))
        self.assertEqual(sum([1 for l in result.splitlines() if l.startswith("timezone")]), 1)
        self.assertTrue(self._checkTimezone(result, {"timezone": "UTC", "ntpservers": []}, line_limit=1))

        # Make sure that a kickstart with a bootloader and timezone has neither added
        result = customize_ks_template("firewall --enabled\nbootloader --location=mbr\ntimezone US/Samoa\n", recipe)
        print(result)
        self.assertEqual(sum([1 for l in result.splitlines() if l.startswith("bootloader")]), 1)
        self.assertTrue(self._checkBootloader(result, "mbr"))
        self.assertEqual(sum([1 for l in result.splitlines() if l.startswith("timezone")]), 1)
        self.assertTrue(self._checkTimezone(result, {"timezone": "US/Samoa", "ntpservers": []}))

    def test_customize_ks_template(self):
        """Test that customize_ks_template works correctly"""
        blueprint_data = """name = "test-kernel"
description = "test recipe"
version = "0.0.1"

[customizations.kernel]
append="nosmt=force"

[customizations.timezone]
timezone = "US/Samoa"
ntpservers = ["0.north-america.pool.ntp.org", "1.north-america.pool.ntp.org"]

[customizations.locale]
keyboard = "de (dvorak)"
languages = ["en_CA.utf8", "en_HK.utf8"]
"""
        tz_dict = {"timezone": "US/Samoa", "ntpservers": ["0.north-america.pool.ntp.org", "1.north-america.pool.ntp.org"]}
        recipe = recipe_from_toml(blueprint_data)

        # Test against a kickstart without bootloader
        result = customize_ks_template("firewall --enabled\n", recipe)
        self.assertTrue(self._checkBootloader(result, "nosmt=force", line_limit=2))
        self.assertEqual(sum([1 for l in result.splitlines() if l.startswith("bootloader")]), 1)
        self.assertTrue(self._checkTimezone(result, tz_dict, line_limit=2))
        self.assertEqual(sum([1 for l in result.splitlines() if l.startswith("timezone")]), 1)
        self.assertTrue(self._checkLang(result, ["en_CA.utf8", "en_HK.utf8"], line_limit=4))
        self.assertEqual(sum([1 for l in result.splitlines() if l.startswith("lang")]), 1)
        self.assertTrue(self._checkKeyboard(result, "de (dvorak)", line_limit=4))
        self.assertEqual(sum([1 for l in result.splitlines() if l.startswith("keyboard")]), 1)

        # Test against a kickstart with a bootloader line
        result = customize_ks_template("firewall --enabled\nbootloader --location=mbr\n", recipe)
        self.assertTrue(self._checkBootloader(result, "nosmt=force"))
        self.assertTrue(self._checkTimezone(result, tz_dict, line_limit=2))

        # Test against all of the available templates
        share_dir = "./share/"
        errors = []
        for compose_type in compose_types(share_dir):
            # Read the kickstart template for this type
            ks_template_path = joinpaths(share_dir, "composer", compose_type) + ".ks"
            ks_template = open(ks_template_path, "r").read()
            result = customize_ks_template(ks_template, recipe)
            if not self._checkBootloader(result, "nosmt=force"):
                errors.append(("bootloader for compose_type %s failed" % compose_type, result))
            if sum([1 for l in result.splitlines() if l.startswith("bootloader")]) != 1:
                errors.append(("bootloader for compose_type %s failed: More than 1 entry" % compose_type, result))


            # google images should retain their timezone settings
            if compose_type == "google":
                if self._checkTimezone(result, tz_dict):
                    errors.append(("timezone for compose_type %s failed" % compose_type, result))
            elif not self._checkTimezone(result, tz_dict, line_limit=2):
                # None of the templates have a timezone to modify, it should be placed at the top
                errors.append(("timezone for compose_type %s failed" % compose_type, result))
            if sum([1 for l in result.splitlines() if l.startswith("timezone")]) != 1:
                errors.append(("timezone for compose_type %s failed: More than 1 entry" % compose_type, result))

            if not self._checkLang(result, ["en_CA.utf8", "en_HK.utf8"]):
                errors.append(("lang for compose_type %s failed" % compose_type, result))
            if sum([1 for l in result.splitlines() if l.startswith("lang")]) != 1:
                errors.append(("lang for compose_type %s failed: More than 1 entry" % compose_type, result))

            if not self._checkKeyboard(result, "de (dvorak)"):
                errors.append(("keyboard for compose_type %s failed" % compose_type, result))
            if sum([1 for l in result.splitlines() if l.startswith("keyboard")]) != 1:
                errors.append(("keyboard for compose_type %s failed: More than 1 entry" % compose_type, result))

        # Print the bad results
        for e, r in errors:
            print("%s:\n%s\n\n" % (e, r))

        self.assertEqual(errors, [])
