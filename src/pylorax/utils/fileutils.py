#
# fileutils.py
# functions for working with files
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
import shutil
import glob
import fileinput
import re


def normalize(src_root, src_path, dst_root, dst_path):
    src = os.path.join(src_root, src_path)
    dst = os.path.join(dst_root, dst_path)
    src = os.path.normpath(src)
    dst = os.path.normpath(dst)

    return src, dst


def remove(target, verbose=False):
    for fname in glob.iglob(target):
        if verbose:
            print "removing '%s'" % (fname,)

        if os.path.islink(fname) or os.path.isfile(fname):
            os.unlink(fname)
        else:
            shutil.rmtree(fname, ignore_errors=True)

def touch(filename, verbose=False):
    if verbose:
        print "touching '%s'" % (filename,)

    if os.path.exists(filename):
        os.utime(filename, None)
    else:
        try:
            f = open(filename, "w")
        except IOError as why:
            print >> sys.stderr, "cannot create '%s': %s" % (filename, why)
            return False
        else:
            f.close()
    
    return True

def copy(src_path, dst_path, src_root="/", dst_root="/",
        nolinks=False, ignore_errors=False, verbose=False):

    filecopy = Copy(ignore_errors, verbose)

    src = os.path.join(src_root, src_path)
    for fname in glob.iglob(src):
        fname = fname.replace(src_root, "", 1)
        
        if src_path[0] != "/" and fname[0] == "/":
            fname = fname[1:]

        filecopy.copy(fname, dst_path, src_root, dst_root, nolinks)

    return filecopy.errors

def move(src_path, dst_path, src_root="/", dst_root="/",
        nolinks=False, ignore_errors=False, verbose=False):

    errors = copy(src_path, dst_path, src_root, dst_root,
            nolinks, ignore_errors, verbose)

    # if everything was copied ok, remove the source
    if not errors:
        src, dst = normalize(src_root, src_path, dst_root, dst_path)
        remove(src, verbose)

    return errors

def chmod(target, mode, recursive=False, verbose=False):
    mode = int(mode)

    for fname in glob.iglob(target):
        if verbose:
            print "changing permissions on '%s'" % (fname,)

        os.chmod(fname, mode)

        if recursive and os.path.isdir(fname):
            for nested in os.listdir(fname):
                nested = os.path.join(fname, nested)
                chmod(nested, mode, recursive, verbose)

def edit(filename, text, append=False, verbose=False):
    mode = "w"
    if append:
        mode = "a"

    if verbose:
        print "editing '%s'" % (filename,)

    try:
        f = open(filename, mode)
    except IOError as why:
        print >> sys.stderr, "cannot edit '%s': %s" % (filename, why)
        return False
    else:
        f.write(text)
        f.close()
        
    return True

def replace(filename, find, replace, verbose=False):
    if verbose:
        print "replacing '%s' for '%s' in '%s'" % (find, replace, filename)

    fin = fileinput.input(filename, inplace=1)
    for line in fin:
        line = re.sub(find, replace, line)
        sys.stdout.write(line)
    fin.close()

    return True


class CopyError(Exception):
    pass

class Copy(object):
    def __init__(self, ignore_errors=False, verbose=False):
        self.Error = CopyError

        self.ignore_errors = ignore_errors
        self.verbose = verbose

        self.errors = []

    def copy(self, src_path, dst_path, src_root="/", dst_root="/", nolinks=False):
        # normalize the source and destination paths
        src, dst = normalize(src_root, src_path, dst_root, dst_path)

        # check if the source exists
        if not os.path.exists(src):
            err_msg = "cannot stat '%s': No such file or directory" % (src,)
            if not self.ignore_errors:
                raise self.Error, err_msg
            else:
                print >> sys.stderr, err_msg
                self.errors.append(err_msg)
                return False    # EXIT

        if os.path.isfile(src):

            # if destination is an existing directory, append the source filename
            # to the destination path
            if os.path.isdir(dst):
                dst = os.path.join(dst, os.path.basename(src))

            # check if the destination exists
            if os.path.isfile(dst):

                # overwrite file
                try:
                    if self.verbose:
                        print "overwriting '%s'" % (dst,)
                    os.unlink(dst)
                except OSError as why:
                    err_msg = "cannot overwrite file '%s': %s" % (dst, why)
                    if not self.ignore_errors:
                        raise self.Error, err_msg
                    else:
                        print >> sys.stderr, err_msg
                        self.errors.append(err_msg)
                        return False    # EXIT

            elif os.path.isdir(dst):

                # do not overwrite directory with a file
                err_msg = "cannot overwrite directory '%s' with non-directory" \
                        % (dst,)
                if not self.ignore_errors:
                    raise self.Error, err_msg
                else:
                    print >> sys.stderr, err_msg
                    self.errors.append(err_msg)
                    return False    # EXIT

            if os.path.islink(src):

                if nolinks:
                    self.__copy_file(os.path.realpath(src), dst)
                else:
                    self.__copy_link(src_path, dst_path, src_root, dst_root,
                            src, dst)

            else:

                self.__copy_file(src, dst)

        elif os.path.isdir(src):

            # append the source directory name to the destination path
            dirname = os.path.basename(src)
            new_dst = os.path.join(dst, dirname)
 
            if os.path.islink(src):

                if nolinks:
                    real_src = os.path.realpath(src)
                    
                    if not os.path.exists(new_dst):
                        os.makedirs(new_dst)

                    for fname in os.listdir(real_src):
                        fname = os.path.join(real_src, fname)
                        
                        if os.path.isfile(fname):
                            self.__copy_file(fname, new_dst)
                        else:
                            dst = os.path.join(new_dst, os.path.basename(fname))
                            shutil.copytree(fname, dst, symlinks=False)
                else:
                    self.__copy_link(src_path, dst_path, src_root, dst_root,
                            src, new_dst)

            else:

                # create the destination directory if it does not exist
                if not os.path.exists(new_dst):
                    os.makedirs(new_dst)

                if os.path.isfile(new_dst):
                    err_msg = "cannot overwrite file '%s' with a directory" \
                            % (new_dst,)
                    if not self.ignore_errors:
                        raise self.Error, err_msg
                    else:
                        print >> sys.stderr, err_msg
                        self.errors.append(err_msg)
                        return False    # EXIT

                new_dst_path = os.path.join(dst_path, dirname)

                fnames = []
                try:
                    fnames = os.listdir(src)
                except OSError as why:
                    err_msg = "cannot list directory '%s': %s'" % (src, why)
                    if not self.ignore_errors:
                        raise self.Error, err_msg
                    else:
                        print >> sys.stderr, err_msg
                        self.errors.append(err_msg)

                for fname in fnames:
                    fname = os.path.join(src_path, fname)
                    self.copy(fname, new_dst_path, src_root, dst_root)

    def __copy_file(self, src, dst):
        if self.verbose:
            print "copying '%s' to '%s'" % (src, dst)

        try:
            shutil.copy(src, dst)
        except (shutil.Error, IOError) as why:
            err_msg = "cannot copy '%s' to '%s': %s" % (src, dst, why)
            if not self.ignore_errors:
                raise self.Error, err_msg
            else:
                print >> sys.stderr, err_msg
                self.errors.append(err_msg)

    def __copy_link(self, src_path, dst_path, src_root, dst_root, src, dst):
        # read the link target
        link_target = os.readlink(src)

        # get the target source and destination paths
        target_src_path = os.path.join(os.path.dirname(src_path), link_target)
        target_dst_path = os.path.join(dst_path, os.path.dirname(link_target))
                
        # create the destination directory if it doesn't exist
        target_dst = os.path.join(dst_root, target_dst_path)
        if not os.path.exists(target_dst):
            os.makedirs(target_dst)

        # copy the target along with the link
        self.copy(target_src_path, target_dst_path, src_root, dst_root)

        # create the symlink named dst, pointing to link_target
        os.symlink(link_target, dst)
