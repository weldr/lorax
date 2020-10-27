#!/usr/bin/python2

from distutils.core import setup
import os
import sys


# config file
data_files = [("/etc/lorax", ["etc/lorax.conf"]),
              ("/usr/lib/tmpfiles.d/", ["systemd/lorax.conf"])]

# shared files
for root, dnames, fnames in os.walk("share"):
    for fname in fnames:
        data_files.append((root.replace("share", "/usr/share/lorax", 1),
                           [os.path.join(root, fname)]))

# executable
data_files.append(("/usr/sbin", ["src/sbin/lorax", "src/sbin/mkefiboot",
                                 "src/sbin/livemedia-creator", "src/sbin/mkksiso"]))
data_files.append(("/usr/bin",  ["src/bin/image-minimizer",
                                 "src/bin/composer-cli"]))

# get the version
sys.path.insert(0, "src")
try:
    import pylorax.version
except ImportError:
    vernum = "devel"
else:
    vernum = pylorax.version.num
finally:
    sys.path = sys.path[1:]


setup(name="lorax",
      version=vernum,
      description="Lorax",
      long_description="Tools for creating bootable images, including the Anaconda boot.iso",
      author="Martin Gracik, Will Woods <wwoods@redhat.com>, Brian C. Lane <bcl@redhat.com>",
      author_email="bcl@redhat.com",
      url="http://www.github.com/weldr/lorax/",
      download_url="http://www.github.com/weldr/lorax/releases/",
      license="GPLv2+",
      packages=["pylorax", "composer", "composer.cli"],
      package_dir={"" : "src"},
      data_files=data_files
      )
