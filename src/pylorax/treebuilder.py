# treebuilder.py - handle arch-specific tree building stuff using templates
#
# Copyright (C) 2011-2015 Red Hat, Inc.
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
logger = logging.getLogger("pylorax.treebuilder")

import os, re
from os.path import basename
from shutil import copytree, copy2
from subprocess import CalledProcessError
from pathlib import Path
import itertools

from pylorax.sysutils import joinpaths, remove
from pylorax.base import DataHolder
from pylorax.ltmpl import LoraxTemplateRunner
import pylorax.imgutils as imgutils
from pylorax.executils import runcmd, runcmd_output, execWithCapture

templatemap = {
    'i386':    'x86.tmpl',
    'x86_64':  'x86.tmpl',
    'ppc64le': 'ppc64le.tmpl',
    's390':    's390.tmpl',
    's390x':   's390.tmpl',
    'aarch64': 'aarch64.tmpl',
    'arm':     'arm.tmpl',
    'armhfp':  'arm.tmpl',
}

def generate_module_info(moddir, outfile=None):
    def module_desc(mod):
        output = runcmd_output(["modinfo", "-F", "description", mod])
        return output.strip()
    def read_module_set(name):
        return set(l.strip() for l in open(joinpaths(moddir,name)) if ".ko" in l)
    modsets = {'scsi':read_module_set("modules.block"),
               'eth':read_module_set("modules.networking")}

    modinfo = list()
    for root, _dirs, files in os.walk(moddir):
        for modtype, modset in modsets.items():
            for mod in modset.intersection(files):  # modules in this dir
                (name, _ext) = os.path.splitext(mod) # foo.ko -> (foo, .ko)
                desc = module_desc(joinpaths(root,mod)) or "%s driver" % name
                modinfo.append(dict(name=name, type=modtype, desc=desc))

    out = open(outfile or joinpaths(moddir,"module-info"), "w")
    out.write("Version 0\n")
    for mod in sorted(modinfo, key=lambda m: m.get('name')):
        out.write('{name}\n\t{type}\n\t"{desc:.65}"\n'.format(**mod))

class RuntimeBuilder(object):
    '''Builds the anaconda runtime image.'''
    def __init__(self, product, arch, dbo, templatedir=None,
                 installpkgs=None, excludepkgs=None,
                 add_templates=None,
                 add_template_vars=None,
                 skip_branding=False):
        root = dbo.conf.installroot
        # use a copy of product so we can modify it locally
        product = product.copy()
        product.name = product.name.lower()
        self.vars = DataHolder(arch=arch, product=product, dbo=dbo, root=root,
                               basearch=arch.basearch, libdir=arch.libdir)
        self.dbo = dbo
        self._runner = LoraxTemplateRunner(inroot=root, outroot=root,
                                           dbo=dbo, templatedir=templatedir)
        self.add_templates = add_templates or []
        self.add_template_vars = add_template_vars or {}
        self._installpkgs = installpkgs or []
        self._excludepkgs = excludepkgs or []
        self._runner.defaults = self.vars
        self.dbo.reset()
        self._skip_branding = skip_branding

    def _install_branding(self):
        """Select the branding from the available 'system-release' packages
        The *best* way to control this is to have a single package in the repo provide 'system-release'
        When there are more than 1 package it will:
        - Make a list of the available packages
        - If variant is set look for a package ending with lower(variant) and use that
        - If there are one or more non-generic packages, use the first one after sorting
        """
        if self._skip_branding:
            return

        release = None
        q = self.dbo.sack.query()
        a = q.available()
        pkgs = sorted([p.name for p in a.filter(provides='system-release')
                                    if not p.name.startswith("generic")])
        if not pkgs:
            logger.error("No system-release packages found, could not get the release")
            return

        logger.debug("system-release packages: %s", pkgs)
        if self.vars.product.variant:
            variant = [p for p in pkgs if p.endswith("-"+self.vars.product.variant.lower())]
            if variant:
                release = variant[0]
        if not release:
            release = pkgs[0]

        # release
        logger.info('got release: %s', release)
        self._runner.installpkg(release)

        # logos
        release, _suffix = release.split('-', 1)
        self._runner.installpkg('%s-logos' % release)

    def install(self):
        '''Install packages and do initial setup with runtime-install.tmpl'''
        self._install_branding()
        if len(self._installpkgs) > 0:
            self._runner.installpkg(*self._installpkgs)
        if len(self._excludepkgs) > 0:
            self._runner.removepkg(*self._excludepkgs)
        self._runner.run("runtime-install.tmpl")
        for tmpl in self.add_templates:
            self._runner.run(tmpl, **self.add_template_vars)

    def writepkglists(self, pkglistdir):
        '''debugging data: write out lists of package contents'''
        if not os.path.isdir(pkglistdir):
            os.makedirs(pkglistdir)
        q = self.dbo.sack.query()
        for pkgobj in q.installed():
            with open(joinpaths(pkglistdir, pkgobj.name), "w") as fobj:
                for fname in pkgobj.files:
                    fobj.write("{0}\n".format(fname))

    def postinstall(self):
        '''Do some post-install setup work with runtime-postinstall.tmpl'''
        # copy configdir into runtime root beforehand
        configdir = joinpaths(self._runner.templatedir,"config_files")
        configdir_path = "tmp/config_files"
        fullpath = joinpaths(self.vars.root, configdir_path)
        if os.path.exists(fullpath):
            remove(fullpath)
        copytree(configdir, fullpath)
        self._runner.run("runtime-postinstall.tmpl", configdir=configdir_path)

    def cleanup(self):
        '''Remove unneeded packages and files with runtime-cleanup.tmpl'''
        self._runner.run("runtime-cleanup.tmpl")

    def verify(self):
        '''Ensure that contents of the installroot can run'''
        status = True

        ELF_MAGIC = b'\x7fELF'

        # Iterate over all files in /usr/bin and /usr/sbin
        # For ELF files, gather them into a list and we'll check them all at
        # the end. For files with a #!, check them as we go
        elf_files = []
        usr_bin = Path(self.vars.root + '/usr/bin')
        usr_sbin = Path(self.vars.root + '/usr/sbin')
        for path in (str(x) for x in itertools.chain(usr_bin.iterdir(), usr_sbin.iterdir()) \
                     if x.is_file()):
            with open(path, "rb") as f:
                magic = f.read(4)
                if magic == ELF_MAGIC:
                    # Save the path, minus the chroot prefix
                    elf_files.append(path[len(self.vars.root):])
                elif magic[:2] == b'#!':
                    # Reopen the file as text and read the first line.
                    # Open as latin-1 so that stray 8-bit characters don't make
                    # things blow up. We only really care about ASCII parts.
                    with open(path, "rt", encoding="latin-1") as f_text:
                        # Remove the #!, split on space, and take the first part
                        shabang = f_text.readline()[2:].split()[0]

                    # Does the path exist?
                    if not os.path.exists(self.vars.root + shabang):
                        logger.error('%s, needed by %s, does not exist', shabang, path)
                        status = False

        # Now, run ldd on all the ELF files
        # Just run ldd once on everything so it isn't logged a million times.
        # At least one thing in the list isn't going to be a dynamic executable,
        # so use execWithCapture to ignore the exit code.
        filename = ''
        for line in execWithCapture('ldd', elf_files, root=self.vars.root,
                log_output=False, filter_stderr=True).split('\n'):
            if line and not line[0].isspace():
                # New filename header, strip the : at the end and save
                filename = line[:-1]
            elif 'not found' in line:
                logger.error('%s, needed by %s, not found', line.split()[0], filename)
                status = False

        return status

    def writepkgsizes(self, pkgsizefile):
        '''debugging data: write a big list of pkg sizes'''
        fobj = open(pkgsizefile, "w")
        getsize = lambda f: os.lstat(f).st_size if os.path.exists(f) else 0
        q = self.dbo.sack.query()
        for p in sorted(q.installed()):
            pkgsize = sum(getsize(joinpaths(self.vars.root,f)) for f in p.files)
            fobj.write("{0.name}.{0.arch}: {1}\n".format(p, pkgsize))

    def generate_module_data(self):
        root = self.vars.root
        moddir = joinpaths(root, "lib/modules/")
        for kernel in findkernels(root=root):
            ksyms = joinpaths(root, "boot/System.map-%s" % kernel.version)
            logger.info("doing depmod and module-info for %s", kernel.version)
            runcmd(["depmod", "-a", "-F", ksyms, "-b", root, kernel.version])
            generate_module_info(moddir+kernel.version, outfile=moddir+"module-info")

    def create_squashfs_runtime(self, outfile="/var/tmp/squashfs.img", compression="xz", compressargs=None, size=2):
        """Create a plain squashfs runtime"""
        compressargs = compressargs or []
        os.makedirs(os.path.dirname(outfile))

        # squash the rootfs
        return imgutils.mksquashfs(self.vars.root, outfile, compression, compressargs)

    def create_ext4_runtime(self, outfile="/var/tmp/squashfs.img", compression="xz", compressargs=None, size=2):
        """Create a squashfs compressed ext4 runtime"""
        # make live rootfs image - must be named "LiveOS/rootfs.img" for dracut
        compressargs = compressargs or []
        workdir = joinpaths(os.path.dirname(outfile), "runtime-workdir")
        os.makedirs(joinpaths(workdir, "LiveOS"))

        # Catch problems with the rootfs being too small and clearly log them
        try:
            imgutils.mkrootfsimg(self.vars.root, joinpaths(workdir, "LiveOS/rootfs.img"),
                                 "Anaconda", size=size)
        except CalledProcessError as e:
            if e.stdout and "No space left on device" in e.stdout:
                logger.error("The rootfs ran out of space with size=%d", size)
            raise

        # squash the live rootfs and clean up workdir
        rc = imgutils.mksquashfs(workdir, outfile, compression, compressargs)
        remove(workdir)
        return rc

    def finished(self):
        """ Done using RuntimeBuilder

        Close the dnf base object
        """
        self.dbo.close()

class TreeBuilder(object):
    '''Builds the arch-specific boot images.
    inroot should be the installtree root (the newly-built runtime dir)'''
    def __init__(self, product, arch, inroot, outroot, runtime, isolabel, domacboot=True, doupgrade=True,
                 templatedir=None, add_templates=None, add_template_vars=None, workdir=None, extra_boot_args=""):

        # NOTE: if you pass an arg named "runtime" to a mako template it'll
        # clobber some mako internal variables - hence "runtime_img".
        self.vars = DataHolder(arch=arch, product=product, runtime_img=runtime,
                               runtime_base=basename(runtime),
                               inroot=inroot, outroot=outroot,
                               basearch=arch.basearch, libdir=arch.libdir,
                               isolabel=isolabel, udev=udev_escape, domacboot=domacboot, doupgrade=doupgrade,
                               workdir=workdir, lower=string_lower,
                               extra_boot_args=extra_boot_args)
        self._runner = LoraxTemplateRunner(inroot, outroot, templatedir=templatedir)
        self._runner.defaults = self.vars
        self.add_templates = add_templates or []
        self.add_template_vars = add_template_vars or {}
        self.templatedir = templatedir
        self.treeinfo_data = None

    @property
    def kernels(self):
        return findkernels(root=self.vars.inroot)

    def rebuild_initrds(self, add_args=None, backup="", prefix=""):
        '''Rebuild all the initrds in the tree. If backup is specified, each
        initrd will be renamed with backup as a suffix before rebuilding.
        If backup is empty, the existing initrd files will be overwritten.
        If suffix is specified, the existing initrd is untouched and a new
        image is built with the filename "${prefix}-${kernel.version}.img"

        If the initrd doesn't exist its name will be created based on the
        name of the kernel.
        '''
        add_args = add_args or []
        dracut = ["dracut", "--nomdadmconf", "--nolvmconf"] + add_args
        if not backup:
            dracut.append("--force")

        if not self.kernels:
            raise Exception("No kernels found, cannot rebuild_initrds")

        for kernel in self.kernels:
            if prefix:
                idir = os.path.dirname(kernel.path)
                outfile = joinpaths(idir, prefix+'-'+kernel.version+'.img')
            elif hasattr(kernel, "initrd"):
                # If there is an existing initrd, use that
                outfile = kernel.initrd.path
            else:
                # Construct an initrd from the kernel name
                outfile = kernel.path.replace("vmlinuz-", "initrd-") + ".img"
            logger.info("rebuilding %s", outfile)
            logger.info("dracut warnings about /proc are safe to ignore")

            if backup:
                initrd = joinpaths(self.vars.inroot, outfile)
                if os.path.exists(initrd):
                    os.rename(initrd, initrd + backup)
            cmd = dracut + [outfile, kernel.version]
            runcmd(cmd, root=self.vars.inroot)

    def build(self):
        templatefile = templatemap[self.vars.arch.basearch]
        for tmpl in self.add_templates:
            self._runner.run(tmpl, **self.add_template_vars)
        self._runner.run(templatefile, kernels=self.kernels)
        self.treeinfo_data = self._runner.results.treeinfo
        self.implantisomd5()

    def implantisomd5(self):
        for _section, data in self.treeinfo_data.items():
            if 'boot.iso' in data:
                iso = joinpaths(self.vars.outroot, data['boot.iso'])
                runcmd(["implantisomd5", iso])

    @property
    def dracut_hooks_path(self):
        """ Return the path to the lorax dracut hooks scripts

            Use the configured share dir if it is setup,
            otherwise default to /usr/share/lorax/dracut_hooks
        """
        if self.templatedir:
            return joinpaths(self.templatedir, "dracut_hooks")
        else:
            return "/usr/share/lorax/dracut_hooks"

    def copy_dracut_hooks(self, hooks):
        """ Copy the hook scripts in hooks into the installroot's /tmp/
        and return a list of commands to pass to dracut when creating the
        initramfs

        hooks is a list of tuples with the name of the hook script and the
        target dracut hook directory
        (eg. [("99anaconda-copy-ks.sh", "/lib/dracut/hooks/pre-pivot")])
        """
        dracut_commands = []
        for hook_script, dracut_path in hooks:
            src = joinpaths(self.dracut_hooks_path, hook_script)
            if not os.path.exists(src):
                logger.error("Missing lorax dracut hook script %s", (src))
                continue
            dst = joinpaths(self.vars.inroot, "/tmp/", hook_script)
            copy2(src, dst)
            dracut_commands += ["--include", joinpaths("/tmp/", hook_script),
                                dracut_path]
        return dracut_commands

#### TreeBuilder helper functions

def findkernels(root="/", kdir="boot"):
    # To find possible flavors, awk '/BuildKernel/ { print $4 }' kernel.spec
    flavors = ('debug', 'PAE', 'PAEdebug', 'smp', 'xen', 'lpae')
    kre = re.compile(r"vmlinuz-(?P<version>.+?\.(?P<arch>[a-z0-9_]+)"
                     r"(.(?P<flavor>{0}))?)$".format("|".join(flavors)))
    kernels = []
    bootfiles = os.listdir(joinpaths(root, kdir))
    for f in bootfiles:
        match = kre.match(f)
        if match:
            kernel = DataHolder(path=joinpaths(kdir, f))
            kernel.update(match.groupdict()) # sets version, arch, flavor
            kernels.append(kernel)

    # look for associated initrd/initramfs/etc.
    for kernel in kernels:
        for f in bootfiles:
            if f.endswith('-'+kernel.version+'.img'):
                imgtype, _rest = f.split('-',1)
                # special backwards-compat case
                if imgtype == 'initramfs':
                    imgtype = 'initrd'
                kernel[imgtype] = DataHolder(path=joinpaths(kdir, f))

    logger.debug("kernels=%s", kernels)
    return kernels

# udev whitelist: 'a-zA-Z0-9#+.:=@_-' (see is_whitelisted in libudev-util.c)
udev_blacklist=' !"$%&\'()*,/;<>?[\\]^`{|}~' # ASCII printable, minus whitelist
udev_blacklist += ''.join(chr(i) for i in range(32)) # ASCII non-printable
def udev_escape(label):
    out = ''
    for ch in label:
        out += ch if ch not in udev_blacklist else '\\x%02x' % ord(ch)
    return out

def string_lower(string):
    """ Return a lowercase string.

    :param string: String to lowercase

    This is used as a filter in the templates.
    """
    return string.lower()
