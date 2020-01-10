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

import glob
import json
from math import ceil
import os
import subprocess
import shutil
import socket
import tempfile

# Use the Lorax treebuilder branch for iso creation
from pylorax.executils import execWithRedirect, execReadlines
from pylorax.imgutils import PartitionMount, mksparse, mkext4img, loop_detach
from pylorax.imgutils import get_loop_name, dm_detach, mount, umount
from pylorax.imgutils import mkqemu_img, mktar, mkcpio, mkfsimage_from_disk
from pylorax.monitor import LogMonitor
from pylorax.mount import IsoMountpoint
from pylorax.sysutils import joinpaths
from pylorax.treebuilder import udev_escape


ROOT_PATH = "/mnt/sysimage/"

class InstallError(Exception):
    pass


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


def find_free_port(start=5900, end=5999, host="127.0.0.1"):
    """ Return first free port in range.

    :param int start: Starting port number
    :param int end: Ending port number
    :param str host: Host IP to search
    :returns: First free port or -1 if none found
    :rtype: int
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    for port in range(start, end+1):
        try:
            s.bind((host, port))
            s.close()
            return port
        except OSError:
            pass

    return -1

def append_initrd(initrd, files):
    """ Append files to an initrd.

    :param str initrd: Path to initrd
    :param list files: list of file paths to add
    :returns: Path to a new initrd
    :rtype: str

    The files are added to the initrd by creating a cpio image
    of the files (stored at /) and writing the cpio to the end of a
    copy of the initrd.

    The initrd is not changed, a copy is made before appending the
    cpio archive.
    """
    qemu_initrd = tempfile.mktemp(prefix="lmc-initrd-", suffix=".img")
    shutil.copy2(initrd, qemu_initrd)
    ks_dir = tempfile.mkdtemp(prefix="lmc-ksdir-")
    for ks in files:
        shutil.copy2(ks, ks_dir)
    ks_initrd = tempfile.mktemp(prefix="lmc-ks-", suffix=".img")
    mkcpio(ks_dir, ks_initrd)
    shutil.rmtree(ks_dir)
    with open(qemu_initrd, "ab") as initrd_fp:
        with open(ks_initrd, "rb") as ks_fp:
            while True:
                data = ks_fp.read(1024**2)
                if not data:
                    break
                initrd_fp.write(data)
    os.unlink(ks_initrd)

    return qemu_initrd

class QEMUInstall(object):
    """
    Run qemu using an iso and a kickstart
    """
    # Mapping of arch to qemu command
    QEMU_CMDS = {"x86_64":  "qemu-system-x86_64",
                 "i386":    "qemu-system-i386",
                 "arm":     "qemu-system-arm",
                 "aarch64": "qemu-system-aarch64",
                 "ppc64le": "qemu-system-ppc64"
                }

    def __init__(self, opts, iso, ks_paths, disk_img, img_size=2048,
                 kernel_args=None, memory=1024, vcpus=None, vnc=None, arch=None,
                 cancel_func=None, virtio_host="127.0.0.1", virtio_port=6080,
                 image_type=None, boot_uefi=False, ovmf_path=None):
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
        :param int vcpus: Number of virtual cpus
        :param str vnc: Arguments to pass to qemu -display
        :param str arch: Optional architecture to use in the virt
        :param cancel_func: Function that returns True if the installation fails
        :type cancel_func: function
        :param str virtio_host: Hostname to connect virtio log to
        :param int virtio_port: Port to connect virtio log to
        :param str image_type: Type of qemu-img disk to create, or None.
        :param bool boot_uefi: Use OVMF to boot the VM in UEFI mode
        :param str ovmf_path: Path to the OVMF firmware
        """
        # Lookup qemu-system- for arch if passed, or try to guess using host arch
        qemu_cmd = [self.QEMU_CMDS.get(arch or os.uname().machine, "qemu-system-"+os.uname().machine)]
        if not os.path.exists("/usr/bin/"+qemu_cmd[0]):
            raise InstallError("%s does not exist, cannot run qemu" % qemu_cmd[0])

        qemu_cmd += ["-no-user-config"]
        qemu_cmd += ["-m", str(memory)]
        if vcpus:
            qemu_cmd += ["-smp", str(vcpus)]

        if not opts.no_kvm and os.path.exists("/dev/kvm"):
            qemu_cmd += ["-machine", "accel=kvm"]

        if boot_uefi:
            qemu_cmd += ["-machine", "q35,smm=on"]
            qemu_cmd += ["-global", "driver=cfi.pflash01,property=secure,value=on"]

        # Copy the initrd from the iso, create a cpio archive of the kickstart files
        # and append it to the temporary initrd.
        qemu_initrd = append_initrd(iso.initrd, ks_paths)
        qemu_cmd += ["-kernel", iso.kernel]
        qemu_cmd += ["-initrd", qemu_initrd]

        # Add the disk and cdrom
        if not os.path.isfile(disk_img):
            mksparse(disk_img, img_size * 1024**2)
        drive_args = "file=%s" % disk_img
        drive_args += ",cache=unsafe,discard=unmap"
        if image_type:
            drive_args += ",format=%s" % image_type
        else:
            drive_args += ",format=raw"
        qemu_cmd += ["-drive", drive_args]

        drive_args = "file=%s,media=cdrom,readonly=on" % iso.iso_path
        qemu_cmd += ["-drive", drive_args]

        # Setup the cmdline args
        # ======================
        cmdline_args = "ks=file:/%s" % os.path.basename(ks_paths[0])
        cmdline_args += " inst.stage2=hd:LABEL=%s" % udev_escape(iso.label)
        if opts.proxy:
            cmdline_args += " inst.proxy=%s" % opts.proxy
        if kernel_args:
            cmdline_args += " "+kernel_args
        cmdline_args += " inst.text inst.cmdline"

        qemu_cmd += ["-append", cmdline_args]

        if not opts.vnc:
            vnc_port = find_free_port()
            if vnc_port == -1:
                raise InstallError("No free VNC ports")
            display_args = "vnc=127.0.0.1:%d" % (vnc_port - 5900)
        else:
            display_args = opts.vnc
        log.info("qemu %s", display_args)
        qemu_cmd += ["-nographic", "-monitor", "none", "-serial", "null", "-display", display_args ]

        # Setup the virtio log port
        qemu_cmd += ["-device", "virtio-serial-pci,id=virtio-serial0"]
        qemu_cmd += ["-device", "virtserialport,bus=virtio-serial0.0,nr=1,chardev=charchannel0"
                                ",id=channel0,name=org.fedoraproject.anaconda.log.0"]
        qemu_cmd += ["-chardev", "socket,id=charchannel0,host=%s,port=%s" % (virtio_host, virtio_port)]

        # Pass through rng from host
        if opts.with_rng != "none":
            qemu_cmd += ["-object", "rng-random,id=virtio-rng0,filename=%s" % opts.with_rng]
            if boot_uefi:
                qemu_cmd += ["-device", "virtio-rng-pci,rng=virtio-rng0,id=rng0,bus=pcie.0,addr=0x9"]
            else:
                qemu_cmd += ["-device", "virtio-rng-pci,rng=virtio-rng0,id=rng0,bus=pci.0,addr=0x9"]

        if boot_uefi and ovmf_path:
            qemu_cmd += ["-drive", "file=%s/OVMF_CODE.secboot.fd,if=pflash,format=raw,unit=0,readonly=on" % ovmf_path]

            # Make a copy of the OVMF_VARS.secboot.fd for this run
            ovmf_vars = tempfile.mktemp(prefix="lmc-OVMF_VARS-", suffix=".fd")
            shutil.copy2(joinpaths(ovmf_path, "/OVMF_VARS.secboot.fd"), ovmf_vars)

            qemu_cmd += ["-drive", "file=%s,if=pflash,format=raw,unit=1" % ovmf_vars]

        log.info("Running qemu")
        log.debug(qemu_cmd)
        try:
            execWithRedirect(qemu_cmd[0], qemu_cmd[1:], reset_lang=False, raise_err=True,
                             callback=lambda p: not (cancel_func and cancel_func()))
        except subprocess.CalledProcessError as e:
            log.error("Running qemu failed:")
            log.error("cmd: %s", " ".join(e.cmd))
            log.error("output: %s", e.output or "")
            raise InstallError("QEMUInstall failed")
        except (OSError, KeyboardInterrupt) as e:
            log.error("Running qemu failed: %s", str(e))
            raise InstallError("QEMUInstall failed")
        finally:
            os.unlink(qemu_initrd)
            if boot_uefi and ovmf_path:
                os.unlink(ovmf_vars)

        if cancel_func and cancel_func():
            log.error("Installation error detected. See logfile for details.")
            raise InstallError("QEMUInstall failed")
        else:
            log.info("Installation finished without errors.")


def novirt_cancel_check(cancel_funcs, proc):
    """
    Check to see if there has been an error in the logs

    :param cancel_funcs: list of functions to call, True from any one cancels the build
    :type cancel_funcs: list
    :param proc: Popen object for the anaconda process
    :type proc: subprocess.Popen
    :returns: True if the process has been terminated

    The cancel_funcs functions should return a True if an error has been detected.
    When an error is detected the process is terminated and this returns True
    """
    for f in cancel_funcs:
        if f():
            proc.terminate()
            return True
    return False


def anaconda_cleanup(dirinstall_path):
    """
    Cleanup any leftover mounts from anaconda

    :param str dirinstall_path: Path where anaconda mounts things
    :returns: True if cleanups were successful. False if any of them failed.

    If anaconda crashes it may leave things mounted under this path. It will
    typically be set to /mnt/sysimage/

    Attempts to cleanup may also fail. Catch these and continue trying the
    other mountpoints.

    Anaconda may also leave /run/anaconda.pid behind, clean that up as well.
    """
    # Anaconda may not clean up its /var/run/anaconda.pid file
    # Make sure the process is really finished (it should be, since it was started from a subprocess call)
    # and then remove the pid file.
    if os.path.exists("/var/run/anaconda.pid"):
        # lorax-composer runs anaconda using unshare so the pid is always 1
        if open("/var/run/anaconda.pid").read().strip() == "1":
            os.unlink("/var/run/anaconda.pid")

    rc = True
    dirinstall_path = os.path.abspath(dirinstall_path)
    # unmount filesystems
    for mounted in reversed(open("/proc/mounts").readlines()):
        (_device, mountpoint, _rest) = mounted.split(" ", 2)
        if mountpoint.startswith(dirinstall_path) and os.path.ismount(mountpoint):
            try:
                umount(mountpoint)
            except subprocess.CalledProcessError:
                log.error("Cleanup of %s failed. See program.log for details", mountpoint)
                rc = False
    return rc


def novirt_install(opts, disk_img, disk_size, cancel_func=None, tar_img=None):
    """
    Use Anaconda to install to a disk image

    :param opts: options passed to livemedia-creator
    :type opts: argparse options
    :param str disk_img: The full path to the disk image to be created
    :param int disk_size: The size of the disk_img in MiB
    :param cancel_func: Function that returns True to cancel build
    :type cancel_func: function
    :param str tar_img: For make_tar_disk, the path to final tarball to be created

    This method runs anaconda to create the image and then based on the opts
    passed creates a qemu disk image or tarfile.
    """
    dirinstall_path = ROOT_PATH

    # Clean up /tmp/ from previous runs to prevent stale info from being used
    for path in ["/tmp/yum.repos.d/", "/tmp/yum.cache/"]:
        if os.path.isdir(path):
            shutil.rmtree(path)

    args = ["--kickstart", opts.ks[0], "--cmdline", "--loglevel", "debug"]
    if opts.anaconda_args:
        for arg in opts.anaconda_args:
            args += arg.split(" ", 1)
    if opts.proxy:
        args += ["--proxy", opts.proxy]
    if opts.armplatform:
        args += ["--armplatform", opts.armplatform]

    if opts.make_iso or opts.make_fsimage or opts.make_pxe_live:
        # Make a blank fs image
        args += ["--dirinstall"]

        mkext4img(None, disk_img, label=opts.fs_label, size=disk_size * 1024**2)
        if not os.path.isdir(dirinstall_path):
            os.mkdir(dirinstall_path)
        mount(disk_img, opts="loop", mnt=dirinstall_path)
    elif opts.make_tar or opts.make_oci:
        # Install under dirinstall_path, make sure it starts clean
        if os.path.exists(dirinstall_path):
            shutil.rmtree(dirinstall_path)

        if opts.make_oci:
            # OCI installs under /rootfs/
            dirinstall_path = joinpaths(dirinstall_path, "rootfs")
            args += ["--dirinstall", dirinstall_path]
        else:
            args += ["--dirinstall"]

        os.makedirs(dirinstall_path)
    else:
        args += ["--image", disk_img]

        # Create the sparse image
        mksparse(disk_img, disk_size * 1024**2)

    log_monitor = LogMonitor(timeout=opts.timeout)
    args += ["--remotelog", "%s:%s" % (log_monitor.host, log_monitor.port)]
    cancel_funcs = [log_monitor.server.log_check]
    if cancel_func is not None:
        cancel_funcs.append(cancel_func)

    # Make sure anaconda has the right product and release
    # Preload libgomp.so.1 to workaround rhbz#1722181
    log.info("Running anaconda.")
    try:
        unshare_args = [ "--pid", "--kill-child", "--mount", "--propagation", "unchanged", "anaconda" ] + args
        for line in execReadlines("unshare", unshare_args, reset_lang=False,
                                  env_add={"ANACONDA_PRODUCTNAME": opts.project,
                                           "ANACONDA_PRODUCTVERSION": opts.releasever,
                                           "LD_PRELOAD": "libgomp.so.1"},
                                  callback=lambda p: not novirt_cancel_check(cancel_funcs, p)):
            log.info(line)

        # Make sure the new filesystem is correctly labeled
        setfiles_args = ["-e", "/proc", "-e", "/sys",
                         "/etc/selinux/targeted/contexts/files/file_contexts", "/"]

        if "--dirinstall" in args:
            # setfiles may not be available, warn instead of fail
            try:
                execWithRedirect("setfiles", setfiles_args, root=dirinstall_path)
            except (subprocess.CalledProcessError, OSError) as e:
                log.warning("Running setfiles on install tree failed: %s", str(e))
        else:
            with PartitionMount(disk_img) as img_mount:
                if img_mount and img_mount.mount_dir:
                    try:
                        execWithRedirect("setfiles", setfiles_args, root=img_mount.mount_dir)
                    except (subprocess.CalledProcessError, OSError) as e:
                        log.warning("Running setfiles on install tree failed: %s", str(e))

                    # For image installs, run fstrim to discard unused blocks. This way
                    # unused blocks do not need to be allocated for sparse image types
                    execWithRedirect("fstrim", [img_mount.mount_dir])

    except (subprocess.CalledProcessError, OSError) as e:
        log.error("Running anaconda failed: %s", e)
        raise InstallError("novirt_install failed")
    finally:
        log_monitor.shutdown()

        # Move the anaconda logs over to a log directory
        log_dir = os.path.abspath(os.path.dirname(opts.logfile))
        log_anaconda = joinpaths(log_dir, "anaconda")
        if not os.path.isdir(log_anaconda):
            os.mkdir(log_anaconda)
        for l in glob.glob("/tmp/*log")+glob.glob("/tmp/anaconda-tb-*"):
            shutil.copy2(l, log_anaconda)
            os.unlink(l)

        # Make sure any leftover anaconda mounts have been cleaned up
        if not anaconda_cleanup(dirinstall_path):
            raise InstallError("novirt_install cleanup of anaconda mounts failed.")

        if not opts.make_iso and not opts.make_fsimage and not opts.make_pxe_live:
            dm_name = os.path.splitext(os.path.basename(disk_img))[0]

            # Remove device-mapper for partitions and disk
            log.debug("Removing device-mapper setup on %s", dm_name)
            for d in sorted(glob.glob("/dev/mapper/"+dm_name+"*"), reverse=True):
                dm_detach(d)

            log.debug("Removing loop device for %s", disk_img)
            loop_detach("/dev/"+get_loop_name(disk_img))

    # qemu disk image is used by bare qcow2 images and by Vagrant
    if opts.image_type:
        log.info("Converting %s to %s", disk_img, opts.image_type)
        qemu_args = []
        for arg in opts.qemu_args:
            qemu_args += arg.split(" ", 1)

        # convert the image to the selected format
        if "-O" not in qemu_args:
            qemu_args.extend(["-O", opts.image_type])
        qemu_img = tempfile.mktemp(prefix="lmc-disk-", suffix=".img")
        execWithRedirect("qemu-img", ["convert"] + qemu_args + [disk_img, qemu_img], raise_err=True)
        if not opts.make_vagrant:
            execWithRedirect("mv", ["-f", qemu_img, disk_img], raise_err=True)
        else:
            # Take the new qcow2 image and package it up for Vagrant
            compress_args = []
            for arg in opts.compress_args:
                compress_args += arg.split(" ", 1)

            vagrant_dir = tempfile.mkdtemp(prefix="lmc-tmpdir-")
            metadata_path = joinpaths(vagrant_dir, "metadata.json")
            execWithRedirect("mv", ["-f", qemu_img, joinpaths(vagrant_dir, "box.img")], raise_err=True)
            if opts.vagrant_metadata:
                shutil.copy2(opts.vagrant_metadata, metadata_path)
            else:
                create_vagrant_metadata(metadata_path)
            update_vagrant_metadata(metadata_path, disk_size)
            if opts.vagrantfile:
                shutil.copy2(opts.vagrantfile, joinpaths(vagrant_dir, "vagrantfile"))

            log.info("Creating Vagrant image")
            rc = mktar(vagrant_dir, disk_img, opts.compression, compress_args, selinux=False)
            if rc:
                raise InstallError("novirt_install mktar failed: rc=%s" % rc)
            shutil.rmtree(vagrant_dir)
    elif opts.make_tar:
        compress_args = []
        for arg in opts.compress_args:
            compress_args += arg.split(" ", 1)

        rc = mktar(dirinstall_path, disk_img, opts.compression, compress_args)
        shutil.rmtree(dirinstall_path)

        if rc:
            raise InstallError("novirt_install mktar failed: rc=%s" % rc)
    elif opts.make_oci:
        # An OCI image places the filesystem under /rootfs/ and adds the json files at the top
        # And then creates a tar of the whole thing.
        compress_args = []
        for arg in opts.compress_args:
            compress_args += arg.split(" ", 1)

        shutil.copy2(opts.oci_config, ROOT_PATH)
        shutil.copy2(opts.oci_runtime, ROOT_PATH)
        rc = mktar(ROOT_PATH, disk_img, opts.compression, compress_args)

        if rc:
            raise InstallError("novirt_install mktar failed: rc=%s" % rc)
    else:
        # For raw disk images, use fallocate to deallocate unused space
        execWithRedirect("fallocate", ["--dig-holes", disk_img], raise_err=True)

    # For make_tar_disk, wrap the result in a tar file, and remove the original disk image.
    if opts.make_tar_disk:
        compress_args = []
        for arg in opts.compress_args:
            compress_args += arg.split(" ", 1)

        rc = mktar(disk_img, tar_img, opts.compression, compress_args, selinux=False)

        if rc:
            raise InstallError("novirt_install mktar failed: rc=%s" % rc)

        os.unlink(disk_img)

def virt_install(opts, install_log, disk_img, disk_size, cancel_func=None, tar_img=None):
    """
    Use qemu to install to a disk image

    :param opts: options passed to livemedia-creator
    :type opts: argparse options
    :param str install_log: The path to write the log from qemu
    :param str disk_img: The full path to the disk image to be created
    :param int disk_size: The size of the disk_img in MiB
    :param cancel_func: Function that returns True to cancel build
    :type cancel_func: function
    :param str tar_img: For make_tar_disk, the path to final tarball to be created

    This uses qemu with a boot.iso and a kickstart to create a disk
    image and then optionally, based on the opts passed, creates tarfile.
    """
    iso_mount = IsoMountpoint(opts.iso, opts.location)
    if not iso_mount.stage2:
        iso_mount.umount()
        raise InstallError("ISO is missing stage2, cannot continue")

    log_monitor = LogMonitor(install_log, timeout=opts.timeout)
    cancel_funcs = [log_monitor.server.log_check]
    if cancel_func is not None:
        cancel_funcs.append(cancel_func)

    kernel_args = ""
    if opts.kernel_args:
        kernel_args += opts.kernel_args
    if opts.proxy:
        kernel_args += " proxy="+opts.proxy

    if opts.image_type and not opts.make_fsimage:
        qemu_args = []
        for arg in opts.qemu_args:
            qemu_args += arg.split(" ", 1)
        if "-f" not in qemu_args:
            qemu_args += ["-f", opts.image_type]

        mkqemu_img(disk_img, disk_size*1024**2, qemu_args)

    if opts.make_fsimage or opts.make_tar or opts.make_oci:
        diskimg_path = tempfile.mktemp(prefix="lmc-disk-", suffix=".img")
    else:
        diskimg_path = disk_img

    try:
        QEMUInstall(opts, iso_mount, opts.ks, diskimg_path, disk_size,
                    kernel_args, opts.ram, opts.vcpus, opts.vnc, opts.arch,
                    cancel_func = lambda : any(f() for f in cancel_funcs),
                    virtio_host = log_monitor.host,
                    virtio_port = log_monitor.port,
                    image_type=opts.image_type, boot_uefi=opts.virt_uefi,
                    ovmf_path=opts.ovmf_path)
        log_monitor.shutdown()
    except InstallError as e:
        log.error("VirtualInstall failed: %s", e)
        raise
    finally:
        log.info("unmounting the iso")
        iso_mount.umount()

    if log_monitor.server.log_check():
        if not log_monitor.server.error_line and opts.timeout:
            msg = "virt_install failed due to timeout"
        else:
            msg = "virt_install failed on line: %s" % log_monitor.server.error_line
        raise InstallError(msg)
    elif cancel_func and cancel_func():
        raise InstallError("virt_install canceled by cancel_func")

    if opts.make_fsimage:
        mkfsimage_from_disk(diskimg_path, disk_img, disk_size, label=opts.fs_label)
        os.unlink(diskimg_path)
    elif opts.make_tar:
        compress_args = []
        for arg in opts.compress_args:
            compress_args += arg.split(" ", 1)

        with PartitionMount(diskimg_path) as img_mount:
            if img_mount and img_mount.mount_dir:
                rc = mktar(img_mount.mount_dir, disk_img, opts.compression, compress_args)
            else:
                rc = 1
        os.unlink(diskimg_path)

        if rc:
            raise InstallError("virt_install failed")
    elif opts.make_oci:
        # An OCI image places the filesystem under /rootfs/ and adds the json files at the top
        # And then creates a tar of the whole thing.
        compress_args = []
        for arg in opts.compress_args:
            compress_args += arg.split(" ", 1)

        with PartitionMount(diskimg_path, submount="rootfs") as img_mount:
            if img_mount and img_mount.temp_dir:
                shutil.copy2(opts.oci_config, img_mount.temp_dir)
                shutil.copy2(opts.oci_runtime, img_mount.temp_dir)
                rc = mktar(img_mount.temp_dir, disk_img, opts.compression, compress_args)
            else:
                rc = 1
        os.unlink(diskimg_path)

        if rc:
            raise InstallError("virt_install failed")
    elif opts.make_vagrant:
        compress_args = []
        for arg in opts.compress_args:
            compress_args += arg.split(" ", 1)

        vagrant_dir = tempfile.mkdtemp(prefix="lmc-tmpdir-")
        metadata_path = joinpaths(vagrant_dir, "metadata.json")
        execWithRedirect("mv", ["-f", disk_img, joinpaths(vagrant_dir, "box.img")], raise_err=True)
        if opts.vagrant_metadata:
            shutil.copy2(opts.vagrant_metadata, metadata_path)
        else:
            create_vagrant_metadata(metadata_path)
        update_vagrant_metadata(metadata_path, disk_size)
        if opts.vagrantfile:
            shutil.copy2(opts.vagrantfile, joinpaths(vagrant_dir, "vagrantfile"))

        rc = mktar(vagrant_dir, disk_img, opts.compression, compress_args, selinux=False)
        if rc:
            raise InstallError("virt_install failed")
        shutil.rmtree(vagrant_dir)

    # For make_tar_disk, wrap the result in a tar file, and remove the original disk image.
    if opts.make_tar_disk:
        compress_args = []
        for arg in opts.compress_args:
            compress_args += arg.split(" ", 1)

        rc = mktar(disk_img, tar_img, opts.compression, compress_args, selinux=False)

        if rc:
            raise InstallError("virt_install mktar failed: rc=%s" % rc)

        os.unlink(disk_img)
