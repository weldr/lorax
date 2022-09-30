image-minimizer
===============

:Authors:
    Brian C. Lane <bcl@redhat.com>

`image-minimizer` is a script used as an interpreter for kickstart `%post`
sections. It is used to remove rpm packages and individual files from the
system that Anaconda has just installed.

It processes a list of commands that tell it which files or rpms to remove, and
which to keep.


image-minimizer cmdline arguments
---------------------------------

    `usage: image-minimizer [-h] [-i STRING] [--dryrun] [-v] STRING`

Optional arguments
^^^^^^^^^^^^^^^^^^

  -h, --help            show this help message and exit
  -i STRING, --installroot STRING
                        Root path to prepend to all file patterns and
                        installation root for RPM operations. Defaults to
                        INSTALL_ROOT or /mnt/sysimage/
  --dryrun              If set, no filesystem changes are made.
  -v, --verbose         Display every action as it is performed.

Positional arguments
^^^^^^^^^^^^^^^^^^^^

  :STRING: Filename to process


NOTES
-----

You cannot pass any arguments to `image-minimizer` when using it from the
kickstart `%post`.

When using this from a kickstart the image-minimizer package needs to be available.
It is not included on the standard boot.iso, so you will need to include `lorax` in
the `%package` section. You can use `image-minimizer` to remove lorax from the install.

If you are using this with `livemedia-creator` it can be installed on the host
system so that `lorax` isn't needed in the `%package` list, and it doesn't need
to be removed.


commands
--------

Commands are listed one per line, followed by a space, and then by the
package, file, or glob.  The globs used are Unix style pathname patterns using
`*`, `?`, and `[]` character ranges. globbing is implemented using the python
glob module.


* drop <PATTERN>
  This will remove files from the installation.

* keep <PATTERN>
  This will keep files, and should follow any `drop` commands including globs.

* droprpm <PATTERN>
  Remove matching rpm packages. Dependencies are not remove, just individual
  packages matching the glob.

* keeprpm <PATTERN>
  Do not remove matching rpm packages, it should follow any `droprpm` commands
  that include globs.


example
-------

Example Anaconda `%post` usage::

    %post --interpreter=image-minimizer --nochroot

    drop /lib/modules/*/kernel/fs
    keep /lib/modules/*/kernel/fs/ext*
    keep /lib/modules/*/kernel/fs/mbcache*
    keep /lib/modules/*/kernel/fs/squashfs

    droprpm make
    droprpm mtools
    droprpm mysql-libs
    droprpm perl
    droprpm perl-Pod-*
    droprpm syslinux
    keeprpm perl-Pod-Simple

    # Not needed after image-minimizer is done
    droprpm lorax

    %end
