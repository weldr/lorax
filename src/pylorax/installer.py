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
import shutil
import sys
import subprocess
import tempfile
from time import sleep
import uuid

from pylorax.executils import execWithRedirect, execWithCapture
from pylorax.imgutils import get_loop_name, dm_detach, mount, umount
from pylorax.imgutils import PartitionMount, mksparse, mkext4img, loop_detach
from pylorax.imgutils import mktar, mkdiskfsimage, mkqcow2
from pylorax.logmonitor import LogMonitor
from pylorax.sysutils import joinpaths
from pylorax.treebuilder import udev_escape

ROOT_PATH = "/mnt/sysimage/"

# no-virt mode doesn't need libvirt, so make it optional
try:
    import libvirt
except ImportError:
    libvirt = None


class InstallError(Exception):
    pass

class IsoMountpoint(object):
    """
    Mount the iso on a temporary directory and check to make sure the
    vmlinuz and initrd.img files exist
    Check the iso for a LiveOS directory and set a flag.
    Extract the iso's label.

    initrd_path can be used to point to a boot.iso tree with a newer
    initrd.img than the iso has. The iso is still used for stage2.
    """
    def __init__( self, iso_path, initrd_path=None ):
        """ iso_path is the path to a  boot.iso
            initrd_path overrides mounting the iso for access to
                        initrd and vmlinuz.
        """
        self.label = None
        self.iso_path = iso_path
        self.initrd_path = initrd_path

        if not self.initrd_path:
            self.mount_dir = mount(self.iso_path, opts="loop")
        else:
            self.mount_dir = self.initrd_path

        kernel_list = [("/isolinux/vmlinuz", "/isolinux/initrd.img"),
                       ("/ppc/ppc64/vmlinuz", "/ppc/ppc64/initrd.img"),
                       ("/images/pxeboot/vmlinuz", "/images/pxeboot/initrd.img")]
        if os.path.isdir( self.mount_dir+"/repodata" ):
            self.repo = self.mount_dir
        else:
            self.repo = None
        self.liveos = os.path.isdir( self.mount_dir+"/LiveOS" )

        try:
            for kernel, initrd in kernel_list:
                if (os.path.isfile(self.mount_dir+kernel) and
                    os.path.isfile(self.mount_dir+initrd)):
                    self.kernel = self.mount_dir+kernel
                    self.initrd = self.mount_dir+initrd
                    break
            else:
                raise Exception("Missing kernel and initrd file in iso, failed"
                                " to search under: {0}".format(kernel_list))
        except:
            self.umount()
            raise

        self.get_iso_label()

    def umount( self ):
        if not self.initrd_path:
            umount(self.mount_dir)

    def get_iso_label( self ):
        """
        Get the iso's label using isoinfo
        """
        isoinfo_output = execWithCapture("isoinfo", ["-d", "-i", self.iso_path])
        log.debug( isoinfo_output )
        for line in isoinfo_output.splitlines():
            if line.startswith("Volume id: "):
                self.label = line[11:]
                return


class VirtualInstall( object ):
    """
    Run virt-install using an iso and kickstart(s)
    """
    def __init__( self, iso, ks_paths, disk_img, img_size=2, 
                  kernel_args=None, memory=1024, vnc=None, arch=None,
                  log_check=None, virtio_host="127.0.0.1", virtio_port=6080,
                  qcow2=False, boot_uefi=False, ovmf_path=None):
        """
        Start the installation

        :param iso: Information about the iso to use for the installation
        :type iso: IsoMountpoint
        :param list ks_paths: Paths to kickstart files. All are injected, the
           first one is the one executed.
        :param str disk_img: Path to a disk image, created it it doesn't exist
        :param int img_size: The image size, in MiB, to create if it doesn't exist
        :param str kernel_args: Extra kernel arguments to pass on the kernel cmdline
        :param int memory: Amount of RAM to assign to the virt, in MiB
        :param str vnc: Arguments to pass to virt-install --graphics
        :param str arch: Optional architecture to use in the virt
        :param log_check: Method that returns True if the installation fails
        :type log_check: method
        :param str virtio_host: Hostname to connect virtio log to
        :param int virtio_port: Port to connect virtio log to
        :param bool qcow2: Set to True if disk_img is a qcow2
        :param bool boot_uefi: Use OVMF to boot the VM in UEFI mode
        :param str ovmf_path: Path to the OVMF firmware
        """
        self.virt_name = "LiveOS-"+str(uuid.uuid4())
        # add --graphics none later
        # add whatever serial cmds are needed later
        args = ["-n", self.virt_name,
                 "-r", str(memory),
                 "--noreboot",
                 "--noautoconsole"]

        args.append("--graphics")
        if vnc:
            args.append(vnc)
        else:
            args.append("none")

        for ks in ks_paths:
            args.append("--initrd-inject")
            args.append(ks)

        disk_opts = "path={0}".format(disk_img)
        if qcow2:
            disk_opts += ",format=qcow2"
        else:
            disk_opts += ",format=raw"
        if not os.path.isfile(disk_img):
            disk_opts += ",size={0}".format(img_size)
        args.append("--disk")
        args.append(disk_opts)

        if iso.liveos:
            disk_opts = "path={0},device=cdrom".format(iso.iso_path)
            args.append("--disk")
            args.append(disk_opts)

        extra_args = "ks=file:/{0}".format(os.path.basename(ks_paths[0]))
        if not vnc:
            extra_args += " inst.cmdline console=ttyS0"
        if kernel_args:
            extra_args += " "+kernel_args
        if iso.liveos:
            extra_args += " stage2=hd:LABEL={0}".format(udev_escape(iso.label))
        args.append("--extra-args")
        args.append(extra_args)

        args.append("--location")
        args.append(iso.mount_dir)

        channel_args = "tcp,host={0}:{1},mode=connect,target_type=virtio" \
                       ",name=org.fedoraproject.anaconda.log.0".format(
                       virtio_host, virtio_port)
        args.append("--channel")
        args.append(channel_args)

        if arch:
            args.append("--arch")
            args.append(arch)

        if boot_uefi and ovmf_path:
            args.append("--boot")
            args.append("loader=%s/OVMF_CODE.fd,loader_ro=yes,loader_type=pflash,nvram_template=%s/OVMF_VARS.fd,loader_secure=no" % (ovmf_path, ovmf_path))

        log.info("Running virt-install.")
        try:
            execWithRedirect("virt-install", args, raise_err=True)
        except subprocess.CalledProcessError as e:
            raise InstallError("Problem starting virtual install: %s" % e)

        conn = libvirt.openReadOnly(None)
        dom = conn.lookupByName(self.virt_name)

        # TODO: If vnc has been passed, we should look up the port and print that
        # for the user at this point

        while dom.isActive() and not log_check():
            sys.stdout.write(".")
            sys.stdout.flush()
            sleep(10)
        print

        if log_check():
            log.info( "Installation error detected. See logfile." )
        else:
            log.info( "Install finished. Or at least virt shut down." )

    def destroy( self ):
        """
        Make sure the virt has been shut down and destroyed

        Could use libvirt for this instead.
        """
        log.info( "Shutting down %s", self.virt_name)
        subprocess.call(["virsh", "destroy", self.virt_name])

        # Undefine the virt, UEFI installs need to have --nvram passed
        subprocess.call(["virsh", "undefine", self.virt_name, "--nvram"])

def novirt_install(opts, disk_img, disk_size, repo_url, callback_func=None):
    """
    Use Anaconda to install to a disk image
    """
    import selinux

    # Set selinux to Permissive if it is Enforcing
    selinux_enforcing = False
    if selinux.is_selinux_enabled() and selinux.security_getenforce():
        selinux_enforcing = True
        selinux.security_setenforce(0)

    # Clean up /tmp/ from previous runs to prevent stale info from being used
    for path in ["/tmp/yum.repos.d/", "/tmp/yum.cache/"]:
        if os.path.isdir(path):
            shutil.rmtree(path)

    args = ["--kickstart", opts.ks[0], "--cmdline", "--repo", repo_url]
    if opts.anaconda_args:
        for arg in opts.anaconda_args:
            args += arg.split(" ", 1)
    if opts.proxy:
        args += ["--proxy", opts.proxy]
    if opts.armplatform:
        args += ["--armplatform", opts.armplatform]

    if opts.make_iso or opts.make_fsimage:
        # Make a blank fs image
        args += ["--dirinstall"]

        mkext4img(None, disk_img, label=opts.fs_label, size=disk_size * 1024**3)
        if not os.path.isdir(ROOT_PATH):
            os.mkdir(ROOT_PATH)
        mount(disk_img, opts="loop", mnt=ROOT_PATH)
    elif opts.make_tar:
        args += ["--dirinstall"]

        # Install directly into ROOT_PATH, make sure it starts clean
        if os.path.exists(ROOT_PATH):
            shutil.rmtree(ROOT_PATH)
        if not os.path.isdir(ROOT_PATH):
            os.mkdir(ROOT_PATH)
    else:
        args += ["--image", disk_img]

        # Create the sparse image
        mksparse(disk_img, disk_size * 1024**3)

    # Make sure anaconda has the right product and release
    os.environ["ANACONDA_PRODUCTNAME"] = opts.project
    os.environ["ANACONDA_PRODUCTVERSION"] = opts.releasever
    rc = execWithRedirect("anaconda", args, callback_func=callback_func)

    # Move the anaconda logs over to a log directory
    log_dir = os.path.abspath(os.path.dirname(opts.logfile))
    log_anaconda = joinpaths(log_dir, "anaconda")
    if not os.path.isdir(log_anaconda):
        os.mkdir(log_anaconda)
    for l in ["anaconda.log", "ifcfg.log", "program.log", "storage.log",
              "packaging.log", "yum.log"]:
        if os.path.exists("/tmp/"+l):
            shutil.copy2("/tmp/"+l, log_anaconda)
            os.unlink("/tmp/"+l)

    if opts.make_iso or opts.make_fsimage:
        umount(ROOT_PATH)
    else:
        # If anaconda failed the disk image may still be in use by dm
        execWithRedirect("anaconda-cleanup", [])

        if disk_img:
            dm_name = os.path.splitext(os.path.basename(disk_img))[0]
            dm_path = "/dev/mapper/"+dm_name
            if os.path.exists(dm_path):
                dm_detach(dm_path)
                loop_detach(get_loop_name(disk_img))

    if selinux_enforcing:
        selinux.security_setenforce(1)

    if rc:
        raise InstallError("novirt_install failed")

    if opts.make_tar:
        compress_args = []
        for arg in opts.compress_args:
            compress_args += arg.split(" ", 1)

        rc = mktar(ROOT_PATH, disk_img, opts.compression, compress_args)
        shutil.rmtree(ROOT_PATH)
        log.info("tar finished with rc=%d", rc)

        if rc:
            raise InstallError("novirt_install failed")
    elif opts.qcow2:
        log.info("Converting %s to qcow2", disk_img)
        qcow2_args = []
        for arg in opts.qcow2_args:
            qcow2_args += arg.split(" ", 1)

        # convert the image to qcow2 format
        if "-O" not in qcow2_args:
            qcow2_args.extend(["-O", "qcow2"])
        qcow2_img = tempfile.mktemp(prefix="disk", suffix=".img")
        execWithRedirect("qemu-img", ["convert"] + qcow2_args + [disk_img, qcow2_img], raise_err=True)
        execWithRedirect("mv", ["-f", qcow2_img, disk_img], raise_err=True)


def virt_install(opts, install_log, disk_img, disk_size):
    """
    Use virt-install to install to a disk image

    install_log is the path to write the log from virt-install
    disk_img is the full path to the final disk or filesystem image
    disk_size is the size of the disk to create in GiB
    """
    iso_mount = IsoMountpoint(opts.iso, opts.location)
    log_monitor = LogMonitor(install_log)

    kernel_args = ""
    if opts.kernel_args:
        kernel_args += opts.kernel_args
    if opts.proxy:
        kernel_args += " proxy="+opts.proxy

    if opts.qcow2 and not opts.make_fsimage:
        # virt-install can't take all the qcow2 options so create the image first
        qcow2_args = []
        for arg in opts.qcow2_args:
            qcow2_args += arg.split(" ", 1)

        mkqcow2(disk_img, disk_size*1024**3, qcow2_args)

    if opts.make_fsimage or opts.make_tar:
        diskimg_path = tempfile.mktemp(prefix="disk", suffix=".img")
    else:
        diskimg_path = disk_img

    try:
        virt = VirtualInstall(iso_mount, opts.ks, diskimg_path, disk_size,
                               kernel_args, opts.ram, opts.vnc, opts.arch,
                               log_check = log_monitor.server.log_check,
                               virtio_host = log_monitor.host,
                               virtio_port = log_monitor.port,
                               qcow2=opts.qcow2, boot_uefi=opts.virt_uefi,
                               ovmf_path=opts.ovmf_path)

        virt.destroy()
        log_monitor.shutdown()
    except InstallError as e:
        log.error("VirtualInstall failed: %s", e)
        raise
    finally:
        log.info("unmounting the iso")
        iso_mount.umount()

    if log_monitor.server.log_check():
        raise InstallError("virt_install failed")

    if opts.make_fsimage:
        mkdiskfsimage(diskimg_path, disk_img, label=opts.fs_label)
        os.unlink(diskimg_path)
    elif opts.make_tar:
        compress_args = []
        for arg in opts.compress_args:
            compress_args += arg.split(" ", 1)

        with PartitionMount(diskimg_path) as img_mount:
            if img_mount and img_mount.mount_dir:
                rc = mktar(img_mount.mount_dir, disk_img, opts.compression, compress_args)
        os.unlink(diskimg_path)

        if rc:
            raise InstallError("virt_install failed")
