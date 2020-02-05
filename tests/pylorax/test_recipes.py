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
from pytoml import TomlError
import shutil
import tempfile
import unittest
from unittest import mock

import pylorax.api.recipes as recipes
from pylorax.api.compose import add_customizations, customize_ks_template
from pylorax.sysutils import joinpaths

from pykickstart.parser import KickstartParser
from pykickstart.version import makeVersion

class BasicRecipeTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # Input toml is in .toml and python dict string is in .dict
        input_recipes = [("full-recipe.toml", "full-recipe.dict"),
                         ("minimal.toml", "minimal.dict"),
                         ("modules-only.toml", "modules-only.dict"),
                         ("packages-only.toml", "packages-only.dict"),
                         ("groups-only.toml", "groups-only.dict"),
                         ("custom-base.toml", "custom-base.dict"),
                         ("repos-git.toml", "repos-git.dict")]
        results_path = "./tests/pylorax/results/"
        self.input_toml = {}
        for (recipe_toml, recipe_dict) in input_recipes:
            with open(joinpaths(results_path, recipe_toml)) as f_toml:
                with open(joinpaths(results_path, recipe_dict)) as f_dict:
                    # XXX Warning, can run arbitrary code
                    result_dict = eval(f_dict.read())
                self.input_toml[recipe_toml] = (f_toml.read(), result_dict)

        # Used by diff tests
        self.old_modules = [recipes.RecipeModule("toml", "2.1"),
                            recipes.RecipeModule("bash", "4.*"),
                            recipes.RecipeModule("httpd", "3.7.*")]
        self.new_modules = [recipes.RecipeModule("toml", "2.1"),
                            recipes.RecipeModule("httpd", "3.8.*"),
                            recipes.RecipeModule("openssh", "2.8.1")]
        self.modules_result = [{"new": {"Modules": {"version": "2.8.1", "name": "openssh"}},
                                "old": None},
                               {"new": None,
                                "old": {"Modules": {"name": "bash", "version": "4.*"}}},
                               {"new": {"Modules": {"version": "3.8.*", "name": "httpd"}},
                                "old": {"Modules": {"version": "3.7.*", "name": "httpd"}}}]

        self.old_packages = [recipes.RecipePackage("python", "2.7.*"),
                             recipes.RecipePackage("parted", "3.2")]
        self.new_packages = [recipes.RecipePackage("python", "2.7.*"),
                             recipes.RecipePackage("parted", "3.2"),
                             recipes.RecipePackage("git", "2.13.*")]
        self.packages_result = [{"new": {"Packages": {"name": "git", "version": "2.13.*"}}, "old": None}]

        self.old_groups = [recipes.RecipeGroup("backup-client"),
                           recipes.RecipeGroup("standard")]
        self.new_groups = [recipes.RecipeGroup("console-internet"),
                           recipes.RecipeGroup("standard")]
        self.groups_result = [{'new': {'Groups': {'name': 'console-internet'}}, 'old': None},
                              {'new': None, 'old': {'Groups': {'name': 'backup-client'}}}]

        # customizations test data and results.
        self.old_custom = {'hostname': 'custombase'}
        self.custom_sshkey1 = {'sshkey': [{'user': 'root', 'key': 'A SSH KEY FOR ROOT'}]}
        self.custom_sshkey2 = {'sshkey': [{'user': 'root', 'key': 'A DIFFERENT SSH KEY FOR ROOT'}]}
        self.custom_sshkey3 = {'sshkey': [{'user': 'root', 'key': 'A SSH KEY FOR ROOT'}, {'user': 'cliff', 'key': 'A SSH KEY FOR CLIFF'}]}
        self.custom_kernel = {'kernel': {'append': 'nosmt=force'}}
        self.custom_user1 = {'user': [{'name': 'admin', 'description': 'Administrator account', 'password': '$6$CHO2$3rN8eviE2t50lmVyBYihTgVRHcaecmeCk31L...', 'key': 'PUBLIC SSH KEY', 'home': '/srv/widget/', 'shell': '/usr/bin/bash', 'groups': ['widget', 'users', 'wheel'], 'uid': 1200, 'gid': 1200}]}
        self.custom_user2 = {'user': [{'name': 'admin', 'description': 'Administrator account', 'password': '$6$CHO2$3rN8eviE2t50lmVyBYihTgVRHcaecmeCk31L...', 'key': 'PUBLIC SSH KEY', 'home': '/root/', 'shell': '/usr/bin/bash', 'groups': ['widget', 'users', 'wheel'], 'uid': 1200, 'gid': 1200}]}
        self.custom_user3 = {'user': [{'name': 'admin', 'description': 'Administrator account', 'password': '$6$CHO2$3rN8eviE2t50lmVyBYihTgVRHcaecmeCk31L...', 'key': 'PUBLIC SSH KEY', 'home': '/srv/widget/', 'shell': '/usr/bin/bash', 'groups': ['widget', 'users', 'wheel'], 'uid': 1200, 'gid': 1200}, {'name': 'norman', 'key': 'PUBLIC SSH KEY'}]}
        self.custom_group = {'group': [{'name': 'widget', 'gid': 1130}]}
        self.custom_timezone1 = {'timezone': {'timezone': 'US/Eastern', 'ntpservers': ['0.north-america.pool.ntp.org', '1.north-america.pool.ntp.org']}}
        self.custom_timezone2 = {'timezone': {'timezone': 'US/Eastern'}}
        self.custom_timezone3 = {'timezone': {'ntpservers': ['0.north-america.pool.ntp.org', '1.north-america.pool.ntp.org']}}
        self.custom_locale1 = {'locale': {'languages': ['en_US.UTF-8'], 'keyboard': 'us'}}
        self.custom_locale2 = {'locale': {'languages': ['en_US.UTF-8']}}
        self.custom_locale3 = {'locale': {'keyboard': 'us'}}
        self.custom_firewall1 = {'firewall': {'ports': ['22:tcp', '80:tcp', 'imap:tcp', '53:tcp', '53:udp'], 'services': {'enabled': ['ftp', 'ntp', 'dhcp'], 'disabled': ['telnet']}}}
        self.custom_firewall2 = {'firewall': {'ports': ['22:tcp', '80:tcp', 'imap:tcp', '53:tcp', '53:udp']}}
        self.custom_firewall3 = {'firewall': {'services': {'enabled': ['ftp', 'ntp', 'dhcp'], 'disabled': ['telnet']}}}
        self.custom_firewall4 = {'firewall': {'services': {'enabled': ['ftp', 'ntp', 'dhcp']}}}
        self.custom_firewall5 = {'firewall': {'services': {'disabled': ['telnet']}}}
        self.custom_services1 = {'services': {'enabled': ['sshd', 'cockpit.socket', 'httpd'], 'disabled': ['postfix', 'telnetd']}}
        self.custom_services2 = {'services': {'enabled': ['sshd', 'cockpit.socket', 'httpd']}}
        self.custom_services3 = {'services': {'disabled': ['postfix', 'telnetd']}}

        self.old_custom.update(self.custom_sshkey1)
        # Build the new custom from these pieces
        self.new_custom = self.old_custom.copy()
        for d in [self.custom_kernel, self.custom_user1, self.custom_group, self.custom_timezone1,
                  self.custom_locale1, self.custom_firewall1, self.custom_services1]:
            self.new_custom.update(d)
        self.custom_result = [{'new': {'Customizations.firewall': {'ports': ['22:tcp', '80:tcp', 'imap:tcp', '53:tcp', '53:udp'],
                                                                   'services': {'disabled': ['telnet'], 'enabled': ['ftp', 'ntp', 'dhcp']}}},
                               'old': None},
                              {'new': {'Customizations.group': [{'gid': 1130, 'name': 'widget'}]},
                               'old': None},
                              {'new': {'Customizations.kernel': {'append': 'nosmt=force'}},
                               'old': None},
                              {'new': {'Customizations.locale': {'keyboard': 'us', 'languages': ['en_US.UTF-8']}},
                               'old': None},
                              {'new': {'Customizations.services': {'disabled': ['postfix', 'telnetd'], 'enabled': ['sshd', 'cockpit.socket', 'httpd']}},
                               'old': None},
                              {'new': {'Customizations.timezone': {'ntpservers': ['0.north-america.pool.ntp.org', '1.north-america.pool.ntp.org'],
                                                                   'timezone': 'US/Eastern'}},
                               'old': None},
                              {'new': {'Customizations.user': [{'description': 'Administrator account', 'gid': 1200,
                                                                'groups': ['widget', 'users', 'wheel'], 'home': '/srv/widget/',
                                                                'key': 'PUBLIC SSH KEY', 'name': 'admin', 
                                                                'password': '$6$CHO2$3rN8eviE2t50lmVyBYihTgVRHcaecmeCk31L...', 'shell': '/usr/bin/bash', 'uid': 1200}]},
                               'old': None}]

        self.maxDiff = None

    @classmethod
    def tearDownClass(self):
        pass

    def toml_to_recipe_test(self):
        """Test converting the TOML string to a Recipe object"""
        for (toml_str, recipe_dict) in self.input_toml.values():
            result = recipes.recipe_from_toml(toml_str)
            self.assertEqual(result, recipe_dict)

    def toml_to_recipe_fail_test(self):
        """Test trying to convert a non-TOML string to a Recipe"""
        with self.assertRaises(TomlError):
            recipes.recipe_from_toml("This is not a TOML string\n")

        with self.assertRaises(recipes.RecipeError):
            recipes.recipe_from_toml('name = "a failed toml string"\n')

    def recipe_to_toml_test(self):
        """Test converting a Recipe object to a TOML string"""
        # In order to avoid problems from matching strings we convert to TOML and
        # then back so compare the Recipes.
        for (toml_str, _recipe_dict) in self.input_toml.values():
            # This is tested in toml_to_recipe
            recipe_1 = recipes.recipe_from_toml(toml_str)
            # Convert the Recipe to TOML and then back to a Recipe
            toml_2 = recipe_1.toml()
            recipe_2 = recipes.recipe_from_toml(toml_2)
            self.assertEqual(recipe_1, recipe_2)

    def recipe_bump_version_test(self):
        """Test the Recipe's version bump function"""

        # Neither have a version
        recipe = recipes.Recipe("test-recipe", "A recipe used for testing", None, None, None, None)
        new_version = recipe.bump_version(None)
        self.assertEqual(new_version, "0.0.1")

        # Original has a version, new does not
        recipe = recipes.Recipe("test-recipe", "A recipe used for testing", None, None, None, None)
        new_version = recipe.bump_version("0.0.1")
        self.assertEqual(new_version, "0.0.2")

        # Original has no version, new does
        recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.0", None, None, None)
        new_version = recipe.bump_version(None)
        self.assertEqual(new_version, "0.1.0")

        # New and Original are the same
        recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.0.1", None, None, None)
        new_version = recipe.bump_version("0.0.1")
        self.assertEqual(new_version, "0.0.2")

        # New is different from Original
        recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", None, None, None)
        new_version = recipe.bump_version("0.0.1")
        self.assertEqual(new_version, "0.1.1")

    def find_field_test(self):
        """Test the find_field_value function"""
        test_list = [{"name":"dog"}, {"name":"cat"}, {"name":"squirrel"}]

        self.assertEqual(recipes.find_field_value("name", "cat", test_list), {"name":"cat"})
        self.assertIsNone(recipes.find_field_value("name", "alien", test_list))
        self.assertIsNone(recipes.find_field_value("color", "green", test_list))
        self.assertIsNone(recipes.find_field_value("color", "green", []))

    def find_name_test(self):
        """Test the find_name function"""
        test_list = [{"name":"dog"}, {"name":"cat"}, {"name":"squirrel"}]

        self.assertEqual(recipes.find_name("cat", test_list), {"name":"cat"})
        self.assertIsNone(recipes.find_name("alien", test_list))
        self.assertIsNone(recipes.find_name("alien", []))

    def find_obj_test(self):
        """Test the find_recipe_obj function"""
        test_recipe = {"customizations": {"hostname": "foo", "users": ["root"]}, "repos": {"git": ["git-repos"]}}

        self.assertEqual(recipes.find_recipe_obj(["customizations", "hostname"], test_recipe, ""), "foo")
        self.assertEqual(recipes.find_recipe_obj(["customizations", "locale"], test_recipe, {}), {})
        self.assertEqual(recipes.find_recipe_obj(["repos", "git"], test_recipe, ""), ["git-repos"])
        self.assertEqual(recipes.find_recipe_obj(["repos", "git", "oak"], test_recipe, ""), "")
        self.assertIsNone(recipes.find_recipe_obj(["pine"], test_recipe))

    def diff_lists_test(self):
        """Test the diff_lists function"""
        self.assertEqual(recipes.diff_lists("Modules", "name", self.old_modules, self.old_modules), [])
        self.assertEqual(recipes.diff_lists("Modules", "name", self.old_modules, self.new_modules), self.modules_result)
        self.assertEqual(recipes.diff_lists("Packages", "name", self.old_packages, self.new_packages), self.packages_result)
        self.assertEqual(recipes.diff_lists("Groups", "name", self.old_groups, self.new_groups), self.groups_result)

    def customizations_diff_test(self):
        """Test the customizations_diff function"""
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], [], [], customizations=self.old_custom)
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", [], [], [], customizations=self.new_custom)
        self.assertEqual(recipes.customizations_diff(old_recipe, new_recipe), self.custom_result)

    def customizations_diff_services_test(self):
        """Test the customizations_diff function with services variations"""
        # Test adding the services customization
        old_custom = self.old_custom.copy()
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], [], [], customizations=old_custom)

        new_custom = old_custom.copy()
        new_custom.update(self.custom_services1)
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", [], [], [], customizations=new_custom)
        result = [{'new': {'Customizations.services': {'disabled': ['postfix', 'telnetd'], 'enabled': ['sshd', 'cockpit.socket', 'httpd']}},
                   'old': None}]
        self.assertEqual(recipes.customizations_diff(old_recipe, new_recipe), result)

        # Test removing disabled
        old_custom = self.old_custom.copy()
        old_custom.update(self.custom_services1)
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], [], [], customizations=old_custom)

        new_custom = self.old_custom.copy()
        new_custom.update(self.custom_services2)
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", [], [], [], customizations=new_custom)
        result = [{'old': {'Customizations.services': {'disabled': ['postfix', 'telnetd'], 'enabled': ['sshd', 'cockpit.socket', 'httpd']}},
                   'new': {'Customizations.services': {'enabled': ['sshd', 'cockpit.socket', 'httpd']}}}]
        self.assertEqual(recipes.customizations_diff(old_recipe, new_recipe), result)

        # Test removing enabled
        old_custom = self.old_custom.copy()
        old_custom.update(self.custom_services1)
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], [], [], customizations=old_custom)

        new_custom = self.old_custom.copy()
        new_custom.update(self.custom_services3)
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", [], [], [], customizations=new_custom)
        result = [{'old': {'Customizations.services': {'disabled': ['postfix', 'telnetd'], 'enabled': ['sshd', 'cockpit.socket', 'httpd']}},
                   'new': {'Customizations.services': {'disabled': ['postfix', 'telnetd']}}}]
        self.assertEqual(recipes.customizations_diff(old_recipe, new_recipe), result)

    def customizations_diff_firewall_test(self):
        """Test the customizations_diff function with firewall variations"""
        # Test adding the firewall customization
        old_custom = self.old_custom.copy()
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], [], [], customizations=old_custom)

        new_custom = old_custom.copy()
        new_custom.update(self.custom_firewall1)
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", [], [], [], customizations=new_custom)
        result = [{'new': {'Customizations.firewall': {'ports': ['22:tcp', '80:tcp', 'imap:tcp', '53:tcp', '53:udp'],
                                                       'services': {'disabled': ['telnet'], 'enabled': ['ftp', 'ntp', 'dhcp']}}},
                   'old': None}]
        self.assertEqual(recipes.customizations_diff(old_recipe, new_recipe), result)

        # Test removing services
        old_custom = self.old_custom.copy()
        old_custom.update(self.custom_firewall1)
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], [], [], customizations=old_custom)

        new_custom = self.old_custom.copy()
        new_custom.update(self.custom_firewall2)
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", [], [], [], customizations=new_custom)
        result = [{'old': {'Customizations.firewall': {'ports': ['22:tcp', '80:tcp', 'imap:tcp', '53:tcp', '53:udp'],
                                                       'services': {'disabled': ['telnet'], 'enabled': ['ftp', 'ntp', 'dhcp']}}},
                   'new': {'Customizations.firewall': {'ports': ['22:tcp', '80:tcp', 'imap:tcp', '53:tcp', '53:udp']}}}]
        self.assertEqual(recipes.customizations_diff(old_recipe, new_recipe), result)

        # Test removing ports
        old_custom = self.old_custom.copy()
        old_custom.update(self.custom_firewall1)
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], [], [], customizations=old_custom)

        new_custom = self.old_custom.copy()
        new_custom.update(self.custom_firewall3)
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", [], [], [], customizations=new_custom)
        result = [{'old': {'Customizations.firewall': {'ports': ['22:tcp', '80:tcp', 'imap:tcp', '53:tcp', '53:udp'],
                                                       'services': {'disabled': ['telnet'], 'enabled': ['ftp', 'ntp', 'dhcp']}}},
                   'new': {'Customizations.firewall': {'services': {'disabled': ['telnet'], 'enabled': ['ftp', 'ntp', 'dhcp']}}}}]
        self.assertEqual(recipes.customizations_diff(old_recipe, new_recipe), result)

        # Test removing disabled services
        old_custom = self.old_custom.copy()
        old_custom.update(self.custom_firewall3)
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], [], [], customizations=old_custom)

        new_custom = self.old_custom.copy()
        new_custom.update(self.custom_firewall4)
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", [], [], [], customizations=new_custom)
        result = [{'old': {'Customizations.firewall': {'services': {'disabled': ['telnet'], 'enabled': ['ftp', 'ntp', 'dhcp']}}},
                   'new': {'Customizations.firewall': {'services': {'enabled': ['ftp', 'ntp', 'dhcp']}}}}]
        self.assertEqual(recipes.customizations_diff(old_recipe, new_recipe), result)

        # Test removing enabled services
        old_custom = self.old_custom.copy()
        old_custom.update(self.custom_firewall3)
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], [], [], customizations=old_custom)

        new_custom = self.old_custom.copy()
        new_custom.update(self.custom_firewall5)
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", [], [], [], customizations=new_custom)
        result = [{'old': {'Customizations.firewall': {'services': {'disabled': ['telnet'], 'enabled': ['ftp', 'ntp', 'dhcp']}}},
                   'new': {'Customizations.firewall': {'services': {'disabled': ['telnet']}}}}]
        self.assertEqual(recipes.customizations_diff(old_recipe, new_recipe), result)

    def customizations_diff_locale_test(self):
        """Test the customizations_diff function with locale variations"""
        # Test adding the locale customization
        old_custom = self.old_custom.copy()
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], [], [], customizations=old_custom)

        new_custom = old_custom.copy()
        new_custom.update(self.custom_locale1)
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", [], [], [], customizations=new_custom)
        result = [{'new': {'Customizations.locale': {'keyboard': 'us', 'languages': ['en_US.UTF-8']}},
                   'old': None}]
        self.assertEqual(recipes.customizations_diff(old_recipe, new_recipe), result)

        # Test removing keyboard
        old_custom = self.old_custom.copy()
        old_custom.update(self.custom_locale1)
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], [], [], customizations=old_custom)

        new_custom = self.old_custom.copy()
        new_custom.update(self.custom_locale2)
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", [], [], [], customizations=new_custom)
        result = [{'old': {'Customizations.locale': {'keyboard': 'us', 'languages': ['en_US.UTF-8']}},
                   'new': {'Customizations.locale': {'languages': ['en_US.UTF-8']}}}]
        self.assertEqual(recipes.customizations_diff(old_recipe, new_recipe), result)

        # Test removing languages
        old_custom = self.old_custom.copy()
        old_custom.update(self.custom_locale1)
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], [], [], customizations=old_custom)

        new_custom = self.old_custom.copy()
        new_custom.update(self.custom_locale3)
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", [], [], [], customizations=new_custom)
        result = [{'old': {'Customizations.locale': {'keyboard': 'us', 'languages': ['en_US.UTF-8']}},
                   'new': {'Customizations.locale': {'keyboard': 'us'}}}]
        self.assertEqual(recipes.customizations_diff(old_recipe, new_recipe), result)

    def customizations_diff_timezone_test(self):
        """Test the customizations_diff function with timezone variations"""
        # Test adding the timezone customization
        old_custom = self.old_custom.copy()
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], [], [], customizations=old_custom)

        new_custom = old_custom.copy()
        new_custom.update(self.custom_timezone1)
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", [], [], [], customizations=new_custom)
        result = [{'new': {'Customizations.timezone': {'ntpservers': ['0.north-america.pool.ntp.org', '1.north-america.pool.ntp.org'], 'timezone': 'US/Eastern'}},
                   'old': None}]
        self.assertEqual(recipes.customizations_diff(old_recipe, new_recipe), result)

        # Test removing ntpservers
        old_custom = self.old_custom.copy()
        old_custom.update(self.custom_timezone1)
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], [], [], customizations=old_custom)

        new_custom = self.old_custom.copy()
        new_custom.update(self.custom_timezone2)
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", [], [], [], customizations=new_custom)
        result = [{'old': {'Customizations.timezone': {'ntpservers': ['0.north-america.pool.ntp.org', '1.north-america.pool.ntp.org'], 'timezone': 'US/Eastern'}},
                   'new': {'Customizations.timezone': {'timezone': 'US/Eastern'}}}]
        self.assertEqual(recipes.customizations_diff(old_recipe, new_recipe), result)

        # Test removing timezone
        old_custom = self.old_custom.copy()
        old_custom.update(self.custom_timezone1)
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], [], [], customizations=old_custom)

        new_custom = self.old_custom.copy()
        new_custom.update(self.custom_timezone3)
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", [], [], [], customizations=new_custom)
        result = [{'old': {'Customizations.timezone': {'ntpservers': ['0.north-america.pool.ntp.org', '1.north-america.pool.ntp.org'], 'timezone': 'US/Eastern'}},
                   'new': {'Customizations.timezone': {'ntpservers': ['0.north-america.pool.ntp.org', '1.north-america.pool.ntp.org']}}}]
        self.assertEqual(recipes.customizations_diff(old_recipe, new_recipe), result)


    def customizations_diff_sshkey_test(self):
        """Test the customizations_diff function with sshkey variations"""
        # Test changed root ssh key
        old_custom = self.old_custom.copy()
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], [], [], customizations=old_custom)

        new_custom = old_custom.copy()
        new_custom.update(self.custom_sshkey2)
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", [], [], [], customizations=new_custom)
        result = [{'new': {'Customizations.sshkey': {'key': 'A DIFFERENT SSH KEY FOR ROOT', 'user': 'root'}},
                   'old': {'Customizations.sshkey': {'key': 'A SSH KEY FOR ROOT', 'user': 'root'}}}]
        self.assertEqual(recipes.customizations_diff(old_recipe, new_recipe), result)

        # Test adding a user's ssh key
        old_custom = self.old_custom.copy()
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], [], [], customizations=old_custom)

        new_custom = old_custom.copy()
        new_custom.update(self.custom_sshkey3)
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", [], [], [], customizations=new_custom)
        result = [{'new': {'Customizations.sshkey': {'key': 'A SSH KEY FOR CLIFF', 'user': 'cliff'}},
                   'old': None}]

        self.assertEqual(recipes.customizations_diff(old_recipe, new_recipe), result)

        # Test removing a user's ssh key
        old_custom = old_custom.copy()
        old_custom.update(self.custom_sshkey3)
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], [], [], customizations=old_custom)

        new_custom = self.old_custom.copy()
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", [], [], [], customizations=new_custom)
        result = [{'old': {'Customizations.sshkey': {'key': 'A SSH KEY FOR CLIFF', 'user': 'cliff'}},
                   'new': None}]
        self.assertEqual(recipes.customizations_diff(old_recipe, new_recipe), result)

    def customizations_diff_user_test(self):
        """Test the customizations_diff function with user variations"""
        # Test changed admin user
        old_custom = self.old_custom.copy()
        old_custom.update(self.custom_user1)
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], [], [], customizations=old_custom)

        new_custom = old_custom.copy()
        new_custom.update(self.custom_user2)
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", [], [], [], customizations=new_custom)
        result = [{'new': {'Customizations.user': {'description': 'Administrator account',
                                                   'gid': 1200,
                                                   'groups': ['widget', 'users', 'wheel'],
                                                   'home': '/root/',
                                                   'key': 'PUBLIC SSH KEY',
                                                   'name': 'admin',
                                                   'password': '$6$CHO2$3rN8eviE2t50lmVyBYihTgVRHcaecmeCk31L...',
                                                   'shell': '/usr/bin/bash',
                                                   'uid': 1200}},
                   'old': {'Customizations.user': {'description': 'Administrator account',
                                                   'gid': 1200,
                                                   'groups': ['widget', 'users', 'wheel'],
                                                   'home': '/srv/widget/',
                                                   'key': 'PUBLIC SSH KEY',
                                                   'name': 'admin',
                                                   'password': '$6$CHO2$3rN8eviE2t50lmVyBYihTgVRHcaecmeCk31L...',
                                                   'shell': '/usr/bin/bash',
                                                   'uid': 1200}}}]
        self.assertEqual(recipes.customizations_diff(old_recipe, new_recipe), result)

        # Test adding a user
        old_custom = self.old_custom.copy()
        old_custom.update(self.custom_user1)
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], [], [], customizations=old_custom)

        new_custom = old_custom.copy()
        new_custom.update(self.custom_user3)
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", [], [], [], customizations=new_custom)
        result = [{'new': {'Customizations.user': {'key': 'PUBLIC SSH KEY', 'name': 'norman'}}, 'old': None}]
        self.assertEqual(recipes.customizations_diff(old_recipe, new_recipe), result)

        # Test removing a user
        old_custom = self.old_custom.copy()
        old_custom.update(self.custom_user3)
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], [], [], customizations=old_custom)

        new_custom = old_custom.copy()
        new_custom.update(self.custom_user1)
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", [], [], [], customizations=new_custom)
        result = [{'new': None, 'old': {'Customizations.user': {'key': 'PUBLIC SSH KEY', 'name': 'norman'}}}]
        self.assertEqual(recipes.customizations_diff(old_recipe, new_recipe), result)



    def recipe_diff_test(self):
        """Test the recipe_diff function"""
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", self.old_modules, self.old_packages, [])
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", self.new_modules, self.new_packages, [])
        result = [{'new': {'Version': '0.3.1'}, 'old': {'Version': '0.1.1'}},
                  {'new': {'Module': {'name': 'openssh', 'version': '2.8.1'}}, 'old': None},
                  {'new': None, 'old': {'Module': {'name': 'bash', 'version': '4.*'}}},
                  {'new': {'Module': {'name': 'httpd', 'version': '3.8.*'}},
                   'old': {'Module': {'name': 'httpd', 'version': '3.7.*'}}},
                  {'new': {'Package': {'name': 'git', 'version': '2.13.*'}}, 'old': None}]
        self.assertEqual(recipes.recipe_diff(old_recipe, new_recipe), result)

        # Empty starting recipe
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", [], self.old_packages, [])
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", self.new_modules, self.new_packages, [])
        result = [{'new': {'Version': '0.3.1'}, 'old': {'Version': '0.1.1'}},
                  {'new': {'Module': {'name': 'httpd', 'version': '3.8.*'}}, 'old': None},
                  {'new': {'Module': {'name': 'openssh', 'version': '2.8.1'}}, 'old': None},
                  {'new': {'Module': {'name': 'toml', 'version': '2.1'}}, 'old': None},
                  {'new': {'Package': {'name': 'git', 'version': '2.13.*'}}, 'old': None}]
        self.assertEqual(recipes.recipe_diff(old_recipe, new_recipe), result)

        # All new git repos
        old_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.1.1", self.old_modules, self.old_packages, [])
        new_recipe = recipes.Recipe("test-recipe", "A recipe used for testing", "0.3.1", self.new_modules, self.new_packages, [])
        result = [{'new': {'Version': '0.3.1'}, 'old': {'Version': '0.1.1'}},
                  {'new': {'Module': {'name': 'openssh', 'version': '2.8.1'}}, 'old': None},
                  {'new': None, 'old': {'Module': {'name': 'bash', 'version': '4.*'}}},
                  {'new': {'Module': {'name': 'httpd', 'version': '3.8.*'}},
                   'old': {'Module': {'name': 'httpd', 'version': '3.7.*'}}},
                  {'new': {'Package': {'name': 'git', 'version': '2.13.*'}}, 'old': None}]
        self.assertEqual(recipes.recipe_diff(old_recipe, new_recipe), result)

    def recipe_freeze_test(self):
        """Test the recipe freeze() function"""
        # Use the repos-git.toml test, it only has http and php in it
        deps = [{"arch": "x86_64",
                 "epoch": 0,
                 "name": "httpd",
                 "release": "1.el7",
                 "version": "2.4.11"},
                {"arch": "x86_64",
                 "epoch": 0,
                 "name": "php",
                 "release": "1.el7",
                 "version": "5.4.2"}]
        result = recipes.recipe_from_toml(self.input_toml["repos-git.toml"][0])
        self.assertEqual(result, self.input_toml["repos-git.toml"][1])

        # Freeze the recipe with our fake deps
        frozen = result.freeze(deps)
        self.assertTrue(frozen is not None)
        http_module = recipes.find_name("httpd", frozen["modules"])
        self.assertTrue(http_module is not None)
        self.assertEqual(http_module["version"], "2.4.11-1.el7.x86_64")

        php_module = recipes.find_name("php", frozen["modules"])
        self.assertTrue(php_module is not None)
        self.assertEqual(php_module["version"], "5.4.2-1.el7.x86_64")


class GitRecipesTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.repo_dir = tempfile.mkdtemp(prefix="lorax.test.repo.")
        self.repo = recipes.open_or_create_repo(self.repo_dir)

        self.results_path = "./tests/pylorax/results/"
        self.examples_path = "./tests/pylorax/blueprints/"
        self.new_recipe = os.path.join(self.examples_path, 'python-testing.toml')

    @classmethod
    def tearDownClass(self):
        if self.repo is not None:
            del self.repo
        shutil.rmtree(self.repo_dir)

    def tearDown(self):
        if os.path.exists(self.new_recipe):
            os.remove(self.new_recipe)

    def _create_another_recipe(self):
        open(self.new_recipe, 'w').write("""name = "python-testing"
description = "A recipe used during testing."
version = "0.0.1"

[[packages]]
name = "python"
version = "2.7.*"
""")

    def test_01_repo_creation(self):
        """Test that creating the repository succeeded"""
        self.assertNotEqual(self.repo, None)

    def test_02_commit_recipe(self):
        """Test committing a Recipe object"""
        recipe = recipes.Recipe("test-recipe", "A recipe used for testing", None, None, None, None)
        oid = recipes.commit_recipe(self.repo, "master", recipe)
        self.assertNotEqual(oid, None)

    def test_03_list_recipe(self):
        """Test listing recipe commits"""
        commits = recipes.list_commits(self.repo, "master", "test-recipe.toml")
        self.assertEqual(len(commits), 1, "Wrong number of commits.")
        self.assertEqual(commits[0].message, "Recipe test-recipe, version 0.0.1 saved.")
        self.assertNotEqual(commits[0].timestamp, None, "Timestamp is None")
        self.assertEqual(len(commits[0].commit), 40, "Commit hash isn't 40 characters")
        self.assertEqual(commits[0].revision, None, "revision is not None")

    def test_03_list_commits_commit_time_val_error(self):
        """Test listing recipe commits which raise CommitTimeValError"""
        with mock.patch('pylorax.api.recipes.GLib.DateTime.to_timeval', return_value=False):
            commits = recipes.list_commits(self.repo, "master", "test-recipe.toml")
        self.assertEqual(len(commits), 0, "Wrong number of commits.")

    def test_04_commit_recipe_file(self):
        """Test committing a TOML file"""
        recipe_path = joinpaths(self.results_path, "full-recipe.toml")
        oid = recipes.commit_recipe_file(self.repo, "master", recipe_path)
        self.assertNotEqual(oid, None)

        commits = recipes.list_commits(self.repo, "master", "http-server.toml")
        self.assertEqual(len(commits), 1, "Wrong number of commits: %s" % commits)

    def test_04_commit_recipe_file_handles_internal_ioerror(self):
        """Test committing a TOML raises RecipeFileError on internal IOError"""
        recipe_path = joinpaths(self.results_path, "non-existing-file.toml")
        with self.assertRaises(recipes.RecipeFileError):
            recipes.commit_recipe_file(self.repo, "master", recipe_path)

    def test_05_commit_toml_dir(self):
        """Test committing a directory of TOML files"""
        # first verify that the newly created file isn't present
        old_commits = recipes.list_commits(self.repo, "master", "python-testing.toml")
        self.assertEqual(len(old_commits), 0, "Wrong number of commits: %s" % old_commits)

        # then create it and commit the entire directory
        self._create_another_recipe()
        recipes.commit_recipe_directory(self.repo, "master", self.examples_path)

        # verify that the newly created file is already in the repository
        new_commits = recipes.list_commits(self.repo, "master", "python-testing.toml")
        self.assertEqual(len(new_commits), 1, "Wrong number of commits: %s" % new_commits)
        # again make sure new_commits != old_commits
        self.assertGreater(len(new_commits), len(old_commits),
                           "New commits shoud differ from old commits")

    def test_05_commit_recipe_directory_handling_internal_exceptions(self):
        """Test committing a directory of TOML files while handling internal exceptions"""
        # first verify that the newly created file isn't present
        old_commits = recipes.list_commits(self.repo, "master", "python-testing.toml")
        self.assertEqual(len(old_commits), 0, "Wrong number of commits: %s" % old_commits)

        # then create it and commit the entire directory
        self._create_another_recipe()

        # try to commit while raising RecipeFileError
        with mock.patch('pylorax.api.recipes.commit_recipe_file', side_effect=recipes.RecipeFileError('TESTING')):
            recipes.commit_recipe_directory(self.repo, "master", self.examples_path)

        # try to commit while raising TomlError
        with mock.patch('pylorax.api.recipes.commit_recipe_file', side_effect=TomlError('TESTING', 0, 0, '__test__')):
            recipes.commit_recipe_directory(self.repo, "master", self.examples_path)

        # verify again that the newly created file isn't present b/c we raised an exception
        new_commits = recipes.list_commits(self.repo, "master", "python-testing.toml")
        self.assertEqual(len(new_commits), 0, "Wrong number of commits: %s" % new_commits)

    def test_06_read_recipe(self):
        """Test reading a recipe from a commit"""
        commits = recipes.list_commits(self.repo, "master", "example-http-server.toml")
        self.assertEqual(len(commits), 1, "Wrong number of commits: %s" % commits)

        recipe = recipes.read_recipe_commit(self.repo, "master", "example-http-server")
        self.assertNotEqual(recipe, None)
        self.assertEqual(recipe["name"], "example-http-server")

        # Read by commit id
        recipe = recipes.read_recipe_commit(self.repo, "master", "example-http-server", commits[0].commit)
        self.assertNotEqual(recipe, None)
        self.assertEqual(recipe["name"], "example-http-server")

        # Read the recipe and its commit id
        (commit_id, recipe) = recipes.read_recipe_and_id(self.repo, "master", "example-http-server", commits[0].commit)
        self.assertEqual(commit_id, commits[0].commit)

    def test_07_tag_commit(self):
        """Test tagging the most recent commit of a recipe"""
        result = recipes.tag_file_commit(self.repo, "master", "not-a-file")
        self.assertEqual(result, None)

        result = recipes.tag_recipe_commit(self.repo, "master", "example-http-server")
        self.assertNotEqual(result, None)

        commits = recipes.list_commits(self.repo, "master", "example-http-server.toml")
        self.assertEqual(len(commits), 1, "Wrong number of commits: %s" % commits)
        self.assertEqual(commits[0].revision, 1)

    def test_08_delete_recipe(self):
        """Test deleting a file from a branch"""
        oid = recipes.delete_recipe(self.repo, "master", "example-http-server")
        self.assertNotEqual(oid, None)

        master_files = recipes.list_branch_files(self.repo, "master")
        self.assertEqual("example-http-server.toml" in master_files, False)

    def test_09_revert_commit(self):
        """Test reverting a file on a branch"""
        commits = recipes.list_commits(self.repo, "master", "example-http-server.toml")
        revert_to = commits[0].commit
        oid = recipes.revert_recipe(self.repo, "master", "example-http-server", revert_to)
        self.assertNotEqual(oid, None)

        commits = recipes.list_commits(self.repo, "master", "example-http-server.toml")
        self.assertEqual(len(commits), 2, "Wrong number of commits: %s" % commits)
        self.assertEqual(commits[0].message, "example-http-server.toml reverted to commit %s" % revert_to)

    def test_10_tag_new_commit(self):
        """Test tagging a newer commit of a recipe"""
        recipe = recipes.read_recipe_commit(self.repo, "master", "example-http-server")
        recipe["description"] = "A modified description"
        oid = recipes.commit_recipe(self.repo, "master", recipe)
        self.assertNotEqual(oid, None)

        # Tag the new commit
        result = recipes.tag_recipe_commit(self.repo, "master", "example-http-server")
        self.assertNotEqual(result, None)

        commits = recipes.list_commits(self.repo, "master", "example-http-server.toml")
        self.assertEqual(len(commits), 3, "Wrong number of commits: %s" % commits)
        self.assertEqual(commits[0].revision, 2)


class ExistingGitRepoRecipesTest(GitRecipesTest):
    @classmethod
    def setUpClass(self):
        # will initialize the git repository in the parent class
        super(ExistingGitRepoRecipesTest, self).setUpClass()

        # reopen the repository again so that tests are executed
        # against the existing repo one more time.
        self.repo = recipes.open_or_create_repo(self.repo_dir)


class GetRevisionFromTagTests(unittest.TestCase):
    def test_01_valid_tag(self):
        revision = recipes.get_revision_from_tag('branch/filename/r123')
        self.assertEqual(123, revision)

    def test_02_invalid_tag_not_a_number(self):
        revision = recipes.get_revision_from_tag('branch/filename/rABC')
        self.assertIsNone(revision)

    def test_02_invalid_tag_missing_revision_string(self):
        revision = recipes.get_revision_from_tag('branch/filename/mybranch')
        self.assertIsNone(revision)

class CustomizationsTests(unittest.TestCase):
    @staticmethod
    def _blueprint_to_ks(blueprint_data):
        recipe_obj = recipes.recipe_from_toml(blueprint_data)
        ks = KickstartParser(makeVersion())

        # write out the customization data, and parse the resulting kickstart
        with tempfile.NamedTemporaryFile(prefix="lorax.test.customizations", mode="w") as f:
            f.write(customize_ks_template("", recipe_obj))
            add_customizations(f, recipe_obj)
            f.flush()
            ks.readKickstart(f.name)

        return ks

    @staticmethod
    def _find_user(ks, username):
        for user in ks.handler.user.userList:
            if user.name == username:
                return user
        return None

    @staticmethod
    def _find_sshkey(ks, username):
        for key in ks.handler.sshkey.sshUserList:
            if key.username == username:
                return key
        return None

    @staticmethod
    def _find_group(ks, groupname):
        for group in ks.handler.group.groupList:
            if group.name == groupname:
                return group
        return None

    def test_hostname(self):
        blueprint_data = """name = "test-hostname"
description = "test recipe"
version = "0.0.1"

[customizations]
hostname = "testy.example.com"
"""
        ks = self._blueprint_to_ks(blueprint_data)
        self.assertEqual(ks.handler.network.hostname, "testy.example.com")

    def test_hostname_list(self):
        """Test that the hostname still works when using [[customizations]] instead of [customizations]"""

        blueprint_data = """name = "test-hostname-list"
description = "test recipe"
version = "0.0.1"

[[customizations]]
hostname = "testy.example.com"
"""
        ks = self._blueprint_to_ks(blueprint_data)
        self.assertEqual(ks.handler.network.hostname, "testy.example.com")

    def test_timezone(self):
        blueprint_data = """name = "test-timezone"
description = "test recipe"
version = "0.0.1"

[customizations.timezone]
timezone = "US/Samoa"
"""
        ks = self._blueprint_to_ks(blueprint_data)
        self.assertEqual(ks.handler.timezone.timezone, "US/Samoa")

    def test_timezone_ntpservers(self):
        blueprint_data = """name = "test-ntpservers"
description = "test recipe"
version = "0.0.1"

[customizations.timezone]
timezone = "US/Samoa"
ntpservers = ["1.north-america.pool.ntp.org"]
"""
        ks = self._blueprint_to_ks(blueprint_data)
        self.assertEqual(ks.handler.timezone.timezone, "US/Samoa")
        self.assertEqual(ks.handler.timezone.ntpservers, ["1.north-america.pool.ntp.org"])

    def test_locale_languages(self):
        blueprint_data = """name = "test-locale"
description = "test recipe"
version = "0.0.1"
"""
        blueprint2_data = blueprint_data + """
[customizations.locale]
languages = ["en_CA.utf8"]
"""
        blueprint3_data = blueprint_data + """
[customizations.locale]
languages = ["en_CA.utf8", "en_HK.utf8"]
"""
        ks = self._blueprint_to_ks(blueprint2_data)
        self.assertEqual(ks.handler.lang.lang, "en_CA.utf8")
        self.assertEqual(ks.handler.lang.addsupport, [])

        ks = self._blueprint_to_ks(blueprint3_data)
        self.assertEqual(ks.handler.lang.lang, "en_CA.utf8")
        self.assertEqual(ks.handler.lang.addsupport, ["en_HK.utf8"])

    def test_locale_keyboard(self):
        blueprint_data = """name = "test-locale"
description = "test recipe"
version = "0.0.1"
"""
        blueprint2_data = blueprint_data + """
[customizations.locale]
keyboard = "us"
"""
        blueprint3_data = blueprint_data + """
[customizations.locale]
keyboard = "de (dvorak)"
"""
        ks = self._blueprint_to_ks(blueprint2_data)
        self.assertEqual(ks.handler.keyboard.keyboard, "us")

        ks = self._blueprint_to_ks(blueprint3_data)
        self.assertEqual(ks.handler.keyboard.keyboard, "de (dvorak)")

    def test_locale(self):
        blueprint_data = """name = "test-locale"
description = "test recipe"
version = "0.0.1"

[customizations.locale]
keyboard = "de (dvorak)"
languages = ["en_CA.utf8", "en_HK.utf8"]
"""
        ks = self._blueprint_to_ks(blueprint_data)
        self.assertEqual(ks.handler.keyboard.keyboard, "de (dvorak)")
        self.assertEqual(ks.handler.lang.lang, "en_CA.utf8")
        self.assertEqual(ks.handler.lang.addsupport, ["en_HK.utf8"])

    def test_firewall_ports(self):
        blueprint_data = """name = "test-firewall"
description = "test recipe"
version = "0.0.1"
"""
        blueprint2_data = blueprint_data + """
[customizations.firewall]
ports = ["22:tcp", "80:tcp", "imap:tcp", "53:tcp", "53:udp"]
"""
        ks = self._blueprint_to_ks(blueprint_data)
        self.assertEqual(ks.handler.firewall.ports, [])
        self.assertEqual(ks.handler.firewall.services, [])
        self.assertEqual(ks.handler.firewall.remove_services, [])

        ks = self._blueprint_to_ks(blueprint2_data)
        self.assertEqual(ks.handler.firewall.ports, ["22:tcp", "53:tcp", "53:udp", "80:tcp", "imap:tcp"])
        self.assertEqual(ks.handler.firewall.services, [])
        self.assertEqual(ks.handler.firewall.remove_services, [])

    def test_firewall_services(self):
        blueprint_data = """name = "test-firewall"
description = "test recipe"
version = "0.0.1"

[customizations.firewall.services]
enabled = ["ftp", "ntp", "dhcp"]
disabled = ["telnet"]
"""
        ks = self._blueprint_to_ks(blueprint_data)
        self.assertEqual(ks.handler.firewall.ports, [])
        self.assertEqual(ks.handler.firewall.services, ["dhcp", "ftp", "ntp"])
        self.assertEqual(ks.handler.firewall.remove_services, ["telnet"])

    def test_firewall(self):
        blueprint_data = """name = "test-firewall"
description = "test recipe"
version = "0.0.1"

[customizations.firewall]
ports = ["22:tcp", "80:tcp", "imap:tcp", "53:tcp", "53:udp"]

[customizations.firewall.services]
enabled = ["ftp", "ntp", "dhcp"]
disabled = ["telnet"]
"""
        ks = self._blueprint_to_ks(blueprint_data)
        self.assertEqual(ks.handler.firewall.ports, ["22:tcp", "53:tcp", "53:udp", "80:tcp", "imap:tcp"])
        self.assertEqual(ks.handler.firewall.services, ["dhcp", "ftp", "ntp"])
        self.assertEqual(ks.handler.firewall.remove_services, ["telnet"])

    def test_services(self):
        blueprint_data = """name = "test-services"
description = "test recipe"
version = "0.0.1"

[customizations.services]
enabled = ["sshd", "cockpit.socket", "httpd"]
disabled = ["postfix", "telnetd"]
"""
        ks = self._blueprint_to_ks(blueprint_data)
        self.assertEqual(sorted(ks.handler.services.enabled), ["cockpit.socket", "httpd", "sshd"])
        self.assertEqual(sorted(ks.handler.services.disabled), ["postfix", "telnetd"])

    def test_user(self):
        blueprint_data = """name = "test-user"
description = "test recipe"
version = "0.0.1"

[[customizations.user]]
name = "admin"
description = "Widget admin account"
password = "$6$CHO2$3rN8eviE2t50lmVyBYihTgVRHcaecmeCk31LeOUleVK/R/aeWVHVZDi26zAH.o0ywBKH9Tc0/wm7sW/q39uyd1"
home = "/srv/widget/"
shell = "/usr/bin/bash"
groups = ["widget", "users", "students"]
uid = 1200

[[customizations.user]]
name = "bart"
key = "SSH KEY FOR BART"
groups = ["students"]
"""

        ks = self._blueprint_to_ks(blueprint_data)

        admin = self._find_user(ks, "admin")
        self.assertIsNotNone(admin)
        self.assertEqual(admin.name, "admin")
        self.assertEqual(admin.password, "$6$CHO2$3rN8eviE2t50lmVyBYihTgVRHcaecmeCk31LeOUleVK/R/aeWVHVZDi26zAH.o0ywBKH9Tc0/wm7sW/q39uyd1")
        self.assertEqual(admin.homedir, "/srv/widget/")
        self.assertEqual(admin.shell, "/usr/bin/bash")
        # order is unimportant, so use a set instead of comparing lists directly
        self.assertEqual(set(admin.groups), {"widget", "users", "students"})
        self.assertEqual(admin.uid, 1200)

        bart = self._find_user(ks, "bart")
        self.assertIsNotNone(bart)
        self.assertEqual(bart.name, "bart")
        self.assertEqual(bart.groups, ["students"])

        bartkey = self._find_sshkey(ks, "bart")
        self.assertIsNotNone(bartkey)
        self.assertEqual(bartkey.username, "bart")
        self.assertEqual(bartkey.key, "SSH KEY FOR BART")

    def test_group(self):
        blueprint_data = """name = "test-group"
description = "test recipe"
version = "0.0.1"

[[customizations.group]]
name = "widget"

[[customizations.group]]
name = "students"
"""

        ks = self._blueprint_to_ks(blueprint_data)

        widget = self._find_group(ks, "widget")
        self.assertIsNotNone(widget)

        students = self._find_group(ks, "students")
        self.assertIsNotNone(students)

    def test_full(self):
        blueprint_data = """name = "custom-base"
description = "A base system with customizations"
version = "0.0.1"
modules = []
groups = []

[[packages]]
name = "bash"
version = "4.4.*"

[[customizations]]
hostname = "custom-base"

[[customizations.sshkey]]
user = "root"
key = "ssh-rsa"

[[customizations.user]]
name = "widget"
description = "Widget process user account"
home = "/srv/widget/"
shell = "/usr/bin/false"
groups = ["dialout", "users"]

[[customizations.user]]
name = "admin"
description = "Widget admin account"
password = ""
home = "/srv/widget/"
shell = "/usr/bin/bash"
groups = ["widget", "users", "students"]
uid = 1200

[[customizations.user]]
name = "plain"
password = "password"

[[customizations.user]]
name = "bart"
key = ""
groups = ["students"]

[[customizations.group]]
name = "widget"

[[customizations.group]]
name = "students"

[customizations.timezone]
timezone = "US/Samoa"
ntpservers = ["0.north-america.pool.ntp.org", "1.north-america.pool.ntp.org"]
"""
        ks = self._blueprint_to_ks(blueprint_data)

        self.assertEqual(ks.handler.network.hostname, "custom-base")

        rootkey = self._find_sshkey(ks, "root")
        self.assertIsNotNone(rootkey)
        self.assertEqual(rootkey.username, "root")
        self.assertEqual(rootkey.key, "ssh-rsa")

        widget = self._find_user(ks, "widget")
        self.assertIsNotNone(widget)
        self.assertEqual(widget.name, "widget")
        self.assertEqual(widget.homedir, "/srv/widget/")
        self.assertEqual(widget.shell, "/usr/bin/false")
        self.assertEqual(set(widget.groups), {"dialout", "users"})

        admin = self._find_user(ks, "admin")
        self.assertIsNotNone(admin)
        self.assertEqual(admin.name, "admin")
        self.assertEqual(admin.password, "")
        self.assertEqual(admin.homedir, "/srv/widget/")
        self.assertEqual(admin.shell, "/usr/bin/bash")
        self.assertEqual(set(admin.groups), {"widget", "users", "students"})
        self.assertEqual(admin.uid, 1200)

        plain = self._find_user(ks, "plain")
        self.assertIsNotNone(plain)
        self.assertEqual(plain.name, "plain")
        self.assertEqual(plain.password, "password")

        # widget does not appear as a separate group line, since a widget
        # group is created for the widget user
        widgetGroup = self._find_group(ks, "widget")
        self.assertIsNone(widgetGroup)

        studentsGroup = self._find_group(ks, "students")
        self.assertIsNotNone(studentsGroup)
        self.assertEqual(studentsGroup.name, "students")

        self.assertEqual(ks.handler.timezone.timezone, "US/Samoa")
        self.assertEqual(ks.handler.timezone.ntpservers, ["0.north-america.pool.ntp.org", "1.north-america.pool.ntp.org"])

class RecipeDictTest(unittest.TestCase):
    def test_check_list_case(self):
        """Test the list case checker function"""
        self.assertEqual(recipes.check_list_case([], []), [])
        self.assertEqual(recipes.check_list_case(["name", "description", "version"], []), [])
        self.assertEqual(recipes.check_list_case(["name", "description", "version"],
                             ["name", "description", "version"]), [])
        self.assertEqual(recipes.check_list_case(["name", "description", "version"],
                             ["name", "Description", "VERSION"]),
                             ["Description should be description", "VERSION should be version"])
        self.assertEqual(recipes.check_list_case(["append"], ["appEnD"], prefix="kernel "),
                             ["kernel appEnD should be append"])

    def test_check_required_list(self):
        """Test the required list function"""
        self.assertEqual(recipes.check_required_list([{}], ["name", "version"]),
                              ["1 is missing 'name', 'version'"])
        self.assertEqual(recipes.check_required_list([{"name": "foo", "version": "1.0.0"}], ["name", "version"]),
                              [])
        self.assertEqual(recipes.check_required_list([{"Name": "foo", "Version": "1.0.0"}], ["name", "version"]),
                              ['1 Name should be name', '1 Version should be version', "1 is missing 'name', 'version'"])

    def test_check_recipe_dict(self):
        """Test the recipe dict checker function"""
        r = {}
        self.assertEqual(recipes.check_recipe_dict(r), ["Missing 'name'", "Missing 'description'"])
        r["name"] = "recipe name"
        r["description"] = "recipe description"
        r["version"] = "92ee0ad691"
        self.assertEqual(recipes.check_recipe_dict(r), ["Invalid 'version', must use Semantic Versioning"])
        r["version"] = "0.0.1"
        self.assertEqual(recipes.check_recipe_dict(r), [])

        r["modules"] = [{"name": "mod1"}]
        self.assertEqual(recipes.check_recipe_dict(r), ["'modules' errors:\n1 is missing 'version'"])
        r["modules"] = [{"name": "mod1", "version": "*"}, {"Name": "mod2", "Version": "1.0"}]
        self.assertEqual(recipes.check_recipe_dict(r), ["'modules' errors:\n2 Name should be name\n2 Version should be version\n2 is missing 'name', 'version'"])
        r["modules"] = [{"name": "mod1", "version": "*"}]
        self.assertEqual(recipes.check_recipe_dict(r), [])

        r["packages"] = [{"name": "pkg1"}]
        self.assertEqual(recipes.check_recipe_dict(r), ["'packages' errors:\n1 is missing 'version'"])
        r["packages"] = [{"name": "pkg1", "version": "*"}, {"Name": "pkg2", "Version": "1.0"}]
        self.assertEqual(recipes.check_recipe_dict(r), ["'packages' errors:\n2 Name should be name\n2 Version should be version\n2 is missing 'name', 'version'"])
        r["packages"] = [{"name": "pkg1", "version": "*"}]
        self.assertEqual(recipes.check_recipe_dict(r), [])

        r["groups"] = [{}]
        self.assertEqual(recipes.check_recipe_dict(r), ["'groups' errors:\n1 is missing 'name'"])
        r["groups"] = [{"Name": "grp1"}]
        self.assertEqual(recipes.check_recipe_dict(r), ["'groups' errors:\n1 Name should be name\n1 is missing 'name'"])
        r["groups"] = [{"name": "grp1"}]
        self.assertEqual(recipes.check_recipe_dict(r), [])

        r["customizations"] = {"kernel": {}}
        self.assertEqual(recipes.check_recipe_dict(r), ["'customizations.kernel': missing append field."])
        r["customizations"] = {"kernel": {"Append": "cmdline-arg"}}
        self.assertEqual(recipes.check_recipe_dict(r), ['kernel Append should be append', "'customizations.kernel': missing append field."])
        r["customizations"] = {"kernel": {"append": "cmdline-arg"}}
        self.assertEqual(recipes.check_recipe_dict(r), [])

        r["customizations"]["sshkey"] = [{"key": "KEY"}]
        self.assertEqual(recipes.check_recipe_dict(r), ["'customizations.sshkey' errors:\n1 is missing 'user'"])
        r["customizations"]["sshkey"] = [{"user": "username", "KEY": "KEY"}]
        self.assertEqual(recipes.check_recipe_dict(r), ["'customizations.sshkey' errors:\n1 KEY should be key\n1 is missing 'key'"])
        r["customizations"]["sshkey"] = [{"user": "username", "key": "KEY"}]
        self.assertEqual(recipes.check_recipe_dict(r), [])

        r["customizations"]["user"] = [{"password": "FOOBAR"}]
        self.assertEqual(recipes.check_recipe_dict(r), ["'customizations.user' errors:\n1 is missing 'name'"])
        r["customizations"]["user"] = [{"naMe": "admin", "key": "KEY"}]
        self.assertEqual(recipes.check_recipe_dict(r), ["'customizations.user' errors:\n1 naMe should be name\n1 is missing 'name'"])
        r["customizations"]["user"] = [{"name": "admin", "key": "KEY"}]
        self.assertEqual(recipes.check_recipe_dict(r), [])

        r["customizations"]["group"] = [{"id": "2001"}]
        self.assertEqual(recipes.check_recipe_dict(r), ["'customizations.group' errors:\n1 is missing 'name'"])
        r["customizations"]["group"] = [{"Name": "admins", "id": "2001"}]
        self.assertEqual(recipes.check_recipe_dict(r), ["'customizations.group' errors:\n1 Name should be name\n1 is missing 'name'"])
        r["customizations"]["group"] = [{"name": "admins", "id": "2001"}]
        self.assertEqual(recipes.check_recipe_dict(r), [])

        r["customizations"]["timezone"] = {}
        self.assertEqual(recipes.check_recipe_dict(r), ["'customizations.timezone': missing timezone or ntpservers fields."])
        r["customizations"]["timezone"] = {"Timezone": "PST8PDT"}
        self.assertEqual(recipes.check_recipe_dict(r), ['timezone Timezone should be timezone'])
        r["customizations"]["timezone"] = {"timezone": "PST8PDT"}
        self.assertEqual(recipes.check_recipe_dict(r), [])

        r["customizations"]["locale"] = {}
        self.assertEqual(recipes.check_recipe_dict(r), ["'customizations.locale': missing languages or keyboard fields."])
        r["customizations"]["locale"] = {"Keyboard": "dvorak"}
        self.assertEqual(recipes.check_recipe_dict(r), ['locale Keyboard should be keyboard'])
        r["customizations"]["locale"] = {"keyboard": "dvorak"}
        self.assertEqual(recipes.check_recipe_dict(r), [])

        r["customizations"]["firewall"] = {}
        self.assertEqual(recipes.check_recipe_dict(r), ["'customizations.firewall': missing ports field or services section."])
        r["customizations"]["firewall"] = {"Ports": "8080:tcp"}
        self.assertEqual(recipes.check_recipe_dict(r), ['firewall Ports should be ports'])
        r["customizations"]["firewall"] = {"ports": "8080:tcp"}
        self.assertEqual(recipes.check_recipe_dict(r), [])

        r["customizations"]["firewall"]["services"] = {}
        self.assertEqual(recipes.check_recipe_dict(r), ["'customizations.firewall.services': missing enabled or disabled fields."])
        r["customizations"]["firewall"]["services"] = {"enabled": "sshd"}
        self.assertEqual(recipes.check_recipe_dict(r), [])

        r["customizations"]["services"] = {}
        self.assertEqual(recipes.check_recipe_dict(r), ["'customizations.services': missing enabled or disabled fields."])
        r["customizations"]["services"] = {"DISABLED": "telnetd"}
        self.assertEqual(recipes.check_recipe_dict(r), ['services DISABLED should be disabled'])
        r["customizations"]["services"] = {"disabled": "telnetd"}
        self.assertEqual(recipes.check_recipe_dict(r), [])

