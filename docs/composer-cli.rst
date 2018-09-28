composer
========

:Authors:
    Brian C. Lane <bcl@redhat.com>

``composer`` is used to interact with the ``lorax-composer`` API server, managing blueprints, exploring available packages, and building new images.

It requires `lorax-composer <lorax-composer.html>`_ to be installed on the
local system, and the user running it needs to be a member of the ``weldr``
group. They do not need to be root, but all of the `security precautions
<lorax-composer.html#security>`_ apply.

composer cmdline arguments
--------------------------

.. argparse::
   :ref: composer.cli.cmdline.composer_cli_parser
   :prog: composer

Edit a Blueprint
----------------

Start out by listing the available blueprints using ``composer blueprints
list``, pick one and save it to the local directory by running ``composer
blueprints save http-server``. If there are no blueprints available you can
copy one of the examples `from the test suite
<https://github.com/weldr/lorax/tree/master/tests/pylorax/blueprints/>`_.

Edit the file (it will be saved with a .toml extension) and change the
description, add a package or module to it. Send it back to the server by
running ``composer blueprints push http-server.toml``. You can verify that it was
saved by viewing the changelog - ``composer blueprints changes http-server``.

Build an image
----------------

Build a ``qcow2`` disk image from this blueprint by running ``composer
compose start http-server qcow2``. It will print a UUID that you can use to
keep track of the build. You can also cancel the build if needed.

The available types of images is displayed by ``composer compose types``.
Currently this consists of: ami, ext4-filesystem, live-iso, partitioned-disk,
qcow2, tar, vhd

Monitor the build status
------------------------

Monitor it using ``composer compose status``, which will show the status of
all the builds on the system. You can view the end of the anaconda build logs
once it is in the ``RUNNING`` state using ``composer compose log UUID``
where UUID is the UUID returned by the start command.

Once the build is in the ``FINISHED`` state you can download the image.

Download the image
------------------

Downloading the final image is done with ``composer compose image UUID`` and it will
save the qcow2 image as ``UUID-disk.qcow2`` which you can then use to boot a VM like this::

    qemu-kvm --name test-image -m 1024 -hda ./UUID-disk.qcow2
