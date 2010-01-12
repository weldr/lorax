#
# launcher.py
# functions for the command line launcher
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


from __future__ import print_function

import sys
import os
from optparse import OptionParser, OptionGroup
import tempfile
import shutil
import ConfigParser

import yum

import pylorax


def main(args):
    version = "%s %s" % (os.path.basename(args[0]), pylorax.__VERSION__)
    usage = "%prog -p PRODUCT -v VERSION -r RELEASE -o OUTPUTDIR REPOSITORY"

    parser = OptionParser(usage=usage)

    # required arguments for image creation
    required = OptionGroup(parser, "required arguments")
    required.add_option("-p", "--product", help="product name",
            metavar="STRING")
    required.add_option("-v", "--version", help="version identifier",
            metavar="STRING")
    required.add_option("-r", "--release", help="release information",
            metavar="STRING")
    required.add_option("-o", "--outputdir", help="output directory",
            metavar="PATHSPEC")

    # optional arguments
    optional = OptionGroup(parser, "optional arguments")
    optional.add_option("-m", "--mirrorlist",
            help="mirrorlist repository (may be listed multiple times)",
            metavar="REPOSITORY", action="append", default=[])
    optional.add_option("-t", "--variant",
            help="variant name", metavar="STRING")
    optional.add_option("-b", "--bugurl",
            help="bug reporting URL for the product", metavar="URL",
            default="your distribution provided bug reporting tool")
    optional.add_option("-u", "--updates",
            help="directory containing updates", metavar="PATHSPEC")

    # output settings
    output = OptionGroup(parser, "output settings")
    output.add_option("--no-colors", help="disable color output",
            action="store_false", default=True, dest="colors")
    output.add_option("--encoding", help="set encoding",
            metavar="STRING", default="utf-8")
    output.add_option("-d", "--debug", help="enable debugging messages",
            action="store_true", default=False)

    # lorax settings
    settings = OptionGroup(parser, "lorax settings")
    settings.add_option("-c", "--cleanup", help="clean up on exit",
            action="store_true", default=False)

    # add the option groups to the parser
    parser.add_option_group(required)
    parser.add_option_group(optional)
    parser.add_option_group(output)
    parser.add_option_group(settings)

    # add the show version option
    parser.add_option("-V", help="show program's version number and exit",
            action="store_true", default=False, dest="showver")

    # parse the arguments
    opts, args = parser.parse_args()
    repositories = args

    if opts.showver:
        print(version)
        sys.exit(0)

    # check for the required arguments
    if not opts.product or not opts.version or not opts.release \
            or not opts.outputdir or not repositories:
        parser.error("missing one or more required arguments")

    # create the temporary directory for lorax
    tempdir = tempfile.mkdtemp(prefix="lorax.", dir=tempfile.gettempdir())

    # create the yumbase object
    installtree = os.path.join(tempdir, "installtree")
    os.mkdir(installtree)

    yumtempdir = os.path.join(tempdir, "yum")
    os.mkdir(yumtempdir)

    yumconf = create_yumconf(repositories, opts.mirrorlist, yumtempdir)
    yb = create_yumbase_object(yumconf, installtree)

    if yb is None:
        print("error: unable to create the yumbase object", file=sys.stderr)
        shutil.rmtree(tempdir)
        sys.exit(1)

    # run lorax
    params = { "product" : opts.product,
               "version" : opts.version,
               "release" : opts.release,
               "outputdir" : opts.outputdir,
               "tempdir" : tempdir,
               "installtree" : installtree,
               "colors" : opts.colors,
               "encoding" : opts.encoding,
               "debug" : opts.debug,
               "cleanup" : opts.cleanup,
               "variant" : opts.variant,
               "bugurl" : opts.bugurl,
               "updates" : opts.updates }

    lorax = pylorax.Lorax(yb, **params)
    lorax.run()


def create_yumconf(repositories, mirrorlists=[], tempdir="/tmp/yum"):

    def sanitize_repo(repo):
        if repo.startswith("/"):
            return "file://%s" % repo
        elif repo.startswith("http://") or repo.startswith("ftp://"):
            return repo
        else:
            return None

    # sanitize the repositories
    repositories = map(sanitize_repo, repositories)

    # remove invalid repositories
    repositories = filter(bool, repositories)

    cachedir = os.path.join(tempdir, "cache")
    if not os.path.isdir(cachedir):
        os.mkdir(cachedir)

    yumconf = os.path.join(tempdir, "yum.conf")
    c = ConfigParser.ConfigParser()

    # add the main section
    section = "main"
    data = { "cachedir" : cachedir,
             "keepcache" : 0,
             "gpgcheck" : 0,
             "plugins" : 0,
             "reposdir" : "",
             "tsflags" : "nodocs" }

    c.add_section(section)
    map(lambda (key, value): c.set(section, key, value), data.items())

    # add the main repository - the first repository from list
    section = "lorax-repo"
    data = { "name" : "lorax repo",
             "baseurl" : repositories[0],
             "enabled" : 1 }

    c.add_section(section)
    map(lambda (key, value): c.set(section, key, value), data.items())

    # add the extra repositories
    for n, extra in enumerate(repositories[1:], start=1):
        section = "lorax-extra-repo-%d" % n
        data = { "name" : "lorax extra repo %d" % n,
                 "baseurl" : extra,
                 "enabled" : 1 }

        c.add_section(section)
        map(lambda (key, value): c.set(section, key, value), data.items())

    # add the mirrorlists
    for n, mirror in enumerate(mirrorlists, start=1):
        section = "lorax-mirrorlist-%d" % n
        data = { "name" : "lorax mirrorlist %d" % n,
                 "mirrorlist" : mirror,
                 "enabled" : 1 }

        c.add_section(section)
        map(lambda (key, value): c.set(section, key, value), data.items())

    # write the yumconf file
    with open(yumconf, "w") as f:
        c.write(f)

    return yumconf


def create_yumbase_object(yumconf, installroot="/"):
    yb = yum.YumBase()

    yb.preconf.fn = yumconf
    yb.preconf.root = installroot
    yb._getConfig()

    yb._getRpmDB()
    yb._getRepos()
    yb._getSacks()

    return yb
