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
from subprocess import CalledProcessError
import sys
import traceback
from time import sleep

from pylorax.sysutils import cpfile
from pylorax.executils import execWithRedirect, execWithCapture

######## Functions for making container images (cpio, squashfs) ##########

def mkcpio(rootdir, outfile, compression="xz", compressargs=["-9"]):
    '''Make a compressed CPIO archive of the given rootdir.
    compression should be "xz", "gzip", "lzma", or None.
    compressargs will be used on the compression commandline.'''
    if compression not in (None, "xz", "gzip", "lzma"):
        raise ValueError, "Unknown compression type %s" % compression
    if compression == "xz":
        compressargs.insert(0, "--check=crc32")
    if compression is None:
        compression = "cat" # this is a little silly
        compressargs = []
    logger.debug("mkcpio %s | %s %s > %s", rootdir, compression,
                                        " ".join(compressargs), outfile)
    find = Popen(["find", ".", "-print0"], stdout=PIPE, cwd=rootdir)
    cpio = Popen(["cpio", "--null", "--quiet", "-H", "newc", "-o"],
                 stdin=find.stdout, stdout=PIPE, cwd=rootdir)
    comp = Popen([compression] + compressargs,
                 stdin=cpio.stdout, stdout=open(outfile, "wb"))
    comp.wait()
    return comp.returncode

def mksquashfs(rootdir, outfile, compression="default", compressargs=[]):
    '''Make a squashfs image containing the given rootdir.'''
    if compression != "default":
        compressargs = ["-comp", compression] + compressargs
    return execWithRedirect("mksquashfs", [rootdir, outfile] + compressargs)

######## Utility functions ###############################################

def mksparse(outfile, size):
    '''use os.ftruncate to create a sparse file of the given size.'''
    fobj = open(outfile, "w")
    os.ftruncate(fobj.fileno(), size)

def loop_attach(outfile):
    '''Attach a loop device to the given file. Return the loop device name.
    Raises CalledProcessError if losetup fails.'''
    dev = execWithCapture("losetup", ["--find", "--show", outfile])
    return dev.strip()

def loop_detach(loopdev):
    '''Detach the given loop device. Return False on failure.'''
    return (execWithRedirect("losetup", ["--detach", loopdev]) == 0)

def get_loop_name(path):
    '''Return the loop device associated with the path.
    Raises RuntimeError if more than one loop is associated'''
    buf = execWithCapture("losetup", ["-j", path])
    if len(buf.splitlines()) > 1:
        # there should never be more than one loop device listed
        raise RuntimeError("multiple loops associated with %s" % path)
    name = os.path.basename(buf.split(":")[0])
    return name

def dm_attach(dev, size, name=None):
    '''Attach a devicemapper device to the given device, with the given size.
    If name is None, a random name will be chosen. Returns the device name.
    raises CalledProcessError if dmsetup fails.'''
    if name is None:
        name = tempfile.mktemp(prefix="lorax.imgutils.", dir="")
    execWithRedirect("dmsetup", ["create", name, "--table",
                                 "0 %i linear %s 0" % (size/512, dev)])
    return name

def dm_detach(dev):
    '''Detach the named devicemapper device. Returns False if dmsetup fails.'''
    dev = dev.replace("/dev/mapper/", "") # strip prefix, if it's there
    return execWithRedirect("dmsetup", ["remove", dev])

def mount(dev, opts="", mnt=None):
    '''Mount the given device at the given mountpoint, using the given opts.
    opts should be a comma-separated string of mount options.
    if mnt is none, a temporary directory will be created and its path will be
    returned.
    raises CalledProcessError if mount fails.'''
    if mnt is None:
        mnt = tempfile.mkdtemp(prefix="lorax.imgutils.")
        logger.debug("make tmp mountdir %s", mnt)
    mount = ["mount"]
    if opts:
        mount += ["-o", opts]
    mount += [dev, mnt]
    execWithRedirect(mount[0], mount[1:])
    return mnt

def umount(mnt,  lazy=False, maxretry=3, retrysleep=1.0):
    '''Unmount the given mountpoint. If lazy is True, do a lazy umount (-l).
    If the mount was a temporary dir created by mount, it will be deleted.
    raises CalledProcessError if umount fails.'''
    umount = ["umount"]
    if lazy: umount += ["-l"]
    umount += [mnt]
    count = 0
    while maxretry > 0:
        try:
            rv = execWithRedirect(umount[0], umount[1:])
        except CalledProcessError:
            count += 1
            if count == maxretry:
                raise
            logger.warn("failed to unmount %s. retrying (%d/%d)...",
                         mnt, count, maxretry)
            if logger.getEffectiveLevel() <= logging.DEBUG:
                fuser = execWithCapture("fuser", ["-vm", mnt])
                logger.debug("fuser -vm:\n%s\n", fuser)
            sleep(retrysleep)
        else:
            break
    if 'lorax.imgutils' in mnt:
        os.rmdir(mnt)
        logger.debug("remove tmp mountdir %s", mnt)
    return (rv == 0)

def copytree(src, dest, preserve=True):
    '''Copy a tree of files using cp -a, thus preserving modes, timestamps,
    links, acls, sparse files, xattrs, selinux contexts, etc.
    If preserve is False, uses cp -R (useful for modeless filesystems)'''
    logger.debug("copytree %s %s", src, dest)
    cp = ["cp", "-a"] if preserve else ["cp", "-R", "-L"]
    cp += [".", os.path.abspath(dest)]
    execWithRedirect(cp[0], cp[1:], cwd=src)

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
        if os.path.isdir(filename):
            copytree(filename, join(dest, imgpath), preserve)
        else:
            cpfile(filename, join(dest, imgpath))

def round_to_blocks(size, blocksize):
    '''If size isn't a multiple of blocksize, round up to the next multiple'''
    diff = size % blocksize
    if diff or not size:
        size += blocksize - diff
    return size

# TODO: move filesystem data outside this function
def estimate_size(rootdir, graft={}, fstype=None, blocksize=4096, overhead=128):
    getsize = lambda f: os.lstat(f).st_size
    if fstype == "btrfs":
        overhead = 64*1024 # don't worry, it's all sparse
    if fstype == "hfsplus":
        overhead = 200 # hack to deal with two bootloader copies
    if fstype in ("vfat", "msdos"):
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

class PartitionMount(object):
    """ Mount a partitioned image file using kpartx """
    def __init__(self, disk_img, mount_ok=None):
        """
        disk_img is the full path to a partitioned disk image
        mount_ok is a function that is passed the mount point and
        returns True if it should be mounted.
        """
        self.mount_dir = None
        self.disk_img = disk_img
        self.mount_ok = mount_ok

        # Default is to mount partition with /etc/passwd
        if not self.mount_ok:
            self.mount_ok = lambda mount_dir: os.path.isfile(mount_dir+"/etc/passwd")

        # Example kpartx output
        # kpartx -p p -v -a /tmp/diskV2DiCW.im
        # add map loop2p1 (253:2): 0 3481600 linear /dev/loop2 2048
        # add map loop2p2 (253:3): 0 614400 linear /dev/loop2 3483648
        kpartx_output = execWithCapture("kpartx", ["-v", "-p", "p", "-a", self.disk_img])
        logger.debug(kpartx_output)

        # list of (deviceName, sizeInBytes)
        self.loop_devices = []
        for line in kpartx_output.splitlines():
            # add map loop2p3 (253:4): 0 7139328 linear /dev/loop2 528384
            # 3rd element is size in 512 byte blocks
            if line.startswith("add map "):
                fields = line[8:].split()
                self.loop_devices.append( (fields[0], int(fields[3])*512) )

    def __enter__(self):
        # Mount the device selected by mount_ok, if possible
        mount_dir = tempfile.mkdtemp()
        for dev, size in self.loop_devices:
            try:
                mount( "/dev/mapper/"+dev, mnt=mount_dir )
                if self.mount_ok(mount_dir):
                    self.mount_dir = mount_dir
                    self.mount_dev = dev
                    self.mount_size = size
                    break
                umount( mount_dir )
            except CalledProcessError:
                logger.debug(traceback.format_exc())
        if self.mount_dir:
            logger.info("Partition mounted on {0} size={1}".format(self.mount_dir, self.mount_size))
        else:
            logger.debug("Unable to mount anything from {0}".format(self.disk_img))
            os.rmdir(mount_dir)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.mount_dir:
            umount( self.mount_dir )
            os.rmdir(self.mount_dir)
            self.mount_dir = None
        execWithRedirect("kpartx", ["-d", self.disk_img])


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
        try:
            execWithRedirect("mkfs.%s" % fstype, mkfsargs + [loopdev])
        except CalledProcessError as e:
            logger.error("mkfs exited with a non-zero return code: %d" % e.returncode)
            logger.error(e.output)
            sys.exit(e.returncode)

        with Mount(loopdev, mountargs) as mnt:
            if rootdir:
                copytree(rootdir, mnt, preserve)
            do_grafts(graft, mnt, preserve)

# convenience functions with useful defaults
def mkdosimg(rootdir, outfile, size=None, label="", mountargs="shortname=winnt,umask=0077", graft={}):
    mkfsimage("msdos", rootdir, outfile, size, mountargs=mountargs,
              mkfsargs=["-n", label], graft=graft)

def mkext4img(rootdir, outfile, size=None, label="", mountargs="", graft={}):
    mkfsimage("ext4", rootdir, outfile, size, mountargs=mountargs,
              mkfsargs=["-L", label, "-b", "1024", "-m", "0"], graft=graft)

def mkbtrfsimg(rootdir, outfile, size=None, label="", mountargs="", graft={}):
    mkfsimage("btrfs", rootdir, outfile, size, mountargs=mountargs,
               mkfsargs=["-L", label], graft=graft)

def mkhfsimg(rootdir, outfile, size=None, label="", mountargs="", graft={}):
    mkfsimage("hfsplus", rootdir, outfile, size, mountargs=mountargs,
              mkfsargs=["-v", label], graft=graft)
