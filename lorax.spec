# NOTE: This specfile is generated from upstream at https://github.com/rhinstaller/lorax
# NOTE: Please submit changes as a pull request
%define debug_package %{nil}

Name:           lorax
Version:        35.0
Release:        1%{?dist}
Summary:        Tool for creating the anaconda install images

License:        GPLv2+
URL:            https://github.com/weldr/lorax
# To generate Source0 do:
# git clone https://github.com/weldr/lorax
# git checkout -b archive-branch lorax-%%{version}-%%{release}
# tito build --tgz
Source0:        %{name}-%{version}.tar.gz

BuildRequires:  python3-devel
BuildRequires:  make
BuildRequires:  systemd-rpm-macros

Requires:       lorax-templates

Requires:       cpio
Requires:       device-mapper
Requires:       dosfstools
Requires:       e2fsprogs
Requires:       findutils
Requires:       gawk
Requires:       xorriso
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
Requires:       psmisc

# Python modules
Requires:       libselinux-python3
Requires:       python3-mako
Requires:       python3-kickstart >= 3.19
Requires:       python3-dnf >= 3.2.0
Requires:       python3-librepo
Requires:       python3-pycdlib

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
Requires:       s390utils >= 2.15.0-2
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

%package docs
Summary: Lorax html documentation
Requires: lorax = %{version}-%{release}

%description docs
Includes the full html documentation for lorax, livemedia-creator, and the pylorax library.

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
Requires: anaconda-install-env-deps
Requires: system-logos
Requires: python3-psutil

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

%package -n composer-cli
Summary: A command line tool for use with the lorax-composer API server

# From Distribution
Requires: python3-urllib3
Requires: python3-toml

%description -n composer-cli
A command line tool for use with the lorax-composer API server. Examine blueprints,
build images, etc. from the command line.

%prep
%setup -q -n %{name}-%{version}

%build

%install
rm -rf $RPM_BUILD_ROOT
make DESTDIR=$RPM_BUILD_ROOT mandir=%{_mandir} install

%files
%defattr(-,root,root,-)
%license COPYING
%doc AUTHORS
%doc docs/composer-cli.rst docs/lorax.rst docs/livemedia-creator.rst docs/product-images.rst
%doc docs/lorax-composer.rst
%doc docs/*ks
%{python3_sitelib}/pylorax
%{python3_sitelib}/*.egg-info
%{_sbindir}/lorax
%{_sbindir}/mkefiboot
%{_sbindir}/livemedia-creator
%{_sbindir}/mkksiso
%{_bindir}/image-minimizer
%dir %{_sysconfdir}/lorax
%config(noreplace) %{_sysconfdir}/lorax/lorax.conf
%dir %{_datadir}/lorax
%{_mandir}/man1/lorax.1*
%{_mandir}/man1/livemedia-creator.1*
%{_mandir}/man1/mkksiso.1*
%{_tmpfilesdir}/lorax.conf

%files docs
%doc docs/html/*

%files lmc-virt

%files lmc-novirt

%files templates-generic
%dir %{_datadir}/lorax/templates.d
%{_datadir}/lorax/templates.d/*

%files -n composer-cli
%{_bindir}/composer-cli
%{python3_sitelib}/composer/*
%{_sysconfdir}/bash_completion.d/composer-cli
%{_mandir}/man1/composer-cli.1*

%changelog
* Wed Mar 03 2021 Brian C. Lane <bcl@redhat.com> 35.0-1
- New lorax documentation - 35.0 (bcl@redhat.com)
- Makefile: Add test-in-podman and docs-in-podman build targets (bcl@redhat.com)
- isolinux.cfg: Rename the 'vesa' menu entry to 'basic' (bcl@redhat.com)
- composer-cli: Add support for start-ostree --url URL (bcl@redhat.com)

* Wed Mar 03 2021 Brian C. Lane <bcl@redhat.com>
- New lorax documentation - 35.0 (bcl@redhat.com)
- Makefile: Add test-in-podman and docs-in-podman build targets (bcl@redhat.com)
- isolinux.cfg: Rename the 'vesa' menu entry to 'basic' (bcl@redhat.com)
- composer-cli: Add support for start-ostree --url URL (bcl@redhat.com)

* Mon Feb 15 2021 Brian C. Lane <bcl@redhat.com> 34.9-1
- Use inst.rescue to trigger rescue mode (awilliam@redhat.com)
  Resolves: rhbz#1928318
* Mon Feb 08 2021 Brian C. Lane <bcl@redhat.com> 34.8-1
- Use image dependencies metapackage (vslavik@redhat.com)
- tests: Include the fedora-updates repo when testing boot.iso building (bcl@redhat.com)

* Wed Jan 20 2021 Brian C. Lane <bcl@redhat.com> 34.7-1
- live/x86.tmpl: Copy livecd-iso-to-disk script, if installed (david.ward@ll.mit.edu)
- templates: Copy license files from the correct path (david.ward@ll.mit.edu)
- test: Fix vm.install for non-LVM cloud images (martin@piware.de)

* Wed Dec 16 2020 Brian C. Lane <bcl@redhat.com> 34.6-1
- Remove LD_PRELOAD libgomp.so.1 from lmc --no-virt (bcl@redhat.com)
- Add POSTIN scriptlet error to the log monitor list (bcl@redhat.com)
- Improve lmc no-virt error handling (bcl@redhat.com)
- lorax.spec: Drop GConf2 requirement (bcl@redhat.com)

* Mon Nov 30 2020 Brian C. Lane <bcl@redhat.com> 34.5-1
- Don't remove libldap_r libraries during runtime-cleanup.tmpl (spichugi@redhat.com)
- Do not use '--loglevel' option when running Anaconda (vtrefny@redhat.com)
- Makefile: quiet rsync use in testing (bcl@redhat.com)
- Switch to using GitHub Actions instead of Travis CI (bcl@redhat.com)

* Mon Nov 02 2020 Brian C. Lane <bcl@redhat.com> 34.4-1
- Update the default release version to 34 (bcl@redhat.com)
- Remove mdmonitor service from boot.iso (bcl@redhat.com)
- Switch to using upstream mk-s390image for s390 cdboot.img creation (bcl@redhat.com)
- sshd_config: Apply suggested changes (bcl@redhat.com)
- lorax.spec: Add BuildRequires on systemd-rpm-macros for tmpfilesdir macro (bcl@redhat.com)

* Wed Oct 07 2020 Brian C. Lane <bcl@redhat.com> 34.3-1
- composer: Fix open file warnings (bcl@redhat.com)
- ltmpl: Fix deprecated escape in docstring (bcl@redhat.com)
- tests: Fix open file warning in test_execWithRedirect (bcl@redhat.com)
- Cleanup imgutil open files and processes (bcl@redhat.com)
- tests: Remove test_del_execReadlines (bcl@redhat.com)
- Fix unclosed files (bcl@redhat.com)
- test: Use Python dev mode during testing (bcl@redhat.com)
- tests: Update composer-cli blueprint server tests (bcl@redhat.com)
- runtime-cleanup: Delete .pyc files (bcl@redhat.com)
- New lorax documentation - 34.3 (bcl@redhat.com)
- doc: Add Blueprint documentation and example to composer-cli.rst (bcl@redhat.com)
- docs: Update docs for lorax-composer removal (bcl@redhat.com)
- tests: Remove unused lorax-composer tests (bcl@redhat.com)
- Remove lorax-composer, it has been replaced by osbuild-composer (bcl@redhat.com)

* Tue Sep 29 2020 Brian C. Lane <bcl@redhat.com> 34.2-1
- runtime-cleanup: Remove ncurses package (bcl@redhat.com)

* Mon Sep 14 2020 Brian C. Lane <bcl@redhat.com> 34.1-1
- Fix broken single-item tuples in a few places (awilliam@redhat.com)
- Drop dpaa2 firmware on non-aarch64 arches (awilliam@redhat.com)
- Drop firmware for Mellanox Spectrum (awilliam@redhat.com)
- runtime-cleanup: big refresh of stale things (awilliam@redhat.com)

* Tue Sep 08 2020 Brian C. Lane <bcl@redhat.com> 34.0-1
- New lorax documentation - 34.0 (bcl@redhat.com)
- runtime-cleanup: strip a bunch of unnecessary firmwares (awilliam@redhat.com)
- runtime-install: specify polkit-gnome to avoid lxpolkit and GTK2 (awilliam@redhat.com)
- runtime-install: exclude gnome-firmware and sigrok-firmware (awilliam@redhat.com)
- runtime-cleanup: Drop video playback acceleration drivers (awilliam@redhat.com)
- runtime-install: don't install notification-daemon (awilliam@redhat.com)

* Tue Sep 08 2020 Brian C. Lane <bcl@redhat.com> 33.9-1
- config_files: Update aarch64, ppc, and sparc timeouts to 60s (bcl@redhat.com)
- templates: Ensure nano is installed for the runtime environment (ngompa13@gmail.com)
- tests: Ignore W0707 raise-missing-from warnings (bcl@redhat.com)
- Switch VMware testing env to improve stability results (chrobert@redhat.com)
- tests: Allow skipping image build in compose sanity test (atodorov@redhat.com)

* Thu Jul 23 2020 Brian C. Lane <bcl@redhat.com> 33.8-1
- composer-cli: Make start-ostree parent and ref optional (bcl@redhat.com)
- composer-cli: Add a get_arg function (bcl@redhat.com)
- Set BACKEND=osbuild-composer if running that test scenario (atodorov@redhat.com)
- tests: Don't check info after compose cancel with osbuild-composer (atodorov@redhat.com)
- tests: Compare blueprints as TOML objects, not strings (atodorov@redhat.com)
- tests: Remove lorax-composer specific checks (atodorov@redhat.com)
- tests: Remove compose after we're done (atodorov@redhat.com)
- tests: don't use beakerlib in blueprint (lars@karlitski.net)
- tests: don't depend on internal state of composer (lars@karlitski.net)
- tests: Do not rely on example blueprints (atodorov@redhat.com)
- tests: Special case compose types for osbuild-composer (atodorov@redhat.com)
- tests: Don't check example blueprints if we don't have to (atodorov@redhat.com)
- tests: Use BACKEND env variable instead of hard-coded values (atodorov@redhat.com)
- tests: Disable non-cli test scenarios b/c osbuild-composer (atodorov@redhat.com)

* Mon Jul 20 2020 Brian C. Lane <bcl@redhat.com> 33.7-1
- Add log entry about dracut and /proc (bcl@redhat.com)
- Skip creating empty /proc/modules for dracut (bcl@redhat.com)
- lorax: Install fcoe-utils (vponcova@redhat.com)
- lorax: Enable swap on zram (vponcova@redhat.com)
- Fix EFI booting for ISOs generated by `mkksiso` (michel@michel-slm.name)
- tests: Disable cloud-init status check (atodorov@redhat.com)

* Thu Jun 18 2020 Brian C. Lane <bcl@redhat.com> 33.6-1
- lorax.spec: Add psmisc for fuser debugging of failed umounts in pylorax.imgutils (bcl@redhat.com)
- composer-cli: Disable retry counter on connection timeout (bcl@redhat.com)
- composer-cli: Change timeout to 5 minutes (bcl@redhat.com)

* Thu Jun 11 2020 Brian C. Lane <bcl@redhat.com> 33.5-1
- lorax-composer: Add deprecation notice to documentation (bcl@redhat.com)
- composer-cli: Return a better error with no value (bcl@redhat.com)
- tests: Add tests for composer-cli compose start JSON POST (bcl@redhat.com)
- composer-cli: Update bash completion for start-ostree (bcl@redhat.com)
- composer-cli: Add new start-ostree command (bcl@redhat.com)
- composer-cli: Add support for --size to compose start (bcl@redhat.com)
- include generic.ins for s390 boot iso (dan@danny.cz)
- test: Put VM image overlay into /var/tmp (martin@piware.de)

* Mon Jun 01 2020 Brian C. Lane <bcl@redhat.com> 33.4-1
- Revert "lorax: Remove vmlinuz from install.img /boot" (bcl@redhat.com)
- composer-cli: Add osbuild-composer to connection failure message (bcl@redhat.com)
- composer-cli: Update docs to mention osbuild-composer and debug options (bcl@redhat.com)
- lorax-composer: Check compose/status for invalid characters (bcl@redhat.com)
- lorax-composer: deleting an unknown workspace should return an error (bcl@redhat.com)
- lorax-composer: Check for valid characters in the undo commit (bcl@redhat.com)
- drop 32-bit support from ppc live image grub.cfg (dan@danny.cz)
- mksquashfs: Catch errors with mksquashfs and report them (bcl@redhat.com)

* Tue May 05 2020 Brian C. Lane <bcl@redhat.com> 33.3-1
- Don't use f-string without interpolation (atodorov@redhat.com)
- lmc-no-virt: Add requirement on anaconda-install-env-deps (bcl@redhat.com)
- rsyslog: Disable journal ratelimits during install (bcl@redhat.com)

* Tue Apr 28 2020 Brian C. Lane <bcl@redhat.com> 33.2-1
- New lorax documentation - 33.2 (bcl@redhat.com)
- test: Work around invalid fedora baseurls (marusak.matej@gmail.com)
- lorax: Add --skip-branding cmdline argument (bcl@redhat.com)
- Update datastore for VMware testing (chrobert@redhat.com)

* Mon Mar 30 2020 Brian C. Lane <bcl@redhat.com> 33.1-1
- lorax: Remove vmlinuz from install.img /boot (bcl@redhat.com)

* Fri Mar 20 2020 Brian C. Lane <bcl@redhat.com> 33.0-1
- tests: Add tests for _install_branding with and without variant (bcl@redhat.com)
- lorax: Update how the release package is chosen (bcl@redhat.com)
- ltmpl: Fix package logging format (bcl@redhat.com)
  Resolves: rhbz#1815000


* Mon Mar 16 2020 Brian C. Lane <bcl@redhat.com> 32.7-1
- lorax: Write package lists in run_transaction (bcl@redhat.com)
- Add dig and comm to the boot.iso (bcl@redhat.com)
- lorax-composer: Add 'weldr' to indicate it supports the weldr API (bcl@redhat.com)
- lorax: Cleanup the removefrom --allbut files (bcl@redhat.com)
- lorax: Add eject back into the boot.iso (bcl@redhat.com)

* Wed Feb 12 2020 Brian C. Lane <bcl@redhat.com> 32.6-1
- New lorax documentation - 32.6 (bcl@redhat.com)
- Update mock documentation to remove --old-chroot (bcl@redhat.com)
- Use .tasks file to trigger removal of stale cloud resources (atodorov@redhat.com)
- tests: OpenStack - apply tags and delete by tags (atodorov@redhat.com)
- tests: Azure - apply tags and delete by tags (atodorov@redhat.com)
- tests: VMware - delete only VMs named Composer-Test-* (atodorov@redhat.com)
- tests: AWS - apply tags when creating resoures and delete by tags (atodorov@redhat.com)
- Reflect fonts packages from comps (akira@tagoh.org)
- lorax: Catch rootfs out of space failures (bcl@redhat.com)
- pylint: whitelist the rpm module (bcl@redhat.com)
- tests: Move the list of packages out of Dockerfile.test into a file (bcl@redhat.com)
- tests: remove ALI_DIR after we're done using the cli (atodorov@redhat.com)
- Test & cleanup script for Alibaba cloud (atodorov@redhat.com)
- tests: run ssh commands in batch mode (jrusz@redhat.com)
- lorax: Log dnf solver debug data in ./debugdata/ (bcl@redhat.com)
- tests: remove --test=2 from compose_sanity (jrusz@redhat.com)

* Thu Jan 16 2020 Brian C. Lane <bcl@redhat.com> 32.5-1
- New lorax documentation - 32.5 (bcl@redhat.com)
- tests: Use mock from unittest (bcl@redhat.com)
- Add --dracut-conf cmdline argument to lorax and livemedia-creator (bcl@redhat.com)
- Add tests for metapackages and package name globs (bcl@redhat.com)
- executils: Drop bufsize=1 from execReadlines (bcl@redhat.com)
- tests: unittest and pytest expect functions to start with test_ (bcl@redhat.com)
- Update to_timeval usage to use format_iso8601 (bcl@redhat.com)
- ltmpl: Update to use collections.abc (bcl@redhat.com)
- test: Use pytest instead of nose (bcl@redhat.com)
- tests: Check for cloud-init presence in azure image (jrusz@redhat.com)
- tests: check for failed compose before trying to cancel (jrusz@redhat.com)
- tests: Enable Elastic Network Adapter support for AWS (atodorov@redhat.com)
- lorax-composer: Enable ami on aarch64 (bcl@redhat.com)

* Fri Jan 10 2020 Brian C. Lane <bcl@redhat.com> 32.4-1
- livemedia-creator: workaround glibc limitation when starting anaconda (dan@danny.cz)
- AWS test: take into account different instance type for non x86 (atodorov@redhat.com)
- Add test for canceling a running compose (jrusz@redhat.com)
- composer-cli: Increase DELETE timeout to 120s (bcl@redhat.com)
- anaconda_cleanup: Remove anaconda.pid if it is left behind (bcl@redhat.com)
- New lorax documentation - 32.4 (bcl@redhat.com)
- docs: Add documentation for new mkksiso --volid feature (bcl@redhat.com)
- mkksiso: Add the option to set the ISO volume label (florian.achleitner@prime-sign.com)
- spec: Add missing BuildRequires: make (florian.achleitner@prime-sign.com)
- tests: Use wildcard versions for packages (bcl@redhat.com)
- composer-cli: Only display the available compose types (bcl@redhat.com)
- fix typo in api docstring (obudai@redhat.com)
- Remove all repo files & install composer-cli from host repos (atodorov@redhat.com)
- Always remove lorax-composer & composer-cli RPMs before installing them (atodorov@redhat.com)
- Always remove existing VM image before building new one (atodorov@redhat.com)
- Add git to Dockerfile.test (bcl@redhat.com)

* Mon Nov 18 2019 Brian C. Lane <bcl@redhat.com> 32.3-1
- lorax-composer: Add cloud-init support to the vhd image (bcl@redhat.com)
- tests: add docker variable to .travis.yml (jrusz@redhat.com)
- tests: Changed Docker to podman in Makefile (jrusz@redhat.com)
- tests: fix blueprints tag test (jrusz@redhat.com)
- test: fix serializing repo_to_source test (jrusz@redhat.com)
- composer-cli: Return int from handle_api_result not bool (bcl@redhat.com)
- mkksiso: copy all the directories over to tmpdir (bcl@redhat.com)
- Add dmidecode on supported architectures (bcl@redhat.com)
- docs: Remove --title from list of lmc variables (bcl@redhat.com)
- Drop old lorax.spec changelog entries (pre-F31) (bcl@redhat.com)

* Tue Nov 05 2019 Brian C. Lane <bcl@redhat.com> 32.2-1
- New lorax documentation - 32.2 (bcl@redhat.com)
- tests: Add 'test_mkksiso' tests (bcl@redhat.com)
- mkksiso: Add documentation (bcl@redhat.com)
- mkksiso: Add a tool to add a kickstart to an existing boot.iso (bcl@redhat.com)
- tests: Add a lorax boot.iso test (bcl@redhat.com)
- test: Add wait_boot method for root logins (bcl@redhat.com)
- tests: Ensure failure if beakerlib results file not found (atodorov@redhat.com)
- tests: Documentation updates (atodorov@redhat.com)
- tests: Use host repositories for make vm (atodorov@redhat.com)
- Remove unused make targets (atodorov@redhat.com)
- DRY when setting up, running & parsing results for beakerlib tests (atodorov@redhat.com)
- tests: Disable mirrors (atodorov@redhat.com)
- tests: Use journalctl -g to check for failed login (bcl@redhat.com)
- tests: Fix check_root_account when used with tar liveimg test (bcl@redhat.com)
- tests: Use the same asserts as before (atodorov@redhat.com)
- tests: switch to using podman instead of docker (atodorov@redhat.com)
- tests: Remove nested vm from tar liveimg kickstart test (bcl@redhat.com)
- tests: Use --http0.9 for curl ssh test (bcl@redhat.com)
- test: Boot the live-iso faster, and login using ssh key (bcl@redhat.com)
- test: Split up the test class to allow booting other images (bcl@redhat.com)
- tests: Split testing the image into a separate script (bcl@redhat.com)
- Add live iso support to s390 (bcl@redhat.com)
- docs: Override macboot/nomacboot documentation (bcl@redhat.com)
- Disable some compose types on other architectures (bcl@redhat.com)
- lorax: Drop unused --title option (bcl@redhat.com)
- tests: Document Azure setup (atodorov@redhat.com)
- tests: unskip Azure scenario (atodorov@redhat.com)

* Wed Oct 16 2019 Brian C. Lane <bcl@redhat.com> 32.1-1
- Bump default platform and releasever to 32 (bcl@redhat.com)
- New lorax documentation - 32.1 (bcl@redhat.com)
- docs: Fix Sphinx errors in docstrings (bcl@redhat.com)
- vm.install: Turn on verbose output (bcl@redhat.com)
- tests: Switch the azure examples used in the lifted tests to use aws (bcl@redhat.com)
- Remove lifted azure support (bcl@redhat.com)
- composer-cli: Add providers info <PROVIDER> command (bcl@redhat.com)
- composer-cli: Fix error handling in providers push (bcl@redhat.com)
- composer-cli: Fix upload log output (bcl@redhat.com)
- Add list to bash completion for composer-cli upload (bcl@redhat.com)
- Update composer-cli documentation (bcl@redhat.com)
- Add composer and lifted to coverage report (bcl@redhat.com)
- composer-cli: Add starting an upload to compose start (bcl@redhat.com)
- composer-cli: Add providers template command (bcl@redhat.com)
- bash_completion: Add support for new composer-cli commands (bcl@redhat.com)
- composer-cli: Add support for providers command (bcl@redhat.com)
- composer-cli: Add support for upload command (bcl@redhat.com)
- Increase ansible verbosity to 2 (bcl@redhat.com)
- lifted: Add support for AWS upload (bcl@redhat.com)
- lifted: Improve logging for upload playbooks (bcl@redhat.com)
- Add upload status examples to compose route docstrings (bcl@redhat.com)
- tests: Add tests for deleting unknown upload and profile (bcl@redhat.com)
- Add docstrings to the new upload functions in pylorax.api.queue (bcl@redhat.com)
- Change /compose/uploads/delete to /upload/delete (bcl@redhat.com)
- tests: Add test for /compose/uploads/delete (bcl@redhat.com)
- tests: Add tests for /compose/uploads/schedule (bcl@redhat.com)
- Add profile support to /uploads/schedule/ (bcl@redhat.com)
- tests: Fix comments about V1 API results including uploads data (bcl@redhat.com)
- lifted: Make sure inputs cannot have path elements (bcl@redhat.com)
- Use consistent naming for upload uuids (bcl@redhat.com)
- tests: Add tests for new upload routes (bcl@redhat.com)
- Fix some docstrings in the v1 API (bcl@redhat.com)
- lifted: Make sure providers list is always sorted (bcl@redhat.com)
- Add /upload/providers/delete route (bcl@redhat.com)
- lifted: Add delete_profile function and tests (bcl@redhat.com)
- Add support for starting a compose upload with the profile (bcl@redhat.com)
- lifted: Add a function to load the settings for a provider's profile (bcl@redhat.com)
- Fix pylint errors in lifted.upload (bcl@redhat.com)
- tests: Add yamllint of the lifted playbooks (bcl@redhat.com)
- tests: Add tests for the new lifted module (bcl@redhat.com)
- All providers should have 'supported_types' (bcl@redhat.com)
- lifted directories should be under share_dir and lib_dir (bcl@redhat.com)
- tests: Add tests for API v1 (bcl@redhat.com)
- Make sure V0 API doesn't return uploads information (bcl@redhat.com)
- Automatically upload composed images to the cloud (egoode@redhat.com)
- Add load and dump to pylorax.api.toml (egoode@redhat.com)
- Support CI testing against a bots project PR (martin@piware.de)
- Makefile: Don't clobber an existing bots checkout (martin@piware.de)
- lorax-composer: Handle RecipeError in commit_recipe_directory (bcl@redhat.com)
- test: Disable pylint subprocess check check (bcl@redhat.com)

* Mon Sep 30 2019 Brian C. Lane <bcl@redhat.com> 32.0-1
- aarch64: Fix live-iso creation on aarch64 (bcl@redhat.com)
- Add test for running composer with --no-system-repos option (jikortus@redhat.com)
- [tests] Use functions for starting and stopping lorax-composer (jikortus@redhat.com)
- Makefile: Update bots target for moved GitHub project (sanne.raymaekers@gmail.com)
- Keep the zramctl utility from util-linux on boot.iso (mkolman@redhat.com)
- Skip kickstart tar test for fedora-30/tar scenario (atodorov@redhat.com)
- Enable fedora-30/tar test scenario (atodorov@redhat.com)
- [tests] Collect compose logs after each build (atodorov@redhat.com)
- [tests] Use a function to wait for compose to finish (jikortus@redhat.com)
- When launching AWS instances wait for the one we just launched (atodorov@redhat.com)
- tests: Add kickstart tar installation test (jikortus@redhat.com)
- tests: add option to disable kernel command line parameters check (jikortus@redhat.com)
- tests: Use a loop to wait for VM and sshd to start (bcl@redhat.com)
- creator.py: include dmsquash-live-ntfs by default (gmt@be-evil.net)
- Skip Azure test b/c misconfigured infra & creds (atodorov@redhat.com)
- tests: Drop tito from the Dockerfile.test (bcl@redhat.com)
- tests: Drop sort from compose types test (bcl@redhat.com)
- Revert "tests: Fix the order of liveimg-tar live-iso" (atodorov@redhat.com)
- New test: assert toml files in git workspace (atodorov@redhat.com)
