from setuptools import setup
import os

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
                                 "src/sbin/livemedia-creator"]))
data_files.append(("/usr/bin",  ["src/bin/image-minimizer", "src/bin/mkksiso"]))

setup(name="lorax",
      version="40.5.7",
      description="Lorax",
      long_description="Tools for creating bootable images, including the Anaconda boot.iso",
      author="Martin Gracik, Will Woods <wwoods@redhat.com>, Brian C. Lane <bcl@redhat.com>",
      author_email="bcl@redhat.com",
      url="http://www.github.com/weldr/lorax/",
      download_url="http://www.github.com/weldr/lorax/releases/",
      license="GPLv2+",
      packages=["pylorax"],
      package_dir={"" : "src"},
      data_files=data_files
      )
