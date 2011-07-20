# imgutils.py - utility functions/classes for building disk images
#
# Copyright (C) 2011  Red Hat, Inc.
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
# Author(s):  Will Woods <wwoods@redhat.com>

import logging
logger = logging.getLogger("pylorax.imgutils")

import os, tempfile
from os.path import join, dirname
from subprocess import *

######## Functions for making container images (cpio, squashfs) ##########

def mkcpio(rootdir, outfile, compression="xz", compressargs=["-9"]):
    '''Make a compressed CPIO archive of the given rootdir.
    compression should be "xz", "gzip", "lzma", or None.
    compressargs will be used on the compression commandline.'''
    if compression not in (None, "xz", "gzip", "lzma"):
        raise ValueError, "Unknown compression type %s" % compression
    chdir = lambda: os.chdir(rootdir)
    if compression == "xz":
        compressargs.insert(0, "--check=crc32")
    if compression is None:
        compression = "cat" # this is a little silly
        compressargs = []
    find = Popen(["find", ".", "-print0"], stdout=PIPE, preexec_fn=chdir)
    cpio = Popen(["cpio", "--null", "--quiet", "-H", "newc", "-o"],
                 stdin=find.stdout, stdout=PIPE, preexec_fn=chdir)
    comp = Popen([compression] + compressargs,
                 stdin=cpio.stdout, stdout=open(outfile, "wb"))
    comp.wait()
    return comp.returncode

def mksquashfs(rootdir, outfile, compression="default", compressargs=[]):
    '''Make a squashfs image containing the given rootdir.'''
    if compression != "default":
        compressargs = ["-comp", compression] + compressargs
    return call(["mksquashfs", rootdir, outfile] + compressargs)

######## Utility functions ###############################################

def mksparse(outfile, size):
    '''use os.ftruncate to create a sparse file of the given size.'''
    fobj = open(outfile, "w")
    os.ftruncate(fobj.fileno(), size)

def loop_attach(outfile):
    '''Attach a loop device to the given file. Return the loop device name.
    Raises CalledProcessError if losetup fails.'''
    dev = check_output(["losetup", "--find", "--show", outfile], stderr=PIPE)
    return dev.strip()

def loop_detach(loopdev):
    '''Detach the given loop device. Return False on failure.'''
    return (call(["losetup", "--detach", loopdev]) == 0)

def dm_attach(dev, size, name=None):
    '''Attach a devicemapper device to the given device, with the given size.
    If name is None, a random name will be chosen. Returns the device name.
    raises CalledProcessError if dmsetup fails.'''
    if name is None:
        name = tempfile.mktemp(prefix="lorax.imgutils.", dir="")
    check_call(["dmsetup", "create", name, "--table",
                "0 %i linear %s 0" % (size/512, dev)],
                stdout=PIPE, stderr=PIPE)
    return name

def dm_detach(dev):
    '''Detach the named devicemapper device. Returns False if dmsetup fails.'''
    dev = dev.replace("/dev/mapper/", "") # strip prefix, if it's there
    return call(["dmsetup", "remove", dev], stdout=PIPE, stderr=PIPE)

def mount(dev, opts="", mnt=None):
    '''Mount the given device at the given mountpoint, using the given opts.
    opts should be a comma-separated string of mount options.
    if mnt is none, a temporary directory will be created and its path will be
    returned.
    raises CalledProcessError if mount fails.'''
    if mnt is None:
        mnt = tempfile.mkdtemp(prefix="lorax.imgutils.")
    mount = ["mount"]
    if opts:
        mount += ["-o", opts]
    check_call(mount + [dev, mnt])
    return mnt

def umount(mnt):
    '''Unmount the given mountpoint. If the mount was a temporary dir created
    by mount, it will be deleted. Returns false if the unmount fails.'''
    rv = call(["umount", mnt])
    if 'lorax.imgutils' in mnt:
        os.rmdir(mnt)
    return (rv == 0)

def copytree(src, dest, preserve=True):
    '''Copy a tree of files using cp -a, thus preserving modes, timestamps,
    links, acls, sparse files, xattrs, selinux contexts, etc.
    If preserve is False, uses cp -R (useful for modeless filesystems)'''
    chdir = lambda: os.chdir(src)
    cp = ["cp", "-a"] if preserve else ["cp", "-R", "-L"]
    check_call(cp + [".", os.path.abspath(dest)], preexec_fn=chdir)

def do_grafts(grafts, dest, preserve=True):
    '''Copy each of the items listed in grafts into dest.
    If the key ends with '/' it's assumed to be a directory which should be
    created, otherwise just the leading directories will be created.'''
    for imgpath, filename in grafts.items():
        if imgpath[-1] == '/':
            targetdir = join(dest, imgpath)
            imgpath = imgpath[:-1]
        else:
            targetdir = join(dest, dirname(imgpath))
        if not os.path.isdir(targetdir):
            os.makedirs(targetdir)
        copytree(filename, join(dest, imgpath), preserve)

def round_to_blocks(size, blocksize):
    '''If size isn't a multiple of blocksize, round up to the next multiple'''
    diff = size % blocksize
    if diff or not size:
        size += blocksize - diff
    return size

def estimate_size(rootdir, graft={}, fstype=None, blocksize=4096, overhead=1024):
    getsize = lambda f: os.lstat(f).st_size
    if fstype == "btrfs":
        overhead = 64*1024 # don't worry, it's all sparse
    if fstype in ("vfat", "msdos"):
        overhead = 128
        blocksize = 2048
        getsize = lambda f: os.stat(f).st_size # no symlinks, count as copies
    total = overhead*blocksize
    dirlist = graft.values()
    if rootdir:
        dirlist.append(rootdir)
    for root in dirlist:
        for top, dirs, files in os.walk(root):
            for f in files + dirs:
                total += round_to_blocks(getsize(join(top,f)), blocksize)
    if fstype == "btrfs":
        total = max(256*1024*1024, total) # btrfs minimum size: 256MB
    return total

######## Execution contexts - use with the 'with' statement ##############

class LoopDev(object):
    def __init__(self, filename, size=None):
        self.filename = filename
        if size:
            mksparse(self.filename, size)
    def __enter__(self):
        self.loopdev = loop_attach(self.filename)
        return self.loopdev
    def __exit__(self, exc_type, exc_value, traceback):
        loop_detach(self.loopdev)

class DMDev(object):
    def __init__(self, dev, size, name=None):
        (self.dev, self.size, self.name) = (dev, size, name)
    def __enter__(self):
        self.mapperdev = dm_attach(self.dev, self.size, self.name)
        return self.mapperdev
    def __exit__(self, exc_type, exc_value, traceback):
        dm_detach(self.mapperdev)

class Mount(object):
    def __init__(self, dev, opts="", mnt=None):
        (self.dev, self.opts, self.mnt) = (dev, opts, mnt)
    def __enter__(self):
        self.mnt = mount(self.dev, self.opts, self.mnt)
        return self.mnt
    def __exit__(self, exc_type, exc_value, traceback):
        umount(self.mnt)

######## Functions for making filesystem images ##########################

def mkfsimage(fstype, rootdir, outfile, size=None, mkfsargs=[], mountargs="", graft={}):
    '''Generic filesystem image creation function.
    fstype should be a filesystem type - "mkfs.${fstype}" must exist.
    graft should be a dict: {"some/path/in/image": "local/file/or/dir"};
      if the path ends with a '/' it's assumed to be a directory.
    Will raise CalledProcessError if something goes wrong.'''
    preserve = (fstype not in ("msdos", "vfat"))
    if not size:
        size = estimate_size(rootdir, graft, fstype)
    with LoopDev(outfile, size) as loopdev:
        check_call(["mkfs.%s" % fstype] + mkfsargs + [loopdev],
                   stdout=PIPE, stderr=PIPE)
        with Mount(loopdev, mountargs) as mnt:
            if rootdir:
                copytree(rootdir, mnt, preserve)
            do_grafts(graft, mnt, preserve)

# convenience functions with useful defaults
def mkdosimg(rootdir, outfile, size=None, label="", mountargs="shortname=winnt,umask=0777", graft={}):
    mkfsimage("msdos", rootdir, outfile, size, mountargs=mountargs,
              mkfsargs=["-n", label], graft=graft)

def mkext4img(rootdir, outfile, size=None, label="", mountargs="", graft={}):
    mkfsimage("ext4", rootdir, outfile, size, mountargs=mountargs,
              mkfsargs=["-L", label, "-b", "1024", "-m", "0"], graft=graft)

def mkbtrfsimg(rootdir, outfile, size=None, label="", mountargs="", graft={}):
    mkfsimage("btrfs", rootdir, outfile, size, mountargs=mountargs,
               mkfsargs=["-L", label], graft=graft)
