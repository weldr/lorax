lorax-composer
==============

:Authors:
    Brian C. Lane <bcl@redhat.com>

``lorax-composer`` is a WELDR API server that allows you to build disk images using
`Blueprints`_ to describe the package versions to be installed into the image.
It is compatible with the Weldr project's bdcs-api REST protocol. More
information on Weldr can be found `on the Weldr blog <http://www.weldr.io>`_.

Behind the scenes it uses `livemedia-creator <livemedia-creator.html>`_ and
`Anaconda <https://anaconda-installer.readthedocs.io/en/latest/>`_ to handle the
installation and configuration of the images.

.. note::

    ``lorax-composer`` is now deprecated. It is being replaced by the
    ``osbuild-composer`` WELDR API server which implements more features (eg.
    ostree, image uploads, etc.) You can still use ``composer-cli`` and
    ``cockpit-composer`` with ``osbuild-composer``. See the documentation or
    the `osbuild website <https://www.osbuild.org/>`_ for more information.


Important Things To Note
------------------------

* As of version 30.7 SELinux can be set to Enforcing. The current state is
  logged for debugging purposes and if there are SELinux denials they should
  be reported as a bug.

* All image types lock the root account, except for live-iso. You will need to either
  use one of the `Customizations`_ methods for setting a ssh key/password, install a
  package that creates a user, or use something like `cloud-init` to setup access at
  boot time.


Installation
------------

The best way to install ``lorax-composer`` is to use ``sudo dnf install
lorax-composer composer-cli``, this will setup the weldr user and install the
systemd socket activation service. You will then need to enable it with ``sudo
systemctl enable lorax-composer.socket && sudo systemctl start
lorax-composer.socket``. This will leave the server off until the first request
is made. Systemd will then launch the server and it will remain running until
the system is rebooted.

Quickstart
----------

1. Create a ``weldr`` user and group by running ``useradd weldr``
2. Remove any pre-existing socket directory with ``rm -rf /run/weldr/``
   A new directory with correct permissions will be created the first time the server runs.
3. Enable the socket activation with ``systemctl enable lorax-composer.socket
   && sudo systemctl start lorax-composer.socket``.

NOTE: You can also run it directly with ``lorax-composer /path/to/blueprints``.  However,
``lorax-composer`` does not react well to being started both on the command line and via
socket activation at the same time.  It is therefore recommended that you run it directly
on the command line only for testing or development purposes.  For real use or development
of other projects that simply use the API, you should stick to socket activation only.

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
doesn't match it will be used as is. eg. Uploading a blueprint with ``version``
set to ``0.1.0`` when the existing blueprint ``version`` is ``0.0.1`` will
result in the new blueprint being stored as ``version 0.1.0``.

[[packages]] and [[modules]]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These entries describe the package names and matching version glob to be installed into the image.

The names must match the names exactly, and the versions can be an exact match
or a filesystem-like glob of the version using ``*`` wildcards and ``?``
character matching.

NOTE: As of lorax-composer-29.2-1 the versions are not used for depsolving,
that is planned for a future release. And currently there are no differences
between ``packages`` and ``modules`` in ``lorax-composer``.

[[groups]]
~~~~~~~~~~

These entries describe a group of packages to be installed into the image.  Package groups are
defined in the repository metadata.  Each group has a descriptive name used primarily for display
in user interfaces and an ID more commonly used in kickstart files.  Here, the ID is the expected
way of listing a group.

Groups have three different ways of categorizing their packages:  mandatory, default, and optional.
For purposes of blueprints, mandatory and default packages will be installed.  There is no mechanism
for selecting optional packages.

Customizations
~~~~~~~~~~~~~~

The ``[customizations]`` section can be used to configure the hostname of the final image. eg.::

    [customizations]
    hostname = "baseimage"

This is optional and may be left out to use the defaults.


[customizations.kernel]
***********************

This allows you to append arguments to the bootloader's kernel commandline. This will not have any
effect on ``tar`` or ``ext4-filesystem`` images since they do not include a bootloader.

For example::

    [customizations.kernel]
    append = "nosmt=force"


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


[customizations.timezone]
*************************

Customizing the timezone and the NTP servers to use for the system::

    [customizations.timezone]
    timezone = "US/Eastern"
    ntpservers = ["0.north-america.pool.ntp.org", "1.north-america.pool.ntp.org"]

The values supported by ``timezone`` can be listed by running ``timedatectl list-timezones``.

If no timezone is setup the system will default to using `UTC`. The ntp servers are also
optional and will default to using the distribution defaults which are fine for most uses.

In some image types there are already NTP servers setup, eg. Google cloud image, and they
cannot be overridden because they are required to boot in the selected environment. But the
timezone will be updated to the one selected in the blueprint.


[customizations.locale]
***********************

Customize the locale settings for the system::

    [customizations.locale]
    languages = ["en_US.UTF-8"]
    keyboard = "us"

The values supported by ``languages`` can be listed by running ``localectl list-locales`` from
the command line.

The values supported by ``keyboard`` can be listed by running ``localectl list-keymaps`` from
the command line.

Multiple languages can be added. The first one becomes the
primary, and the others are added as secondary. One or the other of ``languages``
or ``keyboard`` must be included (or both) in the section.


[customizations.firewall]
*************************

By default the firewall blocks all access except for services that enable their ports explicitly,
like ``sshd``. This command can be used to open other ports or services. Ports are configured using
the port:protocol format::

    [customizations.firewall]
    ports = ["22:tcp", "80:tcp", "imap:tcp", "53:tcp", "53:udp"]

Numeric ports, or their names from ``/etc/services`` can be used in the ``ports`` enabled/disabled lists.

The blueprint settings extend any existing settings in the image templates, so if ``sshd`` is
already enabled it will extend the list of ports with the ones listed by the blueprint.

If the distribution uses ``firewalld`` you can specify services listed by ``firewall-cmd --get-services``
in a ``customizations.firewall.services`` section::

    [customizations.firewall.services]
    enabled = ["ftp", "ntp", "dhcp"]
    disabled = ["telnet"]

Remember that the ``firewall.services`` are different from the names in ``/etc/services``.

Both are optional, if they are not used leave them out or set them to an empty list ``[]``. If you
only want the default firewall setup this section can be omitted from the blueprint.

NOTE: The ``Google`` and ``OpenStack`` templates explicitly disable the firewall for their environment.
This cannot be overridden by the blueprint.

[customizations.services]
*************************

This section can be used to control which services are enabled at boot time.
Some image types already have services enabled or disabled in order for the
image to work correctly, and cannot be overridden. eg. ``ami`` requires
``sshd``, ``chronyd``, and ``cloud-init``. Without them the image will not
boot. Blueprint services are added to, not replacing, the list already in the
templates, if any.

The service names are systemd service units. You may specify any systemd unit
file accepted by ``systemctl enable`` eg. ``cockpit.socket``::

    [customizations.services]
    enabled = ["sshd", "cockpit.socket", "httpd"]
    disabled = ["postfix", "telnetd"]


[[repos.git]]
~~~~~~~~~~~~~

The ``[[repos.git]]`` entries are used to add files from a `git repository<https://git-scm.com/>`
repository to the created image. The repository is cloned, the specified ``ref`` is checked out
and an rpm is created to install the files to a ``destination`` path. The rpm includes a summary
with the details of the repository and reference used to create it. The rpm is also included in the
image build metadata.

To create an rpm named ``server-config-1.0-1.noarch.rpm`` you would add this to your blueprint::

    [[repos.git]]
    rpmname="server-config"
    rpmversion="1.0"
    rpmrelease="1"
    summary="Setup files for server deployment"
    repo="PATH OF GIT REPO TO CLONE"
    ref="v1.0"
    destination="/opt/server/"

* rpmname: Name of the rpm to create, also used as the prefix name in the tar archive
* rpmversion: Version of the rpm, eg. "1.0.0"
* rpmrelease: Release of the rpm, eg. "1"
* summary: Summary string for the rpm
* repo: URL of the get repo to clone and create the archive from
* ref: Git reference to check out. eg. origin/branch-name, git tag, or git commit hash
* destination: Path to install the / of the git repo at when installing the rpm

An rpm will be created with the contents of the git repository referenced, with the files
being installed under ``/opt/server/`` in this case.

``ref`` can be any valid git reference for use with ``git archive``. eg. to use the head
of a branch set it to ``origin/branch-name``, a tag name, or a commit hash.

Note that the repository is cloned in full each time a build is started, so pointing to a
repository with a large amount of history may take a while to clone and use a significant
amount of disk space. The clone is temporary and is removed once the rpm is created.


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
in ``./docs/rhel-minimal.ks``. You should remove the ``url`` and ``repo``
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

Package Sources
---------------

By default lorax-composer uses the host's configured repositories. It copies
the ``*.repo`` files from ``/etc/yum.repos.d/`` into
``/var/lib/lorax/composer/repos.d/`` at startup, these are immutable system
repositories and cannot be deleted or changed. If you want to add additional
repos you can put them into ``/var/lib/lorax/composer/repos.d/`` or use the
``/api/v0/projects/source/*`` API routes to create them.

The new source can be added by doing a POST to the ``/api/v0/projects/source/new``
route using JSON (with `Content-Type` header set to `application/json`) or TOML
(with it set to `text/x-toml`).  The format of the source looks like this (in
TOML)::

    name = "custom-source-1"
    url = "https://url/path/to/repository/"
    type = "yum-baseurl"
    proxy = "https://proxy-url/"
    check_ssl = true
    check_gpg = true
    gpgkey_urls = ["https://url/path/to/gpg-key"]

The ``proxy`` and ``gpgkey_urls`` entries are optional. All of the others are required. The supported
types for the urls are:

* ``yum-baseurl`` is a URL to a yum repository.
* ``yum-mirrorlist`` is a URL for a mirrorlist.
* ``yum-metalink`` is a URL for a metalink.

If ``check_ssl`` is true the https certificates must be valid. If they are self-signed you can either set
this to false, or add your Certificate Authority to the host system.

If ``check_gpg`` is true the GPG key must either be installed on the host system, or ``gpgkey_urls``
should point to it.

You can edit an existing source (other than system sources), by doing a POST to the ``new`` route
with the new version of the source. It will overwrite the previous one.

A list of existing sources is available from ``/api/v0/projects/source/list``, and detailed info
on a source can be retrieved with the ``/api/v0/projects/source/info/<source-name>`` route. By default
it returns JSON but it can also return TOML if ``?format=toml`` is added to the request.

Non-system sources can be deleted by doing a ``DELETE`` request to the
``/api/v0/projects/source/delete/<source-name>`` route.

The documentation for the source API routes can be `found here <pylorax.api.html#api-v0-projects-source-list>`_

The configured sources are used for all blueprint depsolve operations, and for composing images.
When adding additional sources you must make sure that the packages in the source do not
conflict with any other package sources, otherwise depsolving will fail.

DVD ISO Package Source
~~~~~~~~~~~~~~~~~~~~~~

In some situations the system may want to *only* use a DVD iso as the package
source, not the repos from the network. ``lorax-composer`` and ``anaconda``
understand ``file://`` URLs so you can mount an iso on the host, and replace the
system repo files with a configuration file pointing to the DVD.

* Stop the ``lorax-composer.service`` if it is running
* Move the repo files in ``/etc/yum.repos.d/`` someplace safe
* Create a new ``iso.repo`` file in ``/etc/yum.repos.d/``::

     [iso]
     name=iso
     baseurl=file:///mnt/iso/
     enabled=1
     gpgcheck=1
     gpgkey=file:///mnt/iso/RPM-GPG-KEY-redhat-release

* Remove all the cached repo files from ``/var/lib/lorax/composer/repos/``
* Restart the ``lorax-composer.service``
* Check the output of ``composer-cli status show`` for any output specific depsolve errors.
  For example, the DVD usually does not include ``grub2-efi-*-cdboot-*`` so the live-iso image
  type will not be available.

If you want to *add* the DVD source to the existing sources you can do that by
mounting the iso and creating a source file to point to it as described in the
`Package Sources`_ documentation.  In that case there is no need to remove the other
sources from ``/etc/yum.repos.d/`` or clear the cached repos.
