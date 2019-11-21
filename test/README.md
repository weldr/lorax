# Integration Tests

lorax uses Cockpit's integration test framework and infrastructure. To do this,
we're checking out
[cockpit-project/bots/](https://github.com/cockpit-project/bots) repository.
It contains links to test
images and tools to manipulate and start virtual machines from them.

Each test is run on a new instance of a virtual machine.
Branch/test scenario matrix is configured in
[testmap.py](https://github.com/cockpit-project/bots/blob/master/task/testmap.py).

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
snapshot) in `test/images`, which contain the current `test/` and `tests/`
directories and
have newly built rpms from the current checkout installed.

To delete the generated image, run

    $ make vm-reset

Base images are stored in `bots/images`. Set `TEST_DATA` to override this
directory.

To configure the image with all repositories found on the host system use

    $ make vm-local-repos

You may also define `REPOS_DIR` variable to point to another directory
containing yum .repo files. By default the value is `/etc/yum.repos.d`!
This is mostly useful when running tests by hand on a downstream snapshot!

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

## GitHub integration

Tests are automatically triggered for every pull request. To disable tests for
a pull request, add the `no-test` label when opening it.

To interact with GitHub from scripts in `bots/`, generate [a
token](https://github.com/settings/tokens) with at least *repo:status*,
*public_repo*, and *read:org* permissions, and put it into
`~/.config/github-token`.

You can retry a failed test with:

    $ bots/tests-trigger --repo weldr/lorax <PR> <test>

If no test is given, all failed tests will be retried. Pass `--allow` to
trigger tests on a pull request by an outside contributor.


## Azure setup

To authenticate Ansible (used in tests) with Azure you need to set the following
environment variables:
`AZURE_SUBSCRIPTION_ID`, `AZURE_TENANT`, `AZURE_CLIENT_ID` and `AZURE_SECRET`.

From the left-hand side menu at https://portal.azure.com select
*Resource groups* >> *Click on composer RG*. Above the resulting list of resources
you can see *Subscription ID* -> `AZURE_SUBSCRIPTION_ID`.

From the left-hand side menu at https://portal.azure.com select
*Azure Active Directory* >> *App registrations* >> New registration. Give it a name
and leave the rest with default values. Once the AD application has been created
you can click on its name to view its properties. There you have:

* Directory (tenant) ID -> `AZURE_TENANT`
* Application (client) ID -> `AZURE_CLIENT_ID`
* Certificates & secrets (on the left) >> New client secret -> `AZURE_SECRET`

Next make sure the newly created AD App has access to the storage account.
From the left-hand side menu at https://portal.azure.com select
*Storage accounts* >> *composerredhat* >> *Access control (IAM)* >>
*Role assignments* >> *Add* >> *Add role assignment*. Then make sure to select
- Role == Contributor
- Scope == Resource group (Inherited)
- AD app name (not the user owning the application)


Storage account itself must be of type **StorageV2** so tests can upload blobs
to it!
