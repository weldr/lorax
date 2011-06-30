#
# ltmpl.py
#
# Copyright (C) 2009  Red Hat, Inc.
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
# Red Hat Author(s):  Martin Gracik <mgracik@redhat.com>
#                     Will Woods <wwoods@redhat.com>
#

import logging
logger = logging.getLogger("pylorax.ltmpl")

import os, re, glob, shlex, fnmatch
from os.path import basename, isdir
from subprocess import check_call

from sysutils import joinpaths, cpfile, mvfile, replace, remove
from yumhelper import * # Lorax*Callback classes
from base import DataHolder

from mako.lookup import TemplateLookup
from mako.exceptions import text_error_template

class LoraxTemplate(object):
    def __init__(self, directories=["/usr/share/lorax"]):
        # we have to add ["/"] to the template lookup directories or the
        # file includes won't work properly for absolute paths
        self.directories = ["/"] + directories

    def parse(self, template_file, variables):
        lookup = TemplateLookup(directories=self.directories)
        template = lookup.get_template(template_file)

        try:
            textbuf = template.render(**variables)
        except:
            print text_error_template().render()
            raise SystemExit(2)

        # split, strip and remove empty lines
        lines = textbuf.splitlines()
        lines = map(lambda line: line.strip(), lines)
        lines = filter(lambda line: line, lines)

        # remove comments
        lines = filter(lambda line: not line.startswith("#"), lines)

        # mako template now returns unicode strings
        lines = map(lambda line: line.encode("ascii"), lines)

        # split with shlex
        lines = map(shlex.split, lines)

        self.lines = lines
        return lines

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

def rglob(pathname, root="/", fatal=False):
    seen = set()
    rootlen = len(root)+1
    for g in brace_expand(pathname):
        for f in glob.iglob(joinpaths(root, g)):
            if f not in seen:
                seen.add(f)
                yield f[rootlen:] # remove the root to produce relative path
    if fatal and not seen:
        raise IOError, "nothing matching %s in %s" % (pathname, root)

def rexists(pathname, root=""):
    return True if rglob(pathname, root) else False

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
        # some builtin methods
        self.builtins = DataHolder(exists=lambda p: rexists(p, root=inroot),
                                   glob=lambda g: list(rglob(g, root=inroot)))
        self.defaults = defaults
        self.results = DataHolder(treeinfo=dict()) # just treeinfo for now

    def _out(self, path):
        return joinpaths(self.outroot, path)
    def _in(self, path):
        return joinpaths(self.inroot, path)

    def _filelist(self, *pkgs):
        pkglist = self.yum.doPackageLists(pkgnarrow="installed", patterns=pkgs)
        return set([f for pkg in pkglist.installed for f in pkg.filelist])

    def run(self, templatefile, **variables):
        for k,v in self.defaults.items() + self.builtins.items():
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
        for src in rglob(self._in(srcglob), fatal=True):
            cpfile(src, self._out(dest))

    def mkdir(self, *dirs):
        for d in dirs:
            d = self._out(d)
            if not isdir(d):
                os.makedirs(d)

    def replace(self, pat, repl, *fileglobs):
        match = False
        for g in fileglobs:
            for f in rglob(self._out(g)):
                match = True
                replace(f, pat, repl)
        if not match:
            raise IOError, "no files matched %s" % " ".join(fileglobs)

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
        if rexists(self._out(dest)):
            self.remove(dest)
        os.symlink(target, self._out(dest))

    def copy(self, src, dest):
        cpfile(self._out(src), self._out(dest))

    def copyif(self, src, dest):
        if rexists(self._out(src)):
            self.copy(src, dest)

    def move(self, src, dest):
        mvfile(self._out(src), self._out(dest))

    def moveif(self, src, dest):
        if rexists(self._out(src)):
            self.move(src, dest)

    def remove(self, *fileglobs):
        for g in fileglobs:
            for f in rglob(self._out(g)):
                remove(f)

    def chmod(self, fileglob, mode):
        for f in rglob(self._out(fileglob), fatal=True):
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
