#!/usr/bin/python

from distutils.core import setup
import os
import sys


# config file
data_files = [("/etc/lorax", ["etc/lorax.conf"]),
              ("/etc/lorax", ["etc/composer.conf"]),
              ("/usr/lib/systemd/system", ["systemd/lorax-composer.service",
                                           "systemd/lorax-composer.socket"]),
              ("/usr/lib/tmpfiles.d/", ["systemd/lorax-composer.conf"])]

# shared files
for root, dnames, fnames in os.walk("share"):
    for fname in fnames:
        data_files.append((root.replace("share", "/usr/share/lorax", 1),
                           [os.path.join(root, fname)]))

# executable
data_files.append(("/usr/sbin", ["src/sbin/lorax", "src/sbin/mkefiboot",
                                 "src/sbin/livemedia-creator", "src/sbin/lorax-composer"]))
data_files.append(("/usr/bin",  ["src/bin/image-minimizer",
                                 "src/bin/mk-s390-cdboot",
                                 "src/bin/composer"]))

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
      author="Brian C. Lane, Will Woods, Martin Gracik",
      author_email="bcl@redhat.com",
      url="https://rhinstaller.github.io/lorax/",
      download_url="https://github.com/rhinstaller/lorax/releases",
      license="GPLv2+",
      packages=["pylorax", "pylorax.api", "composer", "composer.cli"],
      package_dir={"" : "src"},
      data_files=data_files
      )
