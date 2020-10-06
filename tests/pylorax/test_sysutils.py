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
import io
import unittest
import tempfile
import os

from pylorax.sysutils import joinpaths, touch, replace, chown_, chmod_, remove, linktree
from pylorax.sysutils import _read_file_end

class SysUtilsTest(unittest.TestCase):
    def test_joinpaths(self):
        self.assertEqual(joinpaths("foo", "bar", "baz"), "foo/bar/baz")

        with tempfile.TemporaryDirectory() as tdname:
            with open(os.path.join(tdname, "real-file"), "w") as f:
                f.write("lorax test file")
            os.symlink(os.path.join(tdname, "real-file"), os.path.join(tdname, "link-file"))

            self.assertEqual(joinpaths(tdname, "link-file", follow_symlinks=True),
                             os.path.join(tdname, "real-file"))

    def test_touch(self):
        touch_file="/var/tmp/lorax-test-touch-file"
        touch(touch_file)

        self.assertTrue(os.path.exists(touch_file))
        os.unlink(touch_file)

    def test_replace(self):
        f = tempfile.NamedTemporaryFile(mode="w+t", delete=False)
        f.write("A few words to apply @AARDVARKS@ testing\n")
        f.close()
        replace(f.name, "@AARDVARKS@", "ant eaters")

        with open(f.name) as fr:
            line = fr.readline()
        self.assertEqual(line, "A few words to apply ant eaters testing\n")
        os.unlink(f.name)

    @unittest.skipUnless(os.geteuid() == 0, "requires root privileges")
    def test_chown(self):
        with tempfile.NamedTemporaryFile() as f:
            chown_(f.name, "nobody", "nobody")

    def test_chmod(self):
        with tempfile.NamedTemporaryFile() as f:
            chmod_(f.name, 0o777)
            self.assertEqual(os.stat(f.name).st_mode, 0o100777)

    def test_remove(self):
        remove_file="/var/tmp/lorax-test-remove-file"
        with open(remove_file, "w") as f:
            f.write("test was here")
        remove(remove_file)
        self.assertFalse(os.path.exists(remove_file))

    def test_linktree(self):
        with tempfile.TemporaryDirectory() as tdname:
            path = os.path.join("one", "two", "three")
            os.makedirs(os.path.join(tdname, path))
            with open(os.path.join(tdname, path, "lorax-link-test-file"), "w") as f:
                f.write("test was here")

            linktree(os.path.join(tdname, "one"), os.path.join(tdname, "copy"))

            self.assertTrue(os.path.exists(os.path.join(tdname, "copy", "two", "three", "lorax-link-test-file")))

    def _generate_lines(self, unicode=False):
        # helper to generate several KiB of lines of text
        bio = io.BytesIO()
        for i in range(0,1024):
            if not unicode:
                bio.write(b"Here is another line to test. It is line #%d\n" % i)
            else:
                bio.write(b"Here is \xc3\xa0n\xc3\xb2ther line t\xc3\xb2 test. It is line #%d\n" % i)
        bio.seek(0)
        return bio

    def test_read_file_end(self):
        """Test reading from the end of a file"""
        self.maxDiff = None

        # file of just lines
        f = self._generate_lines()

        # Grab the end of the 'file' to compare with, starting at the next line (hard-coded)
        f.seek(-987, 2)
        result = f.read().decode("utf-8")
        f.seek(0)
        self.assertEqual(_read_file_end(f, 1), result)

        # file of lines with no final \n, chop off the trailing \n
        f.seek(-1,2)
        f.truncate()
        f.seek(0)
        self.assertEqual(_read_file_end(f, 1), result[:-1])

        # short file, truncate it at 1023 characters
        f.seek(1023)
        f.truncate()
        # Grab the end of the file, starting at the next line (hard-coded)
        f.seek(44)
        result = f.read().decode("utf-8")
        f.seek(0)
        self.assertEqual(_read_file_end(f, 1), result)

        # short file with no line endings
        f.seek(43)
        f.truncate()
        # Grab the whole file
        f.seek(0)
        result = f.read().decode("utf-8")
        f.seek(0)
        self.assertEqual(_read_file_end(f, 1), result)

        # file with unicode in it
        f = self._generate_lines(unicode=True)

        # Grab the end of the 'file' to compare with, starting at the next line (hard-coded)
        f.seek(-1000, 2)
        result = f.read().decode("utf-8")
        f.seek(0)
        self.assertEqual(_read_file_end(f, 1), result)

        # file with unicode right on block boundary, so that a decode of it would fail if it didn't
        # move to the next line.
        f.seek(-1000, 2)
        result = f.read().decode("utf-8")
        f.seek(-1025, 2)
        f.write(b"\xc3\xb2")
        f.seek(0)
        self.assertEqual(_read_file_end(f, 1), result)

        # Test for UnicodeDecodeError returning an empty string
        f = io.BytesIO(b"\xff\xff\xffHere is a string with invalid unicode in it.")
        self.assertEqual(_read_file_end(f, 1), "")
