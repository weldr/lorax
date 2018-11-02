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
import xml.etree.ElementTree as ET

from pylorax import find_templates
from pylorax.base import DataHolder
from pylorax.creator import FakeDNF, create_pxe_config, make_appliance, make_squashfs, squashfs_args
from pylorax.executils import runcmd
from pylorax.imgutils import mksparse
from pylorax.sysutils import joinpaths

class CreatorTest(unittest.TestCase):
    def fakednf_test(self):
        """Test FakeDNF class"""
        fake_dbo = FakeDNF(conf=DataHolder(installroot="/a/fake/install/root/"))
        self.assertEqual(fake_dbo.conf.installroot, "/a/fake/install/root/")

    def squashfs_args_test(self):
        """Test squashfs_args results"""
        test_arches = {"x86_64": ("xz", ["-Xbcj", "x86"]),
                       "ppc64": ("xz", ["-Xbcj", "powerpc"]),
                       "ppc64le": ("xz", ["-Xbcj", "powerpc"]),
                       "s390x": ("xz", []),
                       "ia64": ("xz", []),
                       "aarch64": ("xz", [])
        }

        for arch in test_arches:
            opts = DataHolder(compression=None, arch=arch)
            self.assertEqual(squashfs_args(opts), test_arches[arch], (opts, squashfs_args(opts)))

        opts = DataHolder(compression="lzma", arch="x86_64")
        self.assertEqual(squashfs_args(opts), ("lzma", []), (opts, squashfs_args(opts)))

    def make_appliance_test(self):
        """Test creating the appliance description XML file"""
        lorax_templates = find_templates("./share/")
        appliance_template = joinpaths(lorax_templates, "appliance/libvirt.tmpl")
        self.assertTrue(os.path.exists(appliance_template))

        # A fake disk image
        with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
            open(disk_img.name, "wb").write(b"THIS IS A FAKE DISK IMAGE FILE")
            with tempfile.NamedTemporaryFile(prefix="lorax.test.appliance.") as output_xml:
                make_appliance(disk_img.name, "test-appliance", appliance_template, output_xml.name,
                              ["eth0", "eth1"], ram=4096, vcpus=8, arch="x86_64",
                              title="Lorax Test", project="Fedora", releasever="30")

                print(open(output_xml.name).read())
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

    def pxe_config_test(self):
        """Test creation of a PXE config file"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            live_image_name = "live-rootfs.squashfs.img"
            add_pxe_args = ["ostree=/mnt/sysimage/"]
            lorax_templates = find_templates("./share/")
            template = joinpaths(lorax_templates, "pxe-live/pxe-config.tmpl")

            # Make a fake kernel and initrd
            open(joinpaths(work_dir, "vmlinuz-4.18.13-200.fc28.x86_64"), "w").write("I AM A FAKE KERNEL")
            open(joinpaths(work_dir, "initramfs-4.18.13-200.fc28.x86_64.img"), "w").write("I AM A FAKE INITRD")

            # Create the PXE_CONFIG in work_dir
            create_pxe_config(template, work_dir, live_image_name, add_pxe_args)
            print(open(joinpaths(work_dir, "PXE_CONFIG")).read())
            pxe_config = open(joinpaths(work_dir, "PXE_CONFIG")).read()
            self.assertTrue("vmlinuz-4.18.13-200.fc28.x86_64" in pxe_config)
            self.assertTrue("initramfs-4.18.13-200.fc28.x86_64.img" in pxe_config)
            self.assertTrue("/live-rootfs.squashfs.img ostree=/mnt/sysimage/" in pxe_config)

    def make_squashfs_test(self):
        """Test making a squashfs image"""
        with tempfile.TemporaryDirectory(prefix="lorax.test.") as work_dir:
            with tempfile.NamedTemporaryFile(prefix="lorax.test.disk.") as disk_img:
                # Make a small ext4 disk image
                mksparse(disk_img.name, 42 * 1024**2)
                runcmd(["mkfs.ext4", "-L", "Anaconda", "-b", "4096", "-m", "0", disk_img.name])
                opts = DataHolder(compression="xz", arch="x86_64")
                make_squashfs(opts, disk_img.name, work_dir)

                # Make sure it made an install.img
                self.assertTrue(os.path.exists(joinpaths(work_dir, "images/install.img")))

                # Make sure it looks like a squashfs filesystem
                squashfs_sig = open(joinpaths(work_dir, "images/install.img"), "rb").read(4)
                self.assertTrue(squashfs_sig in [b"hsqs", b"sqsh"])
