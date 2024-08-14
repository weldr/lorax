Lorax
=====

:Authors:
    Brian C. Lane <bcl@redhat.com>

"I am the Lorax.  I speak for the trees [and images]."

The `lorax <https://github.com/rhinstaller/lorax>`_ tool is used to create the
`Anaconda <https://github.com/rhinstaller/anaconda>`_ installer boot.iso as
well as the basic release tree, and .treeinfo metadata file. Its dependencies
are fairly light-weight because it needs to be able to run in a mock chroot
environment. It is best to run lorax from the same release as is being targeted
because the templates may have release specific logic in them. eg. Use the
rawhide version to build the boot.iso for rawhide, along with the rawhide
repositories.


lorax cmdline arguments
-----------------------

.. argparse::
    :ref: pylorax.cmdline.lorax_parser
    :prog: lorax

    --macboot : @replace
        Make the iso bootable on UEFI based Mac systems

        Default: True

    --nomacboot : @replace
        Do not create a Mac bootable iso

        Default: False


Quickstart
----------

Run this as root to create a boot.iso in ``./results/``::

    dnf install lorax
    setenforce 0
    lorax -p Fedora -v 38 -r 38 \
    -s http://dl.fedoraproject.org/pub/fedora/linux/releases/38/Everything/x86_64/os/ \
    -s http://dl.fedoraproject.org/pub/fedora/linux/updates/38/Everything/x86_64/ \
    ./results/
    setenforce 1

You can add your own repos with ``-s`` and packages with higher NVRs will
override the ones in the distribution repositories.

Under ``./results/`` will be the release tree files: .discinfo, .treeinfo, everything that
goes onto the boot.iso, the pxeboot directory, and the boot.iso under ``./results/images/``.


Branding
--------

By default lorax will search for the first package that provides ``system-release``
that doesn't start with ``generic-`` and will install it. It then selects a
corresponding logo package by using the first part of the system-release package and
appending ``-logos`` to it. eg. fedora-release and fedora-logos.

Variants
~~~~~~~~

If a ``variant`` is passed to lorax it will select a ``system-release`` package that
ends with the variant name. eg. Passing ``--variant workstation`` will select the
``fedora-release-workstation`` package if it exists. It will select a logo package
the same way it does for non-variants. eg. ``fedora-logos``.

If there is no package ending with the variant name it will fall back to using the
first non-generic package providing ``system-release``.

Custom Branding
~~~~~~~~~~~~~~~

If ``--skip-branding`` is passed to lorax it will skip selecting the
``system-release``, and logos packages and leave it up to the user to pass any
branding related packages to lorax using ``--installpkgs``. When using
``skip-branding`` you must make sure that you provide all of the expected files,
otherwise Anaconda may not work as expected. See the contents of ``fedora-release``
and ``fedora-logos`` for examples of what to include.

Note that this does not prevent something else in the dependency tree from
causing these packages to be included. Using ``--excludepkgs`` may help if they
are unexpectedly included.


Running inside of mock
----------------------

As of mock version 2.0 you no longer need to pass ``--old-chroot``. You will,
however, need to pass ``--enable-network`` so that the mock container can download
packages.

Older versions of mock, between 1.3.4 and 2.0, will need to pass ``--old-chroot``
to mock. These versions of mock default to using systemd-nspawn which cannot
create the needed loop device nodes. Passing ``--old-chroot`` will use the old
system where ``/dev/loop*`` is setup for you.


How it works
------------

Lorax uses `dnf <https://github.com/rpm-software-management/dnf>`_ to install
packages into a temporary directory, sets up configuration files, it then
removes unneeded files to save space, and creates a squashfs filesystem of the
files.  The iso is then built using a generic initramfs and the kernel from the
selected repositories.

To drive these processes Lorax uses a custom template system, based on `Mako
templates <http://www.makotemplates.org/>`_ with the addition of custom
commands (documented in :class:`pylorax.ltmpl.LoraxTemplateRunner`). Mako
supports ``%if/%endif`` blocks as well as free-form python code inside ``<%
%>`` tags and variable substitution with ``${}``. The default templates are
shipped with lorax in ``/usr/share/lorax/templates.d/99-generic/`` and use the
``.tmpl`` extension.


runtime-install.tmpl
~~~~~~~~~~~~~~~~~~~~

The ``runtime-install.tmpl`` template lists packages to be installed using the
``installpkg`` command.  This template is fairly simple, installing common packages and
architecture specific packages. It must end with the ``run_pkg_transaction``
command which tells dnf to download and install the packages.


runtime-postinstall.tmpl
~~~~~~~~~~~~~~~~~~~~~~~~

The ``runtime-postinstall.tmpl`` template is where the system configuration
happens. The installer environment is similar to a normal running system, but
needs some special handling. Configuration files are setup, systemd is told to
start the anaconda.target instead of a default system target, and a number of
unneeded services are disabled, some of which can interfere with the
installation. A number of template commands are used here:

* :func:`append <pylorax.ltmpl.LoraxTemplateRunner.append>` to add text to a file.
* :func:`chmod <pylorax.ltmpl.LoraxTemplateRunner.chmod>` changes the file's mode.
* :func:`install <pylorax.ltmpl.LoraxTemplateRunner.install>` to install a file into the installroot.
* :func:`mkdir <pylorax.ltmpl.LoraxTemplateRunner.mkdir>` makes a new directory.
* :func:`move <pylorax.ltmpl.LoraxTemplateRunner.move>` to move a file into the installroot
* :func:`replace <pylorax.ltmpl.LoraxTemplateRunner.replace>` does text substitution in a file
* :func:`remove <pylorax.ltmpl.LoraxTemplateRunner.remove>` deletes a file
* :func:`runcmd <pylorax.ltmpl.LoraxTemplateRunner.runcmd>` run arbitrary commands.
* :func:`symlink <pylorax.ltmpl.LoraxTemplateRunner.symlink>` creates a symlink
* :func:`systemctl <pylorax.ltmpl.LoraxTemplateRunner.systemctl>` runs systemctl in the installroot


runtime-cleanup.tmpl
~~~~~~~~~~~~~~~~~~~~

The ``runtime-cleanup.tmpl`` template is used to remove files that aren't strictly needed
by the installation environment. In addition to the ``remove`` template command it uses:

* :func:`removepkg <pylorax.ltmpl.LoraxTemplateRunner.removepkg>`
  remove all of a specific package's contents. A package may be pulled in as a dependency, but
  not really used. eg. sound support.
* :func:`removefrom <pylorax.ltmpl.LoraxTemplateRunner.removefrom>`
  Removes some files from a package. A file glob can be used, or the --allbut option to 
  remove everything except a select few.
* :func:`removekmod <pylorax.ltmpl.LoraxTemplateRunner.removekmod>`
  Removes kernel modules


The install.img root filesystem
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note::
    The erofs options are still experimental.  They require dracut-103 or later
    in order for the iso to boot, and the kernel erofs driver must support the
    compression type selected.
    For more information see the `erofs website <https://erofs.docs.kernel.org/en/latest/>`_.

After ``runtime-*.tmpl`` templates have finished their work lorax creates the
root filesystem in the ``install.img`` file.  The ``anaconda-dracut`` and 
``dracut-live`` dracut modules detect the type of rootfs and mounts it for booting.
There are currently four possible formats for this file:

* Plain squashfs filesystem (DEFAULT)
  This can be mounted directly and is simply a squashfs compressed root filesystem.
  It is created by default, when ``--squashfs-only``, or ``--rootfs-type squashfs``
  are passed to lorax.
* squashfs compressed ext4 filesystem
  This creates a ``LiveOS/rootfs.img`` ext4 filesystem of the root filesystem and
  then compresses that with squashfs.  This is selected when passing
  ``--rootfs-type squashfs-ext4`` to lorax.
* Plain erofs filesystem
  This can be mounted directly and is an erofs filesystem compressed using the
  lzma compression algorithm.  This is created when passing ``--rootfs-type erofs``
  to lorax.
* erofs compressed ext4 filesystem
  This is like the ``squashfs-ext4`` option except that it uses erofs. It is
  selected when passing ``--rootfs-type erofs-ext4`` to lorax.

When using erofs the current default is to use lzma compression. You can use
the ``[compression.erofs]`` section of the lorax configuration file to pass a
different compression type and arguments to the ``mkfs.erofs`` program. For
example to use lz4 with extra options create a lorax.conf file with::

    [compression.erofs]
    type = lz4
    args = -E dedupe,all-fragments -C 65536

And run the build with::

    lorax -c ./lorax.conf --rootfs-type erofs ...


iso creation
~~~~~~~~~~~~

The iso creation is handled by another set of templates. The one used depends
on the architecture that the iso is being created for. They are also stored in
``/usr/share/lorax/templates.d/99-generic`` and are named after the arch, like
``x86.tmpl`` and ``aarch64.tmpl``. They handle creation of the tree, copying
configuration template files, configuration variable substitution, treeinfo
metadata (via the :func:`treeinfo <pylorax.ltmpl.LoraxTemplateRunner.treeinfo>`
template command). Kernel and initrd are copied from the installroot to their
final locations and then xorrisofs is run to create the boot.iso


Custom Templates
----------------

The default set of templates and configuration files from the lorax-generic-templates package
are shipped in the ``/usr/share/lorax/templates.d/99-generic/`` directory. You can
make a copy of them and place them into another directory under ``templates.d``
and they will be used instead if their sort order is below all other directories. This
allows multiple packages to ship lorax templates without conflict. You can (and probably
should) select the specific template directory by passing ``--sharedir`` to lorax.

