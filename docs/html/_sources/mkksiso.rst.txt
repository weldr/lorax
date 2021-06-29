mkksiso
=======

:Authors:
    Brian C. Lane <bcl@redhat.com>

``mkksiso`` is a tool for creating kickstart boot isos. In it's simplest form
you can add a kickstart to a boot.iso and the kickstart will be executed when
the iso is booted. If the original iso was created with EFI and Mac support the
kickstart boot.iso will include this support as well.

``mkksiso`` needs to be run as root, it depends on mounting the original iso
and you need to be root to be able to do that.


mkksiso cmdline arguments
-------------------------

Add a kickstart and files to an iso

    ``usage: mkksiso [-h] [-a ADD_PATHS] [-c CMDLINE] [--debug] ks input_iso output_iso``

Optional arguments
^^^^^^^^^^^^^^^^^^

      -h, --help            show this help message and exit
      -a ADD_PATHS, --add ADD_PATHS
                            File or directory to add to ISO (may be used multiple
                            times)
      -c CMDLINE, --cmdline CMDLINE
                            Arguments to add to kernel cmdline
      --debug               print debugging info
      -V VOLID, --volid VOLID
                            Set the ISO volume id, defaults to input's

Positional arguments
^^^^^^^^^^^^^^^^^^^^

    :ks: Kickstart to add to the ISO

    :input_iso: ISO to modify

    :output_iso: Full pathname of iso to be created


Create a kickstart boot.iso or DVD
----------------------------------

Create a kickstart like you normally would, kickstart documentation can be
`found here <https://pykickstart.readthedocs.io/en/latest/>`_, including the
``url`` and ``repo`` commands.  If you are creating a DVD and only need the
content on the DVD you can use the ``cdrom`` command to install without a
network connection. Then run ``mkksiso`` like this::

    mkksiso /PATH/TO/KICKSTART /PATH/TO/ISO /PATH/TO/NEW-ISO

This will create a new iso with the kickstart in the root directory, and the
kernel cmdline will have ``inst.ks=...`` added to it so that it will be
executed when the iso is booted (be careful not to boot on a system you don't
want to wipe out! There will be no prompting).

By default the volume id of the iso is preserved. You can set a custom volid
by passing ``-V`` and the string to set. The kernel cmdline will be changes, and the iso will have th custom volume id.
eg.::

    mkksiso -V "Test Only" /PATH/TO/KICKSTART /PATH/TO/ISO /PATH/TO/NEW-ISO


Adding package repos to a boot.iso
----------------------------------

You can add repo directories to the iso using ``--add /PATH/TO/REPO/``, make
sure it contains the ``repodata`` directory by running ``createrepo_c`` on it
first. In the kickstart you can refer to the directories (and files) on the iso
using ``file:///run/install/repo/DIRECTORY/``. You can then use these repos in
the kickstart like this::

    repo --name=extra-repo --baseurl=file:///run/install/repo/extra-repo/

Run ``mkksiso`` like so::

    mkksiso --add /PATH/TO/REPO/ /PATH/TO/KICKSTART /PATH/TO/ISO /PATH/TO/NEW-ISO


Create a liveimg boot.iso
-------------------------

You can use the kickstart `liveimg command
<https://pykickstart.readthedocs.io/en/latest/kickstart-docs.html#liveimg>`_,
to install a pre-generated disk image or tar to the system the iso is booting
on.

Create a disk image or tar with ``osbuild-composer`` or ``livemedia-creator``,
make sure the image includes tools expected by ``anaconda``, as well as the
kernel and bootloader support.  In ``osbuild-composer`` use the ``tar`` image
type and make sure to include the ``kernel``, ``grub2``, and ``grub2-tools``
packages.  If you plan to install it to a UEFI machine make sure to include
``grub2-efi`` and ``efibootmgr`` in the blueprint.

Add the ``root.tar.xz`` file to the iso using ``--add /PATH/TO/ROOT.TAR.XZ``,
and in the kickstart reference it with the ``liveimg`` command like this::

    liveimg --url=file:///run/install/repo/root.tar.xz

It is also a good idea to use the ``--checksum`` argument to ``liveimg``  to be
sure the file hasn't been corrupted::

    mkksiso --add /PATH/TO/root.tar.xz /PATH/TO/KICKSTART /PATH/TO/ISO /PATH/TO/NEW-ISO

When this iso is booted it will execute the kickstart and install the liveimg
contents to the system without any prompting.


How it works
------------

``mkksiso`` first examines the system to make sure the tools it needs are installed,
it will work with ``xorrisofs`` or ``mkisofs`` installed. It mounts the source iso,
and copies the directories that need to be modified to a temporary directory.

It then modifies the boot configuration files to include the ``inst.ks`` command,
and checks to see if the original iso supports EFI. If it does it regenerates the
EFI boot images with the new configuration, and then runs the available iso creation
tool to add the new files and directories to the new iso. If the architecture is
``x86_64`` it will also make sure the iso can be booted as an iso or from a USB
stick (hybridiso).

The last step is to update the iso checksums so that booting with test enabled
will pass.
