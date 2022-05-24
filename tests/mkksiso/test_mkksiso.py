from collections import OrderedDict
from mkksiso import AlterKernelArgs, JoinKernelArgs, SplitCmdline, quote
import unittest


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
        args = SplitCmdline("BOOT_IMAGE=(hd0,msdos1)/vmlinuz-5.18.0-0.rc5.20220503git9050ba3a61a4b5b.41.fc37.x86_64 root=UUID=6be5119f-8de7-4da1-8e19-3e84cbe5d792 ro console=ttyS0,115200,N81 console=tty1 rhgb quiet")
        self.assertTrue("BOOT_IMAGE" in args)
        self.assertTrue("root" in args)
        self.assertEqual(["UUID=6be5119f-8de7-4da1-8e19-3e84cbe5d792"], args["root"])
        self.assertTrue("ro" in args)
        self.assertEqual([None], args["ro"])
        self.assertTrue("console" in args)
        self.assertTrue(len(args["console"]) == 2)
        self.assertEqual(["ttyS0,115200,N81", "tty1"], args["console"])

    def test_JoinKernelArgs(self):
        args = OrderedDict({"root": ["UUID=6be5119f-8de7-4da1-8e19-3e84cbe5d792"],
                "ro": [None], "quiet": [None],
                "console": ["ttyS0,115200,N81", "tty1"]})
        self.assertEqual("root=UUID=6be5119f-8de7-4da1-8e19-3e84cbe5d792 ro quiet console=ttyS0,115200,N81 console=tty1", JoinKernelArgs(args))
