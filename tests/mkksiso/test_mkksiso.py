from collections import OrderedDict
import filecmp
import os
import random
import shutil
import subprocess
import tempfile
import time
import unittest

from mkksiso import AlterKernelArgs, JoinKernelArgs, SplitCmdline, quote, WrapKernelArgs
from mkksiso import GetCmdline, ListKernelArgs, udev_escape
from mkksiso import EditIsolinux, EditGrub2, EditS390
from mkksiso import CheckDiscinfo, GetISODetails, ExtractISOFiles, MakeKickstartISO


def check_cfg_results(self, tmpdir, configs):
    """
    Helper function to check config file changes against .result files
    """
    test_data = os.path.dirname(__file__) + "/data"
    for cfg in configs:
        with open(test_data + "/" + cfg + ".result") as f:
            expected_cfg = f.read()
        for path in configs[cfg]:
            with open(tmpdir + "/" + path) as f:
                new_cfg = f.read()

            self.maxDiff = None
            self.assertEqual(expected_cfg, new_cfg)

class MkksisoTestCase(unittest.TestCase):
    def test_AlterKernelArgs(self):
        new_kernel_args = AlterKernelArgs(
                OrderedDict({"BOOT_IMAGE": ["kernel-command-stuff"], "console": ["tty1"]}),
                ["quiet", "rd.break"],
                OrderedDict({"inst.ks": ["file:///foo.cfg"], "console": ["ttyS0", "ttyS1"]}))
        self.assertTrue("quiet" not in new_kernel_args)
        self.assertTrue("rd.break" not in new_kernel_args)
        self.assertEqual(["tty1", "ttyS0", "ttyS1"], new_kernel_args["console"])
        self.assertEqual(["file:///foo.cfg"], new_kernel_args["inst.ks"])

    def test_quote(self):
        self.assertEqual('"this is quoted"', quote("this is quoted"))
        self.assertEqual("thisisnotquoted", quote("thisisnotquoted"))

    def test_SplitCmdline(self):
        args = SplitCmdline("BOOT_IMAGE=(hd0,msdos1)/vmlinuz-5.18.0-0.rc5.20220503git9050ba3a61a4b5b.41.fc37.x86_64 root=UUID=6be5119f-8de7-4da1-8e19-3e84cbe5d792 ro console=ttyS0,115200n8 console=tty1 rhgb quiet")
        self.assertTrue("BOOT_IMAGE" in args)
        self.assertTrue("root" in args)
        self.assertEqual(["UUID=6be5119f-8de7-4da1-8e19-3e84cbe5d792"], args["root"])
        self.assertTrue("ro" in args)
        self.assertEqual([None], args["ro"])
        self.assertTrue("console" in args)
        self.assertTrue(len(args["console"]) == 2)
        self.assertEqual(["ttyS0,115200n8", "tty1"], args["console"])

    def test_JoinKernelArgs(self):
        args = OrderedDict({"root": ["UUID=6be5119f-8de7-4da1-8e19-3e84cbe5d792"],
                "ro": [None], "quiet": [None],
                "console": ["ttyS0,115200n8", "tty1"]})
        self.assertEqual("root=UUID=6be5119f-8de7-4da1-8e19-3e84cbe5d792 ro quiet console=ttyS0,115200n8 console=tty1", JoinKernelArgs(args))

    def test_WrapKernelArgs(self):
        kernel_args = OrderedDict({"BOOT_IMAGE": ["(hd0,msdos1)/vmlinuz-5.18.0-0.rc5.20220503git9050ba3a61a4b5b.41.fc37.x86_64"],
                             "root": ["UUID=6be5119f-8de7-4da1-8e19-3e84cbe5d792"],
                             "inst.ks": ["file:///installer.ks"],
                             "quoted": ["A longer string with spaces that is quoted should not be split"],
                             "console": ["tty1"], "quiet": [None], "rhgb": [None]})
        expected = """BOOT_IMAGE=(hd0,msdos1)/vmlinuz-5.18.0-0.rc5.20220503git9050ba3a61a4b5b.41.fc37.x86_64
root=UUID=6be5119f-8de7-4da1-8e19-3e84cbe5d792 inst.ks=file:///installer.ks
quoted="A longer string with spaces that is quoted should not be split"
console=tty1 quiet rhgb
"""
        self.assertEqual(WrapKernelArgs(ListKernelArgs(kernel_args)), expected)

    def test_udev_escape(self):
        self.assertEqual(udev_escape("Si!ly <volid> te$t"), r"Si\x21ly\x20\x3cvolid\x3e\x20te\x24t")

    def test_GetCmdline(self):
        self.assertEqual(GetCmdline("     append ro inst.ks=http://kickstart.cfg quiet", ["append"]),
                        ("     append", "ro inst.ks=http://kickstart.cfg quiet"))
        self.assertEqual(GetCmdline("\t\tlinux ro console=ttyS0 rhgb", ["linuxefi", "linux"]),
                        ("\t\tlinux", "ro console=ttyS0 rhgb"))
        self.assertEqual(GetCmdline("\t\tlinux ro console=ttyS0 rhgb", ["linuxefi", "linux"]),
                        ("\t\tlinux", "ro console=ttyS0 rhgb"))
        self.assertEqual(GetCmdline("\t\tinitrd /images/pxeboot/initrd.img", ["linuxefi", "linux"]),
                        ("", "\t\tinitrd /images/pxeboot/initrd.img"))

    def test_CheckDiscinfo(self):
        with tempfile.TemporaryDirectory(prefix="mkksiso-") as tmpdir:
            with open(tmpdir + "/.discinfo.good", "wt") as f:
                f.write(str(time.time()) + "\n")
                f.write("Fedora mkksiso discinfo test\n")
                f.write(os.uname().machine + "\n")
                f.close()

            with open(tmpdir + "/.discinfo.bad", "wt") as f:
                f.write(str(time.time()) + "\n")
                f.write("Fedora mkksiso discinfo test\n")
                f.write("NOT_AN_ARCH\n")
                f.close()

            # Should not raise an error
            CheckDiscinfo(tmpdir + "/.discinfo.good")

            # Raises an error
            with self.assertRaises(RuntimeError):
                CheckDiscinfo(tmpdir + "/.discinfo.bad")


class EditConfigsTestCase(unittest.TestCase):
    def setUp(self):
        # pylint: disable=attribute-defined-outside-init
        self.rm_args = ["console", "quiet", "inst.cmdline"]
        self.add_args = OrderedDict({
                            "inst.ks": ["file:///installer.ks"],
                            "quoted": ["A longer string with spaces that is quoted should not be split"],
                            "console": ["ttyS0,115200n8", "tty1"]
            })
        self.new_volid = "Fedora-mkksiso-rawhide-test"
        self.old_volid = "Fedora-rawhide-test"
        self.replace_list = [(self.old_volid, self.new_volid)]


    def run_test(self, configs, tmpdir, test_fn):
        """
        Run the test_fn on the configs

        configs is a dict, like this:
        {
            "isolinux.cfg": ["isolinux/isolinux.cfg"],
        }

        The key is a config file under ./data/ and the list is the paths and filenames
        to write to.

        The function is called, and the results are compared to the results
        which are in the file named for the key with '.result' appended. eg.
        './data/isolinux.cfg.result'
        """
        test_data = os.path.dirname(__file__) + "/data"
        # Copy the test data under tmpdir, simulating the root of an ISO
        for cfg in configs:
            for path in configs[cfg]:
                os.makedirs(os.path.dirname(tmpdir + "/" + path), exist_ok=True)
                shutil.copy(test_data + "/" + cfg, tmpdir + "/" + path)

        test_fn(self.rm_args, self.add_args, self.replace_list, tmpdir)

        # Read the modified config file(s) and compare to result file
        check_cfg_results(self, tmpdir, configs)

    def test_EditIsolinux(self):
        with tempfile.TemporaryDirectory(prefix="mkksiso-") as tmpdir:
            self.run_test({"isolinux.cfg": ["isolinux/isolinux.cfg"]}, tmpdir, EditIsolinux)

    def test_EditGrub2(self):
        with tempfile.TemporaryDirectory(prefix="mkksiso-") as tmpdir:
            self.run_test({
                "uefi-grub.cfg": ["EFI/BOOT/grub.cfg"],
                "bios-grub.cfg": ["boot/grub2/grub.cfg", "boot/grub/grub.cfg"],
                "BOOT.conf": ["EFI/BOOT/BOOT.conf"]}, tmpdir, EditGrub2)

    def test_EditS390(self):
        with tempfile.TemporaryDirectory(prefix="mkksiso-") as tmpdir:
            self.run_test({"generic.prm": ["images/generic.prm"],
                           "cdboot.prm": ["images/cdboot.prm"]}, tmpdir, EditS390)


class ISOTestCase(unittest.TestCase):
    test_iso = None
    out_iso = None
    expected_files = []

    def setUp(self):
        self.configs = {
            "isolinux.cfg": ["isolinux/isolinux.cfg"],
            "uefi-grub.cfg": ["EFI/BOOT/grub.cfg"],
            "bios-grub.cfg": ["boot/grub2/grub.cfg", "boot/grub/grub.cfg"],
            "BOOT.conf": ["EFI/BOOT/BOOT.conf"],
            "generic.prm": ["images/generic.prm"],
            "cdboot.prm": ["images/cdboot.prm"]}

        # Make a fake iso that just has the config files in it
        test_data = os.path.dirname(__file__) + "/data"
        with tempfile.TemporaryDirectory(prefix="mkksiso-") as tmpdir:
            grafts = set()
            # Copy the test data under tmpdir, simulating the root of an ISO
            for cfg in self.configs:
                for path in self.configs[cfg]:
                    os.makedirs(os.path.dirname(tmpdir + "/" + path), exist_ok=True)
                    shutil.copy(test_data + "/" + cfg, tmpdir + "/" + path)

                    # Add the top as a graft point
                    grafts.add(path.split("/")[0])
                    self.expected_files.append(path)

            # NOTE: Just want a random filename here, not an open file, so mktemp() is used
            self.test_iso = tempfile.mktemp(prefix="mkksiso-")
            # Make an iso with volid and default config files
            cmd = ["xorrisofs", "-o", self.test_iso, "-R", "-J", "-V", "Fedora-rawhide-test",
                   "-graft-points"]
            cmd.extend(f"{g}={tmpdir}/{g}" for g in grafts)
            subprocess.run(cmd, check=True, capture_output=False, env={"LANG": "C"})

    def tearDown(self):
        if self.test_iso and os.path.exists(self.test_iso):
            os.unlink(self.test_iso)

        if self.out_iso and os.path.exists(self.out_iso):
            os.unlink(self.out_iso)

    def test_GetISODetails(self):
        """
        Test getting the volid and list of files from the test iso
        """
        volid, files = GetISODetails(self.test_iso)

        self.assertEqual(volid, "Fedora-rawhide-test")
        self.assertTrue(len(files) > 0)

        # File list also includes directories, we only care about the files:
        diff = set(self.expected_files) - set(files)
        self.assertEqual(len(diff), 0, diff)

    def test_ExtractISOFiles(self):
        """
        Test extracting files from the test iso
        """
        with tempfile.TemporaryDirectory(prefix="mkksiso-") as tmpdir:
            ExtractISOFiles(self.test_iso, self.expected_files, tmpdir)

            missing = [f for f in self.expected_files if not os.path.exists(tmpdir + "/" + f)]
            self.assertEqual(len(missing), 0, missing)

    def test_MakeKickstartISO(self):
        """
        Test the full process of editing the cmdline and adding a kickstart

        NOTE: This does not run mkefiboot since it needs root and will not work in a container
        """
        rm_args = "console quiet inst.cmdline"
        cmdline = "inst.ks=file:///installer.ks quoted=\"A longer string with spaces that is quoted should not be split\" console=ttyS0,115200n8 console=tty1"
        new_volid = "Fedora-mkksiso-rawhide-test"

        self.out_iso = tempfile.mktemp(prefix="mkksiso-")
        MakeKickstartISO(self.test_iso, self.out_iso, cmdline=cmdline, rm_args=rm_args,
                new_volid=new_volid, implantmd5=True, skip_efi=True)

        with tempfile.TemporaryDirectory(prefix="mkksiso-") as tmpdir:
            ExtractISOFiles(self.out_iso, self.expected_files, tmpdir)

            # Read the modified config file(s) and compare to result file
            check_cfg_results(self, tmpdir, self.configs)

    def test_MakeKickstartISO_updates(self):
        """
        Test if updates image is stored in the ISO correctly.
        """

        self.out_iso = tempfile.mktemp(prefix="mkksiso-")

        with tempfile.NamedTemporaryFile() as mocked_updates:
            open(mocked_updates.name, "wb").close()

            MakeKickstartISO(self.test_iso, self.out_iso, updates_image=mocked_updates.name, skip_efi=True)

            with tempfile.TemporaryDirectory(prefix="mkksiso-") as tmpdir:
                ExtractISOFiles(self.out_iso, [os.path.basename(mocked_updates.name)], tmpdir)

                self.assertTrue(os.path.exists(os.path.join(tmpdir, os.path.basename(mocked_updates.name))))

    def test_MakeKickstartISO_reproducible(self):
        """
        Test output ISO are reproducible when using SOURCE_DATE_EPOCH
        """

        with tempfile.TemporaryDirectory(prefix="mkksiso-dir-") as tmpdir:
            for iso_num in [1,2]:
                # create lots of files in random order to ensure xorriso actually sort by file name
                # and properly force the files timestamps
                extra_dir = os.path.join(tmpdir, str(iso_num), "extra")
                os.makedirs(extra_dir)
                extra_files = list(range(1,999))
                random.shuffle(extra_files)
                for i in extra_files:
                    extra_file = os.path.join(extra_dir, str(i))
                    with open(extra_file, "x") as f:
                        f.write(str(i))
                    os.utime(extra_file, (random.randint(1000, 2000), random.randint(1000, 2000)))

                iso_file = os.path.join(tmpdir, str(iso_num), "test.iso")
                MakeKickstartISO(self.test_iso, iso_file, cmdline="repro=1 repro=2", add_paths=[extra_dir], skip_efi=True, source_date_epoch="42")

            self.assertTrue(filecmp.cmp(os.path.join(tmpdir, "1", "test.iso"),
                                        os.path.join(tmpdir, "2", "test.iso"), shallow=False),
                            "ISO are not identical")
