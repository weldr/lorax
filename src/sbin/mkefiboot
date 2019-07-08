#!/usr/bin/python3
# mkefiboot - a tool to make EFI boot images
#
# Copyright (C) 2011-2015  Red Hat, Inc.
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
# Red Hat Author(s):  Will Woods <wwoods@redhat.com>

import logging
logging.basicConfig()
log = logging.getLogger()

import os, tempfile, argparse
from subprocess import check_call, PIPE
from pylorax.imgutils import mkdosimg, round_to_blocks, LoopDev, DMDev, dm_detach
from pylorax.imgutils import mkhfsimg, Mount, estimate_size
import struct, shutil, glob

def mkefiboot(bootdir, outfile, label):
    '''Make an EFI boot image with the contents of bootdir in EFI/BOOT'''
    mkdosimg(None, outfile, label=label, graft={'EFI/BOOT':bootdir})

def mkmacboot(bootdir, outfile, label, icon=None, product='Generic',
              diskname=None):
    '''Make an EFI boot image for Apple's EFI implementation'''
    graft = {'EFI/BOOT':bootdir}
    if icon and os.path.exists(icon):
        graft['.VolumeIcon.icns'] = icon
    if diskname and os.path.exists(diskname):
        graft['EFI/BOOT/.disk_label'] = diskname
    # shim and grub2 are in 2 places so double the estimate
    size = estimate_size(None, graft=graft) * 2
    mkhfsimg(None, outfile, label=label, graft=graft, size=size)
    macmunge(outfile, product)

# To make an HFS+ image bootable, we need to fill in parts of the
# HFSPlusVolumeHeader structure - specifically, finderInfo[0,1,5].
# For details, see Technical Note TN1150: HFS Plus Volume Format
# http://developer.apple.com/library/mac/#technotes/tn/tn1150.html
#
# Additionally, we want to do some fixups to make it play nicely with
# the startup disk preferences panel.
def macmunge(imgfile, product):
    '''"bless" the EFI bootloader inside the given Mac EFI boot image, by
    writing its inode info into the HFS+ volume header.'''
    # Get the inode number for the boot image and its parent directory
    with LoopDev(imgfile) as loopdev:
        with Mount(loopdev) as mnt:
            shim = glob.glob(os.path.join(mnt, 'EFI/BOOT/BOOT*.EFI'))[0]
            loader = glob.glob(os.path.join(mnt,'EFI/BOOT/grub*.efi'))[0]
            config = glob.glob(os.path.join(mnt,'EFI/*/grub*.cfg'))[0]
            blessnode = os.stat(loader).st_ino
            dirnode = os.stat(os.path.dirname(loader)).st_ino
            with open(os.path.join(mnt,'mach_kernel'), 'w') as kernel:
                kernel.write('Dummy kernel for booting')
            sysdir = os.path.join(mnt,'System/Library/CoreServices/')
            os.makedirs(sysdir)
            with open(os.path.join(sysdir,'SystemVersion.plist'), 'w') as plist:
                plist.write('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
<key>ProductBuildVersion</key>
<string></string>
<key>ProductName</key>
<string>Linux</string>
<key>ProductVersion</key>
<string>%s</string>
</dict>
</plist>
''' % (product,))
            # NOTE: OSX won't boot if we hardlink to /EFI/BOOT and grub2
            # can't read the config file if we hardlink the other direction
            # So copy the files.
            shutil.copy(shim, os.path.join(sysdir,'boot.efi'))
            shutil.copy(loader, sysdir)
            shutil.copy(config, sysdir)

    # format data properly (big-endian UInt32)
    nodedata = struct.pack(">i", blessnode)
    dirdata = struct.pack(">i", dirnode)
    # Write it to the volume header
    with open(imgfile, "r+b") as img:
        img.seek(0x450)      # HFSPlusVolumeHeader->finderInfo
        img.write(dirdata)   # finderInfo[0]
        img.write(nodedata)  # finderInfo[1]
        img.seek(0x464)      #
        img.write(dirdata)   # finderInfo[5]

def mkefidisk(efiboot, outfile):
    '''Make a bootable EFI disk image out of the given EFI boot image.'''
    # pjones sez: "17408 is the size of the GPT tables parted creates,
    #              but there are two of them."
    partsize = os.path.getsize(efiboot) + 17408 * 2
    disksize = round_to_blocks(2 * 17408 + partsize, 512)
    with LoopDev(outfile, disksize) as loopdev:
        with DMDev(loopdev, disksize) as dmdev:
            check_call(["parted", "--script", "/dev/mapper/%s" % dmdev,
            "mklabel", "gpt",
            "unit", "b",
            "mkpart", "'EFI System Partition'", "fat32", "34816", str(partsize),
            "set", "1", "boot", "on"], stdout=PIPE, stderr=PIPE)
            partdev = "/dev/mapper/{0}p1".format(dmdev)
            with open(efiboot, "rb") as infile:
                with open(partdev, "wb") as outfile:
                    outfile.write(infile.read())
            dm_detach(dmdev+"p1")

def main():
    parser = argparse.ArgumentParser(description="Make an EFI boot image from the given directory.")
    parser.add_argument("--debug", action="store_const", const=logging.DEBUG,
        dest="loglevel", default=log.getEffectiveLevel(),
        help="print debugging info")
    parser.add_argument("-d", "--disk", action="store_true",
        help="make a full EFI disk image (including partition table)")
    parser.add_argument("-a", "--apple", action="store_const", const="apple",
        dest="imgtype", default="default",
        help="make an Apple EFI image (use hfs+, bless bootloader)")
    parser.add_argument("-l", "--label", default="EFI",
        help="filesystem label to use (default: %(default)s)")
    parser.add_argument("-i", "--icon", metavar="ICONFILE",
        help="icon file to include (for Apple EFI image)")
    parser.add_argument("-n", "--diskname", metavar="DISKNAME",
        help="disk name image to include (for Apple EFI image)")
    parser.add_argument("-p", "--product", metavar="PRODUCT",
        help="product name to use (for Apple EFI image)")
    parser.add_argument("bootdir", metavar="EFIBOOTDIR",
        help="input directory (will become /EFI/BOOT in the image)")
    parser.add_argument("outfile", metavar="OUTPUTFILE",
        help="output file to write")
    opt = parser.parse_args()
    # logging
    log.setLevel(opt.loglevel)
    # sanity checks
    if not os.path.isdir(opt.bootdir):
        parser.error("%s is not a directory" % opt.bootdir)
    if os.getuid() > 0:
        parser.error("need root permissions")
    if opt.icon and not opt.imgtype == "apple":
        print("Warning: --icon is only useful for Apple EFI images")
    if opt.diskname and not opt.imgtype == "apple":
        print("Warning: --diskname is only useful for Apple EFI images")
    log.debug(opt)
    # do the thing!
    if opt.imgtype == "apple":
        mkmacboot(opt.bootdir, opt.outfile, opt.label, opt.icon, opt.product,
                  opt.diskname)
    else:
        mkefiboot(opt.bootdir, opt.outfile, opt.label)
    if opt.disk:
        efiboot = tempfile.NamedTemporaryFile(prefix="mkefiboot.").name
        shutil.move(opt.outfile, efiboot)
        mkefidisk(efiboot, opt.outfile)

if __name__ == '__main__':
    main()
