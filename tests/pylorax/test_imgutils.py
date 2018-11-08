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
import os
import tempfile
import unittest

from ..lib import get_file_magic
from pylorax.executils import runcmd
from pylorax.imgutils import mkcpio, mktar, mksquashfs, mksparse, mkqcow2, loop_attach, loop_detach
from pylorax.imgutils import get_loop_name, LoopDev, dm_attach, dm_detach, DMDev, Mount
from pylorax.imgutils import mkdosimg, mkext4img, mkbtrfsimg, mkhfsimg, default_image_name
from pylorax.sysutils import joinpaths

def mkfakerootdir(rootdir):
    """Populate a fake rootdir with a few directories and files

    :param rootdir: An existing directory to create files/dirs under
    :type rootdir: str

    Use this for testing the mk* functions that compress a directory tree
    """
    dirs = ["/root", "/usr/sbin/", "/usr/local/", "/home/bart", "/etc/"]
    files = ["/etc/passwd", "/home/bart/.bashrc", "/root/.bashrc"]
    for d in dirs:
        os.makedirs(joinpaths(rootdir, d))
    for f in files:
        if not os.path.isdir(joinpaths(rootdir, os.path.dirname(f))):
            os.makedirs(joinpaths(rootdir, os.path.dirname(f)))
        open(joinpaths(rootdir, f), "w").write("I AM FAKE FILE %s" % f.upper())

class ImgUtilsTest(unittest.TestCase):
    def mkcpio_test(self):
        """Test mkcpio function"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
                mkfakerootdir(work_dir)
                mkcpio(work_dir, disk_img.name, compression=None)

                self.assertTrue(os.path.exists(disk_img.name))
                file_details = get_file_magic(disk_img.name)
                self.assertTrue("cpio" in file_details, file_details)

    def mktar_test(self):
        """Test mktar function"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
                mkfakerootdir(work_dir)
                mktar(work_dir, disk_img.name, compression=None)

                self.assertTrue(os.path.exists(disk_img.name))
                file_details = get_file_magic(disk_img.name)
                self.assertTrue("POSIX tar" in file_details, file_details)

    def compressed_mktar_test(self):
        """Test compressed mktar function"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
                mkfakerootdir(work_dir)
                for (compression, magic) in [("xz", "XZ compressed"),
                                             ("lzma", "LZMA compressed"),
                                             ("gzip", "gzip compressed"),
                                             ("bzip2", "bzip2 compressed")]:
                    os.unlink(disk_img.name)
                    mktar(work_dir, disk_img.name, compression=compression)

                    self.assertTrue(os.path.exists(disk_img.name))
                    file_details = get_file_magic(disk_img.name)
                    self.assertTrue(magic in file_details, (compression, magic, file_details))

    def mksquashfs_test(self):
        """Test mksquashfs function"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
                mkfakerootdir(work_dir)
                disk_img.close()
                mksquashfs(work_dir, disk_img.name)

                self.assertTrue(os.path.exists(disk_img.name))
                file_details = get_file_magic(disk_img.name)
                self.assertTrue("Squashfs" in file_details, file_details)

    def mksparse_test(self):
        """Test mksparse function"""
        with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
            mksparse(disk_img.name, 42 * 1024**2)
            self.assertEqual(os.stat(disk_img.name).st_size, 42 * 1024**2)

    def mkqcow2_test(self):
        """Test mkqcow2 function"""
        with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
            mkqcow2(disk_img.name, 42 * 1024**2)
            file_details = get_file_magic(disk_img.name)
            self.assertTrue("QEMU QCOW" in file_details, file_details)
            self.assertTrue(str(42 * 1024**2) in file_details, file_details)

    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def loop_test(self):
        """Test the loop_* functions (requires loop support)"""
        with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
            mksparse(disk_img.name, 42 * 1024**2)
            loop_dev = loop_attach(disk_img.name)
            try:
                self.assertTrue(loop_dev is not None)
                self.assertEqual(loop_dev[5:], get_loop_name(disk_img.name))
            finally:
                loop_detach(loop_dev)

    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def loop_context_test(self):
        """Test the LoopDev context manager (requires loop)"""
        with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
            mksparse(disk_img.name, 42 * 1024**2)
            with LoopDev(disk_img.name) as loop_dev:
                self.assertTrue(loop_dev is not None)
                self.assertEqual(loop_dev[5:], get_loop_name(disk_img.name))

    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def dm_test(self):
        """Test the dm_* functions (requires device-mapper support)"""
        with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
            mksparse(disk_img.name, 42 * 1024**2)
            with LoopDev(disk_img.name) as loop_dev:
                self.assertTrue(loop_dev  is not None)
                dm_name = dm_attach(loop_dev, 42 * 1024**2)
                try:
                    self.assertTrue(dm_name is not None)
                finally:
                    dm_detach(dm_name)

    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def dmdev_test(self):
        """Test the DMDev context manager (requires device-mapper support)"""
        with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
            mksparse(disk_img.name, 42 * 1024**2)
            with LoopDev(disk_img.name) as loop_dev:
                self.assertTrue(loop_dev  is not None)
                with DMDev(loop_dev, 42 * 1024**2) as dm_name:
                    self.assertTrue(dm_name is not None)

    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def mount_test(self):
        """Test the Mount context manager (requires loop)"""
        with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
            mksparse(disk_img.name, 42 * 1024**2)
            runcmd(["mkfs.ext4", "-L", "Anaconda", "-b", "4096", "-m", "0", disk_img.name])
            with LoopDev(disk_img.name) as loopdev:
                self.assertTrue(loopdev is not None)
                with Mount(loopdev) as mnt:
                    self.assertTrue(mnt is not None)

    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def mkdosimg_test(self):
        """Test mkdosimg function (requires loop)"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
                mkfakerootdir(work_dir)
                mkdosimg(work_dir, disk_img.name)
                self.assertTrue(os.path.exists(disk_img.name))
                file_details = get_file_magic(disk_img.name)
                self.assertTrue("FAT " in file_details, file_details)

    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def mkext4img_test(self):
        """Test mkext4img function (requires loop)"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
                mkfakerootdir(work_dir)
                mkext4img(work_dir, disk_img.name)
                self.assertTrue(os.path.exists(disk_img.name))
                file_details = get_file_magic(disk_img.name)
                self.assertTrue("ext2 filesystem" in file_details, file_details)

    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def mkbtrfsimg_test(self):
        """Test mkbtrfsimg function (requires loop)"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
                mkfakerootdir(work_dir)
                mkbtrfsimg(work_dir, disk_img.name)
                self.assertTrue(os.path.exists(disk_img.name))
                file_details = get_file_magic(disk_img.name)
                self.assertTrue("BTRFS Filesystem" in file_details, file_details)

    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def mkhfsimg_test(self):
        """Test mkhfsimg function (requires loop)"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
                mkfakerootdir(work_dir)
                mkhfsimg(work_dir, disk_img.name, label="test")
                self.assertTrue(os.path.exists(disk_img.name))
                file_details = get_file_magic(disk_img.name)
                self.assertTrue("Macintosh HFS" in file_details, file_details)

    def default_image_name_test(self):
        """Test default_image_name function"""
        for compression, suffix in [("xz", ".xz"), ("gzip", ".gz"), ("bzip2", ".bz2"), ("lzma", ".lzma")]:
            filename = default_image_name(compression, "foobar")
            self.assertTrue(filename.endswith(suffix))

