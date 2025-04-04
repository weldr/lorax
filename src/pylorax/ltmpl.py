#
# ltmpl.py
#
# Copyright (C) 2009-2018  Red Hat, Inc.
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
from subprocess import CalledProcessError
import shutil

from pylorax.sysutils import joinpaths, cpfile, mvfile, replace, remove
from pylorax.dnfhelper import LoraxDownloadCallback, LoraxRpmCallback
from pylorax.base import DataHolder
from pylorax.executils import runcmd, runcmd_output
from pylorax.imgutils import mkcpio, ProcMount

import collections.abc
from mako.lookup import TemplateLookup
from mako.exceptions import text_error_template
import sys, traceback
import struct

import libdnf5 as dnf5
from libdnf5.base import GoalProblem_NO_PROBLEM as NO_PROBLEM
from libdnf5.common import QueryCmp_EQ as EQ
action_is_inbound = dnf5.base.transaction.transaction_item_action_is_inbound


class LoraxTemplate(object):
    def __init__(self, directories=None):
        directories = directories or ["/usr/share/lorax"]
        # we have to add ["/"] to the template lookup directories or the
        # file includes won't work properly for absolute paths
        self.directories = ["/"] + directories

    def parse(self, template_file, variables):
        lookup = TemplateLookup(directories=self.directories)
        template = lookup.get_template(template_file)

        try:
            textbuf = template.render(**variables)
        except:
            logger.error("Problem rendering %s (%s):", template_file, variables)
            logger.error(text_error_template().render())
            raise

        # split, strip and remove empty lines
        lines = textbuf.splitlines()
        lines = [line.strip() for line in lines]
        lines = [line for line in lines if line]

        # remove comments
        lines = [line for line in lines if not line.startswith("#")]

        # split with shlex and perform brace expansion. This can fail, so we unroll the loop
        # for better error reporting.
        expanded_lines = []
        try:
            for line in lines:
                expanded_lines.append(split_and_expand(line))
        except Exception as e:
            logger.error('shlex error processing "%s": %s', line, str(e))
            raise
        return expanded_lines

def split_and_expand(line):
    return [exp for word in shlex.split(line) for exp in brace_expand(word)]

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
    for f in glob.iglob(joinpaths(root, pathname)):
        if f not in seen:
            seen.add(f)
            yield f[rootlen:] # remove the root to produce relative path
    if fatal and not seen:
        raise IOError("nothing matching %s in %s" % (pathname, root))

def rexists(pathname, root=""):
    # Generator is always True, even with no values;
    # bool(rglob(...)) won't work here.
    for _path in rglob(pathname, root):
        return True
    return False

class TemplateRunner(object):
    '''
    This class parses and executes Lorax templates. Sample usage:

      # install a bunch of packages
      runner = LoraxTemplateRunner(inroot=rundir, outroot=rundir, dbo=dnf_obj, basearch="x86_64")
      runner.run("install-packages.ltmpl")

    NOTES:

    * Parsing procedure is roughly:
      1. Mako template expansion (on the whole file)
      2. For each line of the result,

        a. Whitespace splitting (using shlex.split())
        b. Brace expansion (using brace_expand())
        c. If the first token is the name of a function, call that function
           with the rest of the line as arguments

    * Parsing and execution are *separate* passes - so you can't use the result
      of a command in an %if statement (or any other control statements)!
    '''
    def __init__(self, fatalerrors=True, templatedir=None, defaults=None, builtins=None):
        self.fatalerrors = fatalerrors
        self.templatedir = templatedir or "/usr/share/lorax"
        self.templatefile = None
        self.builtins = builtins or {}
        self.defaults = defaults or {}


    def run(self, templatefile, **variables):
        for k,v in list(self.defaults.items()) + list(self.builtins.items()):
            variables.setdefault(k,v)
        logger.debug("executing %s with variables=%s", templatefile, variables)
        self.templatefile = templatefile
        t = LoraxTemplate(directories=[self.templatedir])
        commands = t.parse(templatefile, variables)
        self._run(commands)


    def _run(self, parsed_template):
        logger.info("running %s", self.templatefile)
        for (num, line) in enumerate(parsed_template,1):
            logger.debug("template line %i: %s", num, " ".join(line))
            skiperror = False
            (cmd, args) = (line[0], line[1:])
            # Following Makefile convention, if the command is prefixed with
            # a dash ('-'), we'll ignore any errors on that line.
            if cmd.startswith('-'):
                cmd = cmd[1:]
                skiperror = True
            try:
                # grab the method named in cmd and pass it the given arguments
                f = getattr(self, cmd, None)
                if cmd[0] == '_' or cmd == 'run' or not isinstance(f, collections.abc.Callable):
                    raise ValueError("unknown command %s" % cmd)
                f(*args)
            except Exception: # pylint: disable=broad-except
                if skiperror:
                    logger.debug("ignoring error")
                    continue
                logger.error("template command error in %s:", self.templatefile)
                logger.error("  %s", " ".join(line))
                # format the exception traceback
                exclines = traceback.format_exception(*sys.exc_info())
                # skip the bit about "ltmpl.py, in _run()" - we know that
                exclines.pop(1)
                # log the "ErrorType: this is what happened" line
                logger.error("  %s", exclines[-1].strip())
                # and log the entire traceback to the debug log
                for _line in ''.join(exclines).splitlines():
                    logger.debug("  %s", _line)
                if self.fatalerrors:
                    raise


class InstallpkgMixin:
    """Helper class used with Runner classes"""
    def _pkgver(self, pkg_spec):
        """
        Helper to parse package version compare operators

        Returns a list of matching package objects or an empty list

        Examples:
          "bash>4.01"
          "tmux>=3.1.4-5"
          "grub2<2.06"
        """
        query = dnf5.rpm.PackageQuery(self.dbo)

        # Use default settings - https://dnf5.readthedocs.io/en/latest/api/c%2B%2B/libdnf5_goal_elements.html#goal-structures-and-enums
        settings = dnf5.base.ResolveSpecSettings()

        # Does it contain comparison operators?
        if any(g for g in ['=', '<', '>', '!'] if g in pkg_spec):
            pcv = re.split(r'([!<>=]+)', pkg_spec)
            if not pcv[0]:
                raise RuntimeError("Missing package name")
            if not pcv[-1]:
                raise RuntimeError("Missing version")
            if len(pcv) != 3:
                raise RuntimeError("Too many comparisons")

            # These are not supported, but dnf5 doesn't raise any errors, just returns no results
            if pcv[1] in ("!=", "<>"):
                raise RuntimeError(f"libdnf5 does not support using '{pcv[1]}' to compare versions")
            if pcv[1] in ("<<", ">>"):
                raise RuntimeError(f"Unknown comparison '{pcv[1]}' operator")

            # It wants a single '=' not double...
            if pcv[1] == "==":
                pcv[1] = "="

            # DNF wants spaces which we can't support in the template, rebuild the spec
            # with them.
            pkg_spec = " ".join(pcv)

        query.resolve_pkg_spec(pkg_spec, settings, False)

        # Filter out other arches, list should include basearch and noarch
        query.filter_arch(self._filter_arches)

        # MUST be after the comparison filters. Otherwise it will only return
        # the latest, not the latest of the filtered results.
        query.filter_latest_evr()

        # Filter based on repo priority. Except that if they are the same priority it returns
        # all of them :/
        query.filter_priority()
        return list(query)


    def installpkg(self, *pkgs):
        '''
        installpkg [--required|--optional] [--except PKGGLOB [--except PKGGLOB ...]] PKGGLOB [PKGGLOB ...]
          Request installation of all packages matching the given globs.
          Note that this is just a *request* - nothing is *actually* installed
          until the 'run_pkg_transaction' command is given.

          The non-except PKGGLOB can contain a version comparison. This should
          not be used as a substitute for package dependencies, it should be
          used to enforce installation of tools required by the templates. eg.
          grub2 changed the font location in 2.06-2 so the current templates
          require grub2 to be 2.06-2 or later.

          installpkg tmux>=2.8 bash=5.0.0-1

          It supports the =,!=,>,>=,<,<= operators. == is an alias for =, and
          <> is an alias for !=

          There should be no spaces between the package name, the compare
          operator, and the version.

          NOTE: When testing for equality you must include the version AND
          release, otherwise it won't match anything.

          --required is now the default. If the PKGGLOB can be missing pass --optional
        '''
        if pkgs[0] == '--optional':
            pkgs = pkgs[1:]
            required = False
        elif pkgs[0] == '--required':
            pkgs = pkgs[1:]
            required = True
        else:
            required = True

        excludes = []
        while '--except' in pkgs:
            idx = pkgs.index('--except')
            if len(pkgs) == idx+1:
                raise ValueError("installpkg needs an argument after --except")

            # TODO: Check for bare version compare operators
            excludes.append(pkgs[idx+1])
            pkgs = pkgs[:idx] + pkgs[idx+2:]

        errors = False
        for pkg in pkgs:
            # Did a version compare operatore end up in the list?
            if pkg[0] in ['=', '<', '>', '!']:
                raise RuntimeError("Version compare operators cannot be surrounded by spaces")

            try:
## XXX TODO Update the description here
                # Start by using Subject to generate a package query, which will
                # give us a query object similar to what dbo.install would select,
                # minus the handling for multilib. This query may contain
                # multiple arches. Pull the package names out of that, filter any
                # that match the excludes patterns, and pass those names back to
                # dbo.install to do the actual, arch and version and multilib
                # aware, package selction.

                # dnf queries don't have a concept of negative globs which is why
                # the filtering is done the hard way.

                # Get the latest package, or package matching the selected version
                pkgobjs = self._pkgver(pkg)
                if not pkgobjs:
                    raise RuntimeError(f"no package matched {pkg}")

                ## REMOVE DUPLICATES
                ## If there are duplicate packages from different repositories with the same
                ## priority they will be listed more than once. This is especially bad with
                ## globs like *-firmware
                ##
                ## ASSUME the same nevra is the same package, no matter what repo it comes
                ## from.
                nodupes = dict(zip([p.get_full_nevra() for p in pkgobjs], pkgobjs))
                pkgobjs = nodupes.values()

                # Apply excludes to the name only
                for exclude in excludes:
                    pkgobjs = [p for p in pkgobjs if not fnmatch.fnmatch(p.get_name(), exclude)]

                # If the request is a glob or returns more than one package, expand it in the log
                if len(pkgobjs) > 1 or any(g for g in ['*','?','.'] if g in pkg):
                    logger.info("installpkg: %s expands to %s", pkg, ",".join(p.get_nevra() for p in pkgobjs))

                for p in pkgobjs:
                    try:
                        # Pass them to dnf as NEVRA strings, duplicates are handled differntly
                        # than when they are passed as objects. See:
                        # https://github.com/rpm-software-management/dnf5/issues/1090#issuecomment-1873837189
                        # With the dupe removal code above this isn't strictly needed, but it should
                        # prevent problems if two separate install commands try to add the same
                        # package.
                        self.goal.add_rpm_install(p.get_full_nevra())
                    except Exception as e: # pylint: disable=broad-except
                        if required:
                            raise
                        # Not required, log it and continue processing pkgs
                        logger.error("installpkg %s failed: %s", p.get_nevra(), str(e))

            except Exception as e: # pylint: disable=broad-except
                logger.error("installpkg %s failed: %s", pkg, str(e))
                errors = True

        if errors and required:
            raise RuntimeError("Required installpkg failed.")


# TODO: operate inside an actual chroot for safety? Not that RPM bothers..
class LoraxTemplateRunner(TemplateRunner, InstallpkgMixin):
    '''
    This class parses and executes Lorax templates. Sample usage:

      # install a bunch of packages
      runner = LoraxTemplateRunner(inroot=rundir, outroot=rundir, dbo=dnf_obj, basearch="x86_64")
      runner.run("install-packages.ltmpl")

      # modify a runtime dir
      runner = LoraxTemplateRunner(inroot=rundir, outroot=newrun)
      runner.run("runtime-transmogrify.ltmpl")

    NOTES:

    * Commands that run external programs (e.g. systemctl) currently use
      the *host*'s copy of that program, which may cause problems if there's a
      big enough difference between the host and the image you're modifying.

    * The commands are not executed under a real chroot, so absolute symlinks
      will point *outside* the inroot/outroot. Be careful with symlinks!

    ADDING NEW COMMANDS:

    * Each template command is just a method of the LoraxTemplateRunner
      object - so adding a new command is as easy as adding a new function.

    * Each function gets arguments that correspond to the rest of the tokens
      on that line (after word splitting and brace expansion)

    * Commands should raise exceptions for errors - don't use sys.exit()
    '''
    def __init__(self, inroot, outroot, dbo=None, fatalerrors=True,
                                        templatedir=None, defaults=None, basearch=None):
        self.inroot = inroot
        self.outroot = outroot
        self.dbo = dbo
        self.transaction = None
        if dbo:
            self.goal = dnf5.base.Goal(self.dbo)
        else:
            self.goal = None
        builtins = DataHolder(exists=lambda p: rexists(p, root=inroot),
                              glob=lambda g: list(rglob(g, root=inroot)))
        self.results = DataHolder(treeinfo=dict()) # just treeinfo for now

        # Setup arch filter for package query
        self._filter_arches = ["noarch"]
        if basearch:
            self._filter_arches.append(basearch)

        super(LoraxTemplateRunner, self).__init__(fatalerrors, templatedir, defaults, builtins)
        # TODO: set up custom logger with a filter to add line info

    def _out(self, path):
        return joinpaths(self.outroot, path)
    def _in(self, path):
        return joinpaths(self.inroot, path)

    def _filelist(self, *pkg_specs):
        """ Return the list of files in the packages matching the globs """
        # libdnf5's filter_installed query will not work unless the base it reset and reloaded.
        # Instead we use the transaction that was run, and examine the inbound transaction
        # packages from get_transaction_packages()
        if self.transaction is None:
            raise RuntimeError("Transaction needs to be run before calling _filelists")

        pkglist = []
        for tp in self.transaction.get_transaction_packages():
            if not action_is_inbound(tp.get_action()):
                continue

            pkg = tp.get_package()
            if any(fnmatch.fnmatch(pkg.get_name(), spec) for spec in pkg_specs):
                pkglist.append(pkg)

        # dnf/hawkey doesn't make any distinction between file, dir or ghost like yum did
        # so only return the files.
        return set(f for pkg in pkglist for f in pkg.get_files() if not os.path.isdir(self._out(f)))

    def _getsize(self, *files):
        return sum(os.path.getsize(self._out(f)) for f in files if os.path.isfile(self._out(f)))

    def _write_package_log(self):
        """
        Write the list of installed packages to /root/ on the boot.iso

        If lorax is called with a debug repo find the corresponding debuginfo package
        names and write them to /root/debug-pkgs.log on the boot.iso
        The non-debuginfo packages are written to /root/lorax-packages.log
        """
        if self.transaction is None:
            raise RuntimeError("Transaction needs to be run before calling _write_package_log")

        os.makedirs(self._out("root/"), exist_ok=True)
        pkgs = []
        debug_pkgs = []
        for tp in self.transaction.get_transaction_packages():
            if not action_is_inbound(tp.get_action()):
                continue

            # Get the underlying package
            p = tp.get_package()
            pkgs.append(p.get_nevra())

            # Is a corresponding debuginfo package available?
            q = dnf5.rpm.PackageQuery(self.dbo)
            q.filter_available()
            q.filter_name([f"{p.get_name()}-debuginfo"], EQ)
            if len(list(q)) > 0:
                debug_pkgs.append(f"{p.get_name()}-debuginfo-{p.get_evr()}")

        with open(self._out("root/lorax-packages.log"), "w") as f:
            f.write("\n".join(sorted(pkgs)))
            f.write("\n")

        if debug_pkgs:
            with open(self._out("root/debug-pkgs.log"), "w") as f:
                f.write("\n".join(sorted(debug_pkgs)))
                f.write("\n")

    def _writepkglists(self, pkglistdir):
        """Write package file lists to a directory.
        Each file is named for the package and contains the files installed
        """
        if self.transaction is None:
            raise RuntimeError("Transaction needs to be run before calling _writepkglists")

        if not os.path.isdir(pkglistdir):
            os.makedirs(pkglistdir)
        for tp in self.transaction.get_transaction_packages():
            if not action_is_inbound(tp.get_action()):
                continue

            pkgobj = tp.get_package()
            with open(joinpaths(pkglistdir, pkgobj.get_name()), "w") as fobj:
                for fname in pkgobj.get_files():
                    fobj.write("{0}\n".format(fname))

    def _writepkgsizes(self, pkgsizefile):
        """Write a file with the size of the files installed by the package"""
        if self.transaction is None:
            raise RuntimeError("Transaction needs to be run before calling _writepkgsizes")

        with open(pkgsizefile, "w") as fobj:
            for tp in sorted(self.transaction.get_transaction_packages(),
                             key=lambda x: x.get_package().get_name()):
                if not action_is_inbound(tp.get_action()):
                    continue

                pkgobj = tp.get_package()
                pkgsize = self._getsize(*pkgobj.get_files())
                fobj.write(f"{pkgobj.get_name()}.{pkgobj.get_arch()}: {pkgsize}\n")

    def install(self, srcglob, dest):
        '''
        install SRC DEST
          Copy the given file (or files, if a glob is used) from the input
          tree to the given destination in the output tree.
          The path to DEST must exist in the output tree.
          If DEST is a directory, SRC will be copied into that directory.
          If DEST doesn't exist, SRC will be copied to a file with that name,
          assuming the rest of the path exists.
          This is pretty much like how the 'cp' command works.

          Examples:
            install usr/share/myconfig/grub.conf /boot
            install /usr/share/myconfig/grub.conf.in /boot/grub.conf
        '''
        for src in rglob(self._in(srcglob), fatal=True):
            try:
                cpfile(src, self._out(dest))
            except shutil.Error as e:
                logger.error(e)

    def installimg(self, *args):
        '''
        installimg [--xz|--gzip|--bzip2|--lzma] [-ARG|--ARG=OPTION] SRCDIR DESTFILE
          Create a compressed cpio archive of the contents of SRCDIR and place
          it in DESTFILE.

          If SRCDIR doesn't exist or is empty nothing is created.

          Examples:
            installimg ${LORAXDIR}/product/ images/product.img
            installimg ${LORAXDIR}/updates/ images/updates.img
            installimg --xz -6 ${LORAXDIR}/updates/ images/updates.img
            installimg --xz -9 --memlimit-compress=3700MiB ${LORAXDIR}/updates/ images/updates.img

          Optionally use a different compression type and override the default args
          passed to it. The default is xz -9
        '''
        COMPRESSORS = ("--xz", "--gzip", "--bzip2", "--lzma")
        if len(args) < 2:
            raise ValueError("Not enough args for installimg.")

        srcdir = args[-2]
        destfile = args[-1]
        if not os.path.isdir(self._in(srcdir)) or not os.listdir(self._in(srcdir)):
            return

        compression = "xz"
        compressargs = []
        if args[0] in COMPRESSORS:
            compression = args[0][2:]

        for arg in args[1:-2]:
            if arg.startswith('-'):
                compressargs.append(arg)
            else:
                raise ValueError("Argument is missing -")

        logger.info("Creating image file %s from contents of %s", self._out(destfile), self._in(srcdir))
        logger.debug("Using %s %s compression", compression, compressargs or "")
        mkcpio(self._in(srcdir), self._out(destfile), compression=compression, compressargs=compressargs)

    def mkdir(self, *dirs):
        '''
        mkdir DIR [DIR ...]
          Create the named DIR(s). Will create leading directories as needed.

          Example:
            mkdir /images
        '''
        for d in dirs:
            d = self._out(d)
            if not isdir(d):
                os.makedirs(d)

    def replace(self, pat, repl, *fileglobs):
        '''
        replace PATTERN REPLACEMENT FILEGLOB [FILEGLOB ...]
          Find-and-replace the given PATTERN (Python-style regex) with the given
          REPLACEMENT string for each of the files listed.

          Example:
            replace @VERSION@ ${product.version} /boot/grub.conf /boot/isolinux.cfg
        '''
        match = False
        for g in fileglobs:
            for f in rglob(self._out(g)):
                match = True
                replace(f, pat, repl)
        if not match:
            raise IOError("no files matched %s" % " ".join(fileglobs))

    def append(self, filename, data):
        '''
        append FILE STRING
          Append STRING (followed by a newline character) to FILE.
          Python character escape sequences ('\\n', '\\t', etc.) will be
          converted to the appropriate characters.

          Examples:

            append /etc/depmod.d/dd.conf "search updates built-in"
            append /etc/resolv.conf ""
        '''
        with open(self._out(filename), "a") as fobj:
            fobj.write(bytes(data, "utf8").decode('unicode_escape')+"\n")

    def treeinfo(self, section, key, *valuetoks):
        '''
        treeinfo SECTION KEY ARG [ARG ...]
          Add an item to the treeinfo data store.
          The given SECTION will have a new item added where
          KEY = ARG ARG ...

          Example:
            treeinfo images-${kernel.arch} boot.iso images/boot.iso
        '''
        if section not in self.results.treeinfo:
            self.results.treeinfo[section] = dict()
        self.results.treeinfo[section][key] = " ".join(valuetoks)

    def installkernel(self, section, src, dest):
        '''
        installkernel SECTION SRC DEST
          Install the kernel from SRC in the input tree to DEST in the output
          tree, and then add an item to the treeinfo data store, in the named
          SECTION, where "kernel" = DEST.

          Equivalent to:
            install SRC DEST
            treeinfo SECTION kernel DEST
        '''
        self.install(src, dest)
        self.treeinfo(section, "kernel", dest)

    def installinitrd(self, section, src, dest):
        '''
        installinitrd SECTION SRC DEST
          Same as installkernel, but for "initrd".
        '''
        self.install(src, dest)
        self.chmod(dest, '644')
        self.treeinfo(section, "initrd", dest)

    def installupgradeinitrd(self, section, src, dest):
        '''
        installupgradeinitrd SECTION SRC DEST
          Same as installkernel, but for "upgrade".
        '''
        self.install(src, dest)
        self.chmod(dest, '644')
        self.treeinfo(section, "upgrade", dest)

    def hardlink(self, src, dest):
        '''
        hardlink SRC DEST
          Create a hardlink at DEST which is linked to SRC.
        '''
        if isdir(self._out(dest)):
            dest = joinpaths(dest, basename(src))
        os.link(self._out(src), self._out(dest))

    def symlink(self, target, dest):
        '''
        symlink SRC DEST
          Create a symlink at DEST which points to SRC.
        '''
        if rexists(self._out(dest)):
            self.remove(dest)
        os.symlink(target, self._out(dest))

    def copy(self, src, dest):
        '''
        copy SRC DEST
          Copy SRC to DEST.
          If DEST is a directory, SRC will be copied inside it.
          If DEST doesn't exist, SRC will be copied to a file with
          that name, if the path leading to it exists.
        '''
        try:
            cpfile(self._out(src), self._out(dest))
        except shutil.Error as e:
            logger.error(e)

    def move(self, src, dest):
        '''
        move SRC DEST
          Move SRC to DEST.
        '''
        mvfile(self._out(src), self._out(dest))

    def remove(self, *fileglobs):
        '''
        remove FILEGLOB [FILEGLOB ...]
          Remove all the named files or directories.
          Will *not* raise exceptions if the file(s) are not found.
        '''
        for g in fileglobs:
            for f in rglob(self._out(g)):
                remove(f)
                logger.debug("removed %s", f)

    def chmod(self, fileglob, mode):
        '''
        chmod FILEGLOB OCTALMODE
          Change the mode of all the files matching FILEGLOB to OCTALMODE.
        '''
        for f in rglob(self._out(fileglob), fatal=True):
            os.chmod(f, int(mode,8))

    def log(self, msg):
        '''
        log MESSAGE
          Emit the given log message. Be sure to put it in quotes!

          Example:
            log "Reticulating splines, please wait..."
        '''
        logger.info(msg)

    # TODO: add ssh-keygen, mkisofs(?), find, and other useful commands
    def runcmd(self, *cmdlist):
        '''
        runcmd CMD [ARG ...]
          Run the given command with the given arguments.

          NOTE: All paths given MUST be COMPLETE, ABSOLUTE PATHS to the file
          or files mentioned. ${root}/${inroot}/${outroot} are good for
          constructing these paths.

          FURTHER NOTE: Please use this command only as a last resort!
          Whenever possible, you should use the existing template commands.
          If the existing commands don't do what you need, fix them!

          Examples:
            (this should be replaced with a "find" function)
            runcmd find ${root} -name "*.pyo" -type f -delete
            %for f in find(root, name="*.pyo"):
            remove ${f}
            %endfor
        '''
        cmd = cmdlist
        logger.debug('running command: %s', cmd)
        if cmd[0].startswith("--chdir="):
            logger.error("--chdir is no longer supported for runcmd.")
            raise ValueError("--chdir is no longer supported for runcmd.")

        try:
            stdout = runcmd_output(cmd)
            if stdout:
                logger.debug('command output:\n%s', stdout)
            logger.debug("command finished successfully")
        except CalledProcessError as e:
            if e.output:
                logger.error('command output:\n%s', e.output)
            logger.error('command returned failure (%d)', e.returncode)
            raise

    def removepkg(self, *pkgs):
        '''
        removepkg PKGGLOB [PKGGLOB...]
          Delete the named package(s).

          IMPLEMENTATION NOTES:
            RPM scriptlets (%preun/%postun) are *not* run.
            Files are deleted, but directories are left behind.
        '''
        for p in pkgs:
            filepaths = [f.lstrip('/') for f in self._filelist(p)]
            # TODO: also remove directories that aren't owned by anything else
            if filepaths:
                logger.debug("removepkg %s: %ikb", p, self._getsize(*filepaths)/1024)
                self.remove(*filepaths)
            else:
                logger.debug("removepkg %s: no files to remove!", p)

    def run_pkg_transaction(self):
        '''
        run_pkg_transaction
          Actually install all the packages requested by previous 'installpkg'
          commands.
        '''
        logger.info("Checking dependencies")
        self.transaction = self.goal.resolve()
        if self.transaction.get_problems() != NO_PROBLEM:
            err = "\n".join(self.transaction.get_resolve_logs_as_strings())
            logger.error("Dependency check failed: %s", err)
            raise RuntimeError(err)
        num_pkgs = len(self.transaction.get_transaction_packages())
        logger.info("%d packages selected", num_pkgs)
        if num_pkgs == 0:
            raise RuntimeError("No packages in transaction")

        # Write out the packages installed, including debuginfo packages
        self._write_package_log()

        logger.info("Downloading packages")

        downloader_callbacks = LoraxDownloadCallback(num_pkgs)
        self.dbo.set_download_callbacks(dnf5.repo.DownloadCallbacksUniquePtr(downloader_callbacks))
        try:
            self.transaction.download()
        except Exception as e:
            logger.error("Failed to download the following packages: %s", e)
            raise

        logger.info("Preparing transaction from installation source")

        display = LoraxRpmCallback()
        self.transaction.set_callbacks(dnf5.rpm.TransactionCallbacksUniquePtr(display))
        with ProcMount(self.outroot):
            try:
                result = self.transaction.run()
                if result != dnf5.base.Transaction.TransactionRunResult_SUCCESS:
                    err = "\n".join(self.transaction.get_transaction_problems())
                    raise RuntimeError(err)
            except Exception as e:
                logger.error("The transaction process has ended abruptly: %s", e)
                raise

        # At this point dnf should know about the installed files. Double check that it really does.
        if len(self._filelist("anaconda-core")) == 0:
            raise RuntimeError("Failed to reset dbo to installed package set")

    def removefrom(self, pkg, *globs):
        '''
        removefrom PKGGLOB [--allbut] FILEGLOB [FILEGLOB...]
          Remove all files matching the given file globs from the package
          (or packages) named.
          If '--allbut' is used, all the files from the given package(s) will
          be removed *except* the ones which match the file globs.

          Examples:
            removefrom usbutils /usr/bin/*
            removefrom xfsprogs --allbut /bin/*
        '''
        cmd = "%s %s" % (pkg, " ".join(globs)) # save for later logging
        keepmatches = False
        if globs[0] == '--allbut':
            keepmatches = True
            globs = globs[1:]
        # get pkg filelist and find files that match the globs
        filelist = self._filelist(pkg)
        matches = set()
        for g in globs:
            globs_re = re.compile(fnmatch.translate(g))
            m = [f for f in filelist if globs_re.match(f)]
            if m:
                matches.update(m)
            else:
                logger.debug("removefrom %s %s: no files matched!", pkg, g)
        # are we removing the matches, or keeping only the matches?
        if keepmatches:
            remove_files = filelist.difference(matches)
        else:
            remove_files = matches
        # remove the files
        if remove_files:
            logger.debug("removefrom %s: removed %i/%i files, %ikb/%ikb", cmd,
                             len(remove_files), len(filelist),
                             self._getsize(*remove_files)/1024, self._getsize(*filelist)/1024)
            self.remove(*remove_files)
        else:
            logger.debug("removefrom %s: no files to remove!", cmd)

    # pylint: disable=anomalous-backslash-in-string
    def removekmod(self, *globs):
        '''
        removekmod GLOB [GLOB...] [--allbut] KEEPGLOB [KEEPGLOB...]
          Remove all files and directories matching the given file globs from the kernel
          modules directory.

          If '--allbut' is used, all the files from the modules will be removed *except*
          the ones which match the file globs. There must be at least one initial GLOB
          to search and one KEEPGLOB to keep. The KEEPGLOB is expanded to be *KEEPGLOB*
          so that it will match anywhere in the path.

          This only removes files from under /lib/modules/\\*/kernel/

          Examples:
            removekmod sound drivers/media drivers/hwmon drivers/video
            removekmod drivers/char --allbut virtio_console hw_random
        '''
        cmd = " ".join(globs)
        if "--allbut" in globs:
            idx = globs.index("--allbut")
            if idx == 0:
                raise ValueError("removekmod needs at least one GLOB before --allbut")

            # Apply keepglobs anywhere they appear in the path
            keepglobs = globs[idx+1:]
            if len(keepglobs) == 0:
                raise ValueError("removekmod needs at least one GLOB after --allbut")

            globs = globs[:idx]
        else:
            # Nothing to keep
            keepglobs = []

        filelist = set()
        for g in globs:
            for top_dir in rglob(self._out("/lib/modules/*/kernel/"+g)):
                for root, _dirs, files in os.walk(top_dir):
                    filelist.update(root+"/"+f for f in files)

        # Remove anything matching keepglobs from the list
        matches = set()
        for g in keepglobs:
            globs_re = re.compile(fnmatch.translate("*"+g+"*"))
            m = [f for f in filelist if globs_re.match(f)]
            if m:
                matches.update(m)
            else:
                logger.debug("removekmod %s: no files matched!", g)
        remove_files = filelist.difference(matches)

        if remove_files:
            logger.debug("removekmod: removing %d files", len(remove_files))
            list(remove(f) for f in remove_files)
        else:
            logger.debug("removekmod %s: no files to remove!", cmd)

    def createaddrsize(self, addr, src, dest):
        '''
        createaddrsize INITRD_ADDRESS INITRD ADDRSIZE
          Create the initrd.addrsize file required in LPAR boot process.

          Examples:
            createaddrsize ${INITRD_ADDRESS} ${outroot}/${BOOTDIR}/initrd.img ${outroot}/${BOOTDIR}/initrd.addrsize
        '''
        addrsize = open(dest, "wb")
        addrsize_data = struct.pack(">iiii", 0, int(addr, 16), 0, os.stat(src).st_size)
        addrsize.write(addrsize_data)
        addrsize.close()

    def systemctl(self, cmd, *units):
        '''
        systemctl [enable|disable|mask] UNIT [UNIT...]
          Enable, disable, or mask the given systemd units.

          Examples:
            systemctl disable lvm2-monitor.service
            systemctl mask fedora-storage-init.service fedora-configure.service
        '''
        if cmd not in ('enable', 'disable', 'mask'):
            raise ValueError('unsupported systemctl cmd: %s' % cmd)
        if not units:
            logger.debug("systemctl: no units given for %s, ignoring", cmd)
            return
        self.mkdir("/run/systemd/system") # XXX workaround for systemctl bug
        systemctl = ['systemctl', '--root', self.outroot, '--no-reload', cmd]
        # When a unit doesn't exist systemd aborts the command. Run them one at a time.
        # XXX for some reason 'systemctl enable/disable' always returns 1
        for unit in units:
            try:
                cmd = systemctl + [unit]
                runcmd(cmd)
            except CalledProcessError:
                pass

class LiveTemplateRunner(TemplateRunner, InstallpkgMixin):
    """
    This class parses and executes a limited Lorax template. Sample usage:

      # install a bunch of packages
      runner = LiveTemplateRunner(dbo, templatedir, defaults)
      runner.run("live-install.tmpl")

      It is meant to be used with the live-install.tmpl which lists the per-arch
      pacages needed to build the live-iso output.
    """
    def __init__(self, dbo, fatalerrors=True, templatedir=None, defaults=None):
        self.dbo = dbo
        self.transaction = None
        self.goal = dnf5.base.Goal(self.dbo)
        self.pkgs = []
        self.pkgnames = []
        super(LiveTemplateRunner, self).__init__(fatalerrors, templatedir, defaults)
