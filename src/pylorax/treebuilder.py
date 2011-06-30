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

import os, re, glob, fnmatch
from os.path import basename, isdir, getsize
from subprocess import check_call, check_output, PIPE
from tempfile import NamedTemporaryFile

from sysutils import joinpaths, cpfile, mvfile, replace, remove, linktree
from yumhelper import *
from ltmpl import LoraxTemplate
from base import DataHolder
import imgutils

templatemap = {'i386':    'x86.tmpl',
               'x86_64':  'x86.tmpl',
               'ppc':     'ppc.tmpl',
               'ppc64':   'ppc.tmpl',
               'sparc':   'sparc.tmpl',
               'sparc64': 'sparc.tmpl',
               's390':    's390.tmpl',
               's390x':   's390.tmpl',
               }

def findkernels(root="/", kdir="boot"):
    # To find flavors, awk '/BuildKernel/ { print $4 }' kernel.spec
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

def brace_expand(s):
    if not ('{' in s and ',' in s and '}' in s):
        yield s
    else:
        right = s.find('}')
        left = s[:right].rfind('{')
        (prefix, choices, suffix) = (s[:left], s[left+1:right], s[right+1:])
        for choice in choices.split(','):
            for alt in brace_expand(prefix+choice+suffix):
                yield alt

def _glob(pathname, root="/", fatal=True):
    seen = set()
    rootlen = len(root)+1
    for g in brace_expand(pathname):
        for f in glob.iglob(joinpaths(root, g)):
            if f not in seen:
                seen.add(f)
                yield f[rootlen:] # remove the root to produce relative path
    if fatal and not seen:
        raise IOError, "nothing matching %s in %s" % (pathname, root)

def _exists(pathname, root=""):
    return True if _glob(pathname, root) else False

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

    def build(self):
        templatefile = templatemap[self.vars.arch.basearch]
        self._runner.run(templatefile, kernels=self.kernels)
        self.treeinfo_data = self.runner.results.treeinfo
        self.implantisomd5()

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

    def implantisomd5(self):
        for section, data in self.treeinfo_data.items():
            if 'boot.iso' in data:
                iso = joinpaths(self.vars.outroot, data['boot.iso'])
                check_call(["implantisomd5", iso])


# command notes:
# "install" and "exist" assume their first argument is in inroot
# everything else operates on outroot
# multiple args allowed: mkdir, treeinfo, runcmd, remove, replace
# globs accepted: chmod, install*, remove*, replace

class LoraxTemplateRunner(object):
    def __init__(self, inroot, outroot, yum=None, fatalerrors=False,
                                        templatedir=None, defaults={}):
        self.inroot = inroot
        self.outroot = outroot
        self.yum = yum
        self.fatalerrors = fatalerrors
        self.templatedir = templatedir
        # defaults starts with some builtin methods
        self.defaults = DataHolder(exists=lambda p: _exists(p, root=inroot),
                            glob=lambda g: _glob(g, root=root, fatal=False))
        self.defaults.update(defaults)
        self.results = DataHolder(treeinfo=dict()) # just treeinfo for now

    def _out(self, path):
        return joinpaths(self.outroot, path)
    def _in(self, path):
        return joinpaths(self.inroot, path)

    def _filelist(self, *pkgs):
        pkglist = self.yum.doPackageLists(pkgnarrow="installed", patterns=pkgs)
        return set([f for pkg in pkglist.installed for f in pkg.filelist])

    def run(self, templatefile, **variables):
        for k,v in self.defaults.items():
            variables.setdefault(k,v)
        logger.info("parsing %s", templatefile)
        t = LoraxTemplate(directories=[self.templatedir])
        commands = t.parse(templatefile, variables)
        self._run(commands)

    def _run(self, parsed_template):
        logger.info("running template commands")
        for (num, line) in enumerate(parsed_template,1):
            logger.debug("template line %i: %s", num, " ".join(line))
            (cmd, args) = (line[0], line[1:])
            try:
                # grab the method named in cmd and pass it the given arguments
                f = getattr(self, cmd, None)
                if f is None or cmd is 'run':
                    raise ValueError, "unknown command %s" % cmd
                f(*args)
            except Exception as e:
                logger.error("template command error: %s", str(line))
                if self.fatalerrors:
                    raise
                logger.error(str(e))

    def install(self, srcglob, dest):
        for src in _glob(self._in(srcglob)):
            cpfile(src, self._out(dest))

    def mkdir(self, *dirs):
        for d in dirs:
            d = self._out(d)
            if not isdir(d):
                os.makedirs(d)

    def replace(self, pat, repl, *fileglobs):
        for g in fileglobs:
            for f in _glob(self._out(g)):
                replace(f, pat, repl)

    def append(self, filename, data):
        with open(self._out(filename), "a") as fobj:
            fobj.write(data.decode('string_escape')+"\n")

    def treeinfo(self, section, key, *valuetoks):
        if section not in self.results.treeinfo:
            self.results.treeinfo[section] = dict()
        self.results.treeinfo[section][key] = " ".join(valuetoks)

    def installkernel(self, section, src, dest):
        self.install(src, dest)
        self.treeinfo(section, "kernel", dest)

    def installinitrd(self, section, src, dest):
        self.install(src, dest)
        self.treeinfo(section, "initrd", dest)

    def hardlink(self, src, dest):
        if isdir(self._out(dest)):
            dest = joinpaths(dest, basename(src))
        os.link(self._out(src), self._out(dest))

    def symlink(self, target, dest):
        if _exists(self._out(dest)):
            self.remove(dest)
        os.symlink(target, self._out(dest))

    def copy(self, src, dest):
        cpfile(self._out(src), self._out(dest))

    def copyif(self, src, dest):
        if _exists(self._out(src)):
            self.copy(src, dest)

    def move(self, src, dest):
        mvfile(self._out(src), self._out(dest))

    def moveif(self, src, dest):
        if _exists(self._out(src)):
            self.move(src, dest)

    def remove(self, *fileglobs):
        for g in fileglobs:
            for f in _glob(self._out(g), fatal=False):
                remove(f)

    def chmod(self, fileglob, mode):
        for f in _glob(self._out(fileglob)):
            os.chmod(f, int(mode,8))

    def gconfset(self, path, keytype, value, outfile=None):
        if outfile is None:
            outfile = self._out("etc/gconf/gconf.xml.defaults")
        check_call(["gconftool-2", "--direct",
                    "--config-source=xml:readwrite:%s" % outfile,
                    "--set", "--type", keytype, path, value])

    def log(self, msg):
        logger.info(msg)

    def runcmd(self, *cmdlist):
        '''Note that we need full paths for everything here'''
        chdir = lambda: None
        cmd = cmdlist
        if cmd[0].startswith("chdir="):
            dirname = cmd[0].split('=',1)[1]
            chdir = lambda: os.chdir(dirname)
            cmd = cmd[1:]
        check_call(cmd, preexec_fn=chdir)

    def installpkg(self, *pkgs):
        for p in pkgs:
            self.yum.install(pattern=p)

    def removepkg(self, *pkgs):
        # NOTE: "for p in pkgs: self.yum.remove(pattern=p)" traces back, so..
        filepaths = [f.lstrip('/') for f in self._filelist(*pkgs)]
        self.remove(*filepaths)

    def run_pkg_transaction(self):
        self.yum.buildTransaction()
        self.yum.repos.setProgressBar(LoraxDownloadCallback())
        self.yum.processTransaction(callback=LoraxTransactionCallback(),
                                    rpmDisplay=LoraxRpmCallback())
        self.yum.closeRpmDB()

    def removefrom(self, pkg, *globs):
        globset = set()
        for g in globs:
            globset.update(brace_expand(g))
        globs_re = re.compile("|".join([fnmatch.translate(g) for g in globset]))
        remove = filter(globs_re.match, self._filelist(pkg))
        logger.debug("removing %i files from %s", len(remove), pkg)
        self.remove(*remove)
