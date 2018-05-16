lorax-composer
==============

:Authors:
    Brian C. Lane <bcl@redhat.com>

lorax-composer is an API server that is compatible with the Weldr project's
bdcs-api REST protocol. More information on Weldr can be found `on the Weldr
blog <http://www.weldr.io>`_.

The server runs as root, and communication with it is via a unix domain socket
(``/run/weldr/api.socket`` by default). The directory and socket are owned by
root:weldr so that any user in the weldr group can use the API to control
lorax-composer.

When starting the server it will check for the correct permissions and
ownership of a pre-existing directory, or it will create a new one if it
doesn't exist.  The socket path and group owner's name can be changed from the
cmdline by passing it the ``--socket`` and ``--group`` arguments.

As of version 19.7.7 it will drop root privileges for the API thread. The queue
and compose thread still runs as root because it needs to be able to
mount/umount files and run Anaconda.

Logs
----

Logs are stored under ``/var/log/lorax-composer/`` and include all console
messages as well as extra debugging info and API requests.

Quickstart
----------

1. Create a ``weldr`` user and group by running ``useradd weldr``
2. Remove any pre-existing socket directory with ``rm -rf /run/weldr/``
   A new directory with correct permissions will be created the first time the server runs.
3. Either start it via systemd with ``systemctl start lorax-composer`` or
   run it directly with ``lorax-composer /path/to/blueprints/``

The ``/path/to/blueprints/`` is where the blueprint's git repo will be created, and
all the blueprints created with the ``/api/v0/blueprints/new`` route will be stored.
If there are blueprint ``.toml`` files in the top level of the directory they will
be imported into the blueprint git storage.

Composing Images
----------------

As of version 19.7.7 lorax-composer can create ``tar`` output images. You can use curl to start
a compose like this::

    curl --unix-socket /run/weldr/api.socket -X POST -H "Content-Type: application/json" -d '{"blueprint_name": "http-server", "compose_type": "tar", "branch": "master"}' http:///api/v0/compose

And then monitor it by passing the returned build UUID to ``/compose/status/<uuid>``.

Version 19.7.10 adds support for ``live-iso`` and ``partitioned-disk``

Adding Output Types
-------------------

livemedia-creator supports a large number of output types, and only some of
these are currently available via lorax-composer. To add a new output type to
lorax-composer a kickstart file needs to be added to ``./share/composer/``. The
name of the kickstart is what will be used by the ``/compose/types`` route, and the
``compose_type`` field of the POST to start a compose. It also needs to have
code added to the :py:func:`pylorax.api.compose.compose_args` function. The
``_MAP`` entry in this function defines what lorax-composer will pass to
:py:func:`pylorax.installer.novirt_install` when it runs the compose.  When the
compose is finished the output files need to be copied out of the build
directory (``/var/lib/lorax/composer/results/<UUID>/compose/``),
:py:func:`pylorax.api.compose.move_compose_results` handles this for each type.
You should move them instead of copying to save space.

If the new output type does not have support in livemedia-creator it should be
added there first. This will make the output available to the widest number of
users.

Example: Add partitioned disk support
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Partitioned disk support is something that livemedia-creator already supports
via the ``--make-disk`` cmdline argument. To add this to lorax-composer it
needs 3 things:

* A ``partitioned-disk.ks`` file in ``./share/composer/``
* A new entry in the _MAP in :py:func:`pylorax.api.compose.compose_args`
* Add a bit of code to :py:func:`pylorax.api.compose.move_compose_results` to move the disk image from
  the compose directory to the results directory.

The ``partitioned-disk.ks`` is pretty similar to the example minimal kickstart
in ``./docs/rhel7-minimal.ks``. You should remove the ``url`` and ``repo``
commands, they will be added by the compose process. Make sure the bootloader
packages are included in the ``%packages`` section at the end of the kickstart,
and you will want to leave off the ``%end`` so that the compose can append the
list of packages from the blueprint.

The new ``_MAP`` entry should be a copy of one of the existing entries, but with ``make_disk`` set
to ``True``. Make sure that none of the other ``make_*`` options are ``True``. The ``image_name`` is
what the name of the final image will be.

``move_compose_results()`` can be as simple as moving the output file into
the results directory, or it could do some post-processing on it. The end of
the function should always clean up the ``./compose/`` directory, removing any
unneeded extra files. This is especially true for the ``live-iso`` since it produces
the contents of the iso as well as the boot.iso itself.
