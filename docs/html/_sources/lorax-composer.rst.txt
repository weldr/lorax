lorax-composer
==============

:Authors:
    Brian C. Lane <bcl@redhat.com>

``lorax-composer`` is an API server that allows you to build disk images using
`Blueprints`_ to describe the package versions to be installed into the image.
It is compatible with the Weldr project's bdcs-api REST protocol. More
information on Weldr can be found `on the Weldr blog <http://www.weldr.io>`_.

Behind the scenes it uses `livemedia-creator <livemedia-creator.html>`_ and
`Anaconda <https://anaconda-installer.readthedocs.io/en/latest/>`_ to handle the
installation and configuration of the images.

Installation
------------

The best way to install ``lorax-composer`` is to use ``sudo dnf install
lorax-composer composer-cli``, this will setup the weldr user and install the
systemd socket activation service. You will then need to enable it with ``sudo
systemctl enable lorax-composer.socket``. This will leave the server off until
the first request is made. Systemd will then launch the server and it will
remain running until the system is rebooted.

Quickstart
----------

1. Create a ``weldr`` user and group by running ``useradd weldr``
2. Remove any pre-existing socket directory with ``rm -rf /run/weldr/``
   A new directory with correct permissions will be created the first time the server runs.
3. Enable the socket activation with ``systemctl enable lorax-composer.socket`` or
   run it directly with ``lorax-composer /path/to/blueprints/``

The ``/path/to/blueprints/`` directory is where the blueprints' git repo will
be created, and all the blueprints created with the ``/api/v0/blueprints/new``
route will be stored.  If there are blueprint ``.toml`` files in the top level
of the directory they will be imported into the blueprint git storage when
``lorax-composer`` starts.

Logs
----

Logs are stored under ``/var/log/lorax-composer/`` and include all console
messages as well as extra debugging info and API requests.

Security
--------

Some security related issues that you should be aware of before running ``lorax-composer``:

* One of the API server threads needs to retain root privileges in order to run Anaconda.
* SELinux must be set to Permissive or disabled to allow ``livemedia-creator`` to run Anaconda.
* Only allow authorized users access to the ``weldr`` group and socket.

Since Anaconda kickstarts are used there is the possibility that a user could
inject commands into a blueprint that would result in the kickstart executing
arbitrary code on the host.  Only authorized users should be allowed to build
images using ``lorax-composer``.

lorax-composer cmdline arguments
--------------------------------

.. argparse::
   :ref: pylorax.api.cmdline.lorax_composer_parser
   :prog: lorax-composer


How it Works
------------

The server runs as root, and as ``weldr``. Communication with it is via a unix
domain socket (``/run/weldr/api.socket`` by default). The directory and socket
are owned by ``root:weldr`` so that any user in the ``weldr`` group can use the API
to control ``lorax-composer``.

At startup the server will check for the correct permissions and
ownership of a pre-existing directory, or it will create a new one if it
doesn't exist.  The socket path and group owner's name can be changed from the
cmdline by passing it the ``--socket`` and ``--group`` arguments.

It will then drop root privileges for the API thread and run as the ``weldr``
user. The queue and compose thread still runs as root because it needs to be
able to mount/umount files and run Anaconda.

Composing Images
----------------

The `welder-web <https://github.com/weldr/welder-web/>`_ GUI project can be used to construct
blueprints and create composes using a web browser.

Or use the command line with `composer-cli <composer-cli.html>`_.

Blueprints
----------

Blueprints are simple text files in `TOML <https://github.com/toml-lang/toml>`_ format that describe
which packages, and what versions, to install into the image. They can also define a limited set
of customizations to make to the final image.

Example blueprints can be found in the ``lorax-composer`` `test suite
<https://github.com/weldr/lorax/tree/master/tests/pylorax/blueprints/>`_, with a simple one
looking like this::

    name = "base"
    description = "A base system with bash"
    version = "0.0.1"

    [[packages]]
    name = "bash"
    version = "4.4.*"

The ``name`` field is the name of the blueprint. It can contain spaces, but they will be converted to ``-``
when it is written to disk. It should be short and descriptive.

``description`` can be a longer description of the blueprint, it is only used for display purposes.

``version`` is a `semver compatible <https://semver.org/>`_ version number. If
a new blueprint is uploaded with the same ``version`` the server will
automatically bump the PATCH level of the ``version``. If the ``version``
doesn't match it will be used as is. eg. Uploading a blueprint with ``version`` set to ``0.0.1`` when the existing blueprint ``version`` is ``0.0.1`` will result in the new blueprint being stored as ``version 0.0.1``.

[[packages]] and [[modules]]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These entries describe the package names and matching version glob to be installed into the image.

The names must match the names exactly, and the versions can be an exact match
or a filesystem-like glob of the version using ``*`` wildcards and ``?``
character matching.

NOTE: As of lorax-composer-29.2-1 the versions are not used for depsolving,
that is planned for a future release. And currently there are no differences
between ``packages`` and ``modules`` in ``lorax-composer``.

Customizations
~~~~~~~~~~~~~~

The ``[[customizations]]`` section can be used to configure the hostname of the final image. eg.::

    [[customizations]]
    hostname = "baseimage"


[[customizations.sshkey]]
*************************

Set an existing user's ssh key in the final image::

    [[customizations.sshkey]]
    user = "root"
    key = "PUBLIC SSH KEY"

The key will be added to the user's authorized_keys file.


[[customizations.user]]
***********************

Add a user to the image, and/or set their ssh key.
All fields for this section are optional except for the ``name``, here is a complete example::

    [[customizations.user]]
    name = "admin"
    description = "Administrator account"
    password = "$6$CHO2$3rN8eviE2t50lmVyBYihTgVRHcaecmeCk31L..."
    key = "PUBLIC SSH KEY"
    home = "/srv/widget/"
    shell = "/usr/bin/bash"
    groups = ["widget", "users", "wheel"]
    uid = 1200
    gid = 1200

If the password starts with ``$6$``, ``$5$``, or ``$2b$`` it will be stored as
an encrypted password. Otherwise it will be treated as a plain text password.


[[customizations.group]]
************************

Add a group to the image. ``name`` is required and ``gid`` is optional::

    [[customizations.group]]
    name = "widget"
    gid = 1130


Adding Output Types
-------------------

``livemedia-creator`` supports a large number of output types, and only some of
these are currently available via ``lorax-composer``. To add a new output type to
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
in ``./docs/fedora-minimal.ks``. You should remove the ``url`` and ``repo``
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
