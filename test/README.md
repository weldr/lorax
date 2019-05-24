# Integration Tests

lorax uses Cockpit's integration test framework and infrastructure. To do this,
we're checking out Cockpit's `bots/` subdirectory. It contains links to test
images and tools to manipulate and start virtual machines from them.

Each test is run on a new instance of a virtual machine. 

## Dependencies

These dependencies are needed on Fedora to run tests locally:

    $ sudo dnf install curl expect \
        libvirt libvirt-client libvirt-daemon libvirt-python \
        python python-libguestfs python-lxml libguestfs-xfs \
        python3 libvirt-python3 \
        libguestfs-tools qemu qemu-kvm rpm-build rsync xz

## Building a test VM

To build a test VM, run

    $ make vm

This downloads a base image from Cockpit's infrastructure. You can control
which image is downloaded with the `TEST_OS` environment variable. Cockpit's
[documentation](https://github.com/cockpit-project/cockpit/blob/master/test/README.md#test-configuration)
lists accepted values. It then creates a new image based on that (a qemu
snapshot) in `tests/images`, which contain the current `tests/` directory and
have newly built rpms from the current checkout installed.

To delete the generated image, run

    $ make vm-reset

Base images are stored in `bots/images`. Set `TEST_DATA` to override this
directory.

## Running tests

After building a test image, run

    $ ./test/check-cli [TESTNAME]

or any of the other `check-*` scripts. To debug a test failure, pass `--sit`.
This will keep the test machine running after the first failure and print an
ssh line to connect to it.

Run `make vm` after changing tests or lorax source to recreate the test
machine. It is usually not necessary to reset the VM.

## Updating images

The `bots/` directory is checked out from Cockpit when `make vm` is first run.
To get the latest images you need to update it manually (in order not to poll
GitHub every time):

    $ make -B bots
