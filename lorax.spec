# NOTE: This specfile is generated from upstream at https://github.com/rhinstaller/lorax
# NOTE: Please submit changes as a pull request
%define debug_package %{nil}

Name:           lorax
Version:        34.9.23
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
%if 0%{?rhel} >= 9
Requires:       lorax-templates-rhel
%endif

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

# ppc64le does not include qemu-kvm, skip building lmc-virt
%ifnarch ppc64le
%package lmc-virt
Summary:  livemedia-creator libvirt dependencies
Requires: lorax = %{version}-%{release}
Requires: qemu-kvm

# Fedora edk2 builds currently only support these arches
%ifarch %{ix86} x86_64
Requires: edk2-ovmf
%endif
%ifarch aarch64
Requires: edk2-aarch64
%endif

%description lmc-virt
Additional dependencies required by livemedia-creator when using it with qemu.
%endif

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
%autosetup -n %{name}-%{version} -p1

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
%{_bindir}/mkksiso
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

%ifnarch ppc64le
%files lmc-virt
%endif

%files lmc-novirt

%files templates-generic
%dir %{_datadir}/lorax/templates.d
%{_datadir}/lorax/templates.d/*

%changelog
* Wed Jan 11 2023 Brian C. Lane <bcl@redhat.com> 34.9.23-1
- rsyslog.conf: Set WorkDirectory to /var/lib/rsyslog (bcl)
  Resolves: rhbz#2158731
- lorax.spec: fix changelog entry for 2132511 (bcl)
  Related: rhbz#2132511

* Mon Nov 28 2022 Brian C. Lane <bcl@redhat.com> 34.9.22-1
- On ppc64le Use core.elf from grub2 package (bcl)
  Resolves: rhbz#2143994

* Fri Nov 18 2022 Brian C. Lane <bcl@redhat.com> 34.9.21-1
- livemedia-creator: Allow file: url without networking (bcl)
  Resolves: rhbz#2132511

* Fri Jul 29 2022 Brian C. Lane <bcl@redhat.com> 34.9.20-1
- templates: Update runtime-* templates (bcl)
  Resolves: rhbz#2042057
- templates: Update path to license files (bcl)
  Related: rhbz#2042057
- templates: Update boot timeout to 5s (bcl)
  Related: rhbz#2042057

* Mon Jul 25 2022 Brian C. Lane <bcl@redhat.com> 34.9.19-1
- mkksiso: Optionally support 3 arguments or --ks (bcl)
  Resolves: rhbz#2037015
- mkksiso: Add -U to xorriso on ppc64le (bcl)
  Resolves: rhbz#2109665
- mkksiso: Fix passing -iso-level to xorriso (bcl)
  Related: rhbz#2109665

* Wed Jul 13 2022 Brian C. Lane <bcl@redhat.com> 34.9.18-1
- mkksiso: Set u+rw permission on extracted files and directories (bcl)
  Related: rhbz#2088631
- lorax.spec: Fix changelog (bcl)
  Resolves: rhbz#1972099

* Wed Jun 29 2022 Brian C. Lane <bcl@redhat.com> 34.9.17-1
- minimal.ks: Add include for architecture specific packages (bcl)
  Related: rhbz#2051548
- livemedia.ks: Add include for architecture specific packages (bcl)
  Resolves: rhbz#2051548
- tests: Add tests for mkksiso (bcl)
  Related: rhbz#2037015
- mkksiso: Add kernel cmdline customization support (bcl)
  Resolves: rhbz#2037015
- mkksiso: Move kickstart to --ks KICKSTART (bcl)
  Related: rhbz#2037015
- mkksiso: Add helper functions for kernel cmdline modifications (bcl)
  Related: rhbz#2037015
- lorax.spec: Fix changelog order (bcl)
  Resolves: rhbz#1972099

* Fri Jun 17 2022 Brian C. Lane <bcl@redhat.com> 34.9.16-1
- Makefile: Add local-srpm target to create a .src.rpm from HEAD (bcl)
  Related: rhbz#2088631
- mkksiso: Fix s390x support (bcl)
  Related: rhbz#2088631
- mkksiso: Remove use of os.path.join (bcl)
  Related: rhbz#2088631
- Makefile: Add mkksiso to coverage report (bcl)
  Related: rhbz#2088631
- setup.py: Install mkksiso to /usr/bin (bcl)
  Related: rhbz#2088631
- mkksiso: Fix grub2 editing error (bcl)
  Related: rhbz#2088631
- mkksiso: Rewrite to use xorriso features (bcl)
  Resolves: rhbz#2088631

* Wed Apr 06 2022 Brian C. Lane <bcl@redhat.com> 34.9.15-1
- tito: Add the LoraxRHELTagger from rhel8-branch (bcl)
  Related: rhbz#2070910
- runtime-postinstall: Remove machine specific nvme files (bcl)
  Resolves: rhbz#2070910

* Wed Feb 16 2022 Brian C. Lane <bcl@redhat.com> 34.9.14-1
- Keep nvram module (bcl@redhat.com)
  Resolves: rhbz#2050877

* Fri Feb 04 2022 Brian C. Lane <bcl@redhat.com> 34.9.13-1
- mkksiso: Fix check for unsupported arch error (bcl@redhat.com)
  Related: rhbz#2049192

* Thu Feb 03 2022 Brian C. Lane <bcl@redhat.com> 34.9.12-1
- mkksiso: Improve debug message about unsupported arch (bcl@redhat.com)
  Related: rhbz#2049192
- mkksiso: Add kickstart to s390x cdboot.prm (bcl@redhat.com)
  Resolves: rhbz#2049192

* Thu Jan 20 2022 Brian C. Lane <bcl@redhat.com> 34.9.11-1
- Enable sftp when using inst.sshd (bcl@redhat.com)
  Resolves: rhbz#2040770
- Drop ia32 uefi package installation (bcl@redhat.com)
  Resolves: rhbz#2039035
- Remove 32-bit UEFI packages from example kickstart (bcl@redhat.com)
  Related: rhbz#2039035

* Thu Dec 09 2021 Brian C. Lane <bcl@redhat.com> 34.9.10-1
- mkksiso: Check the length of the filenames (bcl@redhat.com)
  Related: rhbz#2028104
- mkksiso: Check the iso's arch against the host's (bcl@redhat.com)
  Related: rhbz#2028104
- mkksiso: Add missing implantisomd5 tool requirements (bcl@redhat.com)
  Related: rhbz#2028104
- mkksiso: Raise error if no volume id is found (bcl@redhat.com)
  Related: rhbz#2028104
- mount: Add s390x support to IsoMountopoint (bcl@redhat.com)
  Resolves: rhbz#2028104
- mkksiso: Skip mkefiboot for non-UEFI isos (bcl@redhat.com)
- mkksiso: Add -joliet-long (bcl@redhat.com)
  Related: rhbz#2028104
- mkksiso: Return 1 on errors (bcl@redhat.com)
  Related: rhbz#2028104

* Wed Nov 03 2021 Brian C. Lane <bcl@redhat.com> 34.9.9-1
- Change macboot default to false (bcl@redhat.com)
  Resolves: rhbz#2019512
- livemedia-creator: Change defaults to Red Hat Enterprise Linux 9 (bcl@redhat.com)
  Resolves: rhbz#2019133

* Fri Oct 29 2021 Brian C. Lane <bcl@redhat.com> 34.9.8-1
- livemedia.ks: Drop unneeded commands (bcl@redhat.com)
  Related: rhbz#2017993
- livemedia.ks: Install workstation-product-environment (bcl@redhat.com)
  Resolves: rhbz#2017993
- templates: Change nomodeset / basic graphics to use inst.text (bcl@redhat.com)
  Related: rhbz#1961092
- templates: Drop nomodeset / basic graphics menu from live configs (bcl@redhat.com)
  Related: rhbz#1961092
- livemedia.ks: Add isomd5sum for use with rd.live.check (bcl@redhat.com)
  Resolves: rhbz#2015908

* Wed Oct 06 2021 Brian C. Lane <bcl@redhat.com> 34.9.7-1
- runtime-cleanup: Remove dropped package from template (bcl@redhat.com)
  Related: rhbz#1991006
- sshd_config: Update sshd options (bcl@redhat.com)
  Related: rhbz#2007288
- Install nvme-cli tool (bcl@redhat.com)
  Related: rhbz#2010254
- When running the tests in docker/podman use the Fedora 34 image (bcl@redhat.com)
  Related: rhbz#2010542
- Fix pylint warnings about string formatting (bcl@redhat.com)
  Related: rhbz#2010542
- tests: Ignore new pylint warnings (bcl@redhat.com)
  Resolves: rhbz#2010542

* Thu Sep 09 2021 Brian C. Lane <bcl@redhat.com> 34.9.6-1
- github: Run tests for rhel9-branch PRs (bcl@redhat.com)
  Related: rhbz#2000439
- Install unicode.pf2 from new directory (bcl@redhat.com)
  Resolves: rhbz#2000439

* Thu Jul 15 2021 Brian C. Lane <bcl@redhat.com> 34.9.5-1
- Add a context manager for dracut (bcl@redhat.com)
  Resolves: rhbz#1982271
- spec: Fix bug number for dropping gfs2-utils (bcl@redhat.com)
  Related: rhbz#1975378

* Mon Jun 28 2021 Brian C. Lane <bcl@redhat.com> 34.9.4-1
- mkksiso: cmdline should default to empty string (bcl@redhat.com)
  Related: rhbz#1975844
- runtime-install: Remove gfs2-utils (bcl@redhat.com)
  Related: rhbz#1975378

* Thu Jun 10 2021 Brian C. Lane <bcl@redhat.com> 34.9.3-1
- livemedia-creator: Check for mkfs.hfsplus (bcl@redhat.com)

* Tue May 25 2021 Brian C. Lane <bcl@redhat.com> 34.9.2-1
- Add prefixdevname to Anaconda initramfs (rvykydal@redhat.com)
  Related: rhbz#1958173
- Replace metacity with gnome-kiosk (bcl@redhat.com)
  Related: rhbz#1961099
- runtime-install: Install ipcalc (bcl@redhat.com)
  Related: rhbz#1958173
- spec: Update lorax-lmc-virt packages for rhel9 arches (bcl@redhat.com)
  Related: rhbz#1955674
* Wed May 05 2021 Brian C. Lane <bcl@redhat.com> - 34.9.1-2
- qemu-kvm isn't available on ppc64le
- edk2-aarch64 has the UEFI firmware on aarch64
  Related: rhbz#1955674

* Wed May 05 2021 Brian C. Lane <bcl@redhat.com> 34.9.1-1
- livemedia-creator: Use inst.ks on cmdline for virt (bcl@redhat.com)
- image-minimizer: Fix decode() usage (bcl@redhat.com)
- docs: Update example kickstarts for RHEL/CentOS (bcl@redhat.com)
- livemedia-creator: RHEL9 only supports qemu-kvm (bcl@redhat.com)
- runtime-cleanup: Use branding package name instead of product.name (bcl@redhat.com)
- treebuilder: Add branding package to template variables (bcl@redhat.com)
- runtime-cleanup: Remove mcpp and libmcpp cleanup (bcl@redhat.com)
- spec: Fix changelog for 34.9.0 (bcl@redhat.com)

* Thu Apr 29 2021 Brian C. Lane <bcl@redhat.com> 34.9.0-1
- New lorax documentation - 34.9.0 (bcl@redhat.com)
  Related: rhbz#1952978
- composer-cli: Remove all traces of composer-cli (bcl@redhat.com)
  Resolves: rhbz#1952978

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

* Wed Dec 02 2020 Brian C. Lane <bcl@redhat.com> 34.5-1
- lorax.spec: Update for RHEL 9 Alpha changes (bcl@redhat.com)
- lorax: Strip ' from product cmdline argument (bcl@redhat.com)
- Change rootfs default size to 3GiB (sgallagh@redhat.com)

* Thu Oct 29 2020 Brian C. Lane <bcl@redhat.com> - 34.3-4
- Drop unused proc/mount patch
- lorax: Strip ' from product cmdline argument
  temporary fix for pungi bug: https://pagure.io/pungi/pull-request/1463

* Wed Oct 28 2020 Stephen Gallagher <sgallagh@redhat.com> - 34.3-3
- Increase boot.iso rootfs to 3GiB

* Tue Oct 27 2020 Brian C. Lane <bcl@redhat.com> - 34.3-2
- Require lorax-templates-rhel for RHEL9

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
