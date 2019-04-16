# -*- coding: UTF-8 -*-
#
# Copyright (c) 2006-2016 Red Hat, Inc. All rights reserved. This copyrighted material
# is made available to anyone wishing to use, modify, copy, or
# redistribute it subject to the terms and conditions of the GNU General
# Public License v.2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# Author: David Malcolm <dmalcolm@redhat.com>
"""
rpmfluff is a lightweight way of building RPMs, and sabotaging them so they
are broken in controlled ways.

It is intended for use when testing RPM-testers e.g. rpmlint
and writing test cases for RPM tools e.g. yum
"""

from __future__ import print_function

import unittest
import os
import os.path
import shutil
import sys
import rpm
import subprocess

UTF8ENCODE = None

def _which(cmd):
    """Hacked Python 3.3+ shutil.which() with limited functionality."""
    path = os.environ.get("PATH", os.defpath)
    for p in path.split(os.pathsep):
        p = os.path.join(p, cmd)
        if os.path.exists(p) and os.access(p, os.F_OK | os.X_OK):
            return p

if sys.version_info < (3, 3):
    shutil.which = _which

def _utf8_encode(s):
    """
    RPM now returns all string data as surrogate-escaped utf-8 strings
    so we need to introduce backwards compatible method to deal with that
    """
    global UTF8ENCODE

    if UTF8ENCODE is None:
        h = rpm.hdr()
        test = 'test'
        h['name'] = test
        UTF8ENCODE = (test != h['name'])

    if UTF8ENCODE:
        return s.encode('utf-8')
    else:
        return s

def get_rpm_header(path):
    assert(os.path.isfile(path))
    ts = rpm.TransactionSet()
    ts.setVSFlags(-1) # disable all verifications
    fd = os.open(path, os.O_RDONLY)
    try:
        h = ts.hdrFromFdno(fd)
        return h
    finally:
        os.close(fd)

def expand_macros(expr):
    # If the expression contains RPM macros, return the expanded string
    if '%' in expr:
        return subprocess.check_output(['rpm', '-E', expr], universal_newlines=True).strip()
    else:
        return expr

class Check:
    """
    Something that ought to hold for the built RPMs
    and can be checked automatically, and has a name via __str__
    """
    def check(self, build):
        raise NotImplementedError

    def get_failure_message(self):
        raise NotImplementedError

class FailedCheck(Exception):
    """
    Exception class representing a failed L{Check}
    """
    def __init__(self, check, extraInfo=None):
        self.check = check
        self.extraInfo = extraInfo
        super(FailedCheck, self).__init__()

    def __str__(self):
        s = self.check.get_failure_message()
        if self.extraInfo:
            return "%s (%s)"%(s, self.extraInfo)
        else:
            return s

class CheckPayloadFile(Check):
    """Check that a built package contains a specified payload file or directory"""
    def __init__(self, packageName, arch, fullPath):
        self.packageName = packageName
        self.arch = arch
        self.fullPath = fullPath

    def __str__(self):
        return 'Checking that %s RPM on %s contains payload file "%s"'%(self.packageName, self.arch, self.fullPath)

    def get_failure_message(self):
        return '%s RPM on %s does not contain expected payload file "%s"'%(self.packageName, self.arch, self.fullPath)

    def check(self, build):
        rpmHdr = build.get_built_rpm_header(self.arch, self.packageName)
        if _utf8_encode(self.fullPath) not in rpmHdr[rpm.RPMTAG_FILENAMES]:
            raise FailedCheck(self)

class CheckSourceFile(Check):
    """Check that an SRPM contains the given source file"""
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return 'Checking that SRPM contains source file "%s"'%self.name

    def get_failure_message(self):
        return 'SRPM does not contain expected source file "%s"'%(self.name)

    def check(self, build):
        srpmHdr = build.get_built_srpm_header()
        # The values in srpmHdr are binary strings, and self.name
        # may not be a binary string, so encode self.name.
        if _utf8_encode(self.name) not in srpmHdr[rpm.RPMTAG_FILENAMES]:
            raise FailedCheck(self)

class CheckTrigger(Check):
    """Check that a built package contains a specified L{Trigger}"""
    def __init__(self, packageName, arch, trigger):
        self.packageName = packageName
        self.arch = arch
        self.trigger = trigger

    def __str__(self):
        return 'Checking that %s RPM on %s has trigger: %s'%(self.packageName, self.arch, self.trigger)

    def get_failure_message(self):
        return '%s RPM on %s does not contain expected trigger "%s"'%(self.packageName, self.arch, self.trigger)

    def check(self, build):
        rpmHdr = build.get_built_rpm_header(self.arch, self.packageName)
        # Search by event type and trigger condition:
        index = 0
        for t in rpmHdr[rpm.RPMTAG_TRIGGERTYPE]:
            # print(t)
            # print(rpmHdr[rpm.RPMTAG_TRIGGERCONDS][index])
            if t==_utf8_encode(self.trigger.event) and rpmHdr[rpm.RPMTAG_TRIGGERCONDS][index]==_utf8_encode(self.trigger.triggerConds):
                if rpmHdr[rpm.RPMTAG_TRIGGERSCRIPTS][index]!=_utf8_encode(self.trigger.script):
                    raise FailedCheck(self, 'script "%s" did not match expected "%s"'%(rpmHdr[rpm.RPMTAG_TRIGGERSCRIPTS][index],self.trigger.script))
                expectedProgram = self.trigger.program
                if expectedProgram is None:
                    expectedProgram = "/bin/sh"
                if rpmHdr[rpm.RPMTAG_TRIGGERSCRIPTPROG][index]!=_utf8_encode(expectedProgram):
                    raise FailedCheck(self, 'executable "%s" did not match expected "%s"'%(rpmHdr[rpm.RPMTAG_TRIGGERSCRIPTPROG][index],expectedProgram))

                # We have a match:
                return
            # No match: try next one:
            index += 1
        # We din't find the trigger:
        raise FailedCheck(self, 'trigger for event "%s" on "%s" not found within RPM'%(self.trigger.event, self.trigger.triggerConds))

class CheckRequires(Check):
    def __init__(self, packageName, arch, requires):
        self.packageName = packageName
        self.arch = arch
        self.requires = requires

    def __str__(self):
        return 'Checking that %s RPM on %s has "Requires: %s"'%(self.packageName, self.arch, self.requires)

    def get_failure_message(self):
        return '%s RPM on %s does not contain expected "Requires: %s"'%(self.packageName, self.arch, self.requires)

    def check(self, build):
        rpmHdr = build.get_built_rpm_header(self.arch, self.packageName)
        # Search by event type and trigger condition:
        for t in rpmHdr[rpm.RPMTAG_REQUIRES]:
            if t == self.requires:
                return  # found a match

        # We didn't find the requires:
        raise FailedCheck(self)

class CheckProvides(Check):
    def __init__(self, packageName, arch, provides):
        self.packageName = packageName
        self.arch = arch
        self.provides = provides

    def __str__(self):
        return 'Checking that %s RPM on %s has "Provides: %s"'%(self.packageName, self.arch, self.provides)

    def get_failure_message(self):
        return '%s RPM on %s does not contain expected "Provides %s"'%(self.packageName, self.arch, self.provides)

    def check(self, build):
        rpmHdr = build.get_built_rpm_header(self.arch, self.packageName)
        # Search by event type and trigger condition:
        for t in rpmHdr[rpm.RPMTAG_PROVIDES]:
            if t == self.provides:
                return  # found a match

        # We didn't find the provides:
        raise FailedCheck(self)

# Should scrap these in favour of strings, for base64 encoded files
class FileConstraint:
    """
    Abstract base class for describing innards of a file
    """
    def affect_file(self, dstFile):
        raise NotImplementedError

class BytesAt(FileConstraint):
    """
    Class representing byte values at an offset in a file
    """
    def __init__(self, offset, values):
        self.offset = offset
        self.values = values

    def affect_file(self, dstFile):
        dstFile.seek(self.offset)
        dstFile.write(self.values)

def make_png():
    return [BytesAt(0, b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a\x00\x00\x00\x0d\x49\x48\x44\x52"
                       b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4"
                       b"\x89\x00\x00\x00\x0a\x49\x44\x41\x54\x78\x9c\x63\x00\x01\x00\x00"
                       b"\x05\x00\x01\x0d\x0a\x2d\xb4\x00\x00\x00\x00\x49\x45\x4e\x44\xae"
                       b"\x42\x60\x82")]

def make_gif():
    return [BytesAt(0, b"GIF89a\x01\x00\x01\x00\x00\x00\x00\x3b")]

def make_elf(bit_format=64):
    """
    See https://en.wikipedia.org/wiki/Executable_and_Linkable_Format#File_header
    """
    if bit_format == 64:
        return [BytesAt(0, b"\177ELF\002")]
    elif bit_format == 32:
        return [BytesAt(0, b"\177ELF\001")]
    else:
        raise Exception("make_elf: unknown bit format")

class Buildable:
    def is_up_to_date(self):
        raise NotImplementedError

    def make(self):
        # print("considering building %s"%self)
        if not self.is_up_to_date():
            # print("doing it!")
            self.do_make()

    def clean(self):
        raise NotImplementedError

    def do_make(self):
        raise NotImplementedError

class RpmBuild(Buildable):
    """
    Wrapper for an invocation of rpmbuild
    """
    def __init__(self, buildArchs=None):
        """
        buildArchs:
            if None, the build will happen on the current arch
            if non-None, should be a list of strings: the archs to build on
        """
        self.buildArchs = buildArchs

    def is_up_to_date(self):
        # FIXME: crude check for now: does the build dir exist?
        if os.path.isdir(self.get_base_dir()):
            return True
        return False

    def get_base_dir(self):
        """Determine the name of the base directory of the rpmbuild hierarchy"""
        raise NotImplementedError

    def clean(self):
        os.system('rm -rf %s'%self.get_base_dir())

    def __create_directories(self):
        """Sets up the directory hierarchy for the build"""
        os.mkdir(self.get_base_dir())

        # Make fake rpmbuild directories
        for subDir in ['BUILD', 'SOURCES', 'SRPMS', 'RPMS']:
            os.mkdir(os.path.join(self.get_base_dir(), subDir))

    def do_make(self):
        """
        Hook to actually perform the rpmbuild, gathering the necessary source files first
        """
        self.clean()

        self.__create_directories()

        specFileName = self.gather_spec_file(self.get_base_dir())

        sourcesDir = self.get_sources_dir()
        self.gather_sources(sourcesDir)

        absBaseDir = os.path.abspath(self.get_base_dir())

        buildArchs = ()
        if self.buildArchs:
            buildArchs = self.buildArchs
        else:
            buildArchs = (expectedArch,)
        for arch in buildArchs:
            command = ["rpmbuild", "--define", "_topdir %s" % absBaseDir,
                       "--define", "_rpmfilename %%{ARCH}/%%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm",
                       "-ba", "--target", arch, specFileName]
            try:
                log = subprocess.check_output(command, stderr=subprocess.STDOUT).splitlines(True)
            except subprocess.CalledProcessError as e:
                raise RuntimeError('rpmbuild command failed with exit status %s: %s\n%s'
                        % (e.returncode, e.cmd, e.output))
            self.__write_log(log, arch)

        self.check_results()

    def __write_log(self, log, arch):
        log_dir = self.get_build_log_dir(arch)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        filename = self.get_build_log_path(arch)
        f = open(filename, "wb")
        for line in log:
            f.write(line)
        f.close()

    def get_build_log_dir(self, arch):
        """For the sake of standardization, write build logs to $basedir/LOGS/$arch/build.log"""
        return os.path.join(self.get_base_dir(), "LOGS", arch)

    def get_build_log_path(self, arch):
        """For the sake of standardization, write build logs to $basedir/LOGS/$arch/build.log"""
        return os.path.join(self.get_build_log_dir(arch), "build.log")

    def get_build_dir(self):
        return os.path.join(self.get_base_dir(), "BUILD")

    def get_sources_dir(self):
        return os.path.join(self.get_base_dir(), "SOURCES")

    def get_srpms_dir(self):
        return os.path.join(self.get_base_dir(), "SRPMS")

    def get_rpms_dir(self):
        return os.path.join(self.get_base_dir(), "RPMS")

    def gather_sources(self, sourcesDir):
        """
        Pure virtual hook for gathering source for the build to the given location
        """
        raise NotImplementedError

    def gather_spec_file(self, tmpDir):
        """
        Pure virtual hook for gathering specfile for the build to the appropriate location

        @return: full path/name of specfile
        """
        raise NotImplementedError

    def check_results(self):
        """
        Pure virtual hook for performing checks upon the results of the build
        """
        raise NotImplementedError

class SourceFile:
    def __init__(self, sourceName, content, encoding = 'utf8'):
        self.sourceName = sourceName
        self.content = content
        self.encoding = encoding

    def _get_dst_file(self, sourcesDir):
        import codecs
        dstFileName = os.path.join(sourcesDir, self.sourceName)
        if isinstance(self.content, bytes):
            dstFile = open(dstFileName, "wb")
        else:
            dstFile = codecs.open(dstFileName, "wb", self.encoding)
        return dstFile

    def write_file(self, sourcesDir):
        dstFile = self._get_dst_file(sourcesDir)
        dstFile.write(self.content)
        dstFile.close()

class GeneratedSourceFile:
    def __init__(self, sourceName, fileConstraints):
        self.sourceName = sourceName
        self.fileConstraints = fileConstraints

    def _get_dst_file(self, sourcesDir):
        dstFileName = os.path.join(sourcesDir, self.sourceName)
        dstFile = open(dstFileName, 'wb')
        return dstFile

    def write_file(self, sourcesDir):
        dstFile = self._get_dst_file(sourcesDir)
        for c in self.fileConstraints:
            c.affect_file(dstFile)
        dstFile.close()

class ExternalSourceFile:
    def __init__(self, sourceName, path):
        self.sourceName = sourceName
        self.path = path

    def _get_dst_file(self, sourcesDir):
        dstFileName = os.path.join(sourcesDir, self.sourceName)
        dstFile = open(dstFileName, 'wb')
        return dstFile

    def write_file(self, sourcesDir):
        dstFile = self._get_dst_file(sourcesDir)
        for line in open(self.path):
            dstFile.write(line)

class GeneratedTarball:
    def __init__(self, sourceName, internalPath, contents):
        self.sourceName = sourceName
        self.internalPath = internalPath
        self.contents = contents

    def write_file(self, sourcesDir):
        shutil.rmtree(self.internalPath, ignore_errors=True)
        os.mkdir(self.internalPath)
        for content in self.contents:
            content.write_file(self.internalPath)

        compressionOption = '--gzip'
        cmd = ["tar", "--create", compressionOption,
                "--file", os.path.join(sourcesDir, self.sourceName), self.internalPath]
        subprocess.check_call(cmd)
        shutil.rmtree(self.internalPath)


hello_world = """#include <stdio.h>

int
main (int argc, char **argv)
{
    printf ("Hello world\\n");

    return 0;
}
"""

hello_world_patch = r"""--- main.c.old       2007-04-09 13:23:51.000000000 -0400
+++ main.c     2007-04-09 13:24:12.000000000 -0400
@@ -3,7 +3,7 @@
 int
 main (int argc, char **argv)
 {
-    printf ("Hello world\n");
+    printf ("Foo\n");

     return 0;
 }
"""

simple_library_source = """#include <stdio.h>

void greet(const char *message)
{
    printf ("%s\\n", message);
}
"""


defaultChangelogFormat = """* Sun Jul 22 2018 John Doe <jdoe@example.com> - %s-%s
- Initial version
"""

sample_man_page = u""".TH FOO "1" "May 2009" "foo 1.00" "User Commands"
.SH NAME
foo \\- Frobnicates the doohickey
.SH SYNOPSIS
.B foo
[\\fIOPTION\\fR]...

.SH DESCRIPTION
A sample manpage
"""

def get_expected_arch():
    # FIXME: do this by directly querying rpm python bindings:
    evalArch = subprocess.check_output(['rpm', '--eval', '%{_arch}'])

    # first line of output, losing trailing carriage return
    # convert to a unicode type for python3
    return evalArch.strip().decode('ascii')

expectedArch = get_expected_arch()

def can_compile_m32():
    # 64-bit hosts can compile 32-bit binaries by using -m32, but only if the 
    # necessary bits are installed (they are often not).
    return os.path.exists('/usr/include/gnu/stubs-32.h') and os.path.exists('/lib/libgcc_s.so.1')

def can_use_rpm_weak_deps():
    return int(rpm.__version_info__[0]) >= 4 and int(rpm.__version_info__[1]) >= 12

class Trigger:
    def __init__(self, event, triggerConds, script, program=None):
        """For documentation on RPM triggers, see
        U{http://www.rpm.org/support/RPM-Changes-6.html}

        @param event: can be:
          - "un"
          - "in"
          - "postun"
        @type event: string

        @param triggerConds: the name of the target package, potentially with a conditional, e.g.:
          "sendmail"
          "fileutils > 3.0, perl < 1.2"
        @type triggerConds: string

        @param script: textual content of the script to execute
        @type script: string

        @param program: the progam used to execute the script
        @type program: string
        """
        self.event = event
        self.triggerConds = triggerConds
        self.script = script
        self.program = program

    def output(self, specFile, subpackageName=""):
        # Write trigger line:
        specFile.write("%%trigger%s %s"%(self.event, subpackageName))
        if self.program:
            specFile.write("-p %s"%self.program)
        specFile.write(" -- %s\n"%self.triggerConds)

        # Write script:
        specFile.write("%s\n"%self.script)

    def __str__(self):
        result = "%%trigger%s "%(self.event)
        if self.program:
            result += "-p %s"%self.program
        result += " -- %s\n"%self.triggerConds
        result += "%s\n"%self.script
        return result

class Subpackage:
    def __init__(self, suffix):
        """
        @param suffix: the suffix part of the name.  For example, a
        "foo-devel" subpackage of "foo" has name "devel"
        """
        self.suffix = suffix

        # Provide some sane defaults which rpmlint won't complain about:
        self.group = "Applications/Productivity"
        self.summary = "Dummy summary"
        self.description = "This is a dummy description."

        self.section_requires = ""
        self.section_recommends = ""
        self.section_suggests = ""
        self.section_supplements = ""
        self.section_enhances = ""
        self.section_provides = ""
        self.section_obsoletes = ""
        self.section_conflicts = ""
        self.section_files = ""

        self.section_pre = ""
        self.section_post = ""
        self.section_preun = ""
        self.section_postun = ""

        self.triggers = []

    def add_group(self, groupName):
        "Add a group name to the .spec file"
        self.group = groupName

    def add_description(self, descriptiveText):
        "Change the default description for the rpm"
        self.description = descriptiveText

    def add_summary(self, summaryText):
        "Change the default summary text for the rpm.  You can describe the test, or ways in which the rpm is intentionally defective."
        self.summary = summaryText

    def add_requires(self, requirement):
        "Add a Requires: line"
        self.section_requires += "Requires: %s\n"%requirement

    def add_suggests(self, suggestion):
        "Add a Suggests: line"
        self.section_suggests += "Suggests: %s\n"%suggestion

    def add_supplements(self, supplement):
        "Add a Supplements: line"
        self.section_supplements += "Supplements: %s\n"%supplement

    def add_enhances(self, enhancement):
        "Add a Requires: line"
        self.section_enhances += "Enhances: %s\n"%enhancement

    def add_recommends(self, recommendation):
        "Add a Recommends: line"
        self.section_recommends += "Recommends: %s\n"%recommendation

    def add_provides(self, capability):
        "Add a Provides: line"
        self.section_provides += "Provides: %s\n"%capability

    def add_obsoletes(self, obsoletes):
        "Add a Obsoletes: line"
        self.section_obsoletes += "Obsoletes: %s\n"%obsoletes

    def add_conflicts(self, conflicts):
        "Add a Conflicts: line"
        self.section_conflicts += "Conflicts: %s\n"%conflicts

    def add_pre(self, preLine):
        self.section_pre += preLine

    def add_post(self, postLine):
        self.section_post += postLine

    def add_preun(self, preunLine):
        self.section_preun += preunLine

    def add_postun(self, postunLine):
        self.section_postun += postunLine

    def add_trigger(self, trigger):
        "Add a trigger"
        self.triggers.append(trigger)

    def write_triggers(self, specFile):
        for trigger in self.triggers:
            trigger.output(specFile, self.suffix)

class SimpleRpmBuild(RpmBuild):
    """A wrapper for rpmbuild that also provides a canned way of generating a
    specfile and the source files."""
    def __init__(self, name, version, release, buildArchs=None):
        RpmBuild.__init__(self, buildArchs)

        self.specfileEncoding = 'utf-8'

        self.checks = []

        self.header = "# autogenerated specfile\n"
        self.name = name
        self.epoch = None
        self.version = version
        self.release = release
        # Provide sane default which rpmlint won't complain about:
        self.license = "GPL"
        self.vendor = ""
        self.packager = ""
        self.url = ""

        self.basePackage = Subpackage('')
        self.subPackages = []

        self.makeDebugInfo = False

        self.sources = {}
        self.patches = {}

        self.section_sources = ""
        self.section_patches = ""
        self.section_prep = ""
        self.section_build = ""
        self.section_clean = "rm -rf $$RPM_BUILD_ROOT"
        self.section_install = ""

        self.section_pre = ""
        self.section_post = ""
        self.section_preun = ""
        self.section_postun = ""

        self.section_changelog = defaultChangelogFormat%(version, release)

    def get_base_dir(self):
        return "test-rpmbuild-%s-%s-%s"%(self.name, self.version, expand_macros(self.release))

    def get_subpackage_names(self):
        """
        @return: generates a list of subpackage names: e.g.
          ['foo', 'foo-devel', 'foo-debuginfo']
        """
        result = [self.name]
        for sub in self.subPackages:
            result.append("%s-%s"%(self.name, sub.suffix))
        if self.makeDebugInfo:
            result.append("%s-debuginfo"%self.name)
        return result

    def get_subpackage_name(self, suffix):
        if suffix is not None:
            return '%s-%s' % (self.name, suffix)
        else:
            return self.name

    def get_subpackage(self, suffix):
        """
        @return: get a subpackage by suffix (e.g. "devel"), or None/"" for the base package
        """
        if suffix==None or suffix=='':
            return self.basePackage

        for sub in self.subPackages:
            if suffix == sub.suffix:
                return sub
        # Not found:
        return None

    def gather_sources(self, sourcesDir):
        #print(self.sources)
        for source in self.sources.values():
            source.write_file(sourcesDir)
        for patch in self.patches.values():
            patch.write_file(sourcesDir)

    def add_summary(self, summaryText):
        "Change the default summary text for this package"
        self.basePackage.add_summary(summaryText)

    def add_group(self, groupText):
        "Change the default group text for this package"
        self.basePackage.add_group(groupText)

    def add_description(self, descriptiveText):
        "Change the default description text for this package"
        self.basePackage.add_description(descriptiveText)

    def addLicense(self, licenseName):
        "Set License"
        self.license = licenseName

    def addVendor(self, vendorName):
        "Set Vendor name"
        self.vendor = vendorName

    def addPackager(self, packagerName):
        "Set Packager name"
        self.packager = packagerName

    def addUrl(self, urlName):
        "Set URL"
        self.url = urlName

    def add_pre(self, preLine):
        "Append a line to the %pre script section of this package"
        self.section_pre += preLine

    def add_post(self, postLine):
        "Append a line to the %post script section of this package"
        self.section_post += postLine

    def add_preun(self, preunLine):
        "Append a line to the %preun script section of this package"
        self.section_preun += preunLine

    def add_postun(self, postunLine):
        "Append a line to the %postun script section of this package"
        self.section_postun += postunLine

    def gather_spec_file(self, tmpDir):
        import codecs
        specFileName = os.path.join(tmpDir, "%s.spec"%self.name)
        specFile = codecs.open(specFileName, "wb", self.specfileEncoding)
        specFile.write(self.header)
        specFile.write("Summary: %s\n"%self.basePackage.summary)
        specFile.write("Name: %s\n"%self.name)
        if self.epoch:
            specFile.write("Epoch: %s\n"%self.epoch)
        specFile.write("Version: %s\n"%self.version)
        specFile.write("Release: %s\n"%self.release)
        specFile.write("License: %s\n"%self.license)
        specFile.write("Group: %s\n"%self.basePackage.group)
        if self.vendor:
            specFile.write("Vendor: %s\n"%self.vendor)
        if self.packager:
            specFile.write("Packager: %s\n"%self.packager)
        if self.url:
            specFile.write("URL: %s\n"%self.url)
        specFile.write("\n")
        specFile.write("BuildRoot: %(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)\n")

        # FIXME: ExclusiveArch

        specFile.write(self.section_sources)
        specFile.write(self.section_patches)

        specFile.write(self.basePackage.section_requires)
        specFile.write(self.basePackage.section_recommends)
        specFile.write(self.basePackage.section_suggests)
        specFile.write(self.basePackage.section_supplements)
        specFile.write(self.basePackage.section_enhances)
        specFile.write(self.basePackage.section_provides)
        specFile.write(self.basePackage.section_obsoletes)
        specFile.write(self.basePackage.section_conflicts)

        specFile.write("\n")

        specFile.write("%description\n")
        specFile.write("%s\n"%self.basePackage.description)
        specFile.write("\n")

        for sub in self.subPackages:
            specFile.write("%%package %s\n"%sub.suffix)
            specFile.write("Group: %s\n"%sub.group)
            specFile.write("Summary: %s\n"%sub.summary)
            specFile.write(sub.section_requires)
            specFile.write(sub.section_provides)
            specFile.write(sub.section_obsoletes)
            specFile.write(sub.section_conflicts)
            specFile.write("\n")
            specFile.write("%%description %s\n"%sub.suffix)
            specFile.write("%s\n"%sub.description)
            specFile.write("\n")

        specFile.write("%prep\n")
        specFile.write(self.section_prep)
        specFile.write("\n")

        specFile.write("%build\n")
        specFile.write(self.section_build)
        specFile.write("\n")

        specFile.write("%clean\n")
        specFile.write(self.section_clean)
        specFile.write("\n")

        specFile.write("%install\n")
        specFile.write("rm -rf $RPM_BUILD_ROOT\n")
        specFile.write("mkdir $RPM_BUILD_ROOT\n")
        specFile.write(self.section_install)
        specFile.write("\n")

        if self.section_pre != '':
            specFile.write("%pre\n")
            specFile.write(self.section_pre)
            specFile.write("\n")

        if self.section_post != '':
            specFile.write("%post\n")
            specFile.write(self.section_post)
            specFile.write("\n")

        if self.section_preun != '':
            specFile.write("%preun\n")
            specFile.write(self.section_preun)
            specFile.write("\n")

        if self.section_postun != '':
            specFile.write("%postun\n")
            specFile.write(self.section_postun)
            specFile.write("\n")

        self.basePackage.write_triggers(specFile)
        for sub in self.subPackages:
            if sub.section_pre != '':
                specFile.write("%%pre %s\n"%sub.suffix)
                specFile.write(sub.section_pre)
                specFile.write("\n")

            if sub.section_post != '':
                specFile.write("%%post %s\n"%sub.suffix)
                specFile.write(sub.section_post)
                specFile.write("\n")

            if sub.section_preun != '':
                specFile.write("%%preun %s\n"%sub.suffix)
                specFile.write(sub.section_preun)
                specFile.write("\n")

            if sub.section_postun != '':
                specFile.write("%%postun %s\n"%sub.suffix)
                specFile.write(sub.section_postun)
                specFile.write("\n")

            sub.write_triggers(specFile)

        specFile.write("%files\n")
        specFile.write(self.basePackage.section_files)
        specFile.write("\n")

        if self.makeDebugInfo:
            specFile.write("%debug_package\n")

        for sub in self.subPackages:
            specFile.write("%%files %s\n"%sub.suffix)
            specFile.write(sub.section_files)
            specFile.write("\n")

        if self.section_changelog:
            specFile.write("%changelog\n")
            specFile.write(self.section_changelog)
            specFile.write("\n")
        specFile.close()

        return specFileName

    def check_results(self):
        for check in self.checks:
            check.check(self)

    def get_built_srpm(self):
        return self.get_built_rpm('SRPMS')

    def get_built_rpm(self, arch, name=None):
        # name can be given separately to allow for subpackages
        if not name:
            name = self.name

        if arch=="SRPMS":
            archSuffix="src"
        else:
            archSuffix=arch

        builtRpmName="%s-%s-%s.%s.rpm"%(name, self.version, expand_macros(self.release), archSuffix)
        if arch=="SRPMS":
            builtRpmDir = self.get_srpms_dir()
        else:
            builtRpmDir = os.path.join(self.get_rpms_dir(), arch)
        builtRpmPath = os.path.join(builtRpmDir, builtRpmName)
        #print(builtRpmDir)
        #print(builtRpmPath)
        return builtRpmPath

    def get_built_srpm_header(self):
        return self.get_built_rpm_header('SRPMS')

    def get_built_rpm_header(self, arch, name=None):
        rpmFilename = self.get_built_rpm(arch, name)
        return get_rpm_header(rpmFilename)

    def expected_archs(self):
        """Get all arch subdirs we expect, including SRPMS"""
        if self.buildArchs:
            return self.buildArchs + ['SRPMS']
        else:
            return [expectedArch, "SRPMS"]

    def get_build_archs(self):
        """Get all archs we are building on (i.e. not including SRPMS)"""
        if self.buildArchs:
            return self.buildArchs
        else:
            return [expectedArch]

    def add_check(self, check):
        self.checks.append(check)

    def add_payload_check(self, fullPath, subpackageSuffix=None):
        absPath = os.path.join('/', fullPath)
        for arch in self.get_build_archs():
            name = self.get_subpackage_name(subpackageSuffix)
            self.add_check(CheckPayloadFile(name, arch, absPath))

    def escape_path(self, path):
        result = ""
        for char in path:
            if char in " $":
                result += "\\"
            result += char
        return result

    # Various methods for adding things to the build:

    def add_devel_subpackage(self):
        sub = self.add_subpackage('devel')
        sub.group = "Development/Libraries"
        sub.add_requires("%{name} = %{version}")
        return sub

    def add_subpackage(self, name):
        sub = Subpackage(name)
        self.subPackages.append(sub)
        return sub

    def add_requires(self, requirement):
        "Add a Requires: line"
        self.basePackage.add_requires(requirement)

    def add_recommends(self, recommendation):
        "Add a Recommends: line"
        self.basePackage.add_recommends(recommendation)

    def add_suggests(self, suggestion):
        "Add a Suggests: line"
        self.basePackage.add_suggests(suggestion)

    def add_supplements(self, supplement):
        "Add a Supplements: line"
        self.basePackage.add_supplements(supplement)

    def add_enhances(self, enhancement):
        "Add a Requires: line"
        self.basePackage.add_enhances(enhancement)

    def add_provides(self, capability):
        "Add a Provides: line"
        self.basePackage.add_provides(capability)

    def add_obsoletes(self, obsoletes):
        "Add an Obsoletes: line"
        self.basePackage.add_obsoletes(obsoletes)

    def add_conflicts(self, conflicts):
        "Add an Conflicts: line"
        self.basePackage.add_conflicts(conflicts)

    def add_build_requires(self, requirement):
        self.basePackage.section_requires  += "BuildRequires: %s\n"%requirement

    def add_trigger(self, trigger):
        "Add a trigger"
        self.basePackage.add_trigger(trigger)
        for arch in self.get_build_archs():
            self.add_check(CheckTrigger(self.name, arch, trigger))

    def add_source(self, source):
        "Add source; returning index"
        # add source to dict so it can be copied up:
        sourceIndex = len(self.sources)
        self.sources[sourceIndex] = source

        # add to section:
        self.section_sources += "Source%i: %s\n"%(sourceIndex, source.sourceName)

        # add a copyup to BUILD from SOURCES to prep:
        self.section_prep += "cp %%{SOURCE%i} .\n"%(sourceIndex)

        self.add_check(CheckSourceFile(source.sourceName))

        return sourceIndex

    def add_patch(self, patch, applyPatch, patchUrl=None):
        "Add patch; returning index"
        # add patch to dict so it can be copied up:
        patchIndex = len(self.patches)
        self.patches[patchIndex] = patch

        if patchUrl:
            patchName = patchUrl
        else:
            patchName = patch.sourceName

        # add to section:
        self.section_patches += "Patch%i: %s\n"%(patchIndex, patchName)
        self.add_check(CheckSourceFile(patch.sourceName))

        if applyPatch:
            self.section_prep += "%%patch%i\n"%patchIndex

        return patchIndex

    def add_compressed_file(self, sourceFile, installPath, createParentDirs=True, subpackageSuffix=None):
        self.add_source(sourceFile)

        if createParentDirs:
            self.create_parent_dirs(installPath)
        self.section_install += "gzip -c %s > $RPM_BUILD_ROOT/%s\n"%(sourceFile.sourceName, installPath)

        sub = self.get_subpackage(subpackageSuffix)
        sub.section_files += "/%s\n"%installPath
        self.add_payload_check(installPath, subpackageSuffix)

    def create_parent_dirs(self, installPath):
        """
        Given a file at installPath, add commands to installation to ensure
        the directory holding it exists.
        """
        (head, _tail) = os.path.split(installPath)
        self.section_install += "mkdir -p $RPM_BUILD_ROOT/%s\n"%head

    def add_mode(self,
                 installPath,
                 mode):
        self.section_install += "chmod %s $RPM_BUILD_ROOT/%s\n"%(mode, self.escape_path(installPath))

    def add_installed_file(self,
                           installPath,
                           sourceFile,
                           mode=None,
                           createParentDirs=True,
                           subpackageSuffix=None,
                           isConfig=False,
                           isDoc=False,
                           isGhost=False,
                           owner=None,
                           group=None):
        """Add a simple source file to the sources, and set it up to be copied up directly at %install, potentially with certain permissions"""
        sourceId = self.add_source(sourceFile)

        if createParentDirs:
            self.create_parent_dirs(installPath)
        self.section_install += "cp %%{SOURCE%i} $RPM_BUILD_ROOT/%s\n"%(sourceId, self.escape_path(installPath))
        if mode:
            self.section_install += "chmod %s $RPM_BUILD_ROOT/%s\n"%(mode, self.escape_path(installPath))

        sub = self.get_subpackage(subpackageSuffix)
        tag=""
        if owner or group:
            tag += '%%attr(-,%s,%s) ' % (owner or '-', group or '-')
        if isConfig:
            tag+="%config "
        if isDoc:
            tag+="%doc "
        if isGhost:
            tag+="%ghost "
        sub.section_files += '%s"/%s"\n'%(tag, installPath)

    def add_installed_directory(self,
                                installPath,
                                mode=None,
                                subpackageSuffix=None):
        """Add a simple creation of the directory into the %install phase, and pick it up in the %files list"""
        if installPath[-1] == '/':
            installPath = installPath[:-1]
        self.section_install += "mkdir -p $RPM_BUILD_ROOT/%s\n"%installPath
        if mode:
            self.section_install += "chmod %s $RPM_BUILD_ROOT/%s\n"%(mode, self.escape_path(installPath))
        sub = self.get_subpackage(subpackageSuffix)
        sub.section_files += "/%s\n"%installPath
        self.add_payload_check(installPath, subpackageSuffix)

    def add_installed_symlink(self, installedPath, target, subpackageSuffix=None, isConfig=False, isDoc=False, isGhost=False):
        """Add a simple symlinking into the %install phase, and pick it up in the %files list"""
        self.create_parent_dirs(installedPath)
        self.section_install += "ln -s %s $RPM_BUILD_ROOT/%s\n"%(target, installedPath)
        sub = self.get_subpackage(subpackageSuffix)
        tag = ""
        if isConfig:
            tag+="%config "
        if isDoc:
            tag+="%doc "
        if isGhost:
            tag+="%ghost "
        sub.section_files += '%s"/%s"\n'%(tag, installedPath)
        self.add_payload_check(installedPath, subpackageSuffix)

    def add_simple_payload_file(self):
        """Trivial hook for adding a simple file to payload, hardcoding all params"""
        self.add_installed_file(installPath = 'usr/share/doc/hello-world.txt',
                                sourceFile = SourceFile('hello-world.txt', 'hello world\n'),
                                isDoc=True)

    def add_simple_payload_file_random(self, size=100):
        """Trivial hook for adding a simple file to payload, random (ASCII printable chars) content of specified size (default is 100 bytes), name based on the packages ENVRA and count of the source files (to be unique)"""
        import random
        random.seed()
        content = ''
        for _ in range(size):
            content = content + chr(random.randrange(32, 127))
        name = "%s-%s-%s-%s-%s-%s.txt" % (self.epoch, self.name, self.version, expand_macros(self.release), self.get_build_archs()[0], len(self.sources))
        self.add_installed_file(installPath = 'usr/share/doc/%s' % name,
                                sourceFile = SourceFile(name, content),
                                isDoc=True)

    def add_simple_compilation(self,
                               sourceFileName="main.c",
                               sourceContent=hello_world,
                               compileFlags = "",
                               installPath="usr/bin/hello-world",
                               createParentDirs=True,
                               subpackageSuffix=None):
        """Add a simple source file to the sources, build it, and install it somewhere, using the given compilation flags"""
        _sourceId = self.add_source(SourceFile(sourceFileName, sourceContent))
        self.section_build += "%if 0%{?__isa_bits} == 32\n%define mopt -m32\n%endif\n"
        self.section_build += "gcc %%{?mopt} %s %s\n"%(compileFlags, sourceFileName)
        if createParentDirs:
            self.create_parent_dirs(installPath)
        self.section_install += "cp a.out $RPM_BUILD_ROOT/%s\n"%installPath
        sub = self.get_subpackage(subpackageSuffix)
        sub.section_files += "/%s\n"%installPath
        self.add_payload_check(installPath, subpackageSuffix)

    def add_simple_library(self,
                           sourceFileName="foo.c",
                           sourceContent=simple_library_source,
                           compileFlags = "",
                           libraryName = 'libfoo.so',
                           installPath="usr/lib/libfoo.so",
                           createParentDirs=True,
                           subpackageSuffix=None):
        """Add a simple source file to the sources, build it as a library, and
        install it somewhere, using the given compilation flags"""
        _sourceId = self.add_source(SourceFile(sourceFileName, sourceContent))
        self.section_build += "gcc --shared -fPIC -o %s %s %s\n"%(libraryName, compileFlags, sourceFileName)
        if createParentDirs:
            self.create_parent_dirs(installPath)
        self.section_install += "cp %s $RPM_BUILD_ROOT/%s\n" % (libraryName, installPath)
        sub = self.get_subpackage(subpackageSuffix)
        sub.section_files += "/%s\n"%installPath
        self.add_payload_check(installPath, subpackageSuffix)

    def add_fake_virus(self, installPath, sourceName, mode=None, subpackageSuffix=None):
        """
        Generate an anti-virus test file.  Not a real virus, but intended by
        convention to generate a positive when tested by virus scanners.

        See U{http://www.eicar.org/anti_virus_test_file.htm}
        """
        eicarTestContent = r"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
        self.add_installed_file(installPath, SourceFile(sourceName, eicarTestContent), mode, subpackageSuffix=subpackageSuffix)

    def add_multilib_conflict(self, installPath="/usr/share/bogusly-arch-specific-data.txt", createParentDirs=True, subpackageSuffix=None):
        """
        Add an architecture-specific file in a location that shouldn't be
        architecture-specific, so that it would be a conflict if you tried
        to install both 32-bit and 64-bit versions of the generated package.
        """
        if createParentDirs:
            self.create_parent_dirs(installPath)
        self.section_install += 'echo "The value of RPM_OPT_FLAGS during the build is: $RPM_OPT_FLAGS"  > $RPM_BUILD_ROOT/%s\n' % (installPath)
        self.section_install += 'echo "The value of RPM_ARCH during the build is: $RPM_ARCH"  >> $RPM_BUILD_ROOT/%s\n' % (installPath)

        sub = self.get_subpackage(subpackageSuffix)
        sub.section_files += "/%s\n"%installPath
        self.add_payload_check(installPath, subpackageSuffix)

    def add_build_warning(self, message):
        """Add a message to stderr during the build, so that we can simulate
        e.g. testsuite failures"""
        # Want to generate stderr, but avoid stdout having similar content
        # (which would lead to duplicates in the merged log).
        # So we rot13 the desired message, and echo that through a shell
        # rot13 (using tr), getting the desired output to stderr
        import codecs
        rot13Message = codecs.getencoder('rot-13')(message)[0]
        self.section_build += "echo '%s' | tr 'a-zA-Z' 'n-za-mN-ZA-N' 1>&2\n" % rot13Message

    def add_changelog_entry(self,
                            message,
                            version,
                            release,
                            dateStr='Sun Jul 22 2018',
                            nameStr='John Doe <jdoe@example.com>'):
        """Prepend a changelog entry"""
        newEntry = "* %s %s - %s-%s\n- %s\n"%(dateStr, nameStr, version, release, message)
        self.section_changelog = newEntry + "\n" + self.section_changelog

    def add_generated_tarball(self,
                              tarballName,
                              internalPath,
                              contents,
                              extract=True,
                              createParentDirs=True,
                              installPath='/usr/share',
                              subpackageSuffix=None):
        _sourceIndex = self.add_source(GeneratedTarball(tarballName, internalPath, contents))
        if extract:
            self.section_build += "tar -zxvf %s\n" % tarballName
            if createParentDirs:
                self.create_parent_dirs(os.path.join(installPath, internalPath))
            self.section_install += "cp -r %s $RPM_BUILD_ROOT/%s\n" % (internalPath, installPath)
        sub = self.get_subpackage(subpackageSuffix)
        for file in contents:
            sub.section_files += '/%s/%s/%s\n' % (installPath, internalPath, file.sourceName)

    def add_manpage(self,
                    sourceFileName='foo.1',
                    sourceFileContent=sample_man_page,
                    installPath='usr/share/man/man1/foo.1',
                    createParentDirs=True,
                    subpackageSuffix=None):
        sourceIndex = self.add_source(SourceFile(sourceFileName, sourceFileContent))
        if createParentDirs:
            self.create_parent_dirs(installPath)
        self.section_install += 'cp %%{SOURCE%i} $RPM_BUILD_ROOT/%s\n' % (sourceIndex, self.escape_path(installPath))

        # brp-compress will compress all man pages. If the man page is already
        # compressed, it will decompress the page and recompress it.
        (installBase, installExt) = os.path.splitext(installPath)
        if installExt in ('.gz', '.Z', '.bz2', '.xz', '.lzma'):
            finalPath = installBase + '.gz'
        else:
            finalPath = installPath + '.gz'

        sub = self.get_subpackage(subpackageSuffix)
        sub.section_files += '/%s\n' % finalPath
        self.add_payload_check(finalPath, subpackageSuffix)

class YumRepoBuild:
    """Class for easily creating a yum repo from a collection of RpmBuild instances"""
    def __init__(self, rpmBuilds):
        """@type rpmBuilds: list of L{RpmBuild} instances"""
        import tempfile
        self.repoDir = tempfile.mkdtemp()
        self.rpmBuilds = rpmBuilds

    def make(self, *arches):
        # Build all the packages
        for pkg in self.rpmBuilds:
            pkg.make()

        # Now assemble into a yum repo:
        for pkg in self.rpmBuilds:
            for arch in arches:
                if arch in pkg.get_build_archs():
                    for subpackage in pkg.get_subpackage_names():
                        try:
                            shutil.copy(pkg.get_built_rpm(arch, name=subpackage), self.repoDir)
                        except IOError:
                            pass   # possibly repo arch set to noarch+x86_64 but RpmBuild
                                   # built for noarch only?

        try:
            subprocess.check_output(["createrepo_c", self.repoDir], stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            raise RuntimeError('createrepo_c command failed with exit status %s: %s\n%s'
                    % (e.returncode, e.cmd, e.output))

testTrigger='print "This is the trigger!'

class TestSimpleRpmBuild(unittest.TestCase):
    def assert_header_has_item(self, rpmFilename, tagId, item, msg=None):
        # Check that the header tag contains the specified item
        h = get_rpm_header(rpmFilename)
        self.assertIn(_utf8_encode(item), h[tagId], msg)

    def assert_requires(self, rpmFilename, requirement):
        self.assert_header_has_item(rpmFilename, rpm.RPMTAG_REQUIRENAME, requirement,
                "%s does not require %s" % (rpmFilename, requirement))

    def assert_provides(self, rpmFilename, capability):
        self.assert_header_has_item(rpmFilename, rpm.RPMTAG_PROVIDENAME, capability,
                "%s does not provide %s" % (rpmFilename, capability))

    def assert_obsoletes(self, rpmFilename, obsoletes):
        self.assert_header_has_item(rpmFilename, rpm.RPMTAG_OBSOLETENAME, obsoletes,
                "%s does not obsolete %s" % (rpmFilename, obsoletes))

    def assert_conflicts(self, rpmFilename, conflicts):
        self.assert_header_has_item(rpmFilename, rpm.RPMTAG_CONFLICTNAME, conflicts,
                "%s does not conflict with %s" % (rpmFilename, conflicts))

    def assert_recommends(self, rpmFilename, recommendation):
        self.assert_header_has_item(rpmFilename, rpm.RPMTAG_RECOMMENDNAME, recommendation,
                "%s does not recommend %s" % (rpmFilename, recommendation))

    def assert_suggests(self, rpmFilename, suggestion):
        self.assert_header_has_item(rpmFilename, rpm.RPMTAG_SUGGESTNAME, suggestion,
                "%s does not suggest %s" % (rpmFilename, suggestion))

    def assert_supplements(self, rpmFilename, supplement):
        self.assert_header_has_item(rpmFilename, rpm.RPMTAG_SUPPLEMENTNAME, supplement,
                "%s does not supplement %s" % (rpmFilename, supplement))

    def assert_enhances(self, rpmFilename, enhancement):
        self.assert_header_has_item(rpmFilename, rpm.RPMTAG_ENHANCENAME, enhancement,
                "%s does not enhance %s" % (rpmFilename, enhancement))

    def assert_header_contains(self, rpmFilename, tagId, text):
        # Check that the header tag contains the specified piece of text
        ts = rpm.TransactionSet()
        ts.setVSFlags(-1) # disable all verifications
        fd = os.open(rpmFilename, os.O_RDONLY)
        h = ts.hdrFromFdno(fd)
        os.close(fd)
        self.assertIn(text, str(h[tagId]))

    def assert_is_dir(self, dirname):
        self.assertTrue(os.path.isdir(dirname), "%s is not a directory" % dirname)

    def assert_is_file(self, filename):
        self.assertTrue(os.path.isfile(filename), "%s is not a file" % filename)

    def setUp(self):
        # Take the last element of the id (e.g., __main__.TestSimpleRpmBuild.test_add_buildrequires)
        # and replace _ with - to make it look nicer
        pkgname = self.id().split('.')[-1].replace('_', '-')

        self.rpmbuild = SimpleRpmBuild(pkgname, "0.1", "1")

        # If the build directory already exists, go ahead and fail
        self.assertFalse(os.path.isdir(self.rpmbuild.get_base_dir()),
                "build directory %s already exists" % self.rpmbuild.get_base_dir())

    def tearDown(self):
        shutil.rmtree(self.rpmbuild.get_base_dir(), ignore_errors=True)

    def test_build(self):
        self.rpmbuild.make()
        tmpDir = self.rpmbuild.get_base_dir()

        buildDir = os.path.join(tmpDir, "BUILD")
        self.assert_is_dir(buildDir)

        _sourcesDir = os.path.join(tmpDir, "SOURCES")
        self.assert_is_dir(buildDir)

        srpmsDir = os.path.join(tmpDir, "SRPMS")
        self.assert_is_dir(srpmsDir)
        _srpmFile = os.path.join(srpmsDir, "test-build-0.1-1.src.rpm")
        self.assert_is_file(os.path.join(srpmsDir, "test-build-0.1-1.src.rpm"))

        rpmsDir = self.rpmbuild.get_rpms_dir()
        self.assert_is_dir(rpmsDir)

        for arch in [expectedArch]:
            # FIXME: sort out architecture properly
            rpmFile = os.path.join(rpmsDir, arch, "test-build-0.1-1.%s.rpm"%arch)
            self.assert_is_file(rpmFile)
            h = get_rpm_header(rpmFile)
            self.assertEqual(h['name'], b'test-build')
            self.assertEqual(h['version'], b'0.1')
            self.assertEqual(h['release'], b'1')

    def test_add_requires(self):
        self.rpmbuild.add_requires("test-requirement")
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            self.assert_is_file(rpmFile)

            self.assert_requires(rpmFile, 'test-requirement')

    def test_add_provides(self):
        self.rpmbuild.add_provides("test-capability = 2.0")
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            self.assert_is_file(rpmFile)

            self.assert_provides(rpmFile, 'test-capability')

    def test_add_obsoletes(self):
        self.rpmbuild.add_obsoletes("test-obsoletes")
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            self.assert_is_file(rpmFile)

            self.assert_obsoletes(rpmFile, 'test-obsoletes')

    def test_add_conflicts(self):
        self.rpmbuild.add_conflicts('test-conflicts')
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            self.assert_is_file(rpmFile)

            self.assert_conflicts(rpmFile, 'test-conflicts')

    @unittest.skipIf(not can_use_rpm_weak_deps(), 'RPM weak deps are not supported')
    def test_add_recommends(self):
        self.rpmbuild.add_recommends('test-recommendation')
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            self.assert_is_file(rpmFile)

            self.assert_recommends(rpmFile, 'test-recommendation')

    @unittest.skipIf(not can_use_rpm_weak_deps(), 'RPM weak deps are not supported')
    def test_add_suggests(self):
        self.rpmbuild.add_suggests('test-suggestion')
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            self.assert_is_file(rpmFile)

            self.assert_suggests(rpmFile, 'test-suggestion')

    @unittest.skipIf(not can_use_rpm_weak_deps(), 'RPM weak deps are not supported')
    def test_add_supplements(self):
        self.rpmbuild.add_supplements('test-supplement')
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            self.assert_is_file(rpmFile)

            self.assert_supplements(rpmFile, 'test-supplement')

    @unittest.skipIf(not can_use_rpm_weak_deps(), 'RPM weak deps are not supported')
    def test_add_enhances(self):
        self.rpmbuild.add_enhances('test-enhancement')
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            self.assert_is_file(rpmFile)

            self.assert_enhances(rpmFile, 'test-enhancement')

    def test_add_buildrequires(self):
        self.rpmbuild.add_build_requires("gcc")
        self.rpmbuild.make()
        srpmFile = self.rpmbuild.get_built_srpm()
        self.assert_is_file(srpmFile)

        self.assert_requires(srpmFile, 'gcc')

    def test_add_vendor(self):
        vendor = 'My own RPM Lab'
        self.rpmbuild.addVendor(vendor)
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            self.assert_is_file(rpmFile)

            self.assert_header_has_item(rpmFile, rpm.RPMTAG_VENDOR, vendor)

    def test_add_group_default(self):
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            self.assert_is_file(rpmFile)

            self.assert_header_has_item(rpmFile, rpm.RPMTAG_GROUP, 'Applications/Productivity')

    def test_add_group(self):
        group = 'Some/Test/Group'
        self.rpmbuild.add_group(group)
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            self.assert_is_file(rpmFile)

            self.assert_header_has_item(rpmFile, rpm.RPMTAG_GROUP, group)

    def test_add_packager(self):
        packager = 'Some Packager <spackager@example.com>'
        self.rpmbuild.addPackager(packager)
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            self.assert_is_file(rpmFile)

            self.assert_header_has_item(rpmFile, rpm.RPMTAG_PACKAGER, packager)

    def test_add_license(self):
        licenseName = 'SomeLicense'
        self.rpmbuild.addLicense(licenseName)
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            self.assert_is_file(rpmFile)

            self.assert_header_has_item(rpmFile, rpm.RPMTAG_LICENSE, licenseName)

    def test_archs_build(self):
        archs = ('i386', 'x86_64', 'ppc')
        # Override the object created by setUp
        self.rpmbuild = SimpleRpmBuild(self.rpmbuild.name, self.rpmbuild.version,
                self.rpmbuild.release, archs)
        self.rpmbuild.make()
        for arch in archs:
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            self.assert_is_file(rpmFile)

    def test_add_commiter(self):
        commiter = 'Some Commiter <scommiter@example.com>'
        message = 'Fixed bug #123456'
        self.rpmbuild.add_changelog_entry(message, '0.1', '1', 'Sun Jul 22 2018', commiter)
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            self.assert_is_file(rpmFile)

            self.assert_header_contains(rpmFile, rpm.RPMTAG_CHANGELOGNAME, commiter)
            self.assert_header_contains(rpmFile, rpm.RPMTAG_CHANGELOGTEXT, message)

    def test_add_url(self):
        url = 'http://www.example.com/myproject/'
        self.rpmbuild.addUrl(url)
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            self.assert_is_file(rpmFile)

            self.assert_header_has_item(rpmFile, rpm.RPMTAG_URL, url)

    def test_add_pre(self):
        script = 'echo "Hello World!"'
        self.rpmbuild.add_pre(script)
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            self.assert_is_file(rpmFile)

            self.assert_header_has_item(rpmFile, rpm.RPMTAG_PREIN, script)

    def test_add_post(self):
        script = 'echo "Hello World!"'
        self.rpmbuild.add_post(script)
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            self.assert_is_file(rpmFile)

            self.assert_header_has_item(rpmFile, rpm.RPMTAG_POSTIN, script)

    def test_add_preun(self):
        script = 'echo "Hello World!"'
        self.rpmbuild.add_preun(script)
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            self.assert_is_file(rpmFile)

            self.assert_header_has_item(rpmFile, rpm.RPMTAG_PREUN, script)

    def test_add_postun(self):
        script = 'echo "Hello World!"'
        self.rpmbuild.add_postun(script)
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            self.assert_is_file(rpmFile)

            self.assert_header_has_item(rpmFile, rpm.RPMTAG_POSTUN, script)

    def test_add_sub_pre(self):
        script = 'echo "Hello World!"'
        self.rpmbuild.add_subpackage('subpackage-pre-test')
        sub = self.rpmbuild.get_subpackage('subpackage-pre-test')
        sub.add_pre(script)
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch, "%s-%s" % (self.rpmbuild.name, sub.suffix))
            self.assert_is_file(rpmFile)

            self.assert_header_has_item(rpmFile, rpm.RPMTAG_PREIN, script)

    def test_add_sub_post(self):
        script = 'echo "Hello World!"'
        self.rpmbuild.add_subpackage('subpackage-post-test')
        sub = self.rpmbuild.get_subpackage('subpackage-post-test')
        sub.add_post(script)
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch, "%s-%s" % (self.rpmbuild.name, sub.suffix))
            self.assert_is_file(rpmFile)

            self.assert_header_has_item(rpmFile, rpm.RPMTAG_POSTIN, script)

    def test_add_sub_preun(self):
        script = 'echo "Hello World!"'
        self.rpmbuild.add_subpackage('subpackage-preun-test')
        sub = self.rpmbuild.get_subpackage('subpackage-preun-test')
        sub.add_preun(script)
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch, "%s-%s" % (self.rpmbuild.name, sub.suffix))
            self.assert_is_file(rpmFile)

            self.assert_header_has_item(rpmFile, rpm.RPMTAG_PREUN, script)

    def test_add_sub_postun(self):
        script = 'echo "Hello World!"'
        self.rpmbuild.add_subpackage('subpackage-postun-test')
        sub = self.rpmbuild.get_subpackage('subpackage-postun-test')
        sub.add_postun(script)
        self.rpmbuild.make()
        # FIXME: sort out architecture properly
        for arch in [expectedArch]:
            rpmFile = self.rpmbuild.get_built_rpm(arch, "%s-%s" % (self.rpmbuild.name, sub.suffix))
            self.assert_is_file(rpmFile)

            self.assert_header_has_item(rpmFile, rpm.RPMTAG_POSTUN, script)

    def test_subpackage_names_A(self):
        self.assertEqual(self.rpmbuild.get_subpackage_names(), ["test-subpackage-names-A"])

    def test_subpackage_names_B(self):
        self.rpmbuild.add_devel_subpackage()
        self.rpmbuild.add_subpackage('ssl')
        self.rpmbuild.makeDebugInfo=True
        self.assertEqual(self.rpmbuild.get_subpackage_names(), ['test-subpackage-names-B',
                                                                 'test-subpackage-names-B-devel',
                                                                 'test-subpackage-names-B-ssl',
                                                                 'test-subpackage-names-B-debuginfo'])

    def test_png(self):
        self.rpmbuild.add_installed_file("/foo.png", GeneratedSourceFile("foo.png", make_png()))
        self.rpmbuild.make()

    def test_gif(self):
        self.rpmbuild.add_installed_file("/foo.gif", GeneratedSourceFile("foo.gif", make_gif()))
        self.rpmbuild.make()

    def test_elf(self):
        self.rpmbuild.add_installed_file("/foo.so", GeneratedSourceFile("foo.so", make_elf()))
        self.rpmbuild.make()

    def test_elf_32(self):
        self.rpmbuild.add_installed_file("/foo.so",
            GeneratedSourceFile("foo.so", make_elf(bit_format=32)))
        self.rpmbuild.make()

    def test_elf_64(self):
        self.rpmbuild.add_installed_file("/foo.so",
            GeneratedSourceFile("foo.so", make_elf(bit_format=64)))
        self.rpmbuild.make()

    def test_elf_executable(self):
        self.rpmbuild.add_installed_file("/foo.so",
            GeneratedSourceFile("foo.so", make_elf()), mode="0755")
        self.rpmbuild.make()
        rpm_name = self.rpmbuild.get_built_rpm(self.rpmbuild.get_build_archs()[0])
        files = subprocess.check_output(["rpm", "-qp", "--qf",
                                         "[%{FILENAMES} %{FILEMODES:perms}\n]", rpm_name])
        assert files.split(b"\n")[0].strip().decode() == '/foo.so -rwxr-xr-x'

    def test_escape_path(self):
        self.assertEqual(self.rpmbuild.escape_path("Hello World.txt"), "Hello\\ World.txt")

    def test_add_installed_file_with_space(self):
        # see http://www.redhat.com/archives/rpm-list/2006-October/msg00115.html
        self.rpmbuild.add_installed_file("/this filename has a space in it.txt", GeneratedSourceFile("foo.so", make_elf()))
        self.rpmbuild.make()

    def test_add_simple_payload_file(self):
        self.rpmbuild.add_simple_payload_file()
        self.rpmbuild.make()

    def test_add_simple_payload_file_random(self):
        self.rpmbuild.add_simple_payload_file_random()
        self.rpmbuild.make()

    def test_add_simple_payload_file_random_multi(self):
        self.rpmbuild.add_simple_payload_file_random()
        self.rpmbuild.add_simple_payload_file_random()
        self.rpmbuild.add_simple_payload_file_random()
        self.rpmbuild.make()

    def test_add_simple_payload_file_random_size(self):
        self.rpmbuild.add_simple_payload_file_random(100)
        self.rpmbuild.make()

    def test_multiple_sources(self):
        self.rpmbuild.add_installed_file("/test-1", GeneratedSourceFile("test-1", make_elf()))
        self.rpmbuild.add_installed_file("/test-2", GeneratedSourceFile("test-2", make_png()))
        self.rpmbuild.add_installed_file("/test-3", GeneratedSourceFile("test-3", make_gif()))

        self.rpmbuild.make()
        tmpDir = self.rpmbuild.get_base_dir()

        rpmsDir = os.path.join(tmpDir, "RPMS")
        self.assert_is_dir(rpmsDir)

        for arch in [expectedArch]:
            # FIXME: sort out architecture properly
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            h = get_rpm_header(rpmFile)
            self.assertEqual(h['name'], b'test-multiple-sources')
            self.assertEqual(h['version'], b'0.1')
            self.assertEqual(h['release'], b'1')

    def test_generated_tarball(self):
        pkgName = b'test-generated-tarball'
        self.rpmbuild.add_generated_tarball('test-tarball-0.1.tar.gz',
                                'test-tarball-0.1',
                                [GeneratedSourceFile("test-1", make_elf()),
                                 GeneratedSourceFile("test-2", make_png()),
                                 GeneratedSourceFile("test-3", make_gif())])

        self.rpmbuild.make()
        tmpDir = self.rpmbuild.get_base_dir()

        rpmsDir = os.path.join(tmpDir, "RPMS")
        self.assert_is_dir(rpmsDir)

        for arch in [expectedArch]:
            # FIXME: sort out architecture properly
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            h = get_rpm_header(rpmFile)
            self.assertEqual(h['name'], pkgName)
            self.assertEqual(h['version'], b'0.1')
            self.assertEqual(h['release'], b'1')


    def test_simple_compilation(self):
        """Ensure that adding a compiled file works as expected"""
        self.rpmbuild.add_simple_compilation()
        self.rpmbuild.make()

    def test_installed_directory(self):
        """Ensure that adding a directory with specific permissions works as
        expected"""
        self.rpmbuild.add_installed_directory("/var/spool/foo", mode="1777")
        self.rpmbuild.make()

        rpmsDir = self.rpmbuild.get_rpms_dir()
        self.assert_is_dir(rpmsDir)

        for arch in [expectedArch]:
            # FIXME: sort out architecture properly
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            h = get_rpm_header(rpmFile)
            files = list(h.fiFromHeader())
            self.assertEqual(1, len(files))
            (filename, _size, mode, _mtime, _flags, _rdev, _inode, _FNlink, _Fstate, _vflags, _user, _group, _md5sum) = files[0]
            self.assertEqual("/var/spool/foo", filename)
            self.assertEqual(0o041777, mode)

    def test_installed_symlink(self):
        self.rpmbuild.add_installed_symlink("foo", "bar")
        self.rpmbuild.make()

        rpmsDir = self.rpmbuild.get_rpms_dir()
        self.assert_is_dir(rpmsDir)

        for arch in [expectedArch]:
            # FIXME: sort out architecture properly
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            h = get_rpm_header(rpmFile)
            files = list(h.fiFromHeader())
            self.assertEqual(1, len(files))
            self.assertEqual("/foo", files[0][0])

    def test_config_symlink(self):
        self.rpmbuild.add_installed_symlink("foo", "bar", isConfig=True)
        self.rpmbuild.make()

        rpmsDir = self.rpmbuild.get_rpms_dir()
        self.assert_is_dir(rpmsDir)

        for arch in [expectedArch]:
            # FIXME: sort out architecture properly
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            h = get_rpm_header(rpmFile)
            files = list(h.fiFromHeader())
            self.assertEqual(1, len(files))
            self.assertEqual("/foo", files[0][0])

    def test_doc_symlink(self):
        self.rpmbuild.add_installed_symlink("foo", "bar", isDoc=True)
        self.rpmbuild.make()

        rpmsDir = self.rpmbuild.get_rpms_dir()
        self.assert_is_dir(rpmsDir)

        for arch in [expectedArch]:
            # FIXME: sort out architecture properly
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            h = get_rpm_header(rpmFile)
            files = list(h.fiFromHeader())
            self.assertEqual(1, len(files))
            self.assertEqual("/foo", files[0][0])

    def test_ghost_symlink(self):
        self.rpmbuild.add_installed_symlink("foo", "bar", isGhost=True)
        self.rpmbuild.make()

        rpmsDir = self.rpmbuild.get_rpms_dir()
        self.assert_is_dir(rpmsDir)

        for arch in [expectedArch]:
            # FIXME: sort out architecture properly
            rpmFile = self.rpmbuild.get_built_rpm(arch)
            h = get_rpm_header(rpmFile)
            files = list(h.fiFromHeader())
            self.assertEqual(1, len(files))
            self.assertEqual("/foo", files[0][0])

    def test_fake_virus(self):
        """Ensure that adding a fake virus works as expected"""
        self.rpmbuild.add_fake_virus('fake-virus-infectee.exe', 'fake-virus-infectee.exe')
        self.rpmbuild.make()

    def test_debuginfo_generation(self):
        self.rpmbuild.add_simple_compilation(compileFlags="-g")
        self.rpmbuild.basePackage.section_files += "%debug_package\n"
        self.rpmbuild.make()
        for arch in [expectedArch]:
            # FIXME: sort out architecture properly
            rpmFile = self.rpmbuild.get_built_rpm(arch, name="test-debuginfo-generation-debuginfo")
            self.assert_is_file(rpmFile)

    def test_devel_generation(self):
        self.rpmbuild.add_devel_subpackage()
        self.rpmbuild.make()
        for arch in [expectedArch]:
            # FIXME: sort out architecture properly
            rpmFile = self.rpmbuild.get_built_rpm(arch, name="test-devel-generation-devel")
            self.assert_is_file(rpmFile)

            self.assert_requires(rpmFile, 'test-devel-generation')

    def test_triggers(self):
        """Ensure that adding a trigger works as expected"""
        self.rpmbuild.add_trigger(Trigger("in",
                              "fileutils > 3.0",
                              testTrigger,
                              "/usr/bin/perl"))
        self.rpmbuild.make()

    @unittest.skipIf(expectedArch != 'x86_64' or not can_compile_m32(),
                     'host arch is not x86_64 or 32-bit support is missing')
    def test_multiarch_compilation(self):
        """Ensure that building on multiple archs works as expected"""
        self.rpmbuild.buildArchs = ['i386', 'x86_64']
        self.rpmbuild.add_simple_compilation(installPath='/usr/bin/program')
        self.rpmbuild.make()
        hdr = self.rpmbuild.get_built_rpm_header('i386')
        fi = hdr.fiFromHeader()
        fi.next()
        self.assertEqual('/usr/bin/program', fi.FN())
        self.assertEqual(1, fi.FColor())
        hdr = self.rpmbuild.get_built_rpm_header('x86_64')
        fi = hdr.fiFromHeader()
        fi.next()
        self.assertEqual('/usr/bin/program', fi.FN())
        self.assertEqual(2, fi.FColor())

    def test_multilib_conflict(self):
        """Ensure that the hooks to create a multilib conflict work as expected"""
        self.rpmbuild.add_multilib_conflict()
        self.rpmbuild.make()

    def test_build_warning(self):
        """Ensure that the hooks to simulate build warnings work as expected"""
        self.rpmbuild.add_build_warning('# of unexpected failures     15')
        self.rpmbuild.make()

    def test_add_patch(self):
        """Ensure that adding a patch works as expected"""
        self.rpmbuild.add_simple_compilation()
        self.rpmbuild.add_patch(SourceFile(sourceName="change-greeting.patch",
                               content=hello_world_patch),
                    applyPatch=True)
        self.rpmbuild.make()

    def test_add_compressed_file(self):
        """Ensure that adding a compressed file works as expected"""
        self.rpmbuild.add_compressed_file(SourceFile(sourceName="hello-world.txt",
                                         content="Hello world"),
                              installPath='usr/share/hello-world.txt.gz')
        self.rpmbuild.make()

    def test_add_config_file(self):
        """Ensure that adding a file marked as config works as expected"""
        self.rpmbuild.add_installed_file("/etc/foo.conf",
                             SourceFile("foo.conf",
                                        "someOption=True"),
                             isConfig=True)
        self.rpmbuild.make()

    def test_add_doc_file(self):
        """Ensure that adding a file marked as documentation works as expected"""
        self.rpmbuild.add_installed_file("/usr/share/foo/README",
                             SourceFile("README",
                                        "Another useless file telling you to use 'info' rather than being helpful"),
                             isDoc=True)
        self.rpmbuild.make()

    def test_add_ghost_file(self):
        """Ensure that adding a file marked as a ghost works as expected"""
        self.rpmbuild.add_installed_file("/var/cache/foo.txt",
                             SourceFile("foo.txt",
                                        "Dummy file"),
                             isGhost=True)
        self.rpmbuild.make()

    def test_add_file_with_owner_and_group(self):
        self.rpmbuild.add_installed_file('/var/www/html/index.html',
                SourceFile('index.html', '<p>Hello</p>'),
                owner='apache', group='apache')
        self.rpmbuild.make()
        hdr = self.rpmbuild.get_built_rpm_header(expectedArch)
        files = list(hdr.fiFromHeader())
        self.assertEqual(1, len(files))
        (filename, _size, _mode, _mtime, _flags, _rdev, _inode, _FNlink, _Fstate, _vflags, user, group, _md5sum) = files[0]
        self.assertEqual('/var/www/html/index.html', filename)
        self.assertEqual('apache', user)
        self.assertEqual('apache', group)

    def test_specfile_encoding_utf8(self):
        self.rpmbuild.section_changelog = u"* Fri Mar 30 2001 Trond Eivind Glomsr\u00F8d <teg@redhat.com>\nDo something"
        self.rpmbuild.make()

    def test_specfile_encoding_iso8859(self):
        self.rpmbuild.specfileEncoding = 'iso8859_10'
        self.rpmbuild.section_changelog = u"* Fri Mar 30 2001 Trond Eivind Glomsr\u00F8d <teg@redhat.com>\nDo something"
        self.rpmbuild.make()

    def test_epoch(self):
        """Ensuring that setting the epoch works"""
        self.rpmbuild.epoch = 3
        self.rpmbuild.make()

        srpmHdr = self.rpmbuild.get_built_srpm_header()
        self.assertEqual(3, srpmHdr[rpm.RPMTAG_EPOCH])

    def test_add_manpage(self):
        self.rpmbuild.add_manpage()
        self.rpmbuild.make()

    def test_add_compressed_manpage(self):
        """Ensuring that adding an already compressed manpage works correctly"""
        import zlib
        compressedPage = zlib.compress(sample_man_page.encode('ascii'))
        self.rpmbuild.add_manpage(sourceFileName='foo.1.gz',
                                  sourceFileContent=compressedPage,
                                  installPath='usr/share/man/man1/foo.1.gz')
        self.rpmbuild.make()

    def test_add_differently_compressed_manpage(self):
        """Ensuring that a non-gzip compressed manpage is re-compressed"""
        import bz2
        compressedPage = bz2.compress(sample_man_page.encode('ascii'))
        self.rpmbuild.add_manpage(sourceFileName='foo.1.bz2',
                                  sourceFileContent=compressedPage,
                                  installPath='usr/share/man/man1/foo.1.bz2')
        self.rpmbuild.make()

    def test_dist_tag(self):
        """Ensuring that macros in the release tag work"""
        self.rpmbuild.release = '1%{?dist}'
        self.rpmbuild.make()

        self.assert_is_file(self.rpmbuild.get_built_rpm(expectedArch))

class YumRepoBuildTests(unittest.TestCase):
    def assert_is_dir(self, dirname):
        self.assertTrue(os.path.isdir(dirname), "%s is not a directory" % dirname)

    def assert_is_file(self, filename):
        self.assertTrue(os.path.isfile(filename), "%s is not a file" % filename)

    @unittest.skipIf(not shutil.which("createrepo_c"), "createrepo_c not found in PATH")
    def test_small_repo(self):
        """Assemble a small yum repo of 3 packages"""
        pkgs = []
        names = ['foo', 'bar', 'baz']
        for name in names:
            pkgs.append(SimpleRpmBuild("test-package-%s"%name, "0.1", "1"))
        repo = YumRepoBuild(pkgs)

        try:
            repo.make(expectedArch)

            # Check that the expected files were created:
            for name in names:
                rpmFile = os.path.join(repo.repoDir, "test-package-%s-0.1-1.%s.rpm"%(name, expectedArch))
                self.assert_is_file(rpmFile)
            repodataDir = os.path.join(repo.repoDir, "repodata")
            self.assert_is_dir(repodataDir)
            repomd = os.path.join(repodataDir, "repomd.xml")
            self.assert_is_file(repomd)

            # Parse the repomd and look for the expected data
            import xml.etree.ElementTree as ET
            tree = ET.parse(repomd)
            for mdtype in ("filelists", "other", "primary"):
                element = tree.findall(".//{http://linux.duke.edu/metadata/repo}data[@type='%s']/{http://linux.duke.edu/metadata/repo}location" % mdtype)
                self.assertTrue(len(element) == 1, "Could not find data for type %s" % mdtype)
                self.assert_is_file(os.path.join(repo.repoDir, element[0].get('href')))
        finally:
            shutil.rmtree(repo.repoDir, ignore_errors=True)
            for pkg in repo.rpmBuilds:
                shutil.rmtree(pkg.get_base_dir())

    @unittest.skipIf(not shutil.which('createrepo_c'), 'createrepo_c not found in PATH')
    def test_includes_subpackages(self):
        package = SimpleRpmBuild('test-package', '0.1', '1')
        package.add_devel_subpackage()
        package.add_subpackage('python')
        repo = YumRepoBuild([package])
        self.addCleanup(shutil.rmtree, package.get_base_dir())
        self.addCleanup(shutil.rmtree, repo.repoDir)

        repo.make(expectedArch)

        self.assert_is_dir(os.path.join(repo.repoDir, 'repodata'))
        self.assert_is_file(os.path.join(repo.repoDir, 'test-package-0.1-1.%s.rpm' % expectedArch))
        self.assert_is_file(os.path.join(repo.repoDir, 'test-package-devel-0.1-1.%s.rpm' % expectedArch))
        self.assert_is_file(os.path.join(repo.repoDir, 'test-package-python-0.1-1.%s.rpm' % expectedArch))

    @unittest.skipIf(expectedArch != 'x86_64' or not can_compile_m32() or not shutil.which("createrepo_c"),
                     'host arch is not x86_64 or 32-bit support is missing or createrepo_c not found in PATH')
    def test_multiple_arches(self):
        package = SimpleRpmBuild('test-multilib-package', '0.1', '1', ['i386', 'x86_64'])
        repo = YumRepoBuild([package])
        self.addCleanup(shutil.rmtree, package.get_base_dir())
        self.addCleanup(shutil.rmtree, repo.repoDir)

        repo.make('i386', 'x86_64')

        # Check that the repo was built with both the i386 and x86_64 packages
        self.assert_is_dir(os.path.join(repo.repoDir, 'repodata'))
        self.assert_is_file(os.path.join(repo.repoDir, 'test-multilib-package-0.1-1.i386.rpm'))
        self.assert_is_file(os.path.join(repo.repoDir, 'test-multilib-package-0.1-1.x86_64.rpm'))

    @unittest.skipIf(not shutil.which('createrepo_c'), 'createrepo_c not found in PATH')
    def test_arch_with_noarch(self):
        archful_package = SimpleRpmBuild('test-package', '0.1', '1')
        noarch_package = SimpleRpmBuild('python-package', '0.1', '1', ['noarch'])
        repo = YumRepoBuild([archful_package, noarch_package])
        self.addCleanup(shutil.rmtree, archful_package.get_base_dir())
        self.addCleanup(shutil.rmtree, noarch_package.get_base_dir())
        self.addCleanup(shutil.rmtree, repo.repoDir)

        repo.make(expectedArch, 'noarch')

        self.assert_is_dir(os.path.join(repo.repoDir, 'repodata'))
        self.assert_is_file(os.path.join(repo.repoDir, 'test-package-0.1-1.%s.rpm' % expectedArch))
        self.assert_is_file(os.path.join(repo.repoDir, 'python-package-0.1-1.noarch.rpm'))

if __name__ == "__main__":
    unittest.main()

