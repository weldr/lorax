#
# Copyright (C) 2018-2020 Red Hat, Inc.
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
from unittest import mock
import xml.etree.ElementTree as ET

# For kickstart check tests
from pykickstart.parser import KickstartParser
from pykickstart.version import makeVersion

from ..lib import get_file_magic
from pylorax import find_templates
from pylorax.base import DataHolder
from pylorax.creator import FakeDNF, create_pxe_config, make_appliance, make_runtime, squashfs_args
from pylorax.creator import calculate_disk_size, dracut_args, DRACUT_DEFAULT
from pylorax.creator import get_arch, find_ostree_root, check_kickstart, make_livecd
from pylorax.executils import runcmd_output
from pylorax.sysutils import joinpaths


def mkFakeBoot(root_dir):
    """Create a fake kernel and initrd"""
    os.makedirs(joinpaths(root_dir, "boot"))
    with open(joinpaths(root_dir, "boot", "vmlinuz-4.18.13-200.fc28.x86_64"), "w") as f:
        f.write("I AM A FAKE KERNEL")
    with open(joinpaths(root_dir, "boot", "initramfs-4.18.13-200.fc28.x86_64.img"), "w") as f:
        f.write("I AM A FAKE INITRD")


class CreatorTest(unittest.TestCase):
    def test_fakednf(self):
        """Test FakeDNF class"""
        fake_dbo = FakeDNF(conf=DataHolder(installroot="/a/fake/install/root/"))
        self.assertEqual(fake_dbo.conf.installroot, "/a/fake/install/root/")

    def test_squashfs_args(self):
        """Test squashfs_args results"""
        test_arches = {"x86_64": ("xz", ["-Xbcj", "x86"]),
                       "ppc64le": ("xz", ["-Xbcj", "powerpc"]),
                       "s390x": ("xz", []),
                       "ia64": ("xz", []),
                       "aarch64": ("xz", [])
        }

        for arch in test_arches:
            opts = DataHolder(compression=None, compress_args=[], arch=arch)
            self.assertEqual(squashfs_args(opts), test_arches[arch], (opts, squashfs_args(opts)))

        opts = DataHolder(compression="lzma", compress_args=[], arch="x86_64")
        self.assertEqual(squashfs_args(opts), ("lzma", []), (opts, squashfs_args(opts)))

        opts = DataHolder(compression="xz", compress_args=["-X32767"], arch="x86_64")
        self.assertEqual(squashfs_args(opts), ("xz", ["-X32767"]), (opts, squashfs_args(opts)))

        opts = DataHolder(compression="xz", compress_args=["-X32767", "-Xbcj x86"], arch="x86_64")
        self.assertEqual(squashfs_args(opts), ("xz", ["-X32767", "-Xbcj", "x86"]), (opts, squashfs_args(opts)))

    def test_dracut_args(self):
        """Test dracut_args results"""

        # Use default args
        opts = DataHolder(dracut_args=None, dracut_conf=None)
        self.assertEqual(dracut_args(opts), DRACUT_DEFAULT)

        # Use a config file from --dracut-conf
        opts = DataHolder(dracut_args=None, dracut_conf="/var/tmp/project/lmc-dracut.conf")
        self.assertEqual(dracut_args(opts), ["--conf", "/var/tmp/project/lmc-dracut.conf"])

        # Use --dracut-arg
        opts = DataHolder(dracut_args=["--xz",  "--omit plymouth", "--add livenet dmsquash-live dmsquash-live-ntfs"], dracut_conf=None)
        self.assertEqual(dracut_args(opts), ["--xz",  "--omit", "plymouth", "--add", "livenet dmsquash-live dmsquash-live-ntfs"])

    def test_make_appliance(self):
        """Test creating the appliance description XML file"""
        lorax_templates = find_templates("./share/")
        appliance_template = joinpaths(lorax_templates, "appliance/libvirt.tmpl")
        self.assertTrue(os.path.exists(appliance_template))

        # A fake disk image
        with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
            with open(disk_img.name, "wb") as f:
                f.write(b"THIS IS A FAKE DISK IMAGE FILE")
            with tempfile.NamedTemporaryFile(prefix="lorax.test.appliance.") as output_xml:
                make_appliance(disk_img.name, "test-appliance", appliance_template, output_xml.name,
                              ["eth0", "eth1"], ram=4096, vcpus=8, arch="x86_64",
                              title="Lorax Test", project="Fedora", releasever="30")

                with open(output_xml.name) as f:
                    print(f.read())
                # Parse the XML and check for known fields
                tree = ET.parse(output_xml.name)
                image = tree.getroot()
                self.assertEqual(image.find("name").text, "test-appliance")
                boot = image.find("./domain/boot")
                self.assertEqual(boot.get("type"), "hvm")
                self.assertEqual(boot.find("./guest/arch").text, "x86_64")
                self.assertEqual(boot.find("./os/loader").get("dev"), "hd")
                self.assertTrue(boot.find("drive").get("disk").startswith("lorax.test.disk."))
                self.assertEqual(boot.find("drive").get("target"), "hda")
                devices = image.find("./domain/devices")
                self.assertEqual(devices.find("vcpu").text, "8")
                self.assertEqual(devices.find("memory").text, "4096")
                self.assertTrue(len(devices.findall("interface")), 2)
                storage = image.find("storage")
                self.assertTrue(storage.find("disk").get("file").startswith("lorax.test.disk."))
                self.assertEqual(storage.find("./disk/checksum").get("type"), "sha256")
                self.assertEqual(storage.find("./disk/checksum").text, "90611458b33009998f73e25ccc3766b31a8b548cc6c2d84f78ae0e84d64e10a5")

    def test_pxe_config(self):
        """Test creation of a PXE config file"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            live_image_name = "live-rootfs.squashfs.img"
            add_pxe_args = ["ostree=/mnt/sysimage/"]
            lorax_templates = find_templates("./share/")
            template = joinpaths(lorax_templates, "pxe-live/pxe-config.tmpl")

            # Make a fake kernel and initrd
            with open(joinpaths(work_dir, "vmlinuz-4.18.13-200.fc28.x86_64"), "w") as f:
                f.write("I AM A FAKE KERNEL")
            with open(joinpaths(work_dir, "initramfs-4.18.13-200.fc28.x86_64.img"), "w") as f:
                f.write("I AM A FAKE INITRD")

            # Create the PXE_CONFIG in work_dir
            create_pxe_config(template, work_dir, live_image_name, add_pxe_args)
            with open(joinpaths(work_dir, "PXE_CONFIG")) as f:
                pxe_config = f.read()
            print(pxe_config)
            self.assertTrue("vmlinuz-4.18.13-200.fc28.x86_64" in pxe_config)
            self.assertTrue("initramfs-4.18.13-200.fc28.x86_64.img" in pxe_config)
            self.assertTrue("/live-rootfs.squashfs.img ostree=/mnt/sysimage/" in pxe_config)

    def test_make_runtime_squashfs(self):
        """Test making a runtime squashfs only image"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            with tempfile.TemporaryDirectory(prefix="lorax.test.root.") as mount_dir:
                # Make a fake kernel and initrd
                mkFakeBoot(mount_dir)
                opts = DataHolder(project="Fedora", releasever="devel", compression="xz", compress_args=[],
                                  arch="x86_64", squashfs_only=True)
                make_runtime(opts, mount_dir, work_dir)

                # Make sure it made an install.img
                self.assertTrue(os.path.exists(joinpaths(work_dir, "images/install.img")))

                # Make sure it looks like a squashfs filesystem
                file_details = get_file_magic(joinpaths(work_dir, "images/install.img"))
                self.assertTrue("Squashfs" in file_details)

                # Make sure the fake kernel is in there
                cmd = ["unsquashfs", "-n", "-l", joinpaths(work_dir, "images/install.img")]
                results = runcmd_output(cmd)
                self.assertTrue("vmlinuz-" in results)


    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def test_make_runtime_squashfs_ext4(self):
        """Test making a runtime squashfs+ext4 only image"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            with tempfile.TemporaryDirectory(prefix="lorax.test.root.") as mount_dir:
                # Make a fake kernel and initrd
                mkFakeBoot(mount_dir)
                opts = DataHolder(project="Fedora", releasever="devel", compression="xz", compress_args=[],
                                  arch="x86_64", squashfs_only=False)
                make_runtime(opts, mount_dir, work_dir)

                # Make sure it made an install.img
                self.assertTrue(os.path.exists(joinpaths(work_dir, "images/install.img")))

                # Make sure it looks like a squashfs filesystem
                file_details = get_file_magic(joinpaths(work_dir, "images/install.img"))
                self.assertTrue("Squashfs" in file_details)

                # Make sure there is a rootfs.img inside the squashfs
                cmd = ["unsquashfs", "-n", "-l", joinpaths(work_dir, "images/install.img")]
                results = runcmd_output(cmd)
                self.assertTrue("rootfs.img" in results)

    def test_get_arch(self):
        """Test getting the arch of the installed kernel"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            # Make a fake kernel and initrd
            mkFakeBoot(work_dir)
            arch = get_arch(work_dir)
            self.assertTrue(arch == "x86_64")

    def test_find_ostree_root(self):
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            ostree_path = "ostree/boot.1/apu/c8f294c479fc948375a001f06bc524d02900d32c6a1a72061a1dc281e9e93e41/0"
            os.makedirs(joinpaths(work_dir, ostree_path))
            self.assertEqual(find_ostree_root(work_dir), ostree_path)

    def test_good_ks_novirt(self):
        """Test a good kickstart with novirt"""
        opts = DataHolder(no_virt=True, make_fsimage=False, make_pxe_live=False)
        ks_version = makeVersion()
        ks = KickstartParser(ks_version, errorsAreFatal=False, missingIncludeIsFatal=False)
        ks.readKickstartFromString("url --url=http://dl.fedoraproject.com\n"
                                   "network --bootproto=dhcp --activate\n"
                                   "repo --name=other --baseurl=http://dl.fedoraproject.com\n"
                                   "part / --size=4096\n"
                                   "shutdown\n")
        self.assertEqual(check_kickstart(ks, opts), [])

    def test_good_ks_virt(self):
        """Test a good kickstart with virt"""
        opts = DataHolder(no_virt=False, make_fsimage=False, make_pxe_live=False)
        ks_version = makeVersion()
        ks = KickstartParser(ks_version, errorsAreFatal=False, missingIncludeIsFatal=False)
        ks.readKickstartFromString("url --url=http://dl.fedoraproject.com\n"
                                   "network --bootproto=dhcp --activate\n"
                                   "repo --name=other --baseurl=http://dl.fedoraproject.com\n"
                                   "part / --size=4096\n"
                                   "shutdown\n")
        self.assertEqual(check_kickstart(ks, opts), [])

    def test_nomethod_novirt(self):
        """Test a kickstart with repo and no url"""
        opts = DataHolder(no_virt=True, make_fsimage=False, make_pxe_live=False)
        ks_version = makeVersion()
        ks = KickstartParser(ks_version, errorsAreFatal=False, missingIncludeIsFatal=False)
        ks.readKickstartFromString("network --bootproto=dhcp --activate\n"
                                   "repo --name=other --baseurl=http://dl.fedoraproject.com\n"
                                   "part / --size=4096\n"
                                   "shutdown\n")
        errors = check_kickstart(ks, opts)
        self.assertTrue("Only url, nfs and ostreesetup" in errors[0])
        self.assertTrue("repo can only be used with the url" in errors[1])

    def test_no_network(self):
        """Test a kickstart with missing network command"""
        opts = DataHolder(no_virt=True, make_fsimage=False, make_pxe_live=False)
        ks_version = makeVersion()
        ks = KickstartParser(ks_version, errorsAreFatal=False, missingIncludeIsFatal=False)
        ks.readKickstartFromString("url --url=http://dl.fedoraproject.com\n"
                                   "part / --size=4096\n"
                                   "shutdown\n")
        errors = check_kickstart(ks, opts)
        self.assertTrue("The kickstart must activate networking" in errors[0])

    def test_displaymode(self):
        """Test a kickstart with displaymode set"""
        opts = DataHolder(no_virt=True, make_fsimage=False, make_pxe_live=False)
        ks_version = makeVersion()
        ks = KickstartParser(ks_version, errorsAreFatal=False, missingIncludeIsFatal=False)
        ks.readKickstartFromString("url --url=http://dl.fedoraproject.com\n"
                                   "network --bootproto=dhcp --activate\n"
                                   "repo --name=other --baseurl=http://dl.fedoraproject.com\n"
                                   "part / --size=4096\n"
                                   "shutdown\n"
                                   "graphical\n")
        errors = check_kickstart(ks, opts)
        self.assertTrue("must not set a display mode" in errors[0])

    def test_autopart(self):
        """Test a kickstart with autopart"""
        opts = DataHolder(no_virt=True, make_fsimage=True, make_pxe_live=False)
        ks_version = makeVersion()
        ks = KickstartParser(ks_version, errorsAreFatal=False, missingIncludeIsFatal=False)
        ks.readKickstartFromString("url --url=http://dl.fedoraproject.com\n"
                                   "network --bootproto=dhcp --activate\n"
                                   "repo --name=other --baseurl=http://dl.fedoraproject.com\n"
                                   "autopart\n"
                                   "shutdown\n")
        errors = check_kickstart(ks, opts)
        self.assertTrue("Filesystem images must use a single" in errors[0])

    def test_boot_part(self):
        """Test a kickstart with a boot partition"""
        opts = DataHolder(no_virt=True, make_fsimage=True, make_pxe_live=False)
        ks_version = makeVersion()
        ks = KickstartParser(ks_version, errorsAreFatal=False, missingIncludeIsFatal=False)
        ks.readKickstartFromString("url --url=http://dl.fedoraproject.com\n"
                                   "network --bootproto=dhcp --activate\n"
                                   "repo --name=other --baseurl=http://dl.fedoraproject.com\n"
                                   "part / --size=4096\n"
                                   "part /boot --size=1024\n"
                                   "shutdown\n")
        errors = check_kickstart(ks, opts)
        self.assertTrue("Filesystem images must use a single" in errors[0])

    def test_shutdown_virt(self):
        """Test a kickstart with reboot instead of shutdown"""
        opts = DataHolder(no_virt=False, make_fsimage=True, make_pxe_live=False)
        ks_version = makeVersion()
        ks = KickstartParser(ks_version, errorsAreFatal=False, missingIncludeIsFatal=False)
        ks.readKickstartFromString("url --url=http://dl.fedoraproject.com\n"
                                   "network --bootproto=dhcp --activate\n"
                                   "repo --name=other --baseurl=http://dl.fedoraproject.com\n"
                                   "part / --size=4096\n"
                                   "reboot\n")
        errors = check_kickstart(ks, opts)
        self.assertTrue("must include shutdown when using virt" in errors[0])

    def test_disk_size_simple(self):
        """Test calculating the disk size with a simple / partition"""
        opts = DataHolder(no_virt=True, make_fsimage=False, make_iso=False, make_pxe_live=False, image_size_align=0)
        ks_version = makeVersion()
        ks = KickstartParser(ks_version, errorsAreFatal=False, missingIncludeIsFatal=False)
        ks.readKickstartFromString("url --url=http://dl.fedoraproject.com\n"
                                   "network --bootproto=dhcp --activate\n"
                                   "repo --name=other --baseurl=http://dl.fedoraproject.com\n"
                                   "part / --size=4096\n"
                                   "shutdown\n")
        self.assertEqual(calculate_disk_size(opts, ks), 4098)

    def test_disk_size_boot(self):
        """Test calculating the disk size with / and /boot partitions"""
        opts = DataHolder(no_virt=True, make_fsimage=False, make_iso=False, make_pxe_live=False, image_size_align=0)
        ks_version = makeVersion()
        ks = KickstartParser(ks_version, errorsAreFatal=False, missingIncludeIsFatal=False)
        ks.readKickstartFromString("url --url=http://dl.fedoraproject.com\n"
                                   "network --bootproto=dhcp --activate\n"
                                   "repo --name=other --baseurl=http://dl.fedoraproject.com\n"
                                   "part / --size=4096\n"
                                   "part /boot --size=512\n"
                                   "shutdown\n")
        self.assertEqual(calculate_disk_size(opts, ks), 4610)

    def test_disk_size_boot_fsimage(self):
        """Test calculating the disk size with / and /boot partitions on a fsimage"""
        opts = DataHolder(no_virt=True, make_fsimage=True, make_iso=False, make_pxe_live=False, image_size_align=0)
        ks_version = makeVersion()
        ks = KickstartParser(ks_version, errorsAreFatal=False, missingIncludeIsFatal=False)
        ks.readKickstartFromString("url --url=http://dl.fedoraproject.com\n"
                                   "network --bootproto=dhcp --activate\n"
                                   "repo --name=other --baseurl=http://dl.fedoraproject.com\n"
                                   "part / --size=4096\n"
                                   "part /boot --size=512\n"
                                   "shutdown\n")
        self.assertEqual(calculate_disk_size(opts, ks), 4098)

    def test_disk_size_reqpart(self):
        """Test calculating the disk size with reqpart and a / partition"""
        opts = DataHolder(no_virt=True, make_fsimage=False, make_iso=False, make_pxe_live=False, image_size_align=0)
        ks_version = makeVersion()
        ks = KickstartParser(ks_version, errorsAreFatal=False, missingIncludeIsFatal=False)
        ks.readKickstartFromString("url --url=http://dl.fedoraproject.com\n"
                                   "network --bootproto=dhcp --activate\n"
                                   "repo --name=other --baseurl=http://dl.fedoraproject.com\n"
                                   "part / --size=4096\n"
                                   "reqpart\n"
                                   "shutdown\n")
        self.assertEqual(calculate_disk_size(opts, ks), 4598)

    def test_disk_size_reqpart_boot(self):
        """Test calculating the disk size with reqpart --add-boot and a / partition"""
        opts = DataHolder(no_virt=True, make_fsimage=False, make_iso=False, make_pxe_live=False, image_size_align=0)
        ks_version = makeVersion()
        ks = KickstartParser(ks_version, errorsAreFatal=False, missingIncludeIsFatal=False)
        ks.readKickstartFromString("url --url=http://dl.fedoraproject.com\n"
                                   "network --bootproto=dhcp --activate\n"
                                   "repo --name=other --baseurl=http://dl.fedoraproject.com\n"
                                   "part / --size=4096\n"
                                   "reqpart --add-boot\n"
                                   "shutdown\n")
        self.assertEqual(calculate_disk_size(opts, ks), 5622)

    def test_disk_size_align(self):
        """Test aligning the disk size"""
        opts = DataHolder(no_virt=True, make_fsimage=False, make_iso=False, make_pxe_live=False, image_size_align=1024)
        ks_version = makeVersion()
        ks = KickstartParser(ks_version, errorsAreFatal=False, missingIncludeIsFatal=False)
        ks.readKickstartFromString("url --url=http://dl.fedoraproject.com\n"
                                   "network --bootproto=dhcp --activate\n"
                                   "repo --name=other --baseurl=http://dl.fedoraproject.com\n"
                                   "part / --size=4096\n"
                                   "shutdown\n")
        self.assertEqual(calculate_disk_size(opts, ks), 5120)

    @unittest.skipUnless(os.geteuid() == 0 and not os.path.exists("/.in-container"), "requires root privileges, and no containers")
    def test_boot_over_root(self):
        """Test the mount_boot_part_over_root ostree function"""
        # Make a fake disk image with a / and a /boot/loader.0
        # Mount the / partition

    def test_make_livecd_dracut(self):
        """Test the make_livecd function with dracut options"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as tmpdir:
            # Make a fake kernel and initrd
            mkFakeBoot(joinpaths(tmpdir, "mount_dir"))
            os.makedirs(joinpaths(tmpdir, "mount_dir/tmp/config_files"))

            lorax_templates = os.path.abspath(find_templates("./share/"))
            with mock.patch('pylorax.treebuilder.TreeBuilder.build'):
                with mock.patch('pylorax.treebuilder.TreeBuilder.rebuild_initrds') as ri:
                    # Test with no dracut args
                    opts = DataHolder(project="Fedora", releasever="32", lorax_templates=lorax_templates, volid=None,
                                      domacboot=False, extra_boot_args="", dracut_args=None, dracut_conf=None)
                    make_livecd(opts, joinpaths(tmpdir, "mount_dir"), joinpaths(tmpdir, "work_dir"))
                    ri.assert_called_with(add_args=DRACUT_DEFAULT)

                    # Test with --dracut-arg
                    opts = DataHolder(project="Fedora", releasever="32", lorax_templates=lorax_templates, volid=None,
                                      domacboot=False, extra_boot_args="", 
                                      dracut_args=["--xz",  "--omit plymouth", "--add livenet dmsquash-live dmsquash-live-ntfs"], dracut_conf=None)
                    make_livecd(opts, joinpaths(tmpdir, "mount_dir"), joinpaths(tmpdir, "work_dir"))
                    ri.assert_called_with(add_args=["--xz",  "--omit", "plymouth", "--add", "livenet dmsquash-live dmsquash-live-ntfs"])


                    # Test with --dracut-conf
                    opts = DataHolder(project="Fedora", releasever="32", lorax_templates=lorax_templates, volid=None,
                                      domacboot=False, extra_boot_args="", dracut_args=None, 
                                      dracut_conf="/var/tmp/project/lmc-dracut.conf")
                    make_livecd(opts, joinpaths(tmpdir, "mount_dir"), joinpaths(tmpdir, "work_dir"))
                    ri.assert_called_with(add_args=["--conf", "/var/tmp/project/lmc-dracut.conf"])
