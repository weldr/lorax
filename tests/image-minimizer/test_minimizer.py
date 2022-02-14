import os
from subprocess import check_call, CalledProcessError
import tempfile
import unittest

from minimizer import ImageMinimizer

class MinimizerTestCase(unittest.TestCase):
    def test_minimizer_ok(self):
        with tempfile.TemporaryDirectory(prefix="minimize.test.") as rootdir:
            check_call(["dnf", "--releasever=/", "--installroot", rootdir, "install", "-y", \
                        "filesystem"])

            im = ImageMinimizer("./tests/image-minimizer/im-script.txt", rootdir, False, False)
            im.filter()

            # /etc/pki/rpm-gpg/ should only have 2 files
            self.assertEqual(sorted(os.listdir(f"{rootdir}/etc/pki/rpm-gpg/")), ["RPM-GPG-KEY-fedora-11-primary", "RPM-GPG-KEY-fedora-12-primary"])

            # zoneinfo should have 2 directories and a file
            self.assertEqual(sorted(os.listdir(f"{rootdir}/usr/share/zoneinfo/")), ["America", "US", "UTC"])

            check_call(["rpm", "--root", rootdir, "-q", "fedora-release", "fedora-gpg-keys"])

            with self.assertRaises(CalledProcessError):
                check_call(["rpm", "--root", rootdir, "-q", "fedora-repos"])

    def test_minimizer_empty(self):
        ## No packages in tree (this is ok, nothing to remove)
        with tempfile.TemporaryDirectory(prefix="minimize.test.") as rootdir:
            im = ImageMinimizer("./tests/image-minimizer/im-script.txt", rootdir, False, False)
            im.filter()

    def test_minimizer_missing_script(self):
        ## No minimizer script
        with tempfile.TemporaryDirectory(prefix="minimize.test.") as rootdir:
            im = ImageMinimizer("./tests/image-minimizer/missing.txt", rootdir, False, False)
            with self.assertRaises(FileNotFoundError):
                im.filter()

    def test_minimizer_missing_root(self):
        ## Missing directory
        im = ImageMinimizer("./tests/image-minimizer/im-script.txt", "/tmp/minimizer.root", False, False)
        with self.assertRaises(FileNotFoundError):
            im.filter()
