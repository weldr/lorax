#! /usr/bin/env python

from distutils.core import setup
from glob import glob


data_files = [("/etc/lorax", glob("etc/config.*")),
              ("/etc/lorax", ["etc/ignore_errors"]),
              ("/etc/lorax/templates", glob("etc/templates/*"))
              ]


setup(name="lorax",
      version="0.1",
      description="Lorax",
      long_description="",
      author="Martin Gracik",
      author_email="mgracik@redhat.com",
      url="http://",
      download_url="http://",
      license="GPLv2+",
      packages=["pylorax"],
      package_dir={"" : "src"},
      scripts=["src/bin/lorax"],
      data_files=data_files
      )
