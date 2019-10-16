composer-cli
============

:Authors:
    Brian C. Lane <bcl@redhat.com>

``composer-cli`` is used to interact with the ``lorax-composer`` API server, managing blueprints, exploring available packages, and building new images.

It requires `lorax-composer <lorax-composer.html>`_ to be installed on the
local system, and the user running it needs to be a member of the ``weldr``
group. They do not need to be root, but all of the `security precautions
<lorax-composer.html#security>`_ apply.

composer-cli cmdline arguments
------------------------------

.. argparse::
   :ref: composer.cli.cmdline.composer_cli_parser
   :prog: composer-cli

Edit a Blueprint
----------------

Start out by listing the available blueprints using ``composer-cli blueprints
list``, pick one and save it to the local directory by running ``composer-cli
blueprints save http-server``. If there are no blueprints available you can
copy one of the examples `from the test suite
<https://github.com/weldr/lorax/tree/master/tests/pylorax/blueprints/>`_.

Edit the file (it will be saved with a .toml extension) and change the
description, add a package or module to it. Send it back to the server by
running ``composer-cli blueprints push http-server.toml``. You can verify that it was
saved by viewing the changelog - ``composer-cli blueprints changes http-server``.

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
