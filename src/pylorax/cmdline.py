#
# cmdline.py
#
# Copyright (C) 2016  Red Hat, Inc.
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
# Red Hat Author(s):  Brian C. Lane <bcl@redhat.com>

import os
import sys
import argparse

from pylorax import vernum

version = "{0}-{1}".format(os.path.basename(sys.argv[0]), vernum)

def lorax_parser(dracut_default=""):
    """ Return the ArgumentParser for lorax"""

    parser = argparse.ArgumentParser(description="Create the Anaconda boot.iso")

    # required arguments for image creation
    required = parser.add_argument_group("required arguments")
    required.add_argument("-p", "--product", help="product name", required=True, metavar="PRODUCT")
    required.add_argument("-v", "--version", help="version identifier", required=True, metavar="VERSION")
    required.add_argument("-r", "--release", help="release information", required=True, metavar="RELEASE")
    required.add_argument("-s", "--source", help="source repository (may be listed multiple times)",
                        metavar="REPOSITORY", action="append", default=[])
    required.add_argument("--repo", help="source dnf repository file", type=os.path.abspath,
                          dest="repos", metavar="REPOSITORY", action="append", default=[])

    # optional arguments
    optional = parser.add_argument_group("optional arguments")
    optional.add_argument("-m", "--mirrorlist",
                        help="mirrorlist repository (may be listed multiple times)",
                        metavar="REPOSITORY", action="append", default=[])
    optional.add_argument("-t", "--variant", default="",
                        help="variant name", metavar="VARIANT")
    optional.add_argument("-b", "--bugurl",
                        help="bug reporting URL for the product", metavar="URL",
                        default="your distribution provided bug reporting tool")
    optional.add_argument("--isfinal", help="",
                        action="store_true", default=False, dest="isfinal")
    optional.add_argument("-c", "--config", default="/etc/lorax/lorax.conf",
                        help="config file", metavar="CONFIGFILE")
    optional.add_argument("--proxy", default=None,
                          help="repo proxy url:port", metavar="HOST")
    optional.add_argument("-i", "--installpkgs", default=[],
                        action="append", metavar="PACKAGE",
                        help="package glob to install before runtime-install.tmpl runs. (may be listed multiple times)")
    optional.add_argument("-e", "--excludepkgs", default=[],
                        action="append", metavar="PACKAGE",
                        help="package glob to remove before runtime-install.tmpl runs. (may be listed multiple times)")
    optional.add_argument("--buildarch", default=None,
                        help="build architecture", metavar="ARCH")
    optional.add_argument("--volid", default=None,
                        help="volume id", metavar="VOLID")
    optional.add_argument("--macboot", help="",
                        action="store_true", default=True, dest="domacboot")
    optional.add_argument("--nomacboot", help="",
                        action="store_false", dest="domacboot")
    optional.add_argument("--noupgrade", help="",
                        action="store_false", default=True, dest="doupgrade")
    optional.add_argument("--logfile", default="./lorax.log", type=os.path.abspath,
                        help="Path to logfile")
    optional.add_argument("--tmp", default="/var/tmp/lorax",
                        help="Top level temporary directory" )
    optional.add_argument("--cachedir", default=None, type=os.path.abspath,
                        help="DNF cache directory. Default is a temporary dir.")
    optional.add_argument("--workdir", default=None, type=os.path.abspath,
                        help="Work directory, overrides --tmp. Default is a temporary dir under /var/tmp/lorax")
    optional.add_argument("--force", default=False, action="store_true",
                        help="Run even when the destination directory exists")
    optional.add_argument("--add-template", dest="add_templates",
                        action="append", help="Additional template for runtime image",
                        default=[])
    optional.add_argument("--add-template-var", dest="add_template_vars",
                        action="append", help="Set variable for runtime image template",
                        default=[])
    optional.add_argument("--add-arch-template", dest="add_arch_templates",
                        action="append", help="Additional template for architecture-specific image",
                        default=[])
    optional.add_argument("--add-arch-template-var", dest="add_arch_template_vars",
                        action="append", help="Set variable for architecture-specific image",
                        default=[])
    optional.add_argument("--noverify", action="store_false", default=True, dest="verify",
                        help="Do not verify the install root")
    optional.add_argument("--sharedir", metavar="SHAREDIR", type=os.path.abspath,
                          help="Directory containing all the templates. Overrides config file sharedir")
    optional.add_argument("--enablerepo", action="append", default=[], dest="enablerepos",
                          metavar="[repo]", help="Names of repos to enable")
    optional.add_argument("--disablerepo", action="append", default=[], dest="disablerepos",
                          metavar="[repo]", help="Names of repos to disable")
    optional.add_argument("--rootfs-size", type=int, default=2,
                          help="Size of root filesystem in GiB. Defaults to 2.")
    optional.add_argument("--noverifyssl", action="store_true", default=False,
                          help="Do not verify SSL certificates")
    optional.add_argument("--dnfplugin", action="append", default=[], dest="dnfplugins",
                          help="Enable a DNF plugin by name/glob, or * to enable all of them.")
    optional.add_argument("--squashfs-only", action="store_true", default=False,
                          help="Use a plain squashfs filesystem for the runtime.")
    optional.add_argument("--skip-branding", action="store_true", default=False,
                          help="Disable automatic branding package selection. Use --installpkgs to add custom branding.")

    # dracut arguments
    dracut_group = parser.add_argument_group("dracut arguments: (default: %s)" % dracut_default)
    dracut_group.add_argument("--dracut-conf",
                              help="Path to a dracut.conf file to use instead of the "
                                   "default arguments. See the dracut.conf(5) manpage.")
    dracut_group.add_argument("--dracut-arg", action="append", dest="dracut_args",
                              help="Argument to pass to dracut when "
                                   "rebuilding the initramfs. Pass this "
                                   "once for each argument. NOTE: this "
                                   "overrides the defaults.")

    # add the show version option
    parser.add_argument("-V", help="show program's version number and exit",
                      action="version", version=version)

    parser.add_argument("outputdir", help="Output directory", metavar="OUTPUTDIR", type=os.path.abspath)

    return parser


def lmc_parser(dracut_default=""):
    """ Return a ArgumentParser object for live-media-creator."""
    parser = argparse.ArgumentParser(description="Create Live Install Media",
                                     fromfile_prefix_chars="@")

    # These are mutually exclusive, one is required
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--make-iso", action="store_true",
                        help="Build a live iso")
    action.add_argument("--make-disk", action="store_true",
                        help="Build a partitioned disk image")
    action.add_argument("--make-fsimage", action="store_true",
                        help="Build a filesystem image")
    action.add_argument("--make-appliance", action="store_true",
                        help="Build an appliance image and XML description")
    action.add_argument("--make-ami", action="store_true",
                        help="Build an ami image")
    action.add_argument("--make-tar", action="store_true",
                        help="Build a tar of the root filesystem")
    action.add_argument("--make-tar-disk", action="store_true",
                        help="Build a tar of a partitioned disk image")
    action.add_argument("--make-pxe-live", action="store_true",
                        help="Build a live pxe boot squashfs image")
    action.add_argument("--make-ostree-live", action="store_true",
                        help="Build a live pxe boot squashfs image of Atomic Host")
    action.add_argument("--make-oci", action="store_true",
                        help="Build an Open Container Initiative image")
    action.add_argument("--make-vagrant", action="store_true",
                        help="Build a Vagrant Box image")

    parser.add_argument("--iso", type=os.path.abspath,
                        help="Anaconda installation .iso path to use for qemu")
    parser.add_argument("--iso-only", action="store_true",
                        help="Remove all iso creation artifacts except the boot.iso, "
                             "combine with --iso-name to rename the boot.iso")
    parser.add_argument("--iso-name", default=None,
                        help="Name of output iso file for --iso-only. Default is boot.iso")
    parser.add_argument("--ks", action="append", type=os.path.abspath,
                        help="Kickstart file defining the install.")
    parser.add_argument("--image-only", action="store_true",
                        help="Exit after creating fs/disk image.")

    parser.add_argument("--no-virt", action="store_true",
                        help="Run anaconda directly on host instead of using qemu")
    parser.add_argument("--proxy",
                        help="proxy URL to use for the install")
    parser.add_argument("--anaconda-arg", action="append", dest="anaconda_args",
                        help="Additional argument to pass to anaconda (no-virt "
                             "mode). Pass once for each argument")
    parser.add_argument("--armplatform",
                        help="the platform to use when creating images for ARM, "
                             "i.e., highbank, mvebu, omap, tegra, etc.")
    parser.add_argument("--location", default=None, type=os.path.abspath,
                        help="location of iso directory tree with initrd.img "
                             "and vmlinuz. Used to run qemu with a newer initrd "
                             "than the iso.")

    parser.add_argument("--logfile", default="./livemedia.log",
                        type=os.path.abspath,
                        help="Name and path for primary logfile, other logs will "
                             "be created in the same directory.")
    parser.add_argument("--lorax-templates", default=None,
                        type=os.path.abspath,
                        help="Path to mako templates for lorax")
    parser.add_argument("--tmp", default="/var/tmp", type=os.path.abspath,
                        help="Top level temporary directory")
    parser.add_argument("--resultdir", default=None, dest="result_dir",
                        type=os.path.abspath,
                        help="Directory to copy the resulting images and iso into. "
                             "Defaults to the temporary working directory")

    parser.add_argument("--macboot", action="store_true", default=True,
                        dest="domacboot")
    parser.add_argument("--nomacboot", action="store_false",
                        dest="domacboot")

    parser.add_argument("--extra-boot-args", default="", dest="extra_boot_args",
                        help="Extra arguments to add to the bootloader kernel cmdline in the templates")

    image_group = parser.add_argument_group("disk/fs image arguments")
    image_group.add_argument("--disk-image", type=os.path.abspath,
                             help="Path to existing disk image to use for creating final image.")
    image_group.add_argument("--keep-image", action="store_true",
                             help="Keep raw disk image after .iso creation")
    image_group.add_argument("--fs-image", type=os.path.abspath,
                             help="Path to existing filesystem image to use for creating final image.")
    image_group.add_argument("--image-name", default=None,
                             help="Name of output file to create. Used for tar, fs and disk image. Default is a random name.")
    image_group.add_argument("--tar-disk-name", default=None,
                             help="Name of the archive member for make-tar-disk.")
    image_group.add_argument("--fs-label", default="Anaconda",
                             help="Label to set on fsimage, default is 'Anaconda'")
    image_group.add_argument("--image-size-align", type=int, default=0,
                             help="Create a disk image with a size that is a multiple of this value in MiB.")
    image_group.add_argument("--image-type", default=None,
                             help="Create an image with qemu-img. See qemu-img --help for supported formats.")
    image_group.add_argument("--qemu-arg", action="append", dest="qemu_args", default=[],
                             help="Arguments to pass to qemu-img. Pass once for each argument, they will be used for ALL calls to qemu-img.")
    image_group.add_argument("--qcow2", action="store_true",
                             help="Create qcow2 image instead of raw sparse image when making disk images.")
    image_group.add_argument("--qcow2-arg", action="append", dest="qemu_args", default=[],
                             help="Arguments to pass to qemu-img. Pass once for each argument, they will be used for ALL calls to qemu-img.")
    image_group.add_argument("--compression", default="xz",
                             help="Compression binary for make-tar. xz, lzma, gzip, and bzip2 are supported. xz is the default.")
    image_group.add_argument("--compress-arg", action="append", dest="compress_args", default=[],
                             help="Arguments to pass to compression. Pass once for each argument")
    # Group of arguments for appliance creation
    app_group = parser.add_argument_group("appliance arguments")
    app_group.add_argument("--app-name", default=None,
                           help="Name of appliance to pass to template")
    app_group.add_argument("--app-template", default=None,
                           help="Path to template to use for appliance data.")
    app_group.add_argument("--app-file", default="appliance.xml",
                           help="Appliance template results file.")

    # Group of arguments to pass to qemu
    virt_group = parser.add_argument_group("qemu arguments")
    virt_group.add_argument("--ram", metavar="MEMORY", type=int, default=2048,
                            help="Memory to allocate for installer in megabytes.")
    virt_group.add_argument("--vcpus", type=int, default=None,
                            help="Passed to qemu -smp command")
    virt_group.add_argument("--vnc",
                            help="Passed to qemu -display command. eg. vnc=127.0.0.1:5, default is to "
                                 "choose the first unused vnc port.")
    virt_group.add_argument("--arch", default=None,
                            help="System arch to build for. Used to select qemu-system-* command. "
                                 "Defaults to qemu-system-<arch>")
    virt_group.add_argument("--kernel-args",
                            help="Additional argument to pass to the installation kernel")
    virt_group.add_argument("--ovmf-path", default="/usr/share/edk2/ovmf/",
                            help="Path to OVMF firmware")
    virt_group.add_argument("--virt-uefi", action="store_true", default=False,
                            help="Use OVMF firmware to boot the VM in UEFI mode")
    virt_group.add_argument("--no-kvm", action="store_true", default=False,
                            help="Skip using kvm with qemu even if it is available.")
    virt_group.add_argument("--with-rng", default="/dev/random",
                            help="RNG device for QEMU (none for no RNG)")

    # dracut arguments
    dracut_group = parser.add_argument_group("dracut arguments: (default: %s)" % dracut_default)
    dracut_group.add_argument("--dracut-conf",
                              help="Path to a dracut.conf file to use instead of the "
                                   "default arguments. See the dracut.conf(5) manpage.")
    dracut_group.add_argument("--dracut-arg", action="append", dest="dracut_args",
                              help="Argument to pass to dracut when "
                                   "rebuilding the initramfs. Pass this "
                                   "once for each argument. NOTE: this "
                                   "overrides the defaults.")

    # pxe to live arguments
    pxelive_group = parser.add_argument_group("pxe to live arguments")
    pxelive_group.add_argument("--live-rootfs-size", type=int, default=0,
                                help="Size of root filesystem of live image in GiB")
    pxelive_group.add_argument("--live-rootfs-keep-size", action="store_true",
                                help="Keep the original size of root filesystem in live image")

    # OCI specific commands
    oci_group = parser.add_argument_group("OCI arguments")
    oci_group.add_argument("--oci-config",
                              help="config.json OCI configuration file")
    oci_group.add_argument("--oci-runtime",
                              help="runtime.json OCI configuration file")

    # Vagrant specific commands
    vagrant_group = parser.add_argument_group("Vagrant arguments")
    vagrant_group.add_argument("--vagrant-metadata",
                               help="optional metadata.json file")
    vagrant_group.add_argument("--vagrantfile",
                               help="optional vagrantfile")

    parser.add_argument("--project", default="Linux",
                        help="substituted for @PROJECT@ in bootloader config files")
    parser.add_argument("--releasever", default="34",
                        help="substituted for @VERSION@ in bootloader config files")
    parser.add_argument("--volid", default=None, help="volume id")
    parser.add_argument("--squashfs-only", action="store_true", default=False,
                        help="Use a plain squashfs filesystem for the runtime.")
    parser.add_argument("--timeout", default=None, type=int,
                        help="Cancel installer after X minutes")

    # add the show version option
    parser.add_argument("-V", help="show program's version number and exit",
                      action="version", version=version)

    return parser
