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
import glob
import os
import parted
from subprocess import CalledProcessError
import tarfile
import tempfile
import unittest

from ..lib import get_file_magic
from pylorax.executils import runcmd
from pylorax.imgutils import mkcpio, mktar, mksquashfs, mksparse, mkqcow2, loop_attach, loop_detach
from pylorax.imgutils import get_loop_name, LoopDev, dm_attach, dm_detach, DMDev, Mount
from pylorax.imgutils import mkdosimg, mkext4img, mkbtrfsimg, mkhfsimg, default_image_name
from pylorax.imgutils import mount, umount, kpartx_disk_img, PartitionMount, mkfsimage_from_disk
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
        with open(joinpaths(rootdir, f), "w") as ff:
            ff.write("I AM FAKE FILE %s" % f.upper())

def mkfakebootdir(bootdir):
    """Populate a fake /boot directory with a kernel and initrd

    :param bootdir: An existing directory to create files/dirs under
    :type bootdir: str
    """
    with open(joinpaths(bootdir, "vmlinuz-4.18.13-200.fc28.x86_64"), "w") as f:
        f.write("I AM A FAKE KERNEL")
    with open(joinpaths(bootdir, "initramfs-4.18.13-200.fc28.x86_64.img"), "w") as f:
        f.write("I AM A FAKE INITRD")

def mkfakediskimg(disk_img):
    """Create a fake partitioned disk image

    :param disk_img: Full path to a partitioned disk image
    :type disk_img: str
    :returns: True if it was successful, False if something went wrong

    Include /boot, swap, and / partitions with fake kernel and /etc/passwd
    """
    try:
        mksparse(disk_img, 42 * 1024**2)
        # Make a /boot, / and swap partitions on it
        dev = parted.getDevice(disk_img)
        disk = parted.freshDisk(dev, "gpt")

        # (start, length, flags, name)
        for start, length, flags, name in [
                  (  1024**2,    1024**2, None, "boot"),
                  (2*1024**2,  2*1024**2, parted.PARTITION_SWAP, "swap"),
                  (4*1024**2, 38*1024**2, None, "root")]:
            geo = parted.Geometry(device=dev, start=start//dev.sectorSize, length=length//dev.sectorSize)
            part = parted.Partition(disk=disk, type=parted.PARTITION_NORMAL, geometry=geo)
            part.getPedPartition().set_name(name)
            disk.addPartition(partition=part)
            if flags:
                part.setFlag(flags)
        disk.commit()
        os.sync()
    except parted.PartedException:
        return False

    # Mount the disk's partitions
    loop_devs = kpartx_disk_img(disk_img)

    try:
        # Format the partitions
        runcmd(["mkfs.ext4", "/dev/mapper/" + loop_devs[0][0]])
        runcmd(["mkswap", "/dev/mapper/" + loop_devs[1][0]])
        runcmd(["mkfs.ext4", "/dev/mapper/" + loop_devs[2][0]])

        # Mount the boot partition and make a fake kernel and initrd
        boot_mnt = mount("/dev/mapper/" + loop_devs[0][0])
        try:
            mkfakebootdir(boot_mnt)
        finally:
            umount(boot_mnt)

        # Mount the / partition and make a fake / filesystem with /etc/passwd
        root_mnt = mount("/dev/mapper/" + loop_devs[2][0])
        try:
            mkfakerootdir(root_mnt)
        finally:
            umount(root_mnt)
    except Exception:
        return False
    finally:
        # Remove the disk's mounted partitions
        runcmd(["kpartx", "-d", "-s", disk_img])

    return True

class ImgUtilsTest(unittest.TestCase):
    def test_mkcpio(self):
        """Test mkcpio function"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
                mkfakerootdir(work_dir)
                mkcpio(work_dir, disk_img.name, compression=None)

                self.assertTrue(os.path.exists(disk_img.name))
                file_details = get_file_magic(disk_img.name)
                self.assertTrue("cpio" in file_details, file_details)

    def test_mktar(self):
        """Test mktar function"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
                mkfakerootdir(work_dir)
                mktar(work_dir, disk_img.name, compression=None)

                self.assertTrue(os.path.exists(disk_img.name))
                file_details = get_file_magic(disk_img.name)
                self.assertTrue("POSIX tar" in file_details, file_details)

    def test_compressed_mktar(self):
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

    def test_mktar_single_file(self):
        with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img,\
                tempfile.NamedTemporaryFile(prefix="lorax.test.input.") as input_file:
            mktar(input_file.name, disk_img.name, compression=None)

            self.assertTrue(os.path.exists(disk_img.name))
            self.assertTrue(tarfile.is_tarfile(disk_img.name))

            with tarfile.TarFile(disk_img.name) as t:
                self.assertEqual(t.getnames(), [os.path.basename(input_file.name)])

    def test_mksquashfs(self):
        """Test mksquashfs function"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
                mkfakerootdir(work_dir)
                disk_img.close()
                mksquashfs(work_dir, disk_img.name)

                self.assertTrue(os.path.exists(disk_img.name))
                file_details = get_file_magic(disk_img.name)
                self.assertTrue("Squashfs" in file_details, file_details)

    def test_mksparse(self):
        """Test mksparse function"""
        with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
            mksparse(disk_img.name, 42 * 1024**2)
            self.assertEqual(os.stat(disk_img.name).st_size, 42 * 1024**2)

    def test_mkqcow2(self):
        """Test mkqcow2 function"""
        with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
            mkqcow2(disk_img.name, 42 * 1024**2)
            file_details = get_file_magic(disk_img.name)
            self.assertTrue("QEMU QCOW" in file_details, file_details)
            self.assertTrue(str(42 * 1024**2) in file_details, file_details)

    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def test_loop(self):
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
    def test_loop_context(self):
        """Test the LoopDev context manager (requires loop)"""
        with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
            mksparse(disk_img.name, 42 * 1024**2)
            with LoopDev(disk_img.name) as loop_dev:
                self.assertTrue(loop_dev is not None)
                self.assertEqual(loop_dev[5:], get_loop_name(disk_img.name))

    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def test_dm(self):
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
    def test_dmdev(self):
        """Test the DMDev context manager (requires device-mapper support)"""
        with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
            mksparse(disk_img.name, 42 * 1024**2)
            with LoopDev(disk_img.name) as loop_dev:
                self.assertTrue(loop_dev  is not None)
                with DMDev(loop_dev, 42 * 1024**2) as dm_name:
                    self.assertTrue(dm_name is not None)

    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def test_mount(self):
        """Test the Mount context manager (requires loop)"""
        with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
            mksparse(disk_img.name, 42 * 1024**2)
            runcmd(["mkfs.ext4", "-L", "Anaconda", "-b", "4096", "-m", "0", disk_img.name])
            with LoopDev(disk_img.name) as loopdev:
                self.assertTrue(loopdev is not None)
                with Mount(loopdev) as mnt:
                    self.assertTrue(mnt is not None)

    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def test_mkdosimg(self):
        """Test mkdosimg function (requires loop)"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
                mkfakerootdir(work_dir)
                mkdosimg(work_dir, disk_img.name)
                self.assertTrue(os.path.exists(disk_img.name))
                file_details = get_file_magic(disk_img.name)
                self.assertTrue("FAT " in file_details, file_details)

    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def test_mkext4img(self):
        """Test mkext4img function (requires loop)"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
                mkfakerootdir(work_dir)
                graft = {work_dir+"/ext4test/": "./tests/pylorax/templates/install-cmd.tmpl"}
                mkext4img(work_dir, disk_img.name, graft=graft)
                self.assertTrue(os.path.exists(disk_img.name))
                file_details = get_file_magic(disk_img.name)
                self.assertTrue("ext2 filesystem" in file_details, file_details)

    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def test_small_mkext4img(self):
        """Test mkext4img error handling"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
                mkfakerootdir(work_dir)
                # Add a 8MiB file
                with open(joinpaths(work_dir, "large-file"), "w") as f:
                    for _ in range(5):
                        f.write("A" * 1024**2)
                graft = {work_dir+"/ext4test/": "./tests/pylorax/templates/install-cmd.tmpl"}
                try:
                    mkext4img(work_dir, disk_img.name, graft=graft, size=5*1024**2)
                except CalledProcessError as e:
                    self.assertTrue(e.stdout and "No space left on device" in e.stdout)

    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def test_mkbtrfsimg(self):
        """Test mkbtrfsimg function (requires loop)"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
                mkfakerootdir(work_dir)
                mkbtrfsimg(work_dir, disk_img.name)
                self.assertTrue(os.path.exists(disk_img.name))
                file_details = get_file_magic(disk_img.name)
                self.assertTrue("BTRFS Filesystem" in file_details, file_details)

    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def test_mkhfsimg(self):
        """Test mkhfsimg function (requires loop)"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
                mkfakerootdir(work_dir)
                mkhfsimg(work_dir, disk_img.name, label="test")
                self.assertTrue(os.path.exists(disk_img.name))
                file_details = get_file_magic(disk_img.name)
                self.assertTrue("Macintosh HFS" in file_details, file_details)

    def test_default_image_name(self):
        """Test default_image_name function"""
        for compression, suffix in [("xz", ".xz"), ("gzip", ".gz"), ("bzip2", ".bz2"), ("lzma", ".lzma")]:
            filename = default_image_name(compression, "foobar")
            self.assertTrue(filename.endswith(suffix))

    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def test_partition_mount(self):
        """Test PartitionMount context manager (requires loop)"""
        with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
            self.assertTrue(mkfakediskimg(disk_img.name))
            # Make sure it can mount the / with /etc/passwd
            with PartitionMount(disk_img.name) as img_mount:
                self.assertTrue(img_mount is not None)
                self.assertTrue(os.path.isdir(img_mount.mount_dir))
                self.assertTrue(os.path.exists(joinpaths(img_mount.mount_dir, "/etc/passwd")))

            # Make sure submount works
            with PartitionMount(disk_img.name, submount="/a-sub-mount/") as img_mount:
                self.assertTrue(img_mount is not None)
                self.assertTrue(os.path.isdir(img_mount.mount_dir))
                self.assertTrue(os.path.exists(joinpaths(img_mount.mount_dir, "/etc/passwd")))

            # Make sure it can mount the /boot partition with a custom mount_ok function
            def mount_ok(mount_dir):
                kernels = glob.glob(joinpaths(mount_dir, "vmlinuz-*"))
                return len(kernels) > 0

            with PartitionMount(disk_img.name, mount_ok=mount_ok) as img_mount:
                self.assertTrue(img_mount is not None)
                self.assertTrue(os.path.isdir(img_mount.mount_dir))
                self.assertFalse(os.path.exists(joinpaths(img_mount.mount_dir, "/etc/passwd")))
                self.assertTrue(os.path.exists(joinpaths(img_mount.mount_dir, "vmlinuz-4.18.13-200.fc28.x86_64")))
                self.assertTrue(os.path.exists(joinpaths(img_mount.mount_dir, "initramfs-4.18.13-200.fc28.x86_64.img")))

    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def test_mkfsimage_from_disk(self):
        """Test creating a fsimage from the / partition of a disk image"""
        with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
            self.assertTrue(mkfakediskimg(disk_img.name))
            with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as fs_img:
                mkfsimage_from_disk(disk_img.name, fs_img.name)
                self.assertTrue(os.path.exists(fs_img.name))
                file_details = get_file_magic(fs_img.name)
                self.assertTrue("ext2 filesystem" in file_details, file_details)
