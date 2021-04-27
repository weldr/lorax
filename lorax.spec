# NOTE: This specfile is generated from upstream at https://github.com/rhinstaller/lorax
# NOTE: Please submit changes as a pull request
%define debug_package %{nil}

Name:           lorax
Version:        34.10
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
%doc docs/lorax.rst docs/livemedia-creator.rst docs/product-images.rst
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

%changelog
* Mon Apr 26 2021 Brian C. Lane <bcl@redhat.com> 34.10-1
- New lorax documentation - 34.10 (bcl@redhat.com)
- composer-cli: Remove all traces of composer-cli (bcl@redhat.com)
- runtime-cleanup: don't wipe /usr/bin/report-cli (#1937550) (awilliam@redhat.com)

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
