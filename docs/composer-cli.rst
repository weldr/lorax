composer-cli
============

:Authors:
    Brian C. Lane <bcl@redhat.com>

``composer-cli`` is an interactive tool for use with a WELDR API server,
managing blueprints, exploring available packages, and building new images.  As
of Fedora 34, `osbuild-composer <https://osbuild.org>` is the recommended
server.

It requires the server  to be installed on the local system, and the user
running it needs to be a member of the ``weldr`` group.

composer-cli cmdline arguments
------------------------------

.. argparse::
   :ref: composer.cli.cmdline.composer_cli_parser
   :prog: composer-cli

Edit a Blueprint
----------------

Start out by listing the available blueprints using ``composer-cli blueprints
list``, pick one and save it to the local directory by running ``composer-cli
blueprints save http-server``.

Edit the file (it will be saved with a .toml extension) and change the
description, add a package or module to it. Send it back to the server by
running ``composer-cli blueprints push http-server.toml``. You can verify that it was
saved by viewing the changelog - ``composer-cli blueprints changes http-server``.

See the `Example Blueprint`_ for an example.

Build an image
----------------

Build a ``qcow2`` disk image from this blueprint by running ``composer-cli
compose start http-server qcow2``. It will print a UUID that you can use to
keep track of the build. You can also cancel the build if needed.

The available types of images is displayed by ``composer-cli compose types``.
Currently this consists of: alibaba, ami, ext4-filesystem, google, hyper-v,
live-iso, openstack, partitioned-disk, qcow2, tar, vhd, vmdk

You can optionally start an upload of the finished image, see `Image Uploads`_ for
more information.


Monitor the build status
------------------------

Monitor it using ``composer-cli compose status``, which will show the status of
all the builds on the system. You can view the end of the anaconda build logs
once it is in the ``RUNNING`` state using ``composer-cli compose log UUID``
where UUID is the UUID returned by the start command.

Once the build is in the ``FINISHED`` state you can download the image.

Download the image
------------------

Downloading the final image is done with ``composer-cli compose image UUID`` and it will
save the qcow2 image as ``UUID-disk.qcow2`` which you can then use to boot a VM like this::

    qemu-kvm --name test-image -m 1024 -hda ./UUID-disk.qcow2


Image Uploads
-------------

``composer-cli`` can upload the images to a number of services, including AWS,
OpenStack, and vSphere. The upload can be started when the build is finished,
by using ``composer-cli compose start ...`` or an existing image can be uploaded
with ``composer-cli upload start ...``. In order to access the service you need
to pass authentication details to composer-cli using a TOML file, or reference
a previously saved profile.

.. note::
    With ``osbuild-composer`` you can only specify upload targets during
    the compose process.


Providers
---------

Providers are the services providers with Ansible playbook support under
``/usr/share/lorax/lifted/providers/``, you will need to gather some provider
specific information in order to authenticate with it. You can view the
required fields using ``composer-cli providers template <PROVIDER>``, eg. for AWS
you would run::

    composer-cli upload template aws

The output looks like this::

    provider = "aws"

    [settings]
    aws_access_key = "AWS Access Key"
    aws_bucket = "AWS Bucket"
    aws_region = "AWS Region"
    aws_secret_key = "AWS Secret Key"

Save this into an ``aws-credentials.toml`` file and use it when running ``start``.

AWS
^^^

The access key and secret key can be created by going to the
``IAM->Users->Security Credentials`` section and creating a new access key. The
secret key will only be shown when it is first created so make sure to record
it in a secure place. The region should be the region that you want to use the
AMI in, and the bucket can be an existing bucket, or a new one, following the
normal AWS bucket naming rules. It will be created if it doesn't already exist.

When uploading the image it is first uploaded to the s3 bucket, and then
converted to an AMI.  If the conversion is successful the s3 object will be
deleted. If it fails, re-trying after correcting the problem will re-use the
object if you have not deleted it in the meantime, speeding up the process.


Profiles
--------

Profiles store the authentication settings associated with a specific provider.
Providers can have multiple profiles, as long as their names are unique. For
example, you may have one profile for testing and another for production
uploads.

Profiles are created by pushing the provider settings template to the server using
``composer-cli providers push <PROFILE.TOML>`` where ``PROFILE.TOML`` is the same as the
provider template, but with the addition of a ``profile`` field. For example, an AWS
profile named ``test-uploads`` would look like this::

    provider = "aws"
    profile = "test-uploads"

    [settings]
    aws_access_key = "AWS Access Key"
    aws_bucket = "AWS Bucket"
    aws_region = "AWS Region"
    aws_secret_key = "AWS Secret Key"

You can view the profile by using ``composer-cli providers aws test-uploads``.


Build an image and upload results
---------------------------------

If you have a profile named ``test-uploads``::

    composer-cli compose start example-http-server ami "http image" aws test-uploads

Or if you have the settings stored in a TOML file::

    composer-cli compose start example-http-server ami "http image" aws-settings.toml

It will return the UUID of the image build, and the UUID of the upload. Once
the build has finished successfully it will start the upload process, which you
can monitor with ``composer-cli upload info <UPLOAD-UUID>``

You can also view the upload logs from the Ansible playbook with::

    ``composer-cli upload log <UPLOAD-UUID>``

The type of the image must match the type supported by the provider.


Upload an existing image
------------------------

You can upload previously built images, as long as they are in the ``FINISHED`` state, using ``composer-cli upload start ...```. If you have a profile named ``test-uploads``::

    composer-cli upload start <UUID> "http-image" aws test-uploads

Or if you have the settings stored in a TOML file::

    composer-cli upload start <UUID> "http-image" aws-settings.toml

This will output the UUID of the upload, which can then be used to monitor the status in the same way
described above.


Debugging
---------

There are a couple of arguments that can be helpful when debugging problems.
These are only meant for debugging and should not be used to script access to
the API. If you need to do that you can communicate with it directly in the
language of your choice.

``--json`` will return the server's response as a nicely formatted json output
instead of printing what the command would usually print.

``--test=1`` will cause a compose start to start creating an image, and then
end with a failed state.

``--test=2`` will cause a compose to start and then end with a finished state,
without actually composing anything.


Blueprint Reference
-------------------

Blueprints are simple text files in `TOML <https://github.com/toml-lang/toml>`_ format that describe
which packages, and what versions, to install into the image. They can also define a limited set
of customizations to make to the final image.

A basic blueprint looks like this::

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
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

These entries describe the package names and matching version glob to be installed into the image.

The names must match the names exactly, and the versions can be an exact match
or a filesystem-like glob of the version using ``*`` wildcards and ``?``
character matching.

.. note::
    Currently there are no differences between ``packages`` and ``modules``
    in ``osbuild-composer``. Both are treated like an rpm package dependency.

For example, to install ``tmux-2.9a`` and ``openssh-server-8.*``, you would add
this to your blueprint::

    [[packages]]
    name = "tmux"
    version = "2.9a"

    [[packages]]
    name = "openssh-server"
    version = "8.*"



[[groups]]
^^^^^^^^^^

The ``groups`` entries describe a group of packages to be installed into the image.  Package groups are
defined in the repository metadata.  Each group has a descriptive name used primarily for display
in user interfaces and an ID more commonly used in kickstart files.  Here, the ID is the expected
way of listing a group.

Groups have three different ways of categorizing their packages:  mandatory, default, and optional.
For purposes of blueprints, mandatory and default packages will be installed.  There is no mechanism
for selecting optional packages.

For example, if you want to install the ``anaconda-tools`` group you would add this to your
blueprint::

    [[groups]]
    name="anaconda-tools"

``groups`` is a TOML list, so each group needs to be listed separately, like ``packages`` but with
no version number.


Customizations
^^^^^^^^^^^^^^

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

.. warning::

    ``key`` expects the entire content of ``~/.ssh/id_rsa.pub``


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

.. warning::

    ``key`` expects the entire content of ``~/.ssh/id_rsa.pub``


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

.. note::
   Currently ``osbuild-composer`` does not support ``repos.git``

The ``[[repos.git]]`` entries are used to add files from a `git repository <https://git-scm.com/>`_
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

Example Blueprint
-----------------

This example blueprint will install the ``tmux``, ``git``, and ``vim-enhanced``
packages. It will set the ``root`` ssh key, add the ``widget`` and ``admin``
users as well as a ``students`` group::

    name = "example-custom-base"
    description = "A base system with customizations"
    version = "0.0.1"

    [[packages]]
    name = "tmux"
    version = "*"

    [[packages]]
    name = "git"
    version = "*"

    [[packages]]
    name = "vim-enhanced"
    version = "*"

    [customizations]
    hostname = "custombase"

    [[customizations.sshkey]]
    user = "root"
    key = "A SSH KEY FOR ROOT"

    [[customizations.user]]
    name = "widget"
    description = "Widget process user account"
    home = "/srv/widget/"
    shell = "/usr/bin/false"
    groups = ["dialout", "users"]

    [[customizations.user]]
    name = "admin"
    description = "Widget admin account"
    password = "$6$CHO2$3rN8eviE2t50lmVyBYihTgVRHcaecmeCk31LeOUleVK/R/aeWVHVZDi26zAH.o0ywBKH9Tc0/wm7sW/q39uyd1"
    home = "/srv/widget/"
    shell = "/usr/bin/bash"
    groups = ["widget", "users", "students"]
    uid = 1200

    [[customizations.user]]
    name = "plain"
    password = "simple plain password"

    [[customizations.user]]
    name = "bart"
    key = "SSH KEY FOR BART"
    groups = ["students"]

    [[customizations.group]]
    name = "widget"

    [[customizations.group]]
    name = "students"
