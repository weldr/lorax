# NOTE: This specfile is generated from upstream at https://github.com/rhinstaller/lorax
# NOTE: Please submit changes as a pull request
%define debug_package %{nil}

Name:           lorax
Version:        30.12
Release:        1%{?dist}
Summary:        Tool for creating the anaconda install images

Group:          Applications/System
License:        GPLv2+
URL:            https://github.com/weldr/lorax
# To generate Source0 do:
# git clone https://github.com/weldr/lorax
# git checkout -b archive-branch lorax-%%{version}-%%{release}
# tito build --tgz
Source0:        %{name}-%{version}.tar.gz

BuildRequires:  python3-devel

Requires:       lorax-templates

Requires:       GConf2
Requires:       cpio
Requires:       device-mapper
Requires:       dosfstools
Requires:       e2fsprogs
Requires:       findutils
Requires:       gawk
Requires:       xorrisofs
Requires:       glib2
Requires:       glibc
Requires:       glibc-common
Requires:       gzip
Requires:       isomd5sum
Requires:       module-init-tools
Requires:       parted
Requires:       squashfs-tools >= 4.2
Requires:       util-linux
Requires:       xz-lzma-compat
Requires:       xz
Requires:       pigz
Requires:       pbzip2
Requires:       dracut >= 030
Requires:       kpartx

# Python modules
Requires:       libselinux-python3
Requires:       python3-mako
Requires:       python3-kickstart >= 3.19
Requires:       python3-dnf >= 3.2.0
Requires:       python3-librepo

%if 0%{?fedora}
# Fedora specific deps
%ifarch x86_64
Requires:       hfsplus-tools
%endif
%endif

%ifarch %{ix86} x86_64
Requires:       syslinux >= 6.03-1
Requires:       syslinux-nonlinux >= 6.03-1
%endif

%ifarch ppc64le
Requires:       grub2
Requires:       grub2-tools
%endif

%ifarch s390 s390x
Requires:       openssh
%endif

%ifarch %{arm}
Requires:       uboot-tools
%endif

# Moved image-minimizer tool to lorax
Provides:       appliance-tools-minimizer = %{version}-%{release}
Obsoletes:      appliance-tools-minimizer < 007.7-3

%description
Lorax is a tool for creating the anaconda install images.

It also includes livemedia-creator which is used to create bootable livemedia,
including live isos and disk images. It can use libvirtd for the install, or
Anaconda's image install feature.

%package lmc-virt
Summary:  livemedia-creator libvirt dependencies
Requires: lorax = %{version}-%{release}
Requires: qemu

# Fedora edk2 builds currently only support these arches
%ifarch %{ix86} x86_64 %{arm} aarch64
Requires: edk2-ovmf
%endif
Recommends: qemu-kvm

%description lmc-virt
Additional dependencies required by livemedia-creator when using it with qemu.

%package lmc-novirt
Summary:  livemedia-creator no-virt dependencies
Requires: lorax = %{version}-%{release}
Requires: anaconda-core
Requires: anaconda-tui
Requires: system-logos

%description lmc-novirt
Additional dependencies required by livemedia-creator when using it with --no-virt
to run Anaconda.

%package templates-generic
Summary:  Generic build templates for lorax and livemedia-creator
Requires: lorax = %{version}-%{release}
Provides: lorax-templates = %{version}-%{release}

%description templates-generic
Lorax templates for creating the boot.iso and live isos are placed in
/usr/share/lorax/templates.d/99-generic

%package composer
Summary: Lorax Image Composer API Server
# For Sphinx documentation build
BuildRequires: python3-flask python3-gobject libgit2-glib python3-pytoml python3-semantic_version

Requires: lorax = %{version}-%{release}
Requires(pre): /usr/bin/getent
Requires(pre): /usr/sbin/groupadd
Requires(pre): /usr/sbin/useradd

Requires: python3-pytoml
Requires: python3-semantic_version
Requires: libgit2
Requires: libgit2-glib
Requires: python3-flask
Requires: python3-gevent
Requires: anaconda-tui
Requires: qemu-img
Requires: tar

%{?systemd_requires}
BuildRequires: systemd

%description composer
lorax-composer provides a REST API for building images using lorax.

%package -n composer-cli
Summary: A command line tool for use with the lorax-composer API server

# From Distribution
Requires: python3-urllib3

%description -n composer-cli
A command line tool for use with the lorax-composer API server. Examine recipes,
build images, etc. from the command line.

%prep
%setup -q -n %{name}-%{version}

%build

%install
rm -rf $RPM_BUILD_ROOT
make DESTDIR=$RPM_BUILD_ROOT mandir=%{_mandir} install

# Install example blueprints from the test suite.
# This path MUST match the lorax-composer.service blueprint path.
mkdir -p $RPM_BUILD_ROOT/var/lib/lorax/composer/blueprints/
for bp in example-http-server.toml example-development.toml example-atlas.toml; do
    cp ./tests/pylorax/blueprints/$bp $RPM_BUILD_ROOT/var/lib/lorax/composer/blueprints/
done

%pre composer
getent group weldr >/dev/null 2>&1 || groupadd -r weldr >/dev/null 2>&1 || :
getent passwd weldr >/dev/null 2>&1 || useradd -r -g weldr -d / -s /sbin/nologin -c "User for lorax-composer" weldr >/dev/null 2>&1 || :

%post composer
%systemd_post lorax-composer.service
%systemd_post lorax-composer.socket

%preun composer
%systemd_preun lorax-composer.service
%systemd_preun lorax-composer.socket

%postun composer
%systemd_postun_with_restart lorax-composer.service
%systemd_postun_with_restart lorax-composer.socket

%files
%defattr(-,root,root,-)
%license COPYING
%doc AUTHORS docs/livemedia-creator.rst docs/product-images.rst
%doc docs/*ks
%{python3_sitelib}/pylorax
%{python3_sitelib}/*.egg-info
%{_sbindir}/lorax
%{_sbindir}/mkefiboot
%{_sbindir}/livemedia-creator
%{_bindir}/image-minimizer
%{_bindir}/mk-s390-cdboot
%dir %{_sysconfdir}/lorax
%config(noreplace) %{_sysconfdir}/lorax/lorax.conf
%dir %{_datadir}/lorax
%{_mandir}/man1/*.1*
%{_tmpfilesdir}/lorax.conf

%files lmc-virt

%files lmc-novirt

%files templates-generic
%dir %{_datadir}/lorax/templates.d
%{_datadir}/lorax/templates.d/*

%files composer
%config(noreplace) %{_sysconfdir}/lorax/composer.conf
%{python3_sitelib}/pylorax/api/*
%{_sbindir}/lorax-composer
%{_unitdir}/lorax-composer.service
%{_unitdir}/lorax-composer.socket
%dir %{_datadir}/lorax/composer
%{_datadir}/lorax/composer/*
%{_tmpfilesdir}/lorax-composer.conf
%dir %attr(0771, root, weldr) %{_sharedstatedir}/lorax/composer/
%dir %attr(0771, root, weldr) %{_sharedstatedir}/lorax/composer/blueprints/
%attr(0771, weldr, weldr) %{_sharedstatedir}/lorax/composer/blueprints/*

%files -n composer-cli
%{_bindir}/composer-cli
%{python3_sitelib}/composer/*
%{_sysconfdir}/bash_completion.d/composer-cli

%changelog
* Fri Jan 18 2019 Brian C. Lane <bcl@redhat.com> 30.12-1
- Don't exclude /dev from the `setfiles` in `novirt_install` (awilliam@redhat.com)

* Fri Jan 18 2019 Brian C. Lane <bcl@redhat.com> 30.11-1
- dracut-fips is no longer a subpackage, it is included in dracut. (bcl@redhat.com)

* Tue Jan 08 2019 Brian C. Lane <bcl@redhat.com> 30.10-1
- Remove unneeded else from for/else loop. It confuses pylint (bcl@redhat.com)
- Turn off pylint warning about docstring with backslash (bcl@redhat.com)
- Turn off smartquotes in Sphinx documentation (bcl@redhat.com)
- fixes #543 qemu -nodefconfig deprecated (afm404@gmail.com)
- fix spinx build warnings (afm404@gmail.com)
- Revert "lorax-composer: Cancel running Anaconda process" (bcl@redhat.com)
- set inst.stage2 for ppc64le image (rhbz#1577587) (dan@danny.cz)
- Allow customizations to be specified as a toml list (dshea@redhat.com)
- Make sure cancel_func is not None (bcl@redhat.com)
- drop ppc/ppc64 from tests (dan@danny.cz)
- drop ppc/ppc64 from spec (dan@danny.cz)
- all supported arches have docker (dan@danny.cz)
- drop big endian ppc/ppc64 support (dan@danny.cz)
- add qemu command mapping for ppc64le (dan@danny.cz)
- don't reduce initrd size on ppc64/ppc64le (dan@danny.cz)
- fbset has been retired (dan@danny.cz)
- Add timestamps to program.log and dnf.log (bcl@redhat.com)

* Mon Dec 17 2018 Brian C. Lane <bcl@redhat.com> 30.9-1
- lorax: Save information about rootfs filesystem size and usage (bcl@redhat.com)
- Turn on signed tags when using tito. (bcl@redhat.com)
- lorax-composer: Cancel running Anaconda process (bcl@redhat.com)
- Add cancel_func to virt and novirt_install functions (bcl@redhat.com)
- lorax-composer: Check for STATUS before deleting (bcl@redhat.com)
- Check for existing CANCEL request, and exit on FINISHED (bcl@redhat.com)
- tests: use the first IP address if more than 1 retruned from OpenStack (atodorov@redhat.com)
- tests: remove a debugging command (atodorov@redhat.com)
- Add openstack to the image type list in the docs (dshea@redhat.com)

* Thu Dec 06 2018 Brian C. Lane <bcl@redhat.com> 30.8-1
- lorax-composer: Handle packages with multiple builds (bcl@redhat.com)
- lorax-composer: Check the queue and results at startup (bcl@redhat.com)
- Teach OpenStack test to distinguish between RHEL and Fedora (atodorov@redhat.com)
- Use full path for Azure playbook as well (atodorov@redhat.com)
- Use a temporary dir for ssh keys during testing (atodorov@redhat.com)
- Update V_DATASTORE b/c defaults appear to have been changed (atodorov@redhat.com)
- Clone pyvmomi samples in the correct directory (atodorov@redhat.com)
- Use full path when pushing toml files during testing (atodorov@redhat.com)
- Add empty ci_after_success target for Jenkins (atodorov@redhat.com)
- Implicitly specify ssh key directory/files for testing (atodorov@redhat.com)
- [test] Clean up containers.json (atodorov@redhat.com)
- Teach AWS test to distinguish between RHEL and Fedora (atodorov@redhat.com)

* Thu Nov 29 2018 Brian C. Lane <bcl@redhat.com> 30.7-1
- lorax-composer: Install selinux-policy-targeted in images (bcl@redhat.com)
- Remove setfiles from mkrootfsimage (bcl@redhat.com)
- New lorax documentation - 30.7 (bcl@redhat.com)
- Remove SELinux Permissive checks (bcl@redhat.com)
- Drop minor version from php package in blueprint (atodorov@redhat.com)
- Use a temporary shared dir when testing (atodorov@redhat.com)
- Copy blueprints used for testing to temporary directory (atodorov@redhat.com)
- Add make targets for Jenkins (atodorov@redhat.com)
- Add --no-system-repos to lorax-composer (bcl@redhat.com)
- Install grubby-deprecated package for ARMv7 (javierm@redhat.com)
- Teach test_cli.sh to execute test scripts via arguments (atodorov@redhat.com)
- new test: build an image and deploy it on Azure (atodorov@redhat.com)
- Fix typo in comment (atodorov@redhat.com)
- Fix reporting of coverage results to coverall.io (bcl@redhat.com)
- For OpenStack build image with rng-tools installed (atodorov@redhat.com)
- Add tests for partitioned disk images (bcl@redhat.com)
- Create a kpartx_disk_img function (bcl@redhat.com)
- Add tests for pylorax.imgutils (bcl@redhat.com)
- Add tests to test_creator.py (bcl@redhat.com)
- Fix make_appliance and the libvirt.tmpl (bcl@redhat.com)
- Add some tests for creator.py (bcl@redhat.com)
- tests: Add executils test (bcl@redhat.com)
- tests: Add sysutils test (bcl@redhat.com)
- tests: Add discinfo test (bcl@redhat.com)
- tests: Add treeinfo test (bcl@redhat.com)
- Stop using build to run the tests, allow using podman (bcl@redhat.com)
- new test: build and deploy an image in OpenStack (atodorov@redhat.com)
- Fix typos in VM_NAME and cleanup command (atodorov@redhat.com)
- new test: build and deploy images on vSphere (atodorov@redhat.com)
- Update docs with info about ssh keys (atodorov@redhat.com)

* Mon Oct 29 2018 Brian C. Lane <bcl@redhat.com> 30.6-1
- new test: build and deploy images on AWS (atodorov@redhat.com)
- Disable execution of new tests which need Docker privileged mode (atodorov@redhat.com)
- New tests: build ext4-filesystem and partitioned-disk composes (atodorov@redhat.com)
- Update tmux version in tests (atodorov@redhat.com)
- Add tests for ltmpl.py (bcl@redhat.com)
- Move get_dnf_base_object into a module (bcl@redhat.com)
- New lorax documentation - 30.5 (bcl@redhat.com)
- Build manpages for composer-cli and lorax-composer (bcl@redhat.com)
- Add --squashfs-only option to drop inner rootfs.img layer (marmarek@invisiblethingslab.com)
- Update php version to 7.3.* (bcl@redhat.com)
- Update the projects tests to use DNF Repo object (bcl@redhat.com)
- dnf changed the type of gpgkey to a tuple (bcl@redhat.com)
- Install python3-librepo in the test container (bcl@redhat.com)
- lorax: Log when SOURCE_DATE_EPOCH is used for the current time (bcl@redhat.com)
- Drop non-determinism from default templates (marmarek@invisiblethingslab.com)
- Use SOURCE_DATE_EPOCH for volumeid of efi boot image (marmarek@invisiblethingslab.com)
- Preserve timestamps when building fs image (marmarek@invisiblethingslab.com)
- Use SOURCE_DATE_EPOCH for metadata timestamps (marmarek@invisiblethingslab.com)

* Fri Oct 12 2018 Brian C. Lane <bcl@redhat.com> 30.5-1
- Update depsolving with suggestions from dnf (#1636239) (bcl@redhat.com)
- Disable false context-manager pylint error (bcl@redhat.com)
- Fix directory creation for blueprints (bcl@redhat.com)
- Update the tests for new make_dnf_dir arguments. (bcl@redhat.com)
- Change make_dnf_dirs to be run as root (bcl@redhat.com)
- Fix vhd images (vponcova@redhat.com)

* Tue Oct 09 2018 Brian C. Lane <bcl@redhat.com> 30.4-1
- Add an openstack image type (bcl@redhat.com)
- Add cloud-init to vhd images. (dshea@redhat.com)
- Replace /etc/machine-id with an empty file (dshea@redhat.com)

* Mon Oct 08 2018 Brian C. Lane <bcl@redhat.com> 30.3-1
- Update cli tests to use composer-cli name (bcl@redhat.com)
- Revert "Rename composer-cli to composer" (bcl@redhat.com)

* Fri Oct 05 2018 Brian C. Lane <bcl@redhat.com> 30.2-1
- Work around dnf problem with multiple repos (bcl@redhat.com)
- Add and enable cloud-init for ami images (lars@karlitski.net)
- Make no-virt generated images sparser (dshea@redhat.com)
- New lorax documentation - 30.1 (bcl@redhat.com)

* Wed Oct 03 2018 Brian C. Lane <bcl@redhat.com> 30.1-1
- Report an error if the blueprint doesn't exist (bcl@redhat.com)
- cli: Clarify error message for unprivileged access (lars@karlitski.net)
- Write a rootpw line if no root customizations in the blueprint (bcl@redhat.com)

* Tue Oct 02 2018 Brian C. Lane <bcl@redhat.com> 30.0-1
- Add beakerlib to Dockerfile.test (bcl@redhat.com)
- Adjust the new templates for locked root (bcl@redhat.com)
- Adjust projects test for DNF 3.6.1 tuple issue (bcl@redhat.com)
- Don't try to append to DNF config value that can't take it
  (awilliam@redhat.com)
- Always update repo metadata when building an image (bcl@redhat.com)
- Add a test for repo metadata expiration (bcl@redhat.com)
- Add tests for setting root password and ssh key with blueprints
  (bcl@redhat.com)
- Use rootpw for setting the root password instead of user (bcl@redhat.com)
- Lock the root account, except on live-iso (bcl@redhat.com)
- Add new compose types to compose sanity test (dshea@redhat.com)
- Add virt guest agents to the qcow2 compose (dshea@redhat.com)
- Add a vmdk compose type. (dshea@redhat.com)
- Add a vhd compose type for Azure images (dshea@redhat.com)
- Add an ami compose type for AWS images (dshea@redhat.com)
- Remove --fstype from the generated part line (dshea@redhat.com)
- Also run `make check` on travis (lars@karlitski.net)
- Fix pylint errors and warnings (lars@karlitski.net)
- New cli test covering basic compose commands (atodorov@redhat.com)
- Update glusterfs to 5.* (atodorov@redhat.com)
- Execute bash tests for composer-cli (atodorov@redhat.com)
- Rename composer-cli to composer (lars@karlitski.net)
- Include python3-pyatspi on boot.iso (#1506595) (bcl@redhat.com)
- Start a HACKING.md file and document how to run the tests (stefw@redhat.com)
- tests: Fix tests so they run on Fedora 28 (stefw@redhat.com)
- Ignore files created by tests (stefw@redhat.com)
- Makefile: Fix the 'make install' target (stefw@redhat.com)
- Replace CJK fonts with Google Noto CJK (akira@tagoh.org)
- Fix a DeprecationWarning (dshea@redhat.com)
- Fix the expected versions of blueprint components (dshea@redhat.com)
- Switch the test container back to rawhide (dshea@redhat.com)

* Fri Sep 07 2018 Brian C. Lane <bcl@redhat.com> 29.15-1
- Add a Makefile target for building html docs using a rawhide environment (bcl@redhat.com)
- Revert "Don't activate default auto connections after switchroot" (rvykydal@redhat.com)
- Need to explicitly require python3-librepo (#1626413) (bcl@redhat.com)
- New lorax documentation - 29.14 (bcl@redhat.com)

* Thu Sep 06 2018 Brian C. Lane <bcl@redhat.com> 29.14-1
- Add the create ISO component for ARMv7 (pbrobinson@gmail.com)
- Don't activate default auto connections after switchroot (rvykydal@redhat.com)
- Ignore a pylint warning about UnquotingConfigParser get args (bcl@redhat.com)
- Ditch all use of pyanaconda's simpleconfig (awilliam@redhat.com)

* Wed Aug 29 2018 Brian C. Lane <bcl@redhat.com> 29.13-1
- Update the example blueprints for rawhide (bcl@redhat.com)
- Bump required dnf version to 3.2.0 for module_platform_id support (bcl@redhat.com)
- Add support for DNF 3.2 module_platform_id config value (bcl@redhat.com)
- lorax: Only run depmod on the installed kernels (bcl@redhat.com)

* Tue Aug 28 2018 Brian C. Lane <bcl@redhat.com> 29.12-1
- Minor package fixes for aarch64/ARMv7 (pbrobinson@gmail.com)

* Mon Aug 27 2018 Brian C. Lane <bcl@redhat.com> 29.11-1
- Fix composer-cli blueprints changes to get correct total (bcl@redhat.com)
- Fix blueprints/list and blueprints/changes to return the correct total (bcl@redhat.com)
- Add tests for limit=0 routes (bcl@redhat.com)
- Add a function to get_url_json_unlimited to retrieve the total (bcl@redhat.com)
- Fix tests related to blueprint name changes (bcl@redhat.com)
- Add 'example' to the example blueprint names (bcl@redhat.com)
- Use urllib.parse instead of urlparse (bcl@redhat.com)
- In composer-cli, request all results (dshea@redhat.com)
- Add tests for /compose/status filter arguments (dshea@redhat.com)
- Allow '*' as a uuid in /compose/status/<uuid> (dshea@redhat.com)
- Add filter arguments to /compose/status (dshea@redhat.com)
- composer-cli should not log to a file by default (bcl@redhat.com)
- Add documentation for using a DVD as the package source (bcl@redhat.com)
- Set TCP listen backlog for API socket to SOMAXCONN (lars@karlitski.net)
- Update Arm architectures for the latest requirements (pbrobinson@gmail.com)
- New lorax documentation - 29.11 (bcl@redhat.com)
- Add a note about using lorax-composer.service (bcl@redhat.com)
- Ignore dnf.logging when building docs (bcl@redhat.com)
- Bring back import-state.service (#1615332) (rvykydal@redhat.com)
- Fix a little bug in running "modules list". (clumens@redhat.com)
- Fix bash_completion.d typo (bcl@redhat.com)
- Move disklabel and UEFI support to compose.py (bcl@redhat.com)
- Fix more tests. (clumens@redhat.com)
- Change INVALID_NAME to INVALID_CHARS. (clumens@redhat.com)
- Update composer-cli for the new error return types. (clumens@redhat.com)
- Add default error IDs everywhere else. (clumens@redhat.com)
- Add error IDs to things that can go wrong when running a compose.  (clumens@redhat.com)
- Add error IDs for common source-related errors. (clumens@redhat.com)
- Add error IDs for unknown modules and unknown projects. (clumens@redhat.com)
- Add error IDs for when an unknown commit is requested. (clumens@redhat.com)
- Add error IDs for when an unknown blueprint is requested.  (clumens@redhat.com)
- Add error IDs for when an unknown build UUID is requested.  (clumens@redhat.com)
- Add error IDs for bad state conditions. (clumens@redhat.com)
- Change the error return type for bad limit= and offset=. (clumens@redhat.com)
- Don't sort error messages. (clumens@redhat.com)
- Fix bash completion of compose info (bcl@redhat.com)
- Add + to the allowed API string character set (bcl@redhat.com)
- Add job_* timestamp support to compose status (bcl@redhat.com)
- Drop .decode from UTF8_TEST_STRING (bcl@redhat.com)
- Add input string checks to the branch and format arguments (bcl@redhat.com)
- Add a test for invalid characters in the API route (bcl@redhat.com)
- Add etc/bash_completion.d/composer-cli (wwoods@redhat.com)
- composer-cli: clean up "list" commands (wwoods@redhat.com)
- Fix logging argument (bcl@redhat.com)
- Update get_system_repo for dnf (bcl@redhat.com)
- Update ConfigParser usage for Py3 (bcl@redhat.com)
- Update StringIO use for Py3 (bcl@redhat.com)
- Add a test for the pylorax.api.timestamp functions (bcl@redhat.com)
- Fix write_timestamp for py3 (bcl@redhat.com)
- Return a JSON error instead of a 404 on certain malformed URLs.  (clumens@redhat.com)
- Return an error if /modules/info doesn't return anything.  (clumens@redhat.com)
- Update documentation (#409). (clumens@redhat.com)
- Use constants instead of strings (#409). (clumens@redhat.com)
- Write timestamps when important events happen during the compose (#409).  (clumens@redhat.com)
- Return multiple timestamps in API results (#409). (clumens@redhat.com)
- Add a new timestamp.py file to the API directory (#409). (clumens@redhat.com)
- Use the first enabled system repo for the test (bcl@redhat.com)
- Show more details when the system repo delete test fails (bcl@redhat.com)
- Add composer-cli function tests (bcl@redhat.com)
- Add a test library (bcl@redhat.com)
- composer-cli: Add support for Group to blueprints diff (bcl@redhat.com)
- Update status.py to use new handle_api_result (bcl@redhat.com)
- Update sources.py to use new handle_api_result (bcl@redhat.com)
- Update projects.py to use new handle_api_result (bcl@redhat.com)
- Update modules.py to use new handle_api_result (bcl@redhat.com)
- Update compose.py to use new handle_api_result (bcl@redhat.com)
- Update blueprints.py to use new handle_api_result (bcl@redhat.com)
- Modify handle_api_result so it can be used in more places (bcl@redhat.com)
- Fix help output on the compose subcommand. (clumens@redhat.com)
- Add timestamps to "compose-cli compose status" output. (clumens@redhat.com)
- And then add real output to the status command. (clumens@redhat.com)
- Add the beginnings of a new status subcommand. (clumens@redhat.com)
- Document that you shouldn't run lorax-composer twice. (clumens@redhat.com)
- Add PIDFile to the .service file. (clumens@redhat.com)
- composer-cli: Fix non-zero epoch in projets info (bcl@redhat.com)

* Fri Jul 20 2018 Brian C. Lane <bcl@redhat.com> 29.10-1
- New lorax documentation - 29.10 (bcl@redhat.com)
- Add dnf.transaction to list of modules for sphinx to ignore (bcl@redhat.com)
- Log and exit on metadata update errors at startup (bcl@redhat.com)
- Check /projects responses for null values. (bcl@redhat.com)
- Clarify error message from /source/new (bcl@redhat.com)
- Update samba and rsync versions for tests (bcl@redhat.com)
- Support loading groups from the kickstart template files.  (clumens@redhat.com)
- Add group-based tests. (clumens@redhat.com)
- Include groups in depsolving. (clumens@redhat.com)
- Add support for groups to blueprints. (clumens@redhat.com)
- Add help output to each subcommand. (clumens@redhat.com)
- Split the help output into its own module. (clumens@redhat.com)
- If the help subcommand is given, print the help output. (clumens@redhat.com)
- Check the compose templates at startup (bcl@redhat.com)
- Fix a couple typos in lorax-composer docs. (bcl@redhat.com)

* Wed Jun 27 2018 Brian C. Lane <bcl@redhat.com> 29.9-1
- DNF 3: progress callback constants moved to dnf.transaction (awilliam@redhat.com)
- Include example blueprints in the rpm (bcl@redhat.com)
- Make sure /run/weldr has correct ownership and permissions (bcl@redhat.com)

* Fri Jun 22 2018 Brian C. Lane <bcl@redhat.com> 29.8-1
- Fixing bug where test did not try to import pylorax.version (sophiafondell)
- Add the ability to enable DNF plugins for lorax (bcl@redhat.com)
- Allow more than 1 bash build in tests (bcl@redhat.com)
- Update tests for glusterfs 4.1.* on rawhide (bcl@redhat.com)
- Install 'hostname' in runtime-install (for iSCSI) (awilliam@redhat.com)
- Add redhat.exec to s390 .treeinfo (bcl@redhat.com)
- It's /compose/cancel, not /blueprints/cancel. (clumens@redhat.com)
- Retry losetup if loop_attach fails (bcl@redhat.com)
- Add reqpart to example kickstart files (bcl@redhat.com)
- Increase default ram used with lmc and virt to 2048 (bcl@redhat.com)

* Thu Jun 07 2018 Brian C. Lane <bcl@redhat.com> 29.7-1
- New lorax documentation - 29.7 (bcl@redhat.com)
- Add --dracut-arg support to lorax (bcl@redhat.com)
- Make LogRequestHandler configurable (mkolman@redhat.com)
- gevent has deprecated .wsgi, should use .pywsgi instead (bcl@redhat.com)

* Mon Jun 04 2018 Brian C. Lane <bcl@redhat.com> 29.6-1
- New lorax documentation - 29.6 (bcl@redhat.com)
- Override Sphinx documentation version with LORAX_VERSION (bcl@redhat.com)
- Add support for sources to composer-cli (bcl@redhat.com)
- Fix DNF related issues with source selection (bcl@redhat.com)
- Fix handling bad source repos and add a test (bcl@redhat.com)
- Speed up test_dnfbase.py (bcl@redhat.com)
- Make sure new sources show up in the source/list output (bcl@redhat.com)
- Fix make_dnf_dirs (bcl@redhat.com)
- Update test_server for rawhide (bcl@redhat.com)
- Add support for user defined package sources API (bcl@redhat.com)

* Wed May 23 2018 Brian C. Lane <bcl@redhat.com> 29.5-1
- templates: Stop using gconfset (walters@verbum.org)
- Add support for version globs to blueprints (bcl@redhat.com)
- Update atlas blueprint (bcl@redhat.com)

* Thu May 17 2018 Brian C. Lane <bcl@redhat.com> 29.4-1
- Update documentation (#1430906) (bcl@redhat.com)
- really kill kernel-bootwrapper on ppc (dan@danny.cz)

* Mon May 14 2018 Brian C. Lane <bcl@redhat.com> 29.3-1
- Update the README with relevant URLs (bcl@redhat.com)
- Fix documentation for enabling lorax-composer.socket (bcl@redhat.com)
- Add support for systemd socket activation (bcl@redhat.com)
- Remove -boot-info-table from s390 boot.iso creation (#1478448) (bcl@redhat.com)
- Update the generated html docs (bcl@redhat.com)
- Add documentation for lorax-composer and composer-cli (bcl@redhat.com)
- Move lorax-composer and composer-cli argument parsing into modules (bcl@redhat.com)
- Update composer templates for use with Fedora (bcl@redhat.com)
- Add new cmdline args to compose_args settings (bcl@redhat.com)
- lorax-composer also requires tar (bcl@redhat.com)
- Remove temporary files after run_compose (bcl@redhat.com)
- Add --proxy to lorax-composer cmdline (bcl@redhat.com)
- Pass the --tmp value into run_creator and cleanup after a crash (bcl@redhat.com)
- Add --tmp to lorax-composer and set default tempdir (bcl@redhat.com)
- Set lorax_templates to the correct directory (bcl@redhat.com)
- Adjust the disk size estimates to match Anaconda (bcl@redhat.com)
- Skip creating groups with the same name as a user (bcl@redhat.com)
- Add user and group creation to blueprint (bcl@redhat.com)
- Add blueprint customization support for hostname and ssh key (bcl@redhat.com)
- Update setup.py for lorax-composer and composer-cli (bcl@redhat.com)
- Add composer-cli and tests (bcl@redhat.com)
- Fix the compose arguments for the Fedora version of Anaconda (bcl@redhat.com)
- Add selinux check to lorax-composer (bcl@redhat.com)
- Update test_server for blueprint and Yum to DNF changes. (bcl@redhat.com)
- Convert Yum usage to DNF (bcl@redhat.com)
- workspace read and write needs UTF-8 conversion (bcl@redhat.com)
- Return an empty list if depsolve results are empty (bcl@redhat.com)
- The git blob needs to be bytes (bcl@redhat.com)
- Remove bin and sbin from nose (bcl@redhat.com)
- Update the test blueprints (bcl@redhat.com)
- Ignore more pylint errors (bcl@redhat.com)
- Use default commit sort order instead of TIME (bcl@redhat.com)
- Add lorax-composer and the composer kickstart templates (bcl@redhat.com)
- Update pylorax.api.projects for DNF usage (bcl@redhat.com)
- Update dnfbase (formerly yumbase) for DNF support (bcl@redhat.com)
- Move core of livemedia-creator into pylorax.creator (bcl@redhat.com)
- Update dnfbase tests (bcl@redhat.com)
- Convert lorax-composer yum base object to DNF (bcl@redhat.com)
- Use 2to3 to convert the python2 lorax-composer code to python3 (bcl@redhat.com)
- Add the tests from lorax-composer branch (bcl@redhat.com)
- Update .dockerignore (bcl@redhat.com)
- Update lorax.spec for lorax-composer (bcl@redhat.com)
- livemedia-creator: Move core functions into pylorax modules (bcl@redhat.com)

* Thu May 03 2018 Brian C. Lane <bcl@redhat.com> 29.2-1
- Enable testing in Travis and collecting of coverage history (atodorov@redhat.com)
- Check selinux state before creating output directory (bcl@redhat.com)
- change installed packages on ppc (dan@danny.cz)
- drop support for 32-bit ppc (dan@danny.cz)
- remove redundant mkdir (dan@danny.cz)

* Mon Apr 09 2018 Brian C. Lane <bcl@redhat.com> 29.1-1
- Fix anaconda metapackage name (mkolman@redhat.com)
- Include the anaconda-install-env-deps metapackage (mkolman@redhat.com)
- Update the URL in lorax.spec to point to new Lorax location (bcl@redhat.com)
- lorax's gh-pages are under ./lorax/ so make the links relative
  (bcl@redhat.com)
- New lorax documentation - 29.0 (bcl@redhat.com)

* Thu Mar 15 2018 Brian C. Lane <bcl@redhat.com> 29.0-1
- Update Copyright year to 2018 in Sphinx docs (bcl@redhat.com)
- Add links to documentation for previous versions (bcl@redhat.com)
- make docs now also builds html (bcl@redhat.com)
- Update default releasever to Fedora 29 (rawhide) (jkonecny@redhat.com)

* Mon Feb 26 2018 Brian C. Lane <bcl@redhat.com> 28.8-1
- cleanup: don't remove libgstgl (dusty@dustymabe.com)

* Fri Feb 23 2018 Brian C. Lane <bcl@redhat.com> 28.7-1
- Fix _install_branding (bcl@redhat.com)
- livemedia-creator --no-virt requires a system-logos package (bcl@redhat.com)
- Revert "add system-logos dependency for syslinux" (bcl@redhat.com)

* Thu Feb 22 2018 Brian C. Lane <bcl@redhat.com> 28.6-1
- add system-logos dependency for syslinux (pbrobinson@gmail.com)
- Really don't try to build EFI images on i386 (awilliam@redhat.com)

* Mon Jan 29 2018 Brian C. Lane <bcl@redhat.com> 28.5-1
- Don't try to build efi images for basearch=i386. (pjones@redhat.com)
- LMC: Make the QEMU RNG device optional (yturgema@redhat.com)

* Wed Jan 17 2018 Brian C. Lane <bcl@redhat.com> 28.4-1
- Write the --variant string to .buildstamp as 'Variant=' (bcl@redhat.com)
- Run the pylorax tests with 'make test' (bcl@redhat.com)
- Fix installpkg exclude operation (bcl@redhat.com)

* Wed Jan 03 2018 Brian C. Lane <bcl@redhat.com> 28.3-1
- Add --old-chroot to the mock example cmdlines (bcl@redhat.com)
- Don't try and install kernel-PAE on i686 any more (awilliam@redhat.com)
- New lorax documentation - 28.2 (bcl@redhat.com)

* Tue Nov 28 2017 Brian C. Lane <bcl@redhat.com> 28.2-1
- Add documentation about mock changes (#1473880) (bcl@redhat.com)
- Log a more descriptive error when setfiles fails (#1499771) (bcl@redhat.com)
- Add /usr/share/lorax/templates.d ownership to lorax-templates-generic
  (bcl@redhat.com)
- Add dependencies for SE/HMC (vponcova@redhat.com)
- Allow installpkgs to do version pinning through globbing (claudioz@fb.com)
- Storaged re-merged with udisks2 upstream (sgallagh@redhat.com)

* Thu Oct 19 2017 Brian C. Lane <bcl@redhat.com> 28.1-1
- Use bytes when writing strings in mk-s390-cdboot (#1504026) (bcl@redhat.com)

* Tue Oct 17 2017 Brian C. Lane <bcl@redhat.com> 28.0-1
- Add make test target and update .gitignore (atodorov@redhat.com)
- Add first unit test so we can start collecting coverage (atodorov@redhat.com)
- Convert mk-s390-cdboot to python3 (#1497141) (bcl@redhat.com)
- Update false positives (atodorov@redhat.com)
- Rename parameters to match names that dnf uses (atodorov@redhat.com)
- Don't override 'line' from outer scope (atodorov@redhat.com)
- Add swaplabel command (vponcova@redhat.com)

* Wed Sep 27 2017 Brian C. Lane <bcl@redhat.com> 27.11-1
- s390 doesn't need to graft product.img and updates.img into /images (#1496461) (bcl@redhat.com)
- distribute the mk-s390-cdboot utility (dan@danny.cz)
- update graft variable in s390 template (dan@danny.cz)

* Mon Sep 18 2017 Brian C. Lane <bcl@redhat.com> 27.10-1
- Restore all of the grub2-tools on x86_64 and i386 (#1492197) (bcl@redhat.com)

* Fri Aug 25 2017 Brian C. Lane <bcl@redhat.com> 27.9-1
- x86.tmpl: initially define compressargs as empty string (awilliam@redhat.com)
- x86.tmpl: ensure efiarch64 is defined (awilliam@redhat.com)

* Thu Aug 24 2017 Brian C. Lane <bcl@redhat.com> 27.8-1
- Fix grub2-efi-ia32-cdboot and shim-ia32 bits. (pjones@redhat.com)

* Thu Aug 24 2017 Brian C. Lane <bcl@redhat.com> 27.7-1
- Make 64-bit kernel on 32-bit firmware work for x86 efi machines (pjones@redhat.com)
- Don't install rdma bits on 32-bit ARM (#1483278) (awilliam@redhat.com)

* Mon Aug 14 2017 Brian C. Lane <bcl@redhat.com> 27.6-1
- Add creation of a bootable s390 iso (#1478448) (bcl@redhat.com)
- Add mk-s360-cdboot utility (#1478448) (bcl@redhat.com)
- Fix systemctl command (#1478247) (bcl@redhat.com)
- Add version output (#1335456) (bcl@redhat.com)
- Include the dracut fips module in the initrd (#1341280) (bcl@redhat.com)
- Make sure loop device is setup (#1462150) (bcl@redhat.com)

* Wed Aug 02 2017 Brian C. Lane <bcl@redhat.com> 27.5-1
- runtime-cleanup: preserve a couple more gstreamer libs (awilliam@redhat.com)
- perl is needed on all arches now (dennis@ausil.us)

* Mon Jul 10 2017 Brian C. Lane <bcl@redhat.com> 27.4-1
- runtime-cleanup.tmpl: don't delete localedef (jlebon@redhat.com)

* Tue Jun 20 2017 Brian C. Lane <bcl@redhat.com> 27.3-1
- Don't remove libmenu.so library during cleanup on PowerPC (sinny@redhat.com)

* Thu Jun 01 2017 Brian C. Lane <bcl@redhat.com> 27.2-1
- Remove filegraft from arm.tmpl (#1457906) (bcl@redhat.com)
- Use anaconda-core to detect buildarch (sgallagh@redhat.com)

* Wed May 31 2017 Brian C. Lane <bcl@redhat.com> 27.1-1
- arm.tmpl import basename (#1457055) (bcl@redhat.com)

* Tue May 30 2017 Brian C. Lane <bcl@redhat.com> 27.0-1
- Bump version to 27.0 (bcl@redhat.com)
- Try all packages when installpkg --optional is used. (bcl@redhat.com)
- Add support for aarch64 live images (bcl@redhat.com)
- pylint: Ignore different argument lengths for dnf callback. (bcl@redhat.com)
- Adds additional callbacks keyword for start() (jmracek@redhat.com)
- Add ppc64-diag for Power64 platforms (pbrobinson@gmail.com)
- livemedia-creator: Add release license files to / of the iso (bcl@redhat.com)
- lorax: Add release license files to / of the iso (bcl@redhat.com)
- INSTALL_ROOT and LIVE_ROOT are not available during %%post (bcl@redhat.com)
- Add --noverifyssl to lorax (#1430483) (bcl@redhat.com)
