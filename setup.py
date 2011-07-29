#! /usr/bin/env python

from distutils.core import setup
from glob import glob
import os
import sys


# config file
data_files = [("/etc/lorax", ["etc/lorax.conf"])]

# shared files
for root, dnames, fnames in os.walk("share"):
    for fname in fnames:
        data_files.append((root.replace("share", "/usr/share/lorax", 1),
                           [os.path.join(root, fname)]))

# executable
data_files.append(("/usr/sbin", ["src/sbin/lorax", "src/sbin/mkefiboot"]))

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
      long_description="",
      author="Martin Gracik",
      author_email="mgracik@redhat.com",
      url="http://",
      download_url="http://",
      license="GPLv2+",
      packages=["pylorax"],
      package_dir={"" : "src"},
      data_files=data_files
      )
