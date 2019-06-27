# NOTE: This specfile is generated from upstream at https://github.com/rhinstaller/lorax
# NOTE: Please submit changes as a pull request
%define debug_package %{nil}

Name:           lorax
Version:        28.14.30
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
%if 0%{?rhel} >= 8
Requires:       lorax-templates-rhel
%endif

Requires:       GConf2
Requires:       cpio
Requires:       device-mapper
Requires:       dosfstools
Requires:       e2fsprogs
Requires:       findutils
Requires:       gawk
Requires:       genisoimage
Requires:       glib2
Requires:       glibc
Requires:       glibc-common
Requires:       gzip
Requires:       isomd5sum
Requires:       module-init-tools
Requires:       parted
Requires:       squashfs-tools >= 4.2
Requires:       util-linux
Requires:       xz
Requires:       pigz
Requires:       dracut >= 030
Requires:       kpartx

# Python modules
Requires:       libselinux-python3
Requires:       python3-mako
Requires:       python3-kickstart >= 3.16.4
Requires:       python3-dnf >= 3.2.0
Requires:       python3-librepo


%if 0%{?fedora}
# Fedora specific deps
%ifarch x86_64
Requires:       hfsplus-tools
%endif
%endif

%ifarch %{ix86} x86_64
Requires:       syslinux >= 6.02-4
%endif

%ifarch ppc ppc64 ppc64le
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

%package docs
Summary: Lorax html documentation
Requires: lorax = %{version}-%{release}

%description docs
Includes the full html documentation for lorax, livemedia-creator, lorax-composer and the
pylorax library.

%package lmc-virt
Summary:  livemedia-creator libvirt dependencies
Requires: lorax = %{version}-%{release}
Requires: qemu-kvm

# Fedora edk2 builds currently only support these arches
%ifarch %{ix86} x86_64
Requires: edk2-ovmf
%endif

%description lmc-virt
Additional dependencies required by livemedia-creator when using it with qemu-kvm.

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
Requires: python3-rpmfluff
Requires: git
Requires: xz
Requires: createrepo_c

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
%autosetup -p1 -n %{name}-%{version}

%build

%install
rm -rf %{buildroot}
make DESTDIR=%{buildroot} mandir=%{_mandir} install

# Install example blueprints from the test suite.
# This path MUST match the lorax-composer.service blueprint path.
mkdir -p %{buildroot}/var/lib/lorax/composer/blueprints/
for bp in example-http-server.toml example-development.toml example-atlas.toml; do
    cp ./tests/pylorax/blueprints/$bp %{buildroot}/var/lib/lorax/composer/blueprints/
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
%doc AUTHORS
%doc docs/composer-cli.rst docs/lorax.rst docs/livemedia-creator.rst docs/product-images.rst
%doc docs/lorax-composer.rst
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

%files docs
%doc docs/html/*

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
* Thu Jun 27 2019 Brian C. Lane <bcl@redhat.com> 28.14.30-1
- New lorax documentation - 28.14.30 (bcl)
  Related: rhbz#1709594
- Assert that RuntimeErrors have correct messages (egoode)
  Related: rhbz#1709594
- More descriptive error for a bad ref in repos.git (egoode)
  Related: rhbz#1709594
- Add more tests for gitrpm.py (bcl)
  Related: rhbz#1709594
- lorax-composer: Fix installing files from [[repos.git]] to / (bcl)
  Related: rhbz#1709594
- Add tests using repos.git in blueprints (bcl)
  Related: rhbz#1709594
- Move git repo creation into tests/lib.py (bcl)
  Related: rhbz#1709594
- rpmgit: catch potential errors while running git (bcl)
  Related: rhbz#1709594
- tests: Add test for Recipe.freeze() function (bcl)
  Related: rhbz#1709594
- Add repos.git support to lorax-composer builds (bcl)
  Related: rhbz#1709594
- Add pylorax.api.gitrpm module and tests (bcl)
  Related: rhbz#1709594
- Add support for [[repos.git]] section to blueprints (bcl)
  Resolves: rhbz#1709594
- [tests] Handle blueprints in setup_tests/teardown_tests correctly (atodorov)
  Related: rhbz#1714298
- tests: Set BLUEPRINTS_DIR in all cases (lars)
  Related: rhbz#1714298

* Mon Jun 10 2019 Brian C. Lane <bcl@redhat.com> 28.14.29-1
- tests: Update openssh-server to version * (bcl)
  Related: rhbz#1678937
- Remove repos.git related tests (bcl)
  Related: rhbz#1709595
- composer-cli: Update diff support for customizations and repos.git (bcl)
  Related: rhbz#1709595
- Add support for customizations and repos.git to /blueprints/diff/ (bcl)
  Related: rhbz#1709595
- tests: Update custom-base with customizations (bcl)
  Related: rhbz#1709595
- Change customizations.firewall to append items instead of replace (bcl)
  Resolves: rhbz#1709595
- Update customizations.services documentation (bcl)
  Related: rhbz#1709595
- lorax-composer: Add services support to blueprints (bcl)
  Related: rhbz#1709595
- lorax-composer: Add firewall support to blueprints (bcl)
  Related: rhbz#1709595
- lorax-composer: Add locale support to blueprints (bcl)
  Related: rhbz#1709595
- lorax-composer: Fix customizations when creating a recipe (bcl)
  Related: rhbz#1709595
- Update docs for new timezone section (bcl)
  Related: rhbz#1709595
- lorax-composer: Add timezone support to blueprint (bcl)
  Related: rhbz#1709595
- Proposal for adding to the blueprint customizations (bcl)
  Related: rhbz#1709595

* Wed May 29 2019 Brian C. Lane <bcl@redhat.com> 28.14.28-1
- Create a lorax-docs package with the html docs (bcl)
  Resolves: rhbz#1695274
- Fix path to generic.prm (jstodola)
  Resolves: rhbz#1714107

* Thu May 16 2019 Brian C. Lane <bcl@redhat.com> 28.14.27-1
- Add kernel to ext4-filesystem template (bcl)
  Resolves: rhbz#1709792
- Switch the --virt-uefi method to use SecureBoot (bcl)
  Resolves: rhbz#1691661
- qemu wasn't restoring the terminal if it was terminated early (bcl)
  Resolves: rhbz#1691632
- Revert "lorax-composer: Add CDN repo checks to startup and compose start." (bcl)
  Related: rhbz#1691969
- Revert "lorax-composer: Check for CDN only repos" (bcl)
  Related: rhbz#1691969
- Add test for passing custom option on kernel command line (jikortus)
  Related: rhbz#1687743
- Use verify_image function as a helper for generic tests (jikortus)
  Related: rhbz#1704172
- Change [[modules]] to [[packages]] in tests (atodorov)
  Related: rhbz#1698368
- Add new test to verify compose paths exist (atodorov)
  Related: rhbz#1698368
- Add new sanity tests for blueprints (atodorov)
  Related: rhbz#1698368
- Update VMware info for VMware testing (chrobert)
  Related: rhbz#1678937
- Add test for starting compose with deleted blueprint (jikortus)
  Related: rhbz#1699303
- Fixes for locked root account test (jikortus)
  Related: rhbz#1698473
- Fix lorax.spec bz reference (bcl)
  Related: rhbz#1678937

* Fri Apr 05 2019 Brian C. Lane <bcl@redhat.com> 28.14.26-1
- Only use repos with valid urls for test_server.py (bcl)
  Related: rhbz#1678937
- Use strict=False when reading repo files (bcl)
  Related: rhbz#1678937
- tests: Skip docs if not installed (bcl)
  Related: rhbz#1678937
- tests: Make sure example-development is present for delete test (bcl)
  Related: rhbz#1678937
- tests: Make it easier to update version globs (bcl)
  Related: rhbz#1678937
- tests: Select the group to use based on the release (bcl)
  Related: rhbz#1678937
- Add requirements-test.txt (bcl)
  Related: rhbz#1678937
- Fix the google cloud boot console settings (dshea)
  Related: rhbz#1689140
- Add a compose type for alibaba. (dshea)
  Resolves: rhbz#1689140
- Add a compose check for google cloud images. (dshea)
  Related: rhbz#1689140
- Add a compose type for Google Compute Engine (dshea) (dshea)
- Add a new output type, tar-disk. (dshea)
  Related: rhbz#1689140
- Support compressing single files. (dshea)
  Related: rhbz#1689140
- Add an option to align the image size to a multiplier. (dshea)
  Related: rhbz#1689140
- Pass ssl certificate options to anaconda (lars)
  Resolves: rhbz#1663950
- Add checks for disabled root account (jikortus)
- Fixup lorax.spec bugs (bcl)
  Related: rhbz#1678937

* Wed Mar 27 2019 Brian C. Lane <bcl@redhat.com> 28.14.25-1
- New lorax documentation - 28.14.25 (bcl)
  Related: rhbz#1687743
- lorax-composer: pass customization.kernel append to extra_boot_args (bcl)
  Resolves: rhbz#1687743
- Improve logging for template syntax errors (bcl)
  Related: rhbz#1687743
- Add extra boot args to the livemedia-creator iso templates (bcl)
  Related: rhbz#1687743
- lorax-composer: Add the ability to append to the kernel command-line (bcl)
  Related: rhbz#1687743
- lorax-composer: Return UnknownBlueprint errors when using deleted blueprints (bcl)
  Resolves: rhbz#1683441
- lorax-composer: Delete workspace copy when deleting blueprint (bcl)
  Related: rhbz#1683441
- Remove 3G minimum from lorax-composer (bcl)
  Resolves: rhbz#1677741

* Thu Mar 21 2019 Brian C. Lane <bcl@redhat.com> 28.14.24-1
- Add a ppc64le template for live iso creation (bcl)
  Related: rhbz#1673744
- Move the package requirements for live-iso setup out of the template (bcl)
  Resolves: rhbz#1673744
- Remove exclusions from lorax-composer templates (bcl)
  Related: rhbz#1673744
- Add LiveTemplateRunner to parse per-arch live-iso package requirements (bcl)
  Related: rhbz#1673744
- Move the run part of LoraxTemplateRunner into new TemplateRunner class (bcl)
  Related: rhbz#1673744
- lorax-composer: Use reqpart --add-boot for partitioned disk templates (bcl)
  Related: rhbz#1673744
- livemedia-creator: Add support for reqpart kickstart command (bcl)
  Related: rhbz#1673744
- Fix make_appliance and the libvirt.tmpl (bcl)
  Related: rhbz#1673744
- Add get_file_magic to tests/lib.py (bcl)
  Related: rhbz#1673744
- Clarify the ks repo only error message (bcl)
  Related: rhbz#1673744
- Add tests to test_creator.py (bcl)
  Related: rhbz#1673744
- Add some tests for creator.py (bcl)
  Related: rhbz#1673744
- Make the lorax-composer ks templates more generic (bcl)
  Related: rhbz#1673744
- Add some extra cancel_func protection to QEMUInstall (bcl)
  Related: rhbz#1684316
- installer: make sure cancel_func has a value (yuvalt)
  Resolves: rhbz#1684316
- Update VMware datastore location to unblock tests (chrobert)
  Related: rhbz#1678937
- Allow overriding $CLI outside test scripts (atodorov)
  Related: rhbz#1678937
- Use make ci inside test-in-copy target (atodorov)
  Related: rhbz#1678937
- New test: Build live-iso and boot with KVM (atodorov)
- New test: Build qcow2 compose and test it with QEMU-KVM (atodorov)
- Removed remnants of fedora branding. (47631017+jakub-vavra)
  Resolves: rhbz#1672583
- Drop auth from the kickstart examples (bcl)
  Resolves: rhbz#1672583
- New test: Verify tar images with Docker and systemd-nspawn (atodorov)
- Update OpenStack flavor and network settings in tests (atodorov)
- Use existing storage account (jstodola)
- Record date/time of VM creation (jstodola)
- Make sure compose build tests run with SELinux in enforcing mode (jikortus)

* Wed Jan 30 2019 Brian C. Lane <bcl@redhat.com> 28.14.23-1
- lorax: Move default tmp dir to /var/tmp/lorax (bcl)
  Resolves: rhbz#1668408
- Expand parameters as separate words (jstodola)
  Related: rhbz#1653934
- Add /usr/local/bin to PATH for tests (atodorov) (atodorov)
- Do not generate journal.xml from beakerlib (atodorov)
  Related: rhbz#1653934
- Use any tmux version (atodorov)
  Related: rhbz#1653934
- Make test scripts executable with chmod +x (atodorov)
  Related: rhbz#1653934

* Fri Jan 11 2019 Brian C. Lane <bcl@redhat.com> 28.14.22-1
- Report an error if the blueprint doesn't exist (bcl)
  Related: rhbz#1653934
- tmux is version 2.8 on Fedora 28 (atodorov)
  Related: rhbz#1653934
- Disable pylint no-member errors for 2 dnf constants (atodorov)
  Related: rhbz#1653934
- Backport cloud image tests to RHEL 8 (atodorov)
  Related: rhbz#1653934

* Thu Jan 10 2019 Brian C. Lane <bcl@redhat.com> 28.14.21-1
- Remove unneeded else from for/else loop. It confuses pylint (bcl)
  Related: rhbz#1664485
- Allow customizations to be specified as a toml list (dshea)
  Resolves: rhbz#1664485
- New lorax documentation - 28.14.21 (bcl)
  Related: rhbz#1650295
- Update the example livemedia-creator kickstarts for RHEL8 (bcl)
  Resolves: rhbz#1650295
- Change default releasever to 8 (bcl)
  Related: rhbz#1650295

* Tue Jan 08 2019 Brian C. Lane <bcl@redhat.com> 28.14.20-1
- Revert "lorax-composer: Cancel running Anaconda process" (bcl)
  Related: rhbz#1656691
- Make sure cancel_func is not None (bcl)
  Related: rhbz#1656691
- Increase boot.iso rootfs to 3GiB (bcl)
  Resolves: rhbz#1661169

* Tue Dec 18 2018 Brian C. Lane <bcl@redhat.com> 28.14.19-1
- lorax: Save information about rootfs filesystem size and usage (bcl)
  Resolves: rhbz#1659625
- lorax-composer: Cancel running Anaconda process (bcl)
  Resolves: rhbz#1656691
- Add cancel_func to virt and novirt_install functions (bcl)
  Resolves: rhbz#1656691
- lorax-composer: Check for STATUS before deleting (bcl)
  Related: rhbz#1656691
- Check for existing CANCEL request, and exit on FINISHED (bcl)
  Related: rhbz#1656691

* Fri Dec 07 2018 Brian C. Lane <bcl@redhat.com> 28.14.18-1
- New lorax documentation - 28.14.18 (bcl)
  Related: rhbz#1656642
- Add openstack to the image type list in the docs (dshea)
  Related: rhbz#1628645
- lorax-composer: Handle packages with multiple builds (bcl)
  Resolves: rhbz#1656642
- Adjust test_drtfr_gpgkey to pass on Fedora 28 and RHEL 8 (bcl)
  Related: rhbz#1655876
- Update the projects tests to use DNF Repo object (bcl)
  Related: rhbz#1655876
- dnf changed the type of gpgkey to a tuple (bcl)
  Resolves: rhbz#1655876
- lorax-composer: Add CDN repo checks to startup and compose start. (bcl)
  Resolves: rhbz#1655623
- lorax-composer: Check for CDN only repos (bcl)
  Related: rhbz#1655623
- There is no support for edk2-ovmf on arm/arm64 (bcl)
  Resolves: rhbz#1655512
- lorax-composer: Check the queue and results at startup (bcl)
  Resolves: rhbz#1647985

* Thu Nov 29 2018 Brian C. Lane <bcl@redhat.com> 28.14.17-1
- Update documentation for - 28.14.17 (bcl)
  Related: rhbz#1645189
- lorax-composer: Install selinux-policy-targeted in images (bcl)
  Resolves: rhbz#1645189
- Remove setfiles from mkrootfsimage (bcl)
  Related: rhbz#1645189
- Remove SELinux Permissive checks (bcl)
  Resolves: rhbz#1645189
- New lorax documentation - 28.14.17 (bcl)
  Related: rhbz#1639132
- Build manpages for composer-cli and lorax-composer (bcl)
  Resolves: rhbz#1639132
- Add --no-system-repos to lorax-composer (bcl)
  Resolves: rhbz#1650363

* Fri Oct 12 2018 Brian C. Lane <bcl@redhat.com> 28.14.16-1
- Fix vhd images (vponcova)
  Related: rhbz#1628648
- Update depsolving with suggestions from dnf (bcl)
  Resolves: rhbz#1638683

* Tue Oct 09 2018 Brian C. Lane <bcl@redhat.com> 28.14.15-1
- Add an openstack image type (bcl)
  Resolves: rhbz#1628645
- Add cloud-init to vhd images. (dshea)
  Related: rhbz#1628648
- Replace /etc/machine-id with an empty file (dshea)
  Related: rhbz#1628648
  Related: rhbz#1628645
  Related: rhbz#1628647
  Related: rhbz#1628646

* Mon Oct 08 2018 Brian C. Lane <bcl@redhat.com> 28.14.14-1
- Update cli tests to use composer-cli name (bcl)
  Related: rhbz#1635763
- Revert "Rename composer-cli to composer" (bcl)
  Related: rhbz#1635763

* Fri Oct 05 2018 Brian C. Lane <bcl@redhat.com> 28.14.13-1
- New lorax documentation - 28.14.12 (bcl)
  Related: rhbz#1635763
- Adjust the composer-cli tests for the rename to composer (bcl)
  Related: rhbz#1635763
- Rename composer-cli to composer (lars)
  Resolves: rhbz#1635763
- Add and enable cloud-init for ami images (lars)
  Related: rhbz#1628647
- Make no-virt generated images sparser (dshea)
  Related: rhbz#1628645
  Related: rhbz#1628646
  Related: rhbz#1628648
  Related: rhbz#1628647

* Wed Oct 03 2018 Brian C. Lane <bcl@redhat.com> 28.14.12-1
- Write a rootpw line if no root customizations in the blueprint (bcl)
  Resolves: rhbz#1626122

* Tue Oct 02 2018 Brian C. Lane <bcl@redhat.com> 28.14.11-1
- Add beakerlib to Dockerfile.test (bcl)
  Related: rhbz#1613058
- New cli test covering basic compose commands (atodorov) (atodorov)
- Execute bash tests for composer-cli (atodorov) (atodorov)
- Add virt guest agents to the qcow2 compose (dshea)
  Resolves: rhbz#1628645
- Add a vmdk compose type. (dshea)
  Resolves: rhbz#1628646
- Add a vhd compose type for Azure images (dshea)
  Resolves: rhbz#1628648
- Add an ami compose type for AWS images (dshea)
  Resolves: rhbz#1628647
- Remove --fstype from the generated part line (dshea)
  Related: rhbz#1628647
  Related: rhbz#1628648

* Mon Oct 01 2018 Brian C. Lane <bcl@redhat.com> 28.14.10-1
- Add tito support for Related/Resolves to the branch (bcl)
  Related: rhbz#1613058
- Always update repo metadata when building an image (bcl)
  Resolves: rhbz#1631561
- Add a test for repo metadata expiration (bcl)
  Related: rhbz#1631561
- Add tests for setting root password and ssh key with blueprints (bcl)
  Related: rhbz#1626120
- Use rootpw for setting the root password instead of user (bcl)
  Related: rhbz#1626122
- Lock the root account, except on live-iso (bcl)
  Resolves: rhbz#1626122

* Tue Sep 25 2018 Brian C. Lane <bcl@redhat.com> 28.14.9-1
- lorax: Only run depmod on the installed kernels (bcl@redhat.com)
  Resolves: rhbz#1632140
* Tue Sep 18 2018 Brian C. Lane <bcl@redhat.com> 28.14.8-1
- Add prefixdevname support to the boot.iso (bcl@redhat.com)
  Resolves: rhbz#1623000
* Tue Sep 04 2018 Brian C. Lane <bcl@redhat.com> 28.14.7-1
- Ignore a pylint warning about UnquotingConfigParser get args (bcl@redhat.com)
  Related: rhbz#1613058
- Ditch all use of pyanaconda's simpleconfig (awilliam@redhat.com)
  Related: rhbz#1613058
- Require python3-librepo (jwboyer@redhat.com)
  Resolves: rhbz#1624423
* Fri Aug 31 2018 Josh Boyer <jwboyer@redhat.com> 28.14.6-2
- Require python3-librepo

* Wed Aug 29 2018 Brian C. Lane <bcl@redhat.com> 28.14.6-1
- Drop mod_auth_openidc from httpd example blueprint (bcl@redhat.com)
- Bump required dnf version to 3.2.0 for module_platform_id support (bcl@redhat.com)
- Add support for DNF 3.2 module_platform_id config value (bcl@redhat.com)
- Fix /compose/cancel API documentation (bcl@redhat.com)

* Mon Aug 27 2018 Brian C. Lane <bcl@redhat.com> 28.14.5-1
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
- Only include specific blueprints in the rpm (bcl@redhat.com)
- composer-cli should not log to a file by default (bcl@redhat.com)
- Add documentation for using a DVD as the package source (bcl@redhat.com)
- Set TCP listen backlog for API socket to SOMAXCONN (lars@karlitski.net)
- Bring back import-state.service (rvykydal@redhat.com)
- Fix a little bug in running "modules list". (clumens@redhat.com)

* Thu Aug 09 2018 Brian C. Lane <bcl@redhat.com> 28.14.4-1
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
- Run as root/weldr by default. (clumens@redhat.com)
- Fix bash completion of compose info (bcl@redhat.com)
- Add + to the allowed API string character set (bcl@redhat.com)
- Add job_* timestamp support to compose status (bcl@redhat.com)
- Add etc/bash_completion.d/composer-cli (wwoods@redhat.com)
- composer-cli: clean up "list" commands (wwoods@redhat.com)
- Drop .decode from UTF8_TEST_STRING (bcl@redhat.com)
- Add input string checks to the branch and format arguments (bcl@redhat.com)
- Add a test for invalid characters in the API route (bcl@redhat.com)
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

* Mon Jul 30 2018 Brian C. Lane <bcl@redhat.com> 28.14.3-1
- Update to use only qemu-kvm (bcl@redhat.com)
- Fix help output on the compose subcommand. (clumens@redhat.com)
- Add timestamps to "compose-cli compose status" output. (clumens@redhat.com)
- And then add real output to the status command. (clumens@redhat.com)
- Add the beginnings of a new status subcommand. (clumens@redhat.com)
- composer-cli: Fix non-zero epoch in projets info (bcl@redhat.com)
- Adjust test_server and test blueprints so they depsolve (bcl@redhat.com)

* Fri Jul 20 2018 Brian C. Lane <bcl@redhat.com> 28.14.2-1
- New lorax documentation - 28.14.2 (bcl@redhat.com)
- Add dnf.transaction to list of modules for sphinx to ignore (bcl@redhat.com)
- Document that you shouldn't run lorax-composer twice. (clumens@redhat.com)
- Add PIDFile to the .service file. (clumens@redhat.com)
- Don't activate default auto connections after switchroot (rvykydal@redhat.com)
- Use system-logos in live-iso.ks (bcl@redhat.com)
- Update rsync version in http-server.toml (bcl@redhat.com)
- Log and exit on metadata update errors at startup (bcl@redhat.com)
- Check /projects responses for null values. (bcl@redhat.com)
- Clarify error message from /source/new (bcl@redhat.com)
- Support loading groups from the kickstart template files.  (clumens@redhat.com)
- Include groups in depsolving. (clumens@redhat.com)
- Add help output to each subcommand. (clumens@redhat.com)
- Split the help output into its own module. (clumens@redhat.com)
- If the help subcommand is given, print the help output. (clumens@redhat.com)

* Wed Jul 18 2018 Brian C. Lane <bcl@redhat.com> 28.14.1-1
- Add requires on lorax-templates-rhel (bcl@redhat.com)
- Check the compose templates at startup (bcl@redhat.com)
- Install 'hostname' in runtime-install (for iSCSI) (awilliam@redhat.com)
- Fix a couple typos in lorax-composer docs. (bcl@redhat.com)
- Require python3-dnf v3.0.0 or later (bcl@redhat.com)
- DNF 3: progress callback constants moved to dnf.transaction (awilliam@redhat.com)
- Include example blueprints in the rpm (bcl@redhat.com)
- Make sure /run/weldr has correct ownership and permissions (bcl@redhat.com)
- Allow more than 1 bash build in tests (bcl@redhat.com)
- Add redhat.exec to s390 .treeinfo (bcl@redhat.com)

* Thu Jun 07 2018 Brian C. Lane <bcl@redhat.com> 28.14.0-1
- Tag as version 28.14.0-1

* Thu Jun 07 2018 Brian C. Lane <bcl@redhat.com> 28.14-1
- New lorax documentation - 28.14 (bcl@redhat.com)
- Add --dracut-arg support to lorax (bcl@redhat.com)
- gevent has deprecated .wsgi, should use .pywsgi instead (bcl@redhat.com)

* Mon Jun 04 2018 Brian C. Lane <bcl@redhat.com> 28.13-1
- New lorax documentation - 28.13 (bcl@redhat.com)
- Override Sphinx documentation version with LORAX_VERSION (bcl@redhat.com)
- Add support for sources to composer-cli (bcl@redhat.com)
- Fix DNF related issues with source selection (bcl@redhat.com)
- Fix handling bad source repos and add a test (bcl@redhat.com)
- Speed up test_dnfbase.py (bcl@redhat.com)
- Make sure new sources show up in the source/list output (bcl@redhat.com)
- Fix make_dnf_dirs (bcl@redhat.com)
- Update test_server for rawhide (bcl@redhat.com)
- Add support for user defined package sources API (bcl@redhat.com)

* Thu May 24 2018 Brian C. Lane <bcl@redhat.com> 28.12-1
- templates: Stop using gconfset (walters@verbum.org)
- Add support for version globs to blueprints (bcl@redhat.com)
- Update atlas blueprint (bcl@redhat.com)

* Thu May 17 2018 Brian C. Lane <bcl@redhat.com> 28.11-1
- Update the generated html docs (bcl@redhat.com)
- Update the README with relevant URLs (bcl@redhat.com)
- Fix documentation for enabling lorax-composer.socket (bcl@redhat.com)
- Add support for systemd socket activation (bcl@redhat.com)
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
- Check selinux state before creating output directory (bcl@redhat.com)
- really kill kernel-bootwrapper on ppc (dan@danny.cz)
- Use Fedora 28 for Dockerfile.test (bcl@redhat.com)
- Enable testing in Travis and collecting of coverage history (atodorov@redhat.com)
- Remove -boot-info-table from s390 boot.iso creation (#1478448) (bcl@redhat.com)
- change installed packages on ppc (dan@danny.cz)
- drop support for 32-bit ppc (dan@danny.cz)
- remove redundant mkdir (dan@danny.cz)

* Mon Apr 09 2018 Brian C. Lane <bcl@redhat.com> 28.10-1
- Fix anaconda metapackage name (mkolman@redhat.com)
- Include the anaconda-install-env-deps metapackage (mkolman@redhat.com)
- Update the URL in lorax.spec to point to new Lorax location (bcl@redhat.com)
- New lorax documentation - 28.9 (bcl@redhat.com)

* Thu Mar 15 2018 Brian C. Lane <bcl@redhat.com> 28.9-1
- Update default releasever to Fedora 28 (bcl@redhat.com)
- Update Copyright year to 2018 in Sphinx docs (bcl@redhat.com)
- make docs now also builds html (bcl@redhat.com)

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
