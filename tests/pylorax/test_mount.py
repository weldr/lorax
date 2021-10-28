import os
import subprocess
import tempfile
import unittest

from pylorax.mount import IsoMountpoint
from pylorax.sysutils import joinpaths


def mktestiso(rootdir, volid):
    # Make some fake files
    for f in ("/images/pxeboot/vmlinuz", "/images/pxeboot/initrd.img", "/LiveOS/squashfs.img"):
        p = joinpaths(rootdir, "sysroot", f)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as ff:
            ff.write("I AM FAKE FILE %s" % f.upper())

    # Make an iso of the files
    make_iso = ["xorrisofs", "-o", joinpaths(rootdir, "test.iso"),
                "-R", "-J", "-V", volid,
                "-graft-points", "/=%s" % joinpaths(rootdir, "sysroot")]
    subprocess.check_call(make_iso)

@unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
class IsoMountpointTest(unittest.TestCase):
    def test_volid(self):
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            mktestiso(work_dir, "Fedora-test-iso-x86_64")
            self.assertTrue(os.path.exists(joinpaths(work_dir, "test.iso")))

            iso = IsoMountpoint(joinpaths(work_dir, "test.iso"))
            self.addCleanup(iso.umount)
            self.assertEqual(iso.iso_path, joinpaths(work_dir, "test.iso"))
            self.assertIsNotNone(iso.mount_dir)
            self.assertTrue(iso.stage2)
            self.assertTrue(iso.kernel.endswith("vmlinuz"))
            self.assertTrue(iso.initrd.endswith("initrd.img"))
            self.assertEqual(iso.label, "Fedora-test-iso-x86_64")
