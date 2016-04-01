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
import unittest
import tempfile
import os

from pylorax.sysutils import joinpaths, touch, replace, chown_, chmod_, remove, linktree

class SysUtilsTest(unittest.TestCase):
    def joinpaths_test(self):
        self.assertEqual(joinpaths("foo", "bar", "baz"), "foo/bar/baz")

        with tempfile.TemporaryDirectory() as tdname:
            open(os.path.join(tdname, "real-file"), "w").write("lorax test file")
            os.symlink(os.path.join(tdname, "real-file"), os.path.join(tdname, "link-file"))

            self.assertEqual(joinpaths(tdname, "link-file", follow_symlinks=True),
                             os.path.join(tdname, "real-file"))

    def touch_test(self):
        touch_file="/var/tmp/lorax-test-touch-file"
        touch(touch_file)

        self.assertTrue(os.path.exists(touch_file))
        os.unlink(touch_file)

    def replace_test(self):
        f = tempfile.NamedTemporaryFile(mode="w+t", delete=False)
        f.write("A few words to apply @AARDVARKS@ testing\n")
        f.close()
        replace(f.name, "@AARDVARKS@", "ant eaters")

        self.assertEqual(open(f.name).readline(), "A few words to apply ant eaters testing\n")
        os.unlink(f.name)

    @unittest.skipUnless(os.geteuid() == 0, "requires root privileges")
    def chown_test(self):
        with tempfile.NamedTemporaryFile() as f:
            chown_(f.name, "nobody", "nobody")

    def chmod_test(self):
        with tempfile.NamedTemporaryFile() as f:
            chmod_(f.name, 0o777)
            self.assertEqual(os.stat(f.name).st_mode, 0o100777)

    def remove_test(self):
        remove_file="/var/tmp/lorax-test-remove-file"
        open(remove_file, "w").write("test was here")
        remove(remove_file)
        self.assertFalse(os.path.exists(remove_file))

    def linktree_test(self):
        with tempfile.TemporaryDirectory() as tdname:
            path = os.path.join("one", "two", "three")
            os.makedirs(os.path.join(tdname, path))
            open(os.path.join(tdname, path, "lorax-link-test-file"), "w").write("test was here")

            linktree(os.path.join(tdname, "one"), os.path.join(tdname, "copy"))

            self.assertTrue(os.path.exists(os.path.join(tdname, "copy", "two", "three", "lorax-link-test-file")))
