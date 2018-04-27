#
# Copyright (C) 2011-2018  Red Hat, Inc.
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
import logging
log = logging.getLogger("pylorax")


import os
import tempfile
import subprocess
import shutil
import hashlib
import glob
import json
from math import ceil

# Use Mako templates for appliance builder descriptions
from mako.template import Template
from mako.exceptions import text_error_template

# Use the Lorax treebuilder branch for iso creation
from pylorax import ArchData
from pylorax.base import DataHolder
from pylorax.executils import execWithRedirect, runcmd
from pylorax.imgutils import PartitionMount, mkext4img
from pylorax.imgutils import mount, umount, Mount
from pylorax.imgutils import mksquashfs, mkrootfsimg
from pylorax.imgutils import copytree
from pylorax.installer import novirt_install, virt_install, InstallError
from pylorax.treebuilder import TreeBuilder, RuntimeBuilder
from pylorax.treebuilder import findkernels
from pylorax.sysutils import joinpaths, remove


# Default parameters for rebuilding initramfs, override with --dracut-args
DRACUT_DEFAULT = ["--xz", "--add", "livenet dmsquash-live convertfs pollcdrom qemu qemu-net",
                  "--omit", "plymouth", "--no-hostonly", "--debug", "--no-early-microcode"]

RUNTIME = "images/install.img"

class FakeDNF(object):
    """
    A minimal DNF object suitable for passing to RuntimeBuilder

    lmc uses RuntimeBuilder to run the arch specific iso creation
    templates, so the the installroot config value is the important part of
    this. Everything else should be a nop.
    """
    def __init__(self, conf):
        self.conf = conf

    def reset(self):
        pass

def is_image_mounted(disk_img):
    """
    Check to see if the disk_img is mounted

    :returns: True if disk_img is in /proc/mounts
    :rtype: bool
    """
    with open("/proc/mounts") as mounts:
        for mnt in mounts:
            fields = mnt.split()
            if len(fields) > 2 and fields[1] == disk_img:
                return True
    return False

def find_ostree_root(phys_root):
    """
    Find root of ostree deployment

    :param str phys_root: Path to physical root
    :returns: Relative path of ostree deployment root
    :rtype: str
    :raise Exception: More than one deployment roots were found
    """
    ostree_root = ""
    ostree_sysroots = glob.glob(joinpaths(phys_root, "ostree/boot.?/*/*/0"))
    log.debug("ostree_sysroots = %s", ostree_sysroots)
    if ostree_sysroots:
        if len(ostree_sysroots) > 1:
            raise Exception("Too many deployment roots found: %s" % ostree_sysroots)
        ostree_root = os.path.relpath(ostree_sysroots[0], phys_root)
    return ostree_root

def get_arch(mount_dir):
    """
    Get the kernel arch

    :returns: Arch of first kernel found at mount_dir/boot/ or i386
    :rtype: str
    """
    kernels = findkernels(mount_dir)
    if not kernels:
        return "i386"
    return kernels[0].arch

def squashfs_args(opts):
    """ Returns the compression type and args to use when making squashfs

    :param opts: ArgumentParser object with compression and compressopts
    :returns: tuple of compression type and args
    :rtype: tuple
    """
    compression = opts.compression or "xz"
    arch = ArchData(opts.arch or os.uname().machine)
    if compression == "xz" and arch.bcj:
        compressargs = ["-Xbcj", arch.bcj]
    else:
        compressargs = []
    return (compression, compressargs)


def make_appliance(disk_img, name, template, outfile, networks=None, ram=1024,
                   vcpus=1, arch=None, title="Linux", project="Linux",
                   releasever="29"):
    """
    Generate an appliance description file

    :param str disk_img: Full path of the disk image
    :param str name: Name of the appliance, passed to the template
    :param str template: Full path of Mako template
    :param str outfile: Full path of file to write, using template
    :param list networks: List of networks(str) from the kickstart
    :param int ram: Ram, in MiB, passed to template. Default is 1024
    :param int vcpus: CPUs, passed to template. Default is 1
    :param str arch: CPU architecture. Default is 'x86_64'
    :param str title: Title, passed to template. Default is 'Linux'
    :param str project: Project, passed to template. Default is 'Linux'
    :param str releasever: Release version, passed to template. Default is 29
    """
    if not (disk_img and template and outfile):
        return None

    log.info("Creating appliance definition using %s", template)

    if not arch:
        arch = "x86_64"

    log.info("Calculating SHA256 checksum of %s", disk_img)
    sha256 = hashlib.sha256()
    with open(disk_img) as f:
        while True:
            data = f.read(1024**2)
            if not data:
                break
            sha256.update(data)
    log.info("SHA256 of %s is %s", disk_img, sha256.hexdigest())
    disk_info = DataHolder(name=os.path.basename(disk_img), format="raw",
                           checksum_type="sha256", checksum=sha256.hexdigest())
    try:
        result = Template(filename=template).render(disks=[disk_info], name=name,
                          arch=arch, memory=ram, vcpus=vcpus, networks=networks,
                          title=title, project=project, releasever=releasever)
    except Exception:
        log.error(text_error_template().render())
        raise

    with open(outfile, "w") as f:
        f.write(result)


def make_fsimage(diskimage, fsimage, img_size=None, label="Anaconda"):
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

        log.info("Creating fsimage %s (%s)", fsimage, img_size or "minimized")
        if img_size:
            # convert to Bytes
            img_size *= 1024**2

        mkext4img(img_mount.mount_dir, fsimage, size=img_size, label=label)


def make_runtime(opts, mount_dir, work_dir, size=None):
    """
    Make the squashfs image from a directory

    :param opts: options passed to livemedia-creator
    :type opts: argparse options
    :param str mount_dir: Directory tree to compress
    :param str work_dir: Output compressed image to work_dir+images/install.img
    :param int size: Size of disk image, in GiB
    """
    kernel_arch = get_arch(mount_dir)

    # Fake dnf  object
    fake_dbo = FakeDNF(conf=DataHolder(installroot=mount_dir))
    # Fake arch with only basearch set
    arch = ArchData(kernel_arch)
    # TODO: Need to get release info from someplace...
    product = DataHolder(name=opts.project, version=opts.releasever, release="",
                            variant="", bugurl="", isfinal=False)

    # This is a mounted image partition, cannot hardlink to it, so just use it
    # symlink mount_dir/images to work_dir/images so we don't run out of space
    os.makedirs(joinpaths(work_dir, "images"))

    rb = RuntimeBuilder(product, arch, fake_dbo)
    compression, compressargs = squashfs_args(opts)
    log.info("Creating runtime")
    rb.create_runtime(joinpaths(work_dir, RUNTIME), size=size,
                      compression=compression, compressargs=compressargs)


def rebuild_initrds_for_live(opts, sys_root_dir, results_dir):
    """
    Rebuild intrds for pxe live image (root=live:http://)

    :param opts: options passed to livemedia-creator
    :type opts: argparse options
    :param str sys_root_dir: Path to root of the system
    :param str results_dir: Path of directory for storing results
    """
    if not opts.dracut_args:
        dracut_args = DRACUT_DEFAULT
    else:
        dracut_args = []
        for arg in opts.dracut_args:
            dracut_args += arg.split(" ", 1)
    log.info("dracut args = %s", dracut_args)

    dracut = ["dracut", "--nomdadmconf", "--nolvmconf"] + dracut_args

    kdir = "boot"
    if opts.ostree:
        kernels_dir = glob.glob(joinpaths(sys_root_dir, "boot/ostree/*"))
        if kernels_dir:
            kdir = os.path.relpath(kernels_dir[0], sys_root_dir)

    kernels = [kernel for kernel in findkernels(sys_root_dir, kdir)]
    if not kernels:
        raise Exception("No initrds found, cannot rebuild_initrds")

    # Hush some dracut warnings. TODO: bind-mount proc in place?
    open(joinpaths(sys_root_dir,"/proc/modules"),"w")

    if opts.ostree:
        # Dracut assumes to have some dirs in disk image
        # /var/tmp for temp files
        vartmp_dir = joinpaths(sys_root_dir, "var/tmp")
        if not os.path.isdir(vartmp_dir):
            os.mkdir(vartmp_dir)
        # /root (maybe not fatal)
        root_dir = joinpaths(sys_root_dir, "var/roothome")
        if not os.path.isdir(root_dir):
            os.mkdir(root_dir)
        # /tmp (maybe not fatal)
        tmp_dir = joinpaths(sys_root_dir, "sysroot/tmp")
        if not os.path.isdir(tmp_dir):
            os.mkdir(tmp_dir)

    # Write the new initramfs directly to the results directory
    os.mkdir(joinpaths(sys_root_dir, "results"))
    mount(results_dir, opts="bind", mnt=joinpaths(sys_root_dir, "results"))
    # Dracut runs out of space inside the minimal rootfs image
    mount("/var/tmp", opts="bind", mnt=joinpaths(sys_root_dir, "var/tmp"))
    for kernel in kernels:
        if hasattr(kernel, "initrd"):
            outfile = os.path.basename(kernel.initrd.path)
        else:
            # Construct an initrd from the kernel name
            outfile = os.path.basename(kernel.path.replace("vmlinuz-", "initrd-") + ".img")
        log.info("rebuilding %s", outfile)

        kver = kernel.version

        cmd = dracut + ["/results/"+outfile, kver]
        runcmd(cmd, root=sys_root_dir)

        shutil.copy2(joinpaths(sys_root_dir, kernel.path), results_dir)
    umount(joinpaths(sys_root_dir, "var/tmp"), delete=False)
    umount(joinpaths(sys_root_dir, "results"), delete=False)
    os.unlink(joinpaths(sys_root_dir,"/proc/modules"))

def create_pxe_config(template, images_dir, live_image_name, add_args = None):
    """
    Create template for pxe to live configuration

    :param str images_dir: Path of directory with images to be used
    :param str live_image_name: Name of live rootfs image file
    :param list add_args: Arguments to be added to initrd= pxe config
    """

    add_args = add_args or []

    kernels = [kernel for kernel in findkernels(images_dir, kdir="")
               if hasattr(kernel, "initrd")]
    if not kernels:
        return

    kernel = kernels[0]

    add_args_str = " ".join(add_args)


    try:
        result = Template(filename=template).render(kernel=kernel.path,
                          initrd=kernel.initrd.path, liveimg=live_image_name,
                          addargs=add_args_str)
    except Exception:
        log.error(text_error_template().render())
        raise

    with open (joinpaths(images_dir, "PXE_CONFIG"), "w") as f:
        f.write(result)


def create_vagrant_metadata(path, size=0):
    """ Create a default Vagrant metadata.json file

    :param str path: Path to metadata.json file
    :param int size: Disk size in MiB
    """
    metadata = { "provider":"libvirt", "format":"qcow2", "virtual_size": ceil(size / 1024) }
    with open(path, "wt") as f:
        json.dump(metadata, f, indent=4)


def update_vagrant_metadata(path, size):
    """ Update the Vagrant metadata.json file

    :param str path: Path to metadata.json file
    :param int size: Disk size in MiB

    This function makes sure that the provider, format and virtual size of the
    metadata file are set correctly. All other values are left untouched.
    """
    with open(path, "rt") as f:
        try:
            metadata = json.load(f)
        except ValueError as e:
            log.error("Problem reading metadata file %s: %s", path, e)
            return

    metadata["provider"] = "libvirt"
    metadata["format"] = "qcow2"
    metadata["virtual_size"] = ceil(size / 1024)
    with open(path, "wt") as f:
        json.dump(metadata, f, indent=4)


def make_livecd(opts, mount_dir, work_dir):
    """
    Take the content from the disk image and make a livecd out of it

    :param opts: options passed to livemedia-creator
    :type opts: argparse options
    :param str mount_dir: Directory tree to compress
    :param str work_dir: Output compressed image to work_dir+images/install.img

    This uses wwood's squashfs live initramfs method:
     * put the real / into LiveOS/rootfs.img
     * make a squashfs of the LiveOS/rootfs.img tree
     * This is loaded by dracut when the cmdline is passed to the kernel:
       root=live:CDLABEL=<volid> rd.live.image
    """
    kernel_arch = get_arch(mount_dir)

    arch = ArchData(kernel_arch)
    # TODO: Need to get release info from someplace...
    product = DataHolder(name=opts.project, version=opts.releasever, release="",
                            variant="", bugurl="", isfinal=False)

    # Link /images to work_dir/images to make the templates happy
    if os.path.islink(joinpaths(mount_dir, "images")):
        os.unlink(joinpaths(mount_dir, "images"))
    execWithRedirect("/bin/ln", ["-s", joinpaths(work_dir, "images"),
                                 joinpaths(mount_dir, "images")])

    # The templates expect the config files to be in /tmp/config_files
    # I think these should be release specific, not from lorax, but for now
    configdir = joinpaths(opts.lorax_templates,"live/config_files/")
    configdir_path = "tmp/config_files"
    fullpath = joinpaths(mount_dir, configdir_path)
    if os.path.exists(fullpath):
        remove(fullpath)
    copytree(configdir, fullpath)

    isolabel = opts.volid or "{0.name}-{0.version}-{1.basearch}".format(product, arch)
    if len(isolabel) > 32:
        isolabel = isolabel[:32]
        log.warning("Truncating isolabel to 32 chars: %s", isolabel)

    tb = TreeBuilder(product=product, arch=arch, domacboot=opts.domacboot,
                     inroot=mount_dir, outroot=work_dir,
                     runtime=RUNTIME, isolabel=isolabel,
                     templatedir=joinpaths(opts.lorax_templates,"live/"))
    log.info("Rebuilding initrds")
    if not opts.dracut_args:
        dracut_args = DRACUT_DEFAULT
    else:
        dracut_args = []
        for arg in opts.dracut_args:
            dracut_args += arg.split(" ", 1)
    log.info("dracut args = %s", dracut_args)
    tb.rebuild_initrds(add_args=dracut_args)
    log.info("Building boot.iso")
    tb.build()

    return work_dir

def mount_boot_part_over_root(img_mount):
    """
    Mount boot partition to /boot of root fs mounted in img_mount

    Used for OSTree so it finds deployment configurations on live rootfs

    param img_mount: object with mounted disk image root partition
    type img_mount: imgutils.PartitionMount
    """
    root_dir = img_mount.mount_dir
    is_boot_part = lambda dir: os.path.exists(dir+"/loader.0")
    tmp_mount_dir = tempfile.mkdtemp(prefix="lmc-tmpdir-")
    sysroot_boot_dir = None
    for dev, _size in img_mount.loop_devices:
        if dev is img_mount.mount_dev:
            continue
        try:
            mount("/dev/mapper/"+dev, mnt=tmp_mount_dir)
            if is_boot_part(tmp_mount_dir):
                umount(tmp_mount_dir)
                sysroot_boot_dir = joinpaths(root_dir, "boot")
                mount("/dev/mapper/"+dev, mnt=sysroot_boot_dir)
                break
            else:
                umount(tmp_mount_dir)
        except subprocess.CalledProcessError as e:
            log.debug("Looking for boot partition error: %s", e)
    remove(tmp_mount_dir)
    return sysroot_boot_dir

def make_squashfs(opts, disk_img, work_dir):
    """
    Create a squashfs image of an unpartitioned filesystem disk image

    :param str disk_img: Path to the unpartitioned filesystem disk image
    :param str work_dir: Output compressed image to work_dir+images/install.img
    :param str compression: Compression type to use
    :returns: True if squashfs creation was successful. False if there was an error.
    :rtype: bool

    Take disk_img and put it into LiveOS/rootfs.img and squashfs this
    tree into work_dir+images/install.img

    fsck.ext4 is run on the disk image to make sure there are no errors and to zero
    out any deleted blocks to make it compress better. If this fails for any reason
    it will return False and log the error.
    """
    # Make sure free blocks are actually zeroed so it will compress
    rc = execWithRedirect("/usr/sbin/fsck.ext4", ["-y", "-f", "-E", "discard", disk_img])
    if rc != 0:
        log.error("Problem zeroing free blocks of %s", disk_img)
        return False

    liveos_dir = joinpaths(work_dir, "runtime/LiveOS")
    os.makedirs(liveos_dir)
    os.makedirs(os.path.dirname(joinpaths(work_dir, RUNTIME)))

    rc = execWithRedirect("/bin/ln", [disk_img, joinpaths(liveos_dir, "rootfs.img")])
    if rc != 0:
        shutil.copy2(disk_img, joinpaths(liveos_dir, "rootfs.img"))

    compression, compressargs = squashfs_args(opts)
    mksquashfs(joinpaths(work_dir, "runtime"),
               joinpaths(work_dir, RUNTIME), compression, compressargs)
    remove(joinpaths(work_dir, "runtime"))
    return True

def calculate_disk_size(opts, ks):
    """ Calculate the disk size from the kickstart

    :param opts: options passed to livemedia-creator
    :type opts: argparse options
    :param str ks: Path to the kickstart to use for the installation
    :returns: Disk size in MiB
    :rtype: int
    """
    # Disk size for a filesystem image should only be the size of /
    # to prevent surprises when using the same kickstart for different installations.
    unique_partitions = dict((p.mountpoint, p) for p in ks.handler.partition.partitions)
    if opts.no_virt and (opts.make_iso or opts.make_fsimage):
        disk_size = 2 + sum(p.size for p in unique_partitions.values() if p.mountpoint == "/")
    else:
        disk_size = 2 + sum(p.size for p in unique_partitions.values())
    log.info("Using disk size of %sMiB", disk_size)
    return disk_size

def make_image(opts, ks):
    """
    Install to a disk image

    :param opts: options passed to livemedia-creator
    :type opts: argparse options
    :param str ks: Path to the kickstart to use for the installation
    :returns: Path of the image created
    :rtype: str

    Use qemu+boot.iso or anaconda to install to a disk image.
    """
    if opts.image_name:
        disk_img = joinpaths(opts.result_dir, opts.image_name)
    else:
        disk_img = tempfile.mktemp(prefix="lmc-disk-", suffix=".img", dir=opts.result_dir)
    log.info("disk_img = %s", disk_img)
    disk_size = calculate_disk_size(opts, ks)
    try:
        if opts.no_virt:
            novirt_install(opts, disk_img, disk_size)
        else:
            install_log = os.path.abspath(os.path.dirname(opts.logfile))+"/virt-install.log"
            log.info("install_log = %s", install_log)

            virt_install(opts, install_log, disk_img, disk_size)
    except InstallError as e:
        log.error("Install failed: %s", e)
        if not opts.keep_image and os.path.exists(disk_img):
            log.info("Removing bad disk image")
            os.unlink(disk_img)
        raise

    log.info("Disk Image install successful")
    return disk_img


def make_live_images(opts, work_dir, disk_img):
    """
    Create live images from direcory or rootfs image

    :param opts: options passed to livemedia-creator
    :type opts: argparse options
    :param str work_dir: Directory for storing results
    :param str disk_img: Path to disk image (fsimage or partitioned)
    :returns: Path of directory with created images or None
    :rtype: str

    fsck.ext4 is run on the rootfs_image to make sure there are no errors and to zero
    out any deleted blocks to make it compress better. If this fails for any reason
    it will return None and log the error.
    """
    sys_root = ""

    squashfs_root_dir = joinpaths(work_dir, "squashfs_root")
    liveos_dir = joinpaths(squashfs_root_dir, "LiveOS")
    os.makedirs(liveos_dir)
    rootfs_img = joinpaths(liveos_dir, "rootfs.img")

    if opts.fs_image or opts.no_virt:
        # Find the ostree root in the fsimage
        if opts.ostree:
            with Mount(disk_img, opts="loop") as mnt_dir:
                sys_root = find_ostree_root(mnt_dir)

        # Try to hardlink the image, if that fails, copy it
        rc = execWithRedirect("/bin/ln", [disk_img, rootfs_img])
        if rc != 0:
            shutil.copy2(disk_img, rootfs_img)
    else:
        is_root_part = None
        if opts.ostree:
            is_root_part = lambda dir: os.path.exists(dir+"/ostree/deploy")
        with PartitionMount(disk_img, mount_ok=is_root_part) as img_mount:
            if img_mount and img_mount.mount_dir:
                try:
                    mounted_sysroot_boot_dir = None
                    if opts.ostree:
                        sys_root = find_ostree_root(img_mount.mount_dir)
                        mounted_sysroot_boot_dir = mount_boot_part_over_root(img_mount)
                    if opts.live_rootfs_keep_size:
                        size = img_mount.mount_size / 1024**3
                    else:
                        size = opts.live_rootfs_size or None
                    log.info("Creating live rootfs image")
                    mkrootfsimg(img_mount.mount_dir, rootfs_img, "LiveOS", size=size, sysroot=sys_root)
                finally:
                    if mounted_sysroot_boot_dir:
                        umount(mounted_sysroot_boot_dir)
    log.debug("sys_root = %s", sys_root)

    # Make sure free blocks are actually zeroed so it will compress
    rc = execWithRedirect("/usr/sbin/fsck.ext4", ["-y", "-f", "-E", "discard", rootfs_img])
    if rc != 0:
        log.error("Problem zeroing free blocks of %s", disk_img)
        return None

    log.info("Packing live rootfs image")
    add_pxe_args = []
    live_image_name = "live-rootfs.squashfs.img"
    compression, compressargs = squashfs_args(opts)
    mksquashfs(squashfs_root_dir, joinpaths(work_dir, live_image_name), compression, compressargs)

    log.info("Rebuilding initramfs for live")
    with Mount(rootfs_img, opts="loop") as mnt_dir:
        try:
            mount(joinpaths(mnt_dir, "boot"), opts="bind", mnt=joinpaths(mnt_dir, sys_root, "boot"))
            rebuild_initrds_for_live(opts, joinpaths(mnt_dir, sys_root), work_dir)
        finally:
            umount(joinpaths(mnt_dir, sys_root, "boot"), delete=False)

    remove(squashfs_root_dir)

    if opts.ostree:
        add_pxe_args.append("ostree=/%s" % sys_root)
    template = joinpaths(opts.lorax_templates, "pxe-live/pxe-config.tmpl")
    create_pxe_config(template, work_dir, live_image_name, add_pxe_args)

    return work_dir


