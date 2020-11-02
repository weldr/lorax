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

# Use Mako templates for appliance builder descriptions
from mako.template import Template
from mako.exceptions import text_error_template

# Use pykickstart to calculate disk image size
from pykickstart.parser import KickstartParser
from pykickstart.constants import KS_SHUTDOWN
from pykickstart.version import makeVersion

# Use the Lorax treebuilder branch for iso creation
from pylorax import ArchData
from pylorax.base import DataHolder
from pylorax.executils import execWithRedirect, runcmd
from pylorax.imgutils import PartitionMount
from pylorax.imgutils import mount, umount, Mount
from pylorax.imgutils import mksquashfs, mkrootfsimg
from pylorax.imgutils import copytree
from pylorax.installer import novirt_install, virt_install, InstallError
from pylorax.treebuilder import TreeBuilder, RuntimeBuilder
from pylorax.treebuilder import findkernels
from pylorax.sysutils import joinpaths, remove


# Default parameters for rebuilding initramfs, override with --dracut-arg or --dracut-conf
DRACUT_DEFAULT = ["--xz", "--add", "livenet dmsquash-live dmsquash-live-ntfs convertfs pollcdrom qemu qemu-net",
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
    if compression == "xz" and arch.bcj and not opts.compress_args:
        # default to bcj when using xz
        compressargs = ["-Xbcj", arch.bcj]
    elif opts.compress_args:
        compressargs = []
        for arg in opts.compress_args:
            compressargs += arg.split(" ", 1)
    else:
        compressargs = []
    return (compression, compressargs)

def dracut_args(opts):
    """Return a list of the args to pass to dracut

    Return the default argument list unless one of the dracut cmdline arguments
    has been used.
    """
    if opts.dracut_conf:
        return ["--conf", opts.dracut_conf]
    elif opts.dracut_args:
        args = []
        for arg in opts.dracut_args:
            args += arg.split(" ", 1)
        return args
    else:
        return DRACUT_DEFAULT

def make_appliance(disk_img, name, template, outfile, networks=None, ram=1024,
                   vcpus=1, arch=None, title="Linux", project="Linux",
                   releasever="34"):
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
    :param str releasever: Release version, passed to template. Default is 34
    """
    if not (disk_img and template and outfile):
        return None

    log.info("Creating appliance definition using %s", template)

    if not arch:
        arch = "x86_64"

    log.info("Calculating SHA256 checksum of %s", disk_img)
    sha256 = hashlib.sha256()
    with open(disk_img, "rb") as f:
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


def make_runtime(opts, mount_dir, work_dir, size=None):
    """
    Make the squashfs image from a directory

    :param opts: options passed to livemedia-creator
    :type opts: argparse options
    :param str mount_dir: Directory tree to compress
    :param str work_dir: Output compressed image to work_dir+images/install.img
    :param int size: Size of disk image, in GiB
    :returns: rc of squashfs creation
    :rtype: int
    """
    kernel_arch = get_arch(mount_dir)

    # Fake dnf  object
    fake_dbo = FakeDNF(conf=DataHolder(installroot=mount_dir))
    # Fake arch with only basearch set
    arch = ArchData(kernel_arch)
    # TODO: Need to get release info from someplace...
    product = DataHolder(name=opts.project, version=opts.releasever, release="",
                            variant="", bugurl="", isfinal=False)

    rb = RuntimeBuilder(product, arch, fake_dbo)
    compression, compressargs = squashfs_args(opts)

    if opts.squashfs_only:
        log.info("Creating a squashfs only runtime")
        return rb.create_squashfs_runtime(joinpaths(work_dir, RUNTIME), size=size,
                  compression=compression, compressargs=compressargs)
    else:
        log.info("Creating a squashfs+ext4 runtime")
        return rb.create_ext4_runtime(joinpaths(work_dir, RUNTIME), size=size,
                  compression=compression, compressargs=compressargs)


def rebuild_initrds_for_live(opts, sys_root_dir, results_dir):
    """
    Rebuild intrds for pxe live image (root=live:http://)

    :param opts: options passed to livemedia-creator
    :type opts: argparse options
    :param str sys_root_dir: Path to root of the system
    :param str results_dir: Path of directory for storing results
    """
    # cmdline dracut args override the defaults, but need to be parsed
    log.info("dracut args = %s", dracut_args(opts))

    dracut = ["dracut", "--nomdadmconf", "--nolvmconf"] + dracut_args(opts)

    kdir = "boot"
    if opts.ostree:
        kernels_dir = glob.glob(joinpaths(sys_root_dir, "boot/ostree/*"))
        if kernels_dir:
            kdir = os.path.relpath(kernels_dir[0], sys_root_dir)

    kernels = [kernel for kernel in findkernels(sys_root_dir, kdir)]
    if not kernels:
        raise Exception("No initrds found, cannot rebuild_initrds")

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
        log.info("dracut warnings about /proc are safe to ignore")

        kver = kernel.version
        cmd = dracut + ["/results/"+outfile, kver]
        runcmd(cmd, root=sys_root_dir)

        shutil.copy2(joinpaths(sys_root_dir, kernel.path), results_dir)
    umount(joinpaths(sys_root_dir, "var/tmp"), delete=False)
    umount(joinpaths(sys_root_dir, "results"), delete=False)

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
    rc = execWithRedirect("/bin/ln", ["-s", joinpaths(work_dir, "images"),
                                     joinpaths(mount_dir, "images")])
    if rc:
        raise RuntimeError("Failed to symlink images from mount_dir to work_dir")

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
                     templatedir=joinpaths(opts.lorax_templates,"live/"),
                     extra_boot_args=opts.extra_boot_args)
    log.info("Rebuilding initrds")
    log.info("dracut args = %s", dracut_args(opts))
    tb.rebuild_initrds(add_args=dracut_args(opts))
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

def calculate_disk_size(opts, ks):
    """ Calculate the disk size from the kickstart

    :param opts: options passed to livemedia-creator
    :type opts: argparse options
    :param str ks: Path to the kickstart to use for the installation
    :returns: Disk size in MiB
    :rtype: int

    Also takes into account the use of reqpart or reqpart --add-boot
    """
    # Disk size for a filesystem image should only be the size of /
    # to prevent surprises when using the same kickstart for different installations.
    unique_partitions = dict((p.mountpoint, p) for p in ks.handler.partition.partitions)
    if opts.no_virt and (opts.make_iso or opts.make_fsimage):
        disk_size = 2 + sum(p.size for p in unique_partitions.values() if p.mountpoint == "/")
    else:
        disk_size = 2 + sum(p.size for p in unique_partitions.values())

        # reqpart can add 1M, 2M, 200M based on platform. Add 500M to be sure
        if ks.handler.reqpart.seen:
            log.info("Adding 500M for reqpart")
            disk_size += 500

            # It can also request adding /boot which is 1G
            if ks.handler.reqpart.addBoot:
                log.info("Adding 1024M for reqpart --addboot")
                disk_size += 1024

    if opts.image_size_align:
        disk_size += opts.image_size_align - (disk_size % opts.image_size_align)

    log.info("Using disk size of %sMiB", disk_size)
    return disk_size

def make_image(opts, ks, cancel_func=None):
    """
    Install to a disk image

    :param opts: options passed to livemedia-creator
    :type opts: argparse options
    :param str ks: Path to the kickstart to use for the installation
    :param cancel_func: Function that returns True to cancel build
    :type cancel_func: function
    :returns: Path of the image created
    :rtype: str

    Use qemu+boot.iso or anaconda to install to a disk image.
    """

    # For make_tar_disk, opts.image_name is the name of the final tarball.
    # Use opts.tar_disk_name as the name of the disk image
    if opts.make_tar_disk:
        disk_img = joinpaths(opts.result_dir, opts.tar_disk_name)
    elif opts.image_name:
        disk_img = joinpaths(opts.result_dir, opts.image_name)
    else:
        disk_img = tempfile.mktemp(prefix="lmc-disk-", suffix=".img", dir=opts.result_dir)
    log.info("disk_img = %s", disk_img)
    disk_size = calculate_disk_size(opts, ks)

    # For make_tar_disk, pass a second path parameter for the final tarball
    # not the final output file.
    if opts.make_tar_disk:
        tar_img = joinpaths(opts.result_dir, opts.image_name)
    else:
        tar_img = None

    try:
        if opts.no_virt:
            novirt_install(opts, disk_img, disk_size, cancel_func=cancel_func, tar_img=tar_img)
        else:
            install_log = os.path.abspath(os.path.dirname(opts.logfile))+"/virt-install.log"
            log.info("install_log = %s", install_log)

            virt_install(opts, install_log, disk_img, disk_size, cancel_func=cancel_func, tar_img=tar_img)
    except InstallError as e:
        log.error("Install failed: %s", e)
        if not opts.keep_image:
            if os.path.exists(disk_img):
                log.info("Removing bad disk image")
                os.unlink(disk_img)
            if tar_img and os.path.exists(tar_img):
                log.info("Removing bad tar file")
                os.unlink(tar_img)
        raise

    log.info("Disk Image install successful")

    if opts.make_tar_disk:
        return tar_img

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
    rc = mksquashfs(squashfs_root_dir, joinpaths(work_dir, live_image_name), compression, compressargs)
    if rc != 0:
        log.error("mksquashfs failed to create %s", live_image_name)
        return None

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

def check_kickstart(ks, opts):
    """Check the parsed kickstart object for errors

    :param ks: Parsed Kickstart object
    :type ks: pykickstart.parser.KickstartParser
    :param opts: Commandline options to control the process
    :type opts: Either a DataHolder or ArgumentParser
    :returns: List of error strings or empty list
    :rtype: list
    """
    errors = []
    if opts.no_virt and ks.handler.method.method not in ("url", "nfs") \
       and not ks.handler.ostreesetup.seen:
        errors.append("Only url, nfs and ostreesetup install methods are currently supported."
                      "Please fix your kickstart file." )

    if ks.handler.repo.seen and ks.handler.method.method != "url":
        errors.append("repo can only be used with the url install method. Add url to your "
                      "kickstart file.")

    if ks.handler.method.method in ("url", "nfs") and not ks.handler.network.seen:
        errors.append("The kickstart must activate networking if "
                      "the url or nfs install method is used.")

    if ks.handler.displaymode.displayMode is not None:
        errors.append("The kickstart must not set a display mode (text, cmdline, "
                      "graphical), this will interfere with livemedia-creator.")

    if opts.make_fsimage or (opts.make_pxe_live and opts.no_virt):
        # Make sure the kickstart isn't using autopart and only has a / mountpoint
        part_ok = not any(p for p in ks.handler.partition.partitions
                             if p.mountpoint not in ["/", "swap"])
        if not part_ok or ks.handler.autopart.seen:
            errors.append("Filesystem images must use a single / part, not autopart or "
                          "multiple partitions. swap is allowed but not used.")

    if not opts.no_virt and ks.handler.reboot.action != KS_SHUTDOWN:
        errors.append("The kickstart must include shutdown when using virt installation.")

    return errors

def run_creator(opts, cancel_func=None):
    """Run the image creator process

    :param opts: Commandline options to control the process
    :type opts: Either a DataHolder or ArgumentParser
    :param cancel_func: Function that returns True to cancel build
    :type cancel_func: function
    :returns: The result directory and the disk image path.
    :rtype: Tuple of str

    This function takes the opts arguments and creates the selected output image.
    See the cmdline --help for livemedia-creator for the possible options

    (Yes, this is not ideal, but we can fix that later)
    """
    result_dir = None

    # Parse the kickstart
    if opts.ks:
        ks_version = makeVersion()
        ks = KickstartParser(ks_version, errorsAreFatal=False, missingIncludeIsFatal=False)
        ks.readKickstart(opts.ks[0])

    # live iso usually needs dracut-live so warn the user if it is missing
    if opts.ks and opts.make_iso:
        if "dracut-live" not in ks.handler.packages.packageList:
            log.error("dracut-live package is missing from the kickstart.")
            raise RuntimeError("dracut-live package is missing from the kickstart.")

    # Make the disk or filesystem image
    if not opts.disk_image and not opts.fs_image:
        if not opts.ks:
            raise RuntimeError("Image creation requires a kickstart file")

        # Check the kickstart for problems
        errors = check_kickstart(ks, opts)
        if errors:
            list(log.error(e) for e in errors)
            raise RuntimeError("\n".join(errors))

        # Make the image. Output of this is either a partitioned disk image or a fsimage
        try:
            disk_img = make_image(opts, ks, cancel_func=cancel_func)
        except InstallError as e:
            log.error("ERROR: Image creation failed: %s", e)
            raise RuntimeError("Image creation failed: %s" % e)

    if opts.image_only:
        return (result_dir, disk_img)

    if opts.make_iso:
        work_dir = tempfile.mkdtemp(prefix="lmc-work-")
        log.info("working dir is %s", work_dir)

        if (opts.fs_image or opts.no_virt) and not opts.disk_image:
            # Create iso from a filesystem image
            disk_img = opts.fs_image or disk_img
            with Mount(disk_img, opts="loop") as mount_dir:
                rc = make_runtime(opts, mount_dir, work_dir, calculate_disk_size(opts, ks)/1024.0)
                if rc != 0:
                    log.error("make_runtime failed with rc = %d. See program.log", rc)
                    raise RuntimeError("make_runtime failed with rc = %d" % rc)
                if cancel_func and cancel_func():
                    raise RuntimeError("ISO creation canceled")

                result_dir = make_livecd(opts, mount_dir, work_dir)
        else:
            # Create iso from a partitioned disk image
            disk_img = opts.disk_image or disk_img
            with PartitionMount(disk_img) as img_mount:
                if img_mount and img_mount.mount_dir:
                    rc = make_runtime(opts, img_mount.mount_dir, work_dir, calculate_disk_size(opts, ks)/1024.0)
                    if rc != 0:
                        log.error("make_runtime failed with rc = %d. See program.log", rc)
                        raise RuntimeError("make_runtime failed with rc = %d" % rc)
                    result_dir = make_livecd(opts, img_mount.mount_dir, work_dir)

        # --iso-only removes the extra build artifacts, keeping only the boot.iso
        if opts.iso_only and result_dir:
            boot_iso = joinpaths(result_dir, "images/boot.iso")
            if not os.path.exists(boot_iso):
                log.error("%s is missing, skipping --iso-only.", boot_iso)
            else:
                iso_dir = tempfile.mkdtemp(prefix="lmc-result-")
                dest_file = joinpaths(iso_dir, opts.iso_name or "boot.iso")
                shutil.move(boot_iso, dest_file)
                shutil.rmtree(result_dir)
                result_dir = iso_dir

        # cleanup the mess
        # cleanup work_dir?
        if disk_img and not (opts.keep_image or opts.disk_image or opts.fs_image):
            os.unlink(disk_img)
            log.info("Disk image erased")
            disk_img = None
    elif opts.make_appliance:
        if not opts.ks:
            networks = []
        else:
            networks = ks.handler.network.network
        make_appliance(opts.disk_image or disk_img, opts.app_name,
                       opts.app_template, opts.app_file, networks, opts.ram,
                       opts.vcpus or 1, opts.arch, opts.title, opts.project, opts.releasever)
    elif opts.make_pxe_live:
        work_dir = tempfile.mkdtemp(prefix="lmc-work-")
        log.info("working dir is %s", work_dir)
        disk_img = opts.fs_image or opts.disk_image or disk_img
        log.debug("disk image is %s", disk_img)

        result_dir = make_live_images(opts, work_dir, disk_img)
        if result_dir is None:
            log.error("Creating PXE live image failed.")
            raise RuntimeError("Creating PXE live image failed.")

    if opts.result_dir != opts.tmp and result_dir:
        copytree(result_dir, opts.result_dir, preserve=False)
        shutil.rmtree(result_dir)
        result_dir = None

    return (result_dir, disk_img)
