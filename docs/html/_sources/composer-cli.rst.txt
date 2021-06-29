composer-cli
============

:Authors:
    Brian C. Lane <bcl@redhat.com>

``composer-cli`` is an interactive tool for use with a WELDR API server,
managing blueprints, exploring available packages, and building new images.
`lorax-composer <lorax-composer.html>` and `osbuild-composer
<https://osbuild.org>` both implement compatible servers.

It requires server to be installed on the local system, and the user running it
needs to be a member of the ``weldr`` group. They do not need to be root, but
all of the `security precautions <lorax-composer.html#security>`_ apply.

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
<https://github.com/weldr/lorax/tree/rhel8-branch/tests/pylorax/blueprints/>`_.

Edit the file (it will be saved with a .toml extension) and change the
description, add a package or module to it. Send it back to the server by
running ``composer-cli blueprints push http-server.toml``. You can verify that it was
saved by viewing the changelog - ``composer-cli blueprints changes http-server``.

The full blueprint documentation `is here
<https://www.osbuild.org/guides/blueprint-reference/blueprint-reference.html>`_.

Build an image
----------------

Build a ``qcow2`` disk image from this blueprint by running ``composer-cli
compose start http-server qcow2``. It will print a UUID that you can use to
keep track of the build. You can also cancel the build if needed.

The available types of images is displayed by ``composer-cli compose types``.
Currently this consists of: alibaba, ami, ext4-filesystem, google, live-iso,
openstack, partitioned-disk, qcow2, tar, vhd, vmdk

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
OpenStack, and vSphere. The upload can be started when the build is finished
by using ``composer-cli compose start ...``. In order to access the service you need
to pass authentication details to composer-cli using a TOML file.

.. note::

    This is only supported when running the ``osbuild-composer`` API server.


Providers
---------

Providers are where the images are uploaded to. You
will need to gather some provider
specific information in order to authenticate with it. Please refer to the ``osbuild-composer``
documentation for the provider specific fields. You will then create a TOML file with the
name of the provider and the settings, like this::

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


Build an image and upload results
---------------------------------

With the settings stored in a TOML file::

    composer-cli compose start example-http-server ami "http image" aws-settings.toml

It will return the UUID of the image build. Once
the build has finished successfully it will start the upload process.


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
