#
# ramdisk.py
# class for creating init ramdisk
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
#

import sys
import os
import glob
import shutil
import commands
import re
import gzip

import config
import output
import lcs
import utils


class Ramdisk(object):

    def __init__(self):
        # get the config, paths and output objects
        self.conf = config.LoraxConfig.get()
        self.paths = config.LoraxPaths.get()
        self.output = output.Terminal.get()

        self.actions = self.get_actions_from_template()

    def get_actions_from_template(self):
        variables = { "instroot" : self.conf.installtree,
                      "initrd" : self.conf.ramdisktree,
                      "libdir" : self.conf.libdir,
                      "arch" : self.conf.arch,
                      "basearch" : self.conf.basearch,
                      "confdir" : self.conf.confdir,
                      "datadir" : self.conf.datadir }

        if self.conf.initrd_template is not None:
            template = lcs.TemplateParser(variables)
            return template.get_actions(self.conf.initrd_template)

        return []

    # XXX we have to do this, otherwise we get an error, when copying
    def remove_modules_broken_links(self):
        # remove build and source links from modules directories
        build = os.path.join(self.paths.MODULES_DIR, "build")
        if os.path.islink(build):
            utils.remove(build)

        source = os.path.join(self.paths.MODULES_DIR, "source")
        if os.path.islink(source):
            utils.remove(source)

    def move_shared_files(self):
        dirs = [os.path.join(self.paths.INITRD_DATADIR, "noarch"),
                os.path.join(self.paths.INITRD_DATADIR, self.conf.arch)]

        self.output.info(":: copying the custom initrd files")
        for dir in [dir for dir in dirs if os.path.isdir(dir)]:
            utils.scopy(src_root=dir, src_path="*",
                        dst_root=self.conf.ramdisktree, dst_path="")

    def process_actions(self):
        for action in self.actions:
            action.execute()

    def create_modinfo(self, moddir, target):
        modules_map = {}
        for root, dirs, files in os.walk(moddir):
            for file in files:
                modules_map[file] = os.path.join(root, file)

        modules = { "scsi_hostadapter" : "block",
                    "eth" : "networking" }

        blacklist = ( "floppy",
                      "scsi_mod",
                      "libiscsi" )

        list = {}
        for type, file_suffix in modules.items():
            list[type] = {}

            filename = os.path.join(moddir, "modules.%s" % file_suffix)
            if not os.path.isfile(filename):
                continue

            with open(filename, "r") as f:
                for line in f:
                    line = line.strip()

                    if line in modules_map:
                        modname, ext = os.path.splitext(line)
                        if modname in blacklist:
                            continue

                        cmd = "%s -F description %s" % (self.paths.MODINFO,
                                                        modules_map[line])

                        err, output = commands.getstatusoutput(cmd)
                        if err:
                            self.output.warning(output)
                            desc = ""
                        else:
                            desc = output.split("\n")[0]
                            desc = desc.strip()
                            desc = desc[:65]

                        if not desc:
                            desc = "%s driver" % modname
                            info = '%s\n\t%s\n\t"%s"\n' % (modname, type, desc)
                            list[type][modname] = info

        with open(target, "w") as f:
            f.write("Version 0\n")
            for type in list:
                modlist = sorted(list[type].keys())
                for mod in modlist:
                    f.write("%s\n" % list[type][mod])

    def get_kernel_modules(self):
        src_moddir = self.paths.MODULES_DIR
        dst_moddir = os.path.join(self.conf.ramdisktree, "lib", "modules",
                                  self.conf.kernelver)

        # expand modules
        modules = set()

        for name in self.conf.modules:
            if name.startswith("="):
                group = name[1:]

                if group in ("scsi", "ata"):
                    path = os.path.join(src_moddir, "modules.block")
                elif group == "net":
                    path = os.path.join(src_moddir, "modules.networking")
                else:
                    path = os.path.join(src_moddir, "modules.%s" % group)

                if os.path.isfile(path):
                    with open(path, "r") as f:
                        for line in f:
                            module = re.sub(r"\.ko$", "", line.strip())
                            modules.add(module)

            else:
                modules.add(name)

        # resolve modules dependencies
        with open(self.paths.MODULES_DEP, "r") as f:
            lines = map(lambda l: l.strip(), f.readlines())

        modpattern = re.compile(r"^.*/(?P<name>.*)\.ko:(?P<deps>.*)$")
        deppattern = re.compile(r"^.*/(?P<name>.*)\.ko$")
        changed = True

        while changed:
            for line in lines:
                changed = False

                m = modpattern.match(line)
                modname = m.group("name")

                if modname in modules:
                    # add the dependencies
                    for dep in m.group("deps").split():
                        m = deppattern.match(dep)
                        depname = m.group("name")

                        if depname not in modules:
                            changed = True
                            modules.add(depname)

        # copy all modules to the ramdisk tree
        src_path = src_moddir.replace(self.conf.installtree, "", 1)
        if src_path.startswith("/"):
            src_path = src_path[1:]

        dst_path = "lib/modules"

        utils.scopy(src_root=self.conf.installtree, src_path=src_path,
                    dst_root=self.conf.ramdisktree, dst_path=dst_path)

        # remove not needed modules
        for root, dirs, files in os.walk(dst_moddir):
            for file in files:
                full_path = os.path.join(root, file)
                name, ext = os.path.splitext(file)

                if ext == ".ko":
                    if name not in modules:
                        utils.remove(full_path)
                    else:
                        # get the required firmware
                        cmd = "%s -F firmware %s" % (self.paths.MODINFO,
                                                     full_path)
                        err, output = commands.getstatusoutput(cmd)
                        if err:
                            self.output.warning(output)
                            continue

                        for fw in output.split():
                            dst = os.path.join(self.conf.ramdisktree,
                                               "lib", "firmware", fw)

                            # create the destination directory
                            dir = os.path.dirname(dst)
                            if not os.path.isdir(dir):
                                utils.makedirs(dir)

                            # copy the firmware
                            path = os.path.join("lib", "firmware", fw)
                            utils.scopy(src_root=self.conf.installtree,
                                        src_path=path,
                                        dst_root=self.conf.ramdisktree,
                                        dst_path=path)

        # copy additional firmware
        fw = [ ("ipw2100", "ipw2100*"),
               ("ipw2200", "ipw2200*"),
               ("iwl3945", "iwlwifi-3945*"),
               ("iwl4965", "iwlwifi-4965*"),
               ("atmel", "atmel_*.bin"),
               ("zd1211rw", "zd1211"),
               ("qla2xxx", "ql*") ]

        for module, file in fw:
            if module in modules:
                utils.scopy(src_root=self.conf.installtree,
                            src_path=os.path.join("lib", "firmware", file),
                            dst_root=self.conf.ramdisktree,
                            dst_path=os.path.join("lib", "firmware"))

        # compress modules
        for root, dirs, files in os.walk(dst_moddir):
            for file in files:
                if not file.endswith(".ko"):
                    continue

                kopath = os.path.join(root, file)
                with open(kopath, "rb") as f:
                    kodata = f.read()

                gzipped = gzip.open(kopath + ".gz", "wb")
                gzipped.write(kodata)
                gzipped.close()

                os.unlink(kopath)

        # create modinfo
        modinfo = os.path.join(self.conf.tempdir, "module-info")
        self.create_modinfo(src_moddir, modinfo)

        target = os.path.join(self.conf.ramdisktree, "lib", "modules",
                              "module-info")

        cmd = "%s --modinfo-file %s --ignore-missing --modinfo %s > %s" % \
              (self.paths.MODLIST, modinfo, " ".join(list(modules)), target)

        err, output = commands.getstatusoutput(cmd)
        if err:
            self.output.warning(output)

        # run depmod
        cmd = "%s -a -F %s -b %s %s" % (
              self.paths.DEPMOD, self.paths.SYSTEM_MAP, self.conf.installtree,
              self.conf.kernelver)

        err, output = commands.getstatusoutput(cmd)
        if err:
            self.output.warning(output)

        # remove leftovers
        utils.remove(os.path.join(dst_moddir, "modules.*map"))

    def get_keymaps(self):
        if os.path.isfile(self.paths.KEYMAPS_OVERRIDE):
            dst = os.path.join(self.conf.ramdisktree, "etc", "keymaps.gz")
            shutil.copy2(self.paths.KEYMAPS_OVERRIDE, dst)
        else:
            cmd = "%s %s %s %s" % (
                  self.paths.GETKEYMAPS, self.conf.arch,
                  os.path.join(self.conf.ramdisktree, "etc", "keymaps.gz"),
                  self.conf.installtree)

            err, output = commands.getstatusoutput(cmd)
            if err:
                self.output.error(output)
                return False

        return True

    def create_locales(self):
        dir = os.path.join(self.conf.ramdisktree, "usr", "lib", "locale")
        utils.makedirs(dir)

        cmd = "%s -c -i en_US -f UTF-8 --prefix %s en_US" % \
              (self.paths.LOCALEDEF, self.conf.ramdisktree)

        err, output = commands.getstatusoutput(cmd)
        if err:
            self.output.error(output)
            return False

        return True

    def compress(self, filename):
        self.output.info(":: compressing the image file")
        cwd = os.getcwd()
        os.chdir(self.conf.ramdisktree)

        # XXX python cpioarchive does not support writing
        cpioarchive = filename + ".cpio"

        cmd = "find . | cpio --quiet -c -o > %s" % cpioarchive
        err, output = commands.getstatusoutput(cmd)
        if err:
            return False

        os.chdir(cwd)

        with open(cpioarchive, "rb") as f:
            cpiodata = f.read()

        gzipped = gzip.open(filename, "wb")
        gzipped.write(cpiodata)
        gzipped.close()

        os.unlink(cpioarchive)

        return True

    def prepare(self):
        # copy the .buildstamp file
        shutil.copy2(self.conf.buildstamp, self.conf.ramdisktree)

        self.remove_modules_broken_links()
        self.move_shared_files()
        self.process_actions()
        self.get_kernel_modules()
        self.get_keymaps()
        self.create_locales()

    def create(self):
        self.prepare()

        f = getattr(self, "create_%s" % self.conf.basearch, None)
        if f:
            return f()

    def create_i386(self):
        initrd_filename = "initrd.img"
        kernel_filename = "vmlinuz"

        if self.conf.kernelfile.endswith("PAE"):
            initrd_filename = "initrd-PAE.img"
            kernel_filename = "vmlinuz-PAE"

            text = """[images-xen]
kernel = images/pxeboot/vmlinuz-PAE
initrd = images/pxeboot/initrd-PAE.img

"""

            utils.edit(self.conf.treeinfo, append=True, text=text)

        initrd_filename = os.path.join(self.conf.tempdir, initrd_filename)
        self.compress(initrd_filename)

        kernel_filename = os.path.join(self.conf.tempdir, kernel_filename)
        shutil.copy2(self.conf.kernelfile, kernel_filename)

        return kernel_filename, initrd_filename

    def create_x86_64(self):
        return self.create_i386()

    def run_s390(self):
        initrd_filename = os.path.join(self.conf.tempdir, "initrd.img")
        self.compress(initrd_filename)

        kernel_filename = os.path.join(self.conf.tempdir, "kernel.img")
        shutil.copy2(self.conf.kernelfile, kernel_filename)

        cmd = "%s %s %s" % (self.paths.GENINITRDSZ,
                            os.path.getsize(initrd_filename),
                            os.path.join(self.conf.imagesdir, "initrd.size"))

        err, output = commands.getstatusoutput(cmd)
        if err:
            self.output.warning(output)

        for filename in (self.paths.REDHAT_EXEC, self.paths.GENERIC_PRM):
            shutil.copy2(filename, self.conf.imagesdir)
            shutil.copy2(filename, self.conf.outputdir)

        cmd = "%s -i %s -r %s -p %s -o %s" % (
              MKS390CD, kernel_filename, initrd_filename,
              self.paths.GENERIC_PRM,
              os.path.join(self.conf.imagesdir, "cdboot.img"))

        err, output = commands.getstatusoutput(cmd)
        if err:
            self.output.warning(output)

        text = """[images-%s]
kernel = images/kernel.img
initrd = images/initrd.img
initrd.size = images/initrd.size
generic.prm = images/generic.prm
generic.ins = generic.ins
cdboot.img = images/cdboot.img

""" % self.conf.arch

        utils.edit(self.conf.treeinfo, append=True, text=text)

        return kernel_filename, initrd_filename

    def run_s390x(self):
        return self.run_s390()

    # XXX this should be removed
    def run_alpha(self):
        raise NotImplementedError

    def run_ia64(self):
        raise NotImplementedError

    def run_ppc(self):
        raise NotImplementedError

    def run_ppc64(self):
        raise NotImplementedError
