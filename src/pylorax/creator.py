#
# Copyright (C) 2011-2017  Red Hat, Inc.
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
from pykickstart.version import makeVersion, RHEL7

# Use the Lorax treebuilder branch for iso creation
from pylorax import ArchData
from pylorax.base import DataHolder
from pylorax.treebuilder import TreeBuilder, RuntimeBuilder
from pylorax.treebuilder import findkernels
from pylorax.sysutils import joinpaths, remove
from pylorax.imgutils import Mount, PartitionMount, copytree, mount, umount
from pylorax.imgutils import mksquashfs, mkrootfsimg
from pylorax.executils import execWithRedirect, runcmd
from pylorax.installer import InstallError, novirt_install, virt_install

RUNTIME = "images/install.img"

# Default parameters for rebuilding initramfs, override with --dracut-arg
DRACUT_DEFAULT = ["--xz", "--add", "livenet dmsquash-live convertfs pollcdrom",
                  "--omit", "plymouth", "--no-hostonly", "--no-early-microcode"]


def get_ks_disk_size(ks):
    """Return the size of the kickstart's disk partitions

    :param ks: The kickstart
    :type ks: Kickstart object
    :returns: The size of the disk, in GiB
    """
    disk_size = 1 + (sum([p.size for p in ks.handler.partition.partitions]) / 1024)
    log.info("disk_size = %sGiB", disk_size)
    return disk_size

def is_image_mounted(disk_img):
    """
    Return True if the disk_img is mounted
    """
    with open("/proc/mounts") as mounts:
        for _mount in mounts:
            fields = _mount.split()
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
    ostree_sysroots = glob.glob(joinpaths(phys_root, "ostree/boot.0/*/*/0"))
    if ostree_sysroots:
        if len(ostree_sysroots) > 1:
            raise Exception("Too many deployment roots found: %s" % ostree_sysroots)
        ostree_root = os.path.relpath(ostree_sysroots[0], phys_root)
    return ostree_root

class KernelInfo(object):
    """
    Info about the kernels in boot_dir
    """
    def __init__(self, boot_dir):
        self.boot_dir = boot_dir
        self.list = self.get_kernels()
        self.arch = self.get_kernel_arch()
        log.debug("kernel_list for %s = %s", self.boot_dir, self.list)
        log.debug("kernel_arch is %s", self.arch)

    def get_kernels(self):
        """
        Get a list of the kernels in the boot_dir

        Examine the vmlinuz-* versions and return a list of them

        Ignore any with -rescue- in them, these are dracut rescue images.
        The user shoud add
        -dracut-config-rescue
        to the kickstart to remove them, but catch it here as well.
        """
        files = os.listdir(self.boot_dir)
        return [f[8:] for f in files if f.startswith("vmlinuz-") \
                and f.find("-rescue-") == -1]

    def get_kernel_arch(self):
        """
        Get the arch of the first kernel in boot_dir

        Defaults to i386
        """
        if self.list:
            kernel_arch = self.list[0].split(".")[-1]
        else:
            kernel_arch = "i386"
        return kernel_arch


def make_appliance(disk_img, name, template, outfile, networks=None, ram=1024,
                   vcpus=1, arch=None, title="Linux", project="Linux",
                   releasever="7"):
    """
    Generate an appliance description file

    disk_img    Full path of the disk image
    name        Name of the appliance, passed to the template
    template    Full path of Mako template
    outfile     Full path of file to write, using template
    networks    List of networks from the kickstart
    ram         Ram, in MB, passed to template. Default is 1024
    vcpus       CPUs, passed to template. Default is 1
    arch        CPU architecture. Default is 'x86_64'
    title       Title, passed to template. Default is 'Linux'
    project     Project, passed to template. Default is 'Linux'
    releasever  Release version, passed to template. Default is 17
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
            data = f.read(1024*1024)
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


def make_runtime(opts, mount_dir, work_dir):
    """
    Make the squashfs image from a directory

    Result is in work_dir+RUNTIME
    """
    kernels = KernelInfo(joinpaths(mount_dir, "boot" ))

    # Fake yum object
    fake_yum = DataHolder(conf=DataHolder(installroot=mount_dir))
    # Fake arch with only basearch set
    arch = ArchData(kernels.arch)
    # TODO: Need to get release info from someplace...
    product = DataHolder(name=opts.project, version=opts.releasever, release="",
                            variant="", bugurl="", isfinal=False)

    # This is a mounted image partition, cannot hardlink to it, so just use it
    # symlink mount_dir/images to work_dir/images so we don't run out of space
    os.makedirs(joinpaths(work_dir, "images"))

    rb = RuntimeBuilder(product, arch, fake_yum)
    log.info("Creating runtime")
    rb.create_runtime(joinpaths(work_dir, RUNTIME), size=None)

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
        kernels_dir = glob.glob(joinpaths(sys_root_dir, "boot/ostree/*"))[0]
        kdir = os.path.relpath(kernels_dir, sys_root_dir)

    kernels = [kernel for kernel in findkernels(sys_root_dir, kdir)
               if hasattr(kernel, "initrd")]
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

    for kernel in kernels:
        outfile = kernel.initrd.path + ".live"
        log.info("rebuilding %s", outfile)

        kver = kernel.version

        cmd = dracut + [outfile, kver]
        runcmd(cmd, root=sys_root_dir)

        new_initrd_path = joinpaths(results_dir, os.path.basename(kernel.initrd.path))
        shutil.move(joinpaths(sys_root_dir, outfile), new_initrd_path)
        os.chmod(new_initrd_path, 0644)
        shutil.copy2(joinpaths(sys_root_dir, kernel.path), results_dir)

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

def make_livecd(opts, mount_dir, work_dir):
    """
    Take the content from the disk image and make a livecd out of it

    This uses wwood's squashfs live initramfs method:
     * put the real / into LiveOS/rootfs.img
     * make a squashfs of the LiveOS/rootfs.img tree
     * make a simple initramfs with the squashfs.img and /etc/cmdline in it
     * make a cpio of that tree
     * append the squashfs.cpio to a dracut initramfs for each kernel installed

    Then on boot dracut reads /etc/cmdline which points to the squashfs.img
    mounts that and then mounts LiveOS/rootfs.img as /

    """
    kernels = KernelInfo(joinpaths(mount_dir, "boot" ))

    arch = ArchData(kernels.arch)
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
    shutil.copytree(configdir, fullpath)

    isolabel = opts.volid or "{0.name} {0.version} {1.basearch}".format(product, arch)
    if len(isolabel) > 32:
        isolabel = isolabel[:32]
        log.warn("Truncating isolabel to 32 chars: %s", isolabel)

    tb = TreeBuilder(product=product, arch=arch, domacboot=opts.domacboot,
                     inroot=mount_dir, outroot=work_dir,
                     runtime=RUNTIME, isolabel=isolabel,
                     templatedir=joinpaths(opts.lorax_templates,"live/"))
    log.info( "Rebuilding initrds" )
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
    tmp_mount_dir = tempfile.mkdtemp()
    sys_root = find_ostree_root(root_dir)
    sysroot_boot_dir = None
    for dev, _size in img_mount.loop_devices:
        if dev is img_mount.mount_dev:
            continue
        try:
            mount("/dev/mapper/"+dev, mnt=tmp_mount_dir)
            if is_boot_part(tmp_mount_dir):
                umount(tmp_mount_dir)
                sysroot_boot_dir = joinpaths(joinpaths(root_dir, sys_root), "boot")
                mount("/dev/mapper/"+dev, mnt=sysroot_boot_dir)
                break
            else:
                umount(tmp_mount_dir)
        except subprocess.CalledProcessError as e:
            log.debug("Looking for boot partition error: %s", e)
    remove(tmp_mount_dir)
    return sysroot_boot_dir

def make_squashfs(disk_img, work_dir, compression="xz"):
    """
    Take disk_img and put it into LiveOS/rootfs.img and squashfs this
    tree into work_dir+RUNTIME
    """
    liveos_dir = joinpaths(work_dir, "runtime/LiveOS")
    os.makedirs(liveos_dir)
    os.makedirs(os.path.dirname(joinpaths(work_dir, RUNTIME)))

    rc = execWithRedirect("/bin/ln", [disk_img, joinpaths(liveos_dir, "rootfs.img")])
    if rc != 0:
        shutil.copy2(disk_img, joinpaths(liveos_dir, "rootfs.img"))

    mksquashfs(joinpaths(work_dir, "runtime"),
               joinpaths(work_dir, RUNTIME), compression)
    remove(joinpaths(work_dir, "runtime"))


def make_image(opts, ks, callback_func=None):
    """
    Install to an image

    Use virt or anaconda to install to an image.

    Returns the full path of of the image created.
    """
    disk_size = get_ks_disk_size(ks)

    if opts.image_name:
        disk_img = joinpaths(opts.result_dir, opts.image_name)
    else:
        disk_img = tempfile.mktemp(prefix="disk", suffix=".img", dir=opts.result_dir)
    log.info("disk_img = %s", disk_img)

    try:
        if opts.no_virt:
            novirt_install(opts, disk_img, disk_size, ks.handler.method.url, callback_func=callback_func)
        else:
            install_log = os.path.abspath(os.path.dirname(opts.logfile))+"/virt-install.log"
            log.info("install_log = %s", install_log)

            virt_install(opts, install_log, disk_img, disk_size)
    except InstallError as e:
        log.error("Install failed: %s", e)
        if not opts.keep_image:
            log.info("Removing bad disk image")
            if os.path.exists(disk_img):
                os.unlink(disk_img)
        raise

    log.info("Disk Image install successful")
    return disk_img


def make_live_images(opts, work_dir, root_dir, rootfs_image=None, size=None):
    """
    Create live images from direcory or rootfs image

    :param opts: options passed to livemedia-creator
    :type opts: argparse options
    :param str work_dir: Directory for storing results
    :param str root_dir: Root directory of live filesystem tree
    :param str rootfs_image: Path to live rootfs image to be used
    :returns: Path of directory with created images
    :rtype: str
    """
    sys_root = ""
    if opts.ostree:
        sys_root = find_ostree_root(root_dir)

    squashfs_root_dir = joinpaths(work_dir, "squashfs_root")
    liveos_dir = joinpaths(squashfs_root_dir, "LiveOS")
    os.makedirs(liveos_dir)

    if rootfs_image:
        rc = execWithRedirect("/bin/ln", [rootfs_image, joinpaths(liveos_dir, "rootfs.img")])
        if rc != 0:
            shutil.copy2(rootfs_image, joinpaths(liveos_dir, "rootfs.img"))
    else:
        log.info("Creating live rootfs image")
        mkrootfsimg(root_dir, joinpaths(liveos_dir, "rootfs.img"), "LiveOS", size=size, sysroot=sys_root)

    log.info("Packing live rootfs image")
    add_pxe_args = []
    live_image_name = "live-rootfs.squashfs.img"
    mksquashfs(squashfs_root_dir,
                joinpaths(work_dir, live_image_name),
                opts.compression,
                opts.compress_args)

    remove(squashfs_root_dir)

    log.info("Rebuilding initramfs for live")
    rebuild_initrds_for_live(opts, joinpaths(root_dir, sys_root), work_dir)

    if opts.ostree:
        add_pxe_args.append("ostree=/%s" % sys_root)
    template = joinpaths(opts.lorax_templates, "pxe-live/pxe-config.tmpl")
    create_pxe_config(template, work_dir, live_image_name, add_pxe_args)

    return work_dir

def run_creator(opts, callback_func=None):
    """Run the image creator process

    :param opts: Commandline options to control the process
    :type opts: Either a DataHolder or ArgumentParser
    :returns: The result directory and the disk image path.
    :rtype: Tuple of str

    This function takes the opts arguments and creates the selected output image.
    See the cmdline --help for livemedia-creator for the possible options

    (Yes, this is not ideal, but we can fix that later)
    """
    result_dir = None

    # Parse the kickstart
    if opts.ks:
        ks_version = makeVersion(RHEL7)
        ks = KickstartParser( ks_version, errorsAreFatal=False, missingIncludeIsFatal=False )
        ks.readKickstart( opts.ks[0] )

    # Make the disk or filesystem image
    if not opts.disk_image and not opts.fs_image:
        if not opts.ks:
            raise RuntimeError("Image creation requires a kickstart file")

        errors = []
        if ks.handler.method.method != "url" and opts.no_virt:
            errors.append("Only url install method is currently supported. Please "
                          "fix your kickstart file." )

        if ks.handler.displaymode.displayMode is not None:
            errors.append("The kickstart must not set a display mode (text, cmdline, "
                          "graphical), this will interfere with livemedia-creator.")

        if opts.make_fsimage:
            # Make sure the kickstart isn't using autopart and only has a / mountpoint
            part_ok = not any(p for p in ks.handler.partition.partitions
                                 if p.mountpoint not in ["/", "swap"])
            if not part_ok or ks.handler.autopart.seen:
                errors.append("Filesystem images must use a single / part, not autopart or "
                              "multiple partitions. swap is allowed but not used.")

        if errors:
            raise RuntimeError("\n".join(errors))

        # Make the image. Output of this is either a partitioned disk image or a fsimage
        # Can also fail with InstallError
        disk_img = make_image(opts, ks, callback_func=callback_func)

    # Only create the disk image, return that now
    if opts.image_only:
        return (result_dir, disk_img)

    if opts.make_iso:
        work_dir = tempfile.mkdtemp()
        log.info("working dir is %s", work_dir)

        if (opts.fs_image or opts.no_virt) and not opts.disk_image:
            # Create iso from a filesystem image
            disk_img = opts.fs_image or disk_img

            make_squashfs(disk_img, work_dir)
            with Mount(disk_img, opts="loop") as mount_dir:
                result_dir = make_livecd(opts, mount_dir, work_dir)
        else:
            # Create iso from a partitioned disk image
            disk_img = opts.disk_image or disk_img
            with PartitionMount(disk_img) as img_mount:
                if img_mount and img_mount.mount_dir:
                    make_runtime(opts, img_mount.mount_dir, work_dir)
                    result_dir = make_livecd(opts, img_mount.mount_dir, work_dir)

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
                       opts.vcpus, opts.arch, opts.title, opts.project, opts.releasever)
    elif opts.make_pxe_live:
        work_dir = tempfile.mkdtemp()
        log.info("working dir is %s", work_dir)

        if (opts.fs_image or opts.no_virt) and not opts.disk_image:
            # Create pxe live images from a filesystem image
            disk_img = opts.fs_image or disk_img
            with Mount(disk_img, opts="loop") as mnt_dir:
                result_dir = make_live_images(opts, work_dir, mnt_dir, rootfs_image=disk_img)
        else:
            # Create pxe live images from a partitioned disk image
            disk_img = opts.disk_image or disk_img
            is_root_part = None
            if opts.ostree:
                is_root_part = lambda dir: os.path.exists(dir+"/ostree/deploy")
            with PartitionMount(disk_img, mount_ok=is_root_part) as img_mount:
                if img_mount and img_mount.mount_dir:
                    try:
                        mounted_sysroot_boot_dir = None
                        if opts.ostree:
                            mounted_sysroot_boot_dir = mount_boot_part_over_root(img_mount)
                        if opts.live_rootfs_keep_size:
                            size = img_mount.mount_size / 1024**3
                        else:
                            size = opts.live_rootfs_size or None
                        result_dir = make_live_images(opts, work_dir, img_mount.mount_dir, size=size)
                    finally:
                        if mounted_sysroot_boot_dir:
                            umount(mounted_sysroot_boot_dir)

    if opts.result_dir != opts.tmp and result_dir:
        copytree(result_dir, opts.result_dir, preserve=False)
        shutil.rmtree( result_dir )
        result_dir = None

    return (result_dir, disk_img)
