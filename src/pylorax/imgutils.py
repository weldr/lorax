# imgutils.py - utility functions/classes for building disk images
#
# Copyright (C) 2011-2018 Red Hat, Inc.
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
from subprocess import Popen, PIPE, CalledProcessError
import sys
import time
import traceback
import multiprocessing
from time import sleep
import shutil

from pylorax.sysutils import cpfile
from pylorax.executils import execWithRedirect, execWithCapture
from pylorax.executils import runcmd, runcmd_output

######## Functions for making container images (cpio, tar, squashfs) ##########

def compress(command, rootdir, outfile, compression="xz", compressargs=None):
    '''Make a compressed archive of the given rootdir.
    command is a list of the archiver commands to run
    compression should be "xz", "gzip", "lzma", "bzip2", or None.
    compressargs will be used on the compression commandline.'''
    if compression not in (None, "xz", "gzip", "lzma", "bzip2"):
        raise ValueError("Unknown compression type %s" % compression)
    compressargs = compressargs or ["-9"]
    if compression == "xz":
        compressargs.insert(0, "--check=crc32")
    if compression is None:
        compression = "cat" # this is a little silly
        compressargs = []

    # make compression run with multiple threads if possible
    if compression in ("xz", "lzma"):
        compressargs.insert(0, "-T%d" % multiprocessing.cpu_count())
    elif compression == "gzip":
        compression = "pigz"
        compressargs.insert(0, "-p%d" % multiprocessing.cpu_count())
    elif compression == "bzip2":
        compression = "pbzip2"
        compressargs.insert(0, "-p%d" % multiprocessing.cpu_count())

    logger.debug("find %s -print0 |%s | %s %s > %s", rootdir, " ".join(command),
                 compression, " ".join(compressargs), outfile)
    find, archive, comp = None, None, None
    try:
        find = Popen(["find", ".", "-print0"], stdout=PIPE, cwd=rootdir)
        archive = Popen(command, stdin=find.stdout, stdout=PIPE, cwd=rootdir)
        comp = Popen([compression] + compressargs,
                     stdin=archive.stdout, stdout=open(outfile, "wb"))
        comp.wait()
        return comp.returncode
    except OSError as e:
        logger.error(e)
        # Kill off any hanging processes
        list(p.kill() for p in (find, archive, comp) if p)
        return 1

def mkcpio(rootdir, outfile, compression="xz", compressargs=None):
    compressargs = compressargs or ["-9"]
    return compress(["cpio", "--null", "--quiet", "-H", "newc", "-o"],
                    rootdir, outfile, compression, compressargs)

def mktar(rootdir, outfile, compression="xz", compressargs=None, selinux=True):
    compressargs = compressargs or ["-9"]
    tar_cmd = ["tar", "--no-recursion"]
    if selinux:
        tar_cmd += ["--selinux", "--acls", "--xattrs"]
    tar_cmd += ["-cf-", "--null", "-T-"]
    return compress(tar_cmd, rootdir, outfile, compression, compressargs)

def mksquashfs(rootdir, outfile, compression="default", compressargs=None):
    '''Make a squashfs image containing the given rootdir.'''
    compressargs = compressargs or []
    if compression != "default":
        compressargs = ["-comp", compression] + compressargs
    return execWithRedirect("mksquashfs", [rootdir, outfile] + compressargs)

def mkrootfsimg(rootdir, outfile, label, size=2, sysroot=""):
    """
    Make rootfs image from a directory

    :param str rootdir: Root directory
    :param str outfile: Path of output image file
    :param str label: Filesystem label
    :param int size: Size of the image in GiB, if None computed automatically
    :param str sysroot: path to system (deployment) root relative to physical root
    """
    if size:
        fssize = size * (1024*1024*1024) # 2GB sparse file compresses down to nothin'
    else:
        fssize = None       # Let mkext4img figure out the needed size

    mkext4img(rootdir, outfile, label=label, size=fssize)


######## Utility functions ###############################################

def mksparse(outfile, size):
    '''use os.ftruncate to create a sparse file of the given size.'''
    fobj = open(outfile, "w")
    os.ftruncate(fobj.fileno(), size)

def mkqcow2(outfile, size, options=None):
    '''use qemu-img to create a file of the given size.
       options is a list of options passed to qemu-img

       Default format is qcow2, override by passing "-f", fmt
       in options.
    '''
    mkqemu_img(outfile, size, options)

def mkqemu_img(outfile, size, options=None):
    '''use qemu-img to create a file of the given size.
       options is a list of options passed to qemu-img

       Default format is qcow2, override by passing "-f", fmt
       in options.
    '''
    options = options or []
    if "-f" not in options:
        options.extend(["-f", "qcow2"])
    runcmd(["qemu-img", "create"] + options + [outfile, str(size)])

def loop_waitfor(loop_dev, outfile):
    """Make sure the loop device is attached to the outfile.

    It seems that on rare occasions losetup can return before the /dev/loopX is
    ready for use, causing problems with mkfs. This tries to make sure that the
    loop device really is associated with the backing file before continuing.

    Raise RuntimeError if it isn't setup after 5 tries.
    """
    for _x in range(0,5):
        runcmd(["udevadm", "settle", "--timeout", "300"])
        ## XXX Note that losetup --list output can be truncated to 64 bytes in some
        ##     situations. Don't use it to lookup backing file, go the other way
        ##     and lookup the loop for the backing file. See util-linux lib/loopdev.c
        ##     loopcxt_get_backing_file()
        if get_loop_name(outfile) == os.path.basename(loop_dev):
            return

        # If this really is a race, give it some time to settle down
        time.sleep(1)

    raise RuntimeError("Unable to setup %s on %s" % (loop_dev, outfile))

def loop_attach(outfile):
    """Attach a loop device to the given file. Return the loop device name.

    On rare occasions it appears that the device never shows up, some experiments
    seem to indicate that it may be a race with another process using /dev/loop* devices.

    So we now try 3 times before actually failing.

    Raises CalledProcessError if losetup fails.
    """
    retries = 0
    while True:
        try:
            retries += 1
            dev = runcmd_output(["losetup", "--find", "--show", outfile]).strip()

            # Sometimes the loop device isn't ready yet, make extra sure before returning
            loop_waitfor(dev, outfile)
        except RuntimeError:
            # Try to setup the loop device 3 times
            if retries == 3:
                logger.error("loop_attach failed, retries exhausted.")
                raise
            logger.debug("Try %d failed, %s did not appear.", retries, dev)
        break
    return dev

def loop_detach(loopdev):
    '''Detach the given loop device. Return False on failure.'''
    return (execWithRedirect("losetup", ["--detach", loopdev]) == 0)

def get_loop_name(path):
    '''Return the loop device associated with the path.
    Raises RuntimeError if more than one loop is associated'''
    buf = runcmd_output(["losetup", "-j", path])
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
    runcmd(["dmsetup", "create", name, "--table",
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
    cmd = ["mount"]
    if opts:
        cmd += ["-o", opts]
    cmd += [dev, mnt]
    runcmd(cmd)
    return mnt

def umount(mnt,  lazy=False, maxretry=3, retrysleep=1.0, delete=True):
    '''Unmount the given mountpoint. If lazy is True, do a lazy umount (-l).
    If the mount was a temporary dir created by mount, it will be deleted.
    raises CalledProcessError if umount fails.'''
    cmd = ["umount"]
    if lazy: cmd += ["-l"]
    cmd += [mnt]
    count = 0
    while maxretry > 0:
        try:
            rv = runcmd(cmd)
        except CalledProcessError:
            count += 1
            if count == maxretry:
                raise
            logger.warning("failed to unmount %s. retrying (%d/%d)...",
                           mnt, count, maxretry)
            if logger.getEffectiveLevel() <= logging.DEBUG:
                fuser = execWithCapture("fuser", ["-vm", mnt])
                logger.debug("fuser -vm:\n%s\n", fuser)
            sleep(retrysleep)
        else:
            break
    if delete and 'lorax.imgutils' in mnt:
        os.rmdir(mnt)
        logger.debug("remove tmp mountdir %s", mnt)
    return (rv == 0)

def copytree(src, dest, preserve=True):
    '''Copy a tree of files using cp -a, thus preserving modes, timestamps,
    links, acls, sparse files, xattrs, selinux contexts, etc.
    If preserve is False, uses cp -R (useful for modeless filesystems)
    raises CalledProcessError if copy fails.'''
    logger.debug("copytree %s %s", src, dest)
    cp = ["cp", "-a"] if preserve else ["cp", "-R", "-L", "--preserve=timestamps"]
    cp += [join(src, "."), os.path.abspath(dest)]
    runcmd(cp)

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
def estimate_size(rootdir, graft=None, fstype=None, blocksize=4096, overhead=256):
    graft = graft or {}
    getsize = lambda f: os.lstat(f).st_size
    if fstype == "btrfs":
        overhead = 64*1024 # don't worry, it's all sparse
    if fstype == "hfsplus":
        overhead = 200 # hack to deal with two bootloader copies
    if fstype in ("vfat", "msdos"):
        blocksize = 2048
        getsize = lambda f: os.stat(f).st_size # no symlinks, count as copies
    total = overhead*blocksize
    dirlist = list(graft.values())
    if rootdir:
        dirlist.append(rootdir)
    for root in dirlist:
        for top, dirs, files in os.walk(root):
            for f in files + dirs:
                total += round_to_blocks(getsize(join(top,f)), blocksize)
    if fstype == "btrfs":
        total = max(256*1024*1024, total) # btrfs minimum size: 256MB
    logger.info("Size of %s block %s fs at %s estimated to be %s", blocksize, fstype, rootdir, total)
    return total

######## Execution contexts - use with the 'with' statement ##############

class LoopDev(object):
    def __init__(self, filename, size=None):
        self.loopdev = None
        self.filename = filename
        if size:
            mksparse(self.filename, size)
    def __enter__(self):
        self.loopdev = loop_attach(self.filename)
        return self.loopdev
    def __exit__(self, exc_type, exc_value, tracebk):
        loop_detach(self.loopdev)

class DMDev(object):
    def __init__(self, dev, size, name=None):
        self.mapperdev = None
        (self.dev, self.size, self.name) = (dev, size, name)
    def __enter__(self):
        self.mapperdev = dm_attach(self.dev, self.size, self.name)
        return self.mapperdev
    def __exit__(self, exc_type, exc_value, tracebk):
        dm_detach(self.mapperdev)

class Mount(object):
    def __init__(self, dev, opts="", mnt=None):
        (self.dev, self.opts, self.mnt) = (dev, opts, mnt)
    def __enter__(self):
        self.mnt = mount(self.dev, self.opts, self.mnt)
        return self.mnt
    def __exit__(self, exc_type, exc_value, tracebk):
        umount(self.mnt)

def kpartx_disk_img(disk_img):
    """Attach a disk image's partitions to /dev/loopX using kpartx

    :param disk_img: The full path to a partitioned disk image
    :type disk_img: str
    :returns: list of (loopXpN, size)
    :rtype: list of tuples
    """
    # Example kpartx output
    # kpartx -p p -v -a /tmp/diskV2DiCW.im
    # add map loop2p1 (253:2): 0 3481600 linear /dev/loop2 2048
    # add map loop2p2 (253:3): 0 614400 linear /dev/loop2 3483648
    kpartx_output = runcmd_output(["kpartx", "-v", "-a", "-s", disk_img])
    logger.debug(kpartx_output)

    # list of (deviceName, sizeInBytes)
    loop_devices = []
    for line in kpartx_output.splitlines():
        # add map loop2p3 (253:4): 0 7139328 linear /dev/loop2 528384
        # 3rd element is size in 512 byte blocks
        if line.startswith("add map "):
            fields = line[8:].split()
            loop_devices.append( (fields[0], int(fields[3])*512) )
    return loop_devices

class PartitionMount(object):
    """ Mount a partitioned image file using kpartx """
    def __init__(self, disk_img, mount_ok=None, submount=None):
        """
        :param str disk_img: The full path to a partitioned disk image
        :param mount_ok: A function that is passed the mount point and
                         returns True if it should be mounted.
        :param str submount: Directory inside mount_dir to mount at

        If mount_ok is not set it will look for /etc/passwd

        If the partition is found it will be mounted under a temporary
        directory and self.temp_dir set to it. If submount is passed it will be
        created and mounted there instead, with self.mount_dir set to point to
        it. self.mount_dev is set to the loop device, and self.mount_size is
        set to the size of the partition.

        When no subdir is passed self.temp_dir and self.mount_dir will be the same.
        """
        self.mount_dev = None
        self.mount_size = None
        self.mount_dir = None
        self.disk_img = disk_img
        self.mount_ok = mount_ok
        self.submount = submount
        self.temp_dir = None

        # Default is to mount partition with /etc/passwd
        if not self.mount_ok:
            self.mount_ok = lambda mount_dir: os.path.isfile(mount_dir+"/etc/passwd")

        # list of (deviceName, sizeInBytes)
        self.loop_devices = kpartx_disk_img(self.disk_img)

    def __enter__(self):
        # Mount the device selected by mount_ok, if possible
        self.temp_dir = tempfile.mkdtemp()
        if self.submount:
            mount_dir = os.path.normpath(os.path.sep.join([self.temp_dir, self.submount]))
            os.makedirs(mount_dir, mode=0o755, exist_ok=True)
        else:
            mount_dir = self.temp_dir
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
            logger.info("Partition mounted on %s size=%s", self.mount_dir, self.mount_size)
        else:
            logger.debug("Unable to mount anything from %s", self.disk_img)
            os.rmdir(self.temp_dir)
            self.temp_dir = None
        return self

    def __exit__(self, exc_type, exc_value, tracebk):
        if self.temp_dir:
            umount(self.mount_dir)
            shutil.rmtree(self.temp_dir)
            self.mount_dir = None
            self.temp_dir = None
        execWithRedirect("kpartx", ["-d", "-s", self.disk_img])


######## Functions for making filesystem images ##########################

def mkfsimage(fstype, rootdir, outfile, size=None, mkfsargs=None, mountargs="", graft=None):
    '''Generic filesystem image creation function.
    fstype should be a filesystem type - "mkfs.${fstype}" must exist.
    graft should be a dict: {"some/path/in/image": "local/file/or/dir"};
    if the path ends with a '/' it's assumed to be a directory.
    Will raise CalledProcessError if something goes wrong.'''
    mkfsargs = mkfsargs or []
    graft = graft or {}
    preserve = (fstype not in ("msdos", "vfat"))
    if not size:
        size = estimate_size(rootdir, graft, fstype)
    with LoopDev(outfile, size) as loopdev:
        try:
            runcmd(["mkfs.%s" % fstype] + mkfsargs + [loopdev])
        except CalledProcessError as e:
            logger.error("mkfs exited with a non-zero return code: %d", e.returncode)
            logger.error(e.output)
            sys.exit(e.returncode)

        with Mount(loopdev, mountargs) as mnt:
            if rootdir:
                copytree(rootdir, mnt, preserve)
            do_grafts(graft, mnt, preserve)

            # Save information about filesystem usage
            execWithRedirect("df", [mnt])

    # Make absolutely sure that the data has been written
    runcmd(["sync"])

# convenience functions with useful defaults
def mkdosimg(rootdir, outfile, size=None, label="", mountargs="shortname=winnt,umask=0077", graft=None):
    graft = graft or {}
    mkfsargs = ["-n", label]
    if 'SOURCE_DATE_EPOCH' in os.environ:
        mkfsargs.extend(["-i",
                "{:x}".format(int(os.environ['SOURCE_DATE_EPOCH']))])
    mkfsimage("msdos", rootdir, outfile, size, mountargs=mountargs,
              mkfsargs=mkfsargs, graft=graft)

def mkext4img(rootdir, outfile, size=None, label="", mountargs="", graft=None):
    graft = graft or {}
    mkfsimage("ext4", rootdir, outfile, size, mountargs=mountargs,
              mkfsargs=["-L", label, "-b", "4096", "-m", "0"], graft=graft)

def mkbtrfsimg(rootdir, outfile, size=None, label="", mountargs="", graft=None):
    graft = graft or {}
    mkfsimage("btrfs", rootdir, outfile, size, mountargs=mountargs,
               mkfsargs=["-L", label], graft=graft)

def mkhfsimg(rootdir, outfile, size=None, label="", mountargs="", graft=None):
    graft = graft or {}
    mkfsimage("hfsplus", rootdir, outfile, size, mountargs=mountargs,
              mkfsargs=["-v", label], graft=graft)

def mkfsimage_from_disk(diskimage, fsimage, img_size=None, label="Anaconda"):
    """
    Copy the / partition of a partitioned disk image to an un-partitioned
    disk image.

    :param str diskimage: The full path to partitioned disk image with a /
    :param str fsimage: The full path of the output fs image file
    :param int img_size: Optional size of the fsimage in MiB or None to make
       it as small as possible
    :param str label: The label to apply to the image. Defaults to "Anaconda"
    """
    with PartitionMount(diskimage) as img_mount:
        if not img_mount or not img_mount.mount_dir:
            return None

        logger.info("Creating fsimage %s (%s)", fsimage, img_size or "minimized")
        if img_size:
            # convert to Bytes
            img_size *= 1024**2

        mkext4img(img_mount.mount_dir, fsimage, size=img_size, label=label)

def default_image_name(compression, basename):
    """ Return a default image name with the correct suffix for the compression type.

    :param str compression: Compression type
    :param str basename: Base filename
    :returns: basename with compression suffix

    If the compression is unknown it defaults to xz
    """
    SUFFIXES = {"xz": ".xz", "gzip": ".gz", "bzip2": ".bz2", "lzma": ".lzma"}
    return basename + SUFFIXES.get(compression, ".xz")
