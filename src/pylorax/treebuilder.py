# treebuilder.py - handle arch-specific tree building stuff using templates
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
logger = logging.getLogger("pylorax.treebuilder")

import os, re
from os.path import basename, isdir
from subprocess import check_call, check_output

from sysutils import joinpaths, remove, linktree
from base import DataHolder
from ltmpl import LoraxTemplateRunner
import imgutils

templatemap = {
    'i386':    'x86.tmpl',
    'x86_64':  'x86.tmpl',
    'ppc':     'ppc.tmpl',
    'ppc64':   'ppc.tmpl',
    'sparc':   'sparc.tmpl',
    'sparc64': 'sparc.tmpl',
    's390':    's390.tmpl',
    's390x':   's390.tmpl',
}

class RuntimeBuilder(object):
    '''Builds the anaconda runtime image.'''
    def __init__(self, product, arch, yum, templatedir=None):
        root = yum.conf.installroot
        # use a copy of product so we can modify it locally
        product = product.copy()
        product.name = product.name.lower()
        self.vars = DataHolder(arch=arch, product=product, yum=yum, root=root,
                               basearch=arch.basearch, libdir=arch.libdir)
        self.yum = yum
        self._runner = LoraxTemplateRunner(inroot=root, outroot=root, yum=yum)
        self._runner.templatedir = templatedir
        self._runner.defaults = self.vars

    def install(self):
        '''Install packages and do initial setup with runtime-install.tmpl'''
        self._runner.run("runtime-install.tmpl")

    def postinstall(self, configdir="/usr/share/lorax/config_files"):
        '''Do some post-install setup work with runtime-postinstall.tmpl'''
        # link configdir into runtime root beforehand
        configdir_path = "tmp/config_files"
        fullpath = joinpaths(self.vars.root, configdir_path)
        if os.path.exists(fullpath):
            remove(fullpath)
        linktree(configdir, fullpath)
        self._runner.run("runtime-postinstall.tmpl", configdir=configdir_path)

    def cleanup(self):
        '''Remove unneeded packages and files with runtime-cleanup.tmpl'''
        # get removelocales list first
        localedir = joinpaths(self.vars.root, "usr/share/locale")
        langtable = joinpaths(self.vars.root, "usr/share/anaconda/lang-table")
        locales = set([d for d in os.listdir(localedir) if isdir(joinpaths(localedir,d))])
        keeplocales = [line.split()[1] for line in open(langtable)]
        removelocales = locales.difference(keeplocales)
        self._runner.run("runtime-cleanup.tmpl", removelocales=removelocales)

    def create_runtime(self, outfile="/tmp/squashfs.img"):
        # make live rootfs image - must be named "LiveOS/rootfs.img" for dracut
        workdir = joinpaths(os.path.dirname(outfile), "runtime-workdir")
        fssize = 2 * (1024*1024*1024) # 2GB sparse file compresses down to nothin'
        os.makedirs(joinpaths(workdir, "LiveOS"))
        imgutils.mkext4img(self.vars.root, joinpaths(workdir, "LiveOS/rootfs.img"),
                           label="Anaconda", size=fssize)
        # squash the live rootfs and clean up workdir
        imgutils.mksquashfs(workdir, outfile)
        remove(workdir)

class TreeBuilder(object):
    '''Builds the arch-specific boot images.
    inroot should be the installtree root (the newly-built runtime dir)'''
    def __init__(self, product, arch, inroot, outroot, runtime, templatedir=None):
        # NOTE: if you pass an arg named "runtime" to a mako template it'll
        # clobber some mako internal variables - hence "runtime_img".
        self.vars = DataHolder(arch=arch, product=product, runtime_img=runtime,
                               inroot=inroot, outroot=outroot,
                               basearch=arch.basearch, libdir=arch.libdir,
                               udev_escape=udev_escape)
        self._runner = LoraxTemplateRunner(inroot, outroot)
        self._runner.templatedir = templatedir
        self._runner.defaults = self.vars

    @property
    def kernels(self):
        return findkernels(root=self.vars.inroot)

    def generate_module_data(self):
        inroot = self.vars.inroot
        for kernel in self.kernels:
            kver = kernel.version
            ksyms = joinpaths(inroot, "boot/System.map-%s" % kver)
            logger.info("doing depmod and module-info for %s", kver)
            check_call(["depmod", "-a", "-F", ksyms, "-b", inroot, kver])
            generate_module_info(joinpaths(inroot, "modules", kver))

    def rebuild_initrds(self, add_args=[], backup=""):
        '''Rebuild all the initrds in the tree. If backup is specified, each
        initrd will be renamed with backup as a suffix before rebuilding.
        If backup is empty, the existing initrd files will be overwritten.'''
        dracut = ["/sbin/dracut", "--nomdadmconf", "--nolvmconf"] + add_args
        if not backup:
            dracut.append("--force")
        # XXX FIXME: add anaconda dracut module!
        for kernel in self.kernels:
            logger.info("rebuilding %s", kernel.initrd.path)
            if backup:
                initrd = joinpaths(self.vars.inroot, kernel.initrd.path)
                os.rename(initrd, initrd + backup)
            check_call(["chroot", self.vars.inroot] + \
                       dracut + [kernel.initrd.path, kernel.version])

    def build(self):
        templatefile = templatemap[self.vars.arch.basearch]
        self._runner.run(templatefile, kernels=self.kernels)
        self.treeinfo_data = self._runner.results.treeinfo
        self.implantisomd5()

    def implantisomd5(self):
        for section, data in self.treeinfo_data.items():
            if 'boot.iso' in data:
                iso = joinpaths(self.vars.outroot, data['boot.iso'])
                check_call(["implantisomd5", iso])

#### TreeBuilder helper functions

def findkernels(root="/", kdir="boot"):
    # To find possible flavors, awk '/BuildKernel/ { print $4 }' kernel.spec
    flavors = ('debug', 'PAE', 'PAEdebug', 'smp', 'xen')
    kre = re.compile(r"vmlinuz-(?P<version>.+?\.(?P<arch>[a-z0-9_]+)"
                     r"(\.(?P<flavor>{0}))?)$".format("|".join(flavors)))
    kernels = []
    for f in os.listdir(joinpaths(root, kdir)):
        match = kre.match(f)
        if match:
            kernel = DataHolder(path=joinpaths(kdir, f))
            kernel.update(match.groupdict()) # sets version, arch, flavor
            kernels.append(kernel)

    # look for associated initrd/initramfs
    for kernel in kernels:
        # NOTE: if both exist, the last one found will win
        for imgname in ("initrd", "initramfs"):
            i = kernel.path.replace("vmlinuz", imgname, 1) + ".img"
            if os.path.exists(joinpaths(root, i)):
                kernel.initrd = DataHolder(path=i)

    return kernels

def generate_module_info(moddir, outfile=None):
    def module_desc(mod):
        return check_output(["modinfo", "-F", "description", mod]).strip()
    def read_module_set(name):
        return set(l.strip() for l in open(joinpaths(moddir,name)) if ".ko" in l)
    modsets = {'scsi':read_module_set("modules.block"),
               'eth':read_module_set("modules.networking")}

    modinfo = list()
    for root, dirs, files in os.walk(moddir):
        for modtype, modset in modsets.items():
            for mod in modset.intersection(files):  # modules in this dir
                (name, ext) = os.path.splitext(mod) # foo.ko -> (foo, .ko)
                desc = module_desc(joinpaths(root,mod)) or "%s driver" % name
                modinfo.append(dict(name=name, type=modtype, desc=desc))

    out = open(outfile or joinpaths(moddir,"module-info"), "w")
    for mod in sorted(modinfo, key=lambda m: m.get('name')):
        out.write('{name}\n\t{type}\n\t"{desc:.65}"\n'.format(**mod))

# udev whitelist: 'a-zA-Z0-9#+.:=@_-' (see is_whitelisted in libudev-util.c)
udev_blacklist=' !"$%&\'()*,/;<>?[\\]^`{|}~' # ASCII printable, minus whitelist
udev_blacklist += ''.join(chr(i) for i in range(32)) # ASCII non-printable
def udev_escape(label):
    out = u''
    for ch in label.decode('utf8'):
        out += ch if ch not in udev_blacklist else u'\\x%02x' % ord(ch)
    return out.encode('utf8')
