# NOTE: This specfile is generated from upstream at https://github.com/rhinstaller/lorax
# NOTE: Please submit changes as a pull request
%define debug_package %{nil}

Name:           lorax
Version:        28.3
Release:        1%{?dist}
Summary:        Tool for creating the anaconda install images

Group:          Applications/System
License:        GPLv2+
URL:            https://github.com/rhinstaller/lorax
# To generate Source0 do:
# git clone https://github.com/rhinstaller/lorax
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
Requires:       python3-kickstart
Requires:       python3-dnf >= 2.0.0


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
Requires:       kernel-bootwrapper
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
Provides:       appliance-tools-minimizer
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

%description lmc-novirt
Additional dependencies required by livemedia-creator when using it with --no-virt
to run Anaconda.

%package templates-generic
Summary:  Generic build templates for lorax and livemedia-creator
Requires: lorax = %{version}-%{release}
Provides: lorax-templates

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

%files lmc-virt

%files lmc-novirt

%files templates-generic
%dir %{_datadir}/lorax/templates.d
%{_datadir}/lorax/templates.d/*


%changelog
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

* Mon Mar 06 2017 Brian C. Lane <bcl@redhat.com> 26.7-1
- add ostree to get installed in anaconda environment (dusty@dustymabe.com)
- Add dependency for lvmdump -l command (#1255659) (jkonecny@redhat.com)

* Tue Feb 21 2017 Brian C. Lane <bcl@redhat.com> 26.6-1
- Create /dev/random and /dev/urandom before running rpm -qa (#1420523) (bcl@redhat.com)
- Fix duplicate kernel messages in /tmp/syslog (#1382611) (rvykydal@redhat.com)

* Mon Feb 06 2017 Brian C. Lane <bcl@redhat.com> 26.5-1
- Print the full NEVRA when installing packages. (bcl@redhat.com)

* Fri Jan 13 2017 Brian C. Lane <bcl@redhat.com> 26.4-1
- Only cleanup libhistory from readline (dennis@ausil.us)
- Do not install rsh to anaconda chroot (gitDeveloper@bitthinker.com)
- Fixed NameError on result_dir when calling with --image-only (yturgema@redhat.com)

* Tue Dec 06 2016 Brian C. Lane <bcl@redhat.com> 26.3-1
- New lorax documentation - 26.2 (bcl@redhat.com)
- runtime-postinstall: PYTHONDIR is no longer used. (bcl@redhat.com)
- Only require edk2-ovmf on supported arches. (bcl@redhat.com)

* Tue Nov 22 2016 Brian C. Lane <bcl@redhat.com> 26.2-1
- add exception for lulzbot-marlin-firmware (pbrobinson@gmail.com)
- drop kexec arch conditional for aarch64 (pbrobinson@gmail.com)
- imgutils: Don't relabel /ostree (walters@verbum.org)
- Added option to remove packages (parallel to installpkgs) (riehecky@fnal.gov)
- templates: When a subprocess fatally errors, output its stderr directly (walters@verbum.org)

* Mon Oct 17 2016 Brian C. Lane <bcl@redhat.com> 26.1-1
- Add missing fonts (#1370118) (vponcova@redhat.com)
- drop ssh server key generation for s390(x) (#1383641) (dan@danny.cz)

* Fri Sep 30 2016 Brian C. Lane <bcl@redhat.com> 26.0-1
- Bump version to 26.0 (bcl@redhat.com)
- adapt to DNF 2.0 API changes (i.gnatenko.brain@gmail.com)

* Mon Sep 26 2016 Brian C. Lane <bcl@redhat.com> 25.16-1
- Fix broken sshd.inst boot option (#1378378) (jjelen@redhat.com)
- Don't log dracut initrd regeneration messages into /tmp/syslog (#1369439) (rvykydal@redhat.com)
- Use imjournal for rsyslogd instead of sharing /dev/log with journal (#1369439) (rvykydal@redhat.com)
- livemedia-creator: Check for packaging failures in the logs (#1374809) (bcl@redhat.com)
- templates: Enusre basic.target.wants dir exists for rngd (walters@verbum.org)

* Thu Sep 08 2016 Brian C. Lane <bcl@redhat.com> 25.15-1
- Keep fsfreeze in install environment (#1315468) (rmarshall@redhat.com)
- Add ppc64le kernel path (mkumatag@in.ibm.com)
- Install storaged-iscsi to the runtime (#1347415) (vpodzime@redhat.com)

* Tue Aug 23 2016 Brian C. Lane <bcl@redhat.com> 25.14-1
- lorax: Add --rootfs-size (#1368743) (bcl@redhat.com)
- Revert "Use size=10 by default" (bcl@redhat.com)

* Fri Aug 12 2016 Brian C. Lane <bcl@redhat.com> 25.13-1
- as of Fedora 25 s390x now has docker (pbrobinson@fedoraproject.org)
- ppc64le doesn't have pcmciatools (pbrobinson@fedoraproject.org)
- add grub2-tools to aarch64, drop duplicate grubby (pbrobinson@fedoraproject.org)
- Allow supplying a disk image for PXE live systems (code@schoeller.se)
- Use size=10 by default (walters@verbum.org)

* Thu Jul 28 2016 Brian C. Lane <bcl@redhat.com> 25.12-1
- New lorax documentation - 25.12 (bcl@redhat.com)
- Don't install python3-dnf-langpacks (vpodzime@redhat.com)

* Wed Jul 20 2016 Brian C. Lane <bcl@redhat.com> 25.11-1
- Fix aarch64 installs due to missing/unsupported packages
  (pbrobinson@gmail.com)
- Keep fb_sys_fops module needed for ast support (#1272658) (bcl@redhat.com)

* Wed Jul 13 2016 Brian C. Lane <bcl@redhat.com> 25.10-1
- Installing *-firmware should be optional (bcl@redhat.com)

* Fri Jul 08 2016 Brian C. Lane <bcl@redhat.com> 25.9-1
- Fix installpkg error handling (bcl@redhat.com)
- Switch installpkg default to --required (bcl@redhat.com)
- Keep all of the kernel drivers/target/ modules (#1348381) (bcl@redhat.com)
- Keep the pci utilities for use in kickstarts (#1344926) (bcl@redhat.com)
- Make sure cmdline config file exists (#1348304) (bcl@redhat.com)
- Stop using undocumented DNF logging API (bcl@redhat.com)

* Thu Jun 02 2016 Brian C. Lane <bcl@redhat.com> 25.8-1
- livemedia-creator: Always copy novirt logs before cleanup (bcl@redhat.com)

* Fri May 27 2016 Brian C. Lane <bcl@redhat.com> 25.7-1
- do not remove libutempter as tmux gained a dep on it (dennis@ausil.us)
- New lorax documentation - 25.6 (bcl@redhat.com)
- Update lmc UEFI support to use the edk2-ovmf package (bcl@redhat.com)

* Fri May 13 2016 Brian C. Lane <bcl@redhat.com> 25.6-1
- Add efi, product, and updates image paths to treeinfo (bcl@redhat.com)
- livemedia-creator: Update make-pxe-live to support missing initramfs
  (bcl@redhat.com)
- Rebuild initramfs if it is missing (bcl@redhat.com)
- Add a new error to the log monitor. (bcl@redhat.com)
- Fix DataHolder to handle hasattr (bcl@redhat.com)

* Fri Apr 29 2016 Brian C. Lane <bcl@redhat.com> 25.5-1
- Add example kickstart for Atomic PXE live no-virt (bcl@redhat.com)
- Update ostree boot handling (bcl@redhat.com)
- pylorax: Add delete option to umount (bcl@redhat.com)
- Refactor PXE live creation code (bcl@redhat.com)
- Change --make-pxe-live --no-virt use a fsimage (bcl@redhat.com)
- Allow ostreesetup kickstart (bcl@redhat.com)

* Mon Apr 18 2016 Brian C. Lane <bcl@redhat.com> 25.4-1
- livemedia-creator: Make sure make-iso kickstart includes dracut-live
  (bcl@redhat.com)
- livemedia-creator: Simplify cleanup for no-virt (bcl@redhat.com)
- Copying same file shouldn't crash (#1269213) (bcl@redhat.com)

* Wed Mar 30 2016 Brian C. Lane <bcl@redhat.com> 25.3-1
- livemedia-creator: Use correct suffix on default image names (#1318958)
  (bcl@redhat.com)
- livemedia-creator: Pass -Xbcj to mksquashfs (bcl@redhat.com)
- templates: On 32 bit systems limit the amount of memory xz uses
  (bcl@redhat.com)
- ltmpl: Add compressor selection and argument passing to installimg
  (bcl@redhat.com)
- livemedia-creator: Update example kickstarts (bcl@redhat.com)
- image-minimizer: Fix argument parsing (bcl@redhat.com)
- livemedia-creator: Check selinux state and exit (bcl@redhat.com)
- livemedia-creator: Catch dnf download error (bcl@redhat.com)
- templates: Fix runtime_img check (bcl@redhat.com)
- Remove gnome-icon-theme (dshea@redhat.com)
- Exclude unused firmware from package selection. (dshea@redhat.com)
- Add a means of excluding packages from a glob (dshea@redhat.com)
- Clean up /dev. (dshea@redhat.com)
- Remove /var/lib/dnf (dshea@redhat.com)
- Remove a bunch of stuff pulled in by webkitgtk (dshea@redhat.com)
- lorax-lmc-virt now uses qemu not libvirt and virt-install (bcl@redhat.com)
- New lorax documentation - 25.2 (bcl@redhat.com)
- Use Sphinx to generate manpages (bcl@redhat.com)
- livemedia-creator: Use sphinx-argparse to document args (bcl@redhat.com)
- Move argument parsers into pylorax.cmdline (bcl@redhat.com)
- livemedia-creator: Fix off by 1024 error (bcl@redhat.com)
- Create UDF iso when stage2 is >= 4GiB (#1312158) (bcl@redhat.com)

* Tue Mar 15 2016 Brian C. Lane <bcl@redhat.com> 25.2-1
- Not all arches currently have docker (#1317632) (pbrobinson@gmail.com)

* Wed Mar 09 2016 Brian C. Lane <bcl@redhat.com> 25.1-1
- Change location of basearch to dnf.rpm.basearch (#1312087) (bcl@redhat.com)
- livemedia-creator: Change fsck.ext4 discard failures to errors
  (bcl@redhat.com)
- pylorax: proc.returncode can be None (bcl@redhat.com)
- livemedia-creator: Create runtime using kickstart partition size
  (bcl@redhat.com)
- livemedia-creator: Update kickstarts for rawhide (bcl@redhat.com)
- pylorax: Fix undefind strings on subprocess crash (bcl@redhat.com)
- Keep /usr/bin/xrdb (#1241724) (dshea@redhat.com)
- Install the libblockdev-lvm-dbus plugin (#1264816) (vpodzime@redhat.com)
- livemedia-creator: Bump default releasever to 25 (bcl@redhat.com)
- Add docker-anaconda-addon (bcl@redhat.com)
- livemedia-creator: Use qemu instead of virt-install (bcl@redhat.com)
- Bump version to 25.0 (bcl@redhat.com)

* Tue Mar 01 2016 Brian C. Lane <bcl@redhat.com> 24.14-1
- Add glibc-all-langpacks (#1312607) (dshea@redhat.com)

* Thu Feb 25 2016 Brian C. Lane <bcl@redhat.com> 24.13-1
- templates: Reinstate gpgme-pthread.so for ostree (walters@verbum.org)
- Include grub2-efi-modules on the boot.iso (#1277227) (bcl@redhat.com)
- Keep modules needed for ast video driver support (#1272658) (bcl@redhat.com)

* Fri Feb 19 2016 Brian C. Lane <bcl@redhat.com> 24.12-1
- Put the NM loglevel config in the right place. (bcl@redhat.com)

* Fri Feb 19 2016 Brian C. Lane <bcl@redhat.com> 24.11-1
- configure NetworkManager to loglevel=DEBUG (#1274647) (rvykydal@redhat.com)
- New lorax documentation - 24.10 (bcl@redhat.com)

* Fri Feb 12 2016 Brian C. Lane <bcl@redhat.com> 24.10-1
- Add rng-tools and start rngd.service by default (#1258516) (bcl@redhat.com)
- livemedia-creator: Stop passing --repo to anaconda (#1304802)
  (bcl@redhat.com)
- livemedia-creator: Add /usr/share/lorax/templates.d/ support (bcl@redhat.com)
- Move templates to /usr/share/lorax/templates.d/99-generic (bcl@redhat.com)
- Add check for templates.d in the sharedir (bcl@redhat.com)
- Add documentation for the lorax command and templates (bcl@redhat.com)
- Remove the removal of the eintr checker, which has been removed
  (dshea@redhat.com)

* Wed Jan 13 2016 Brian C. Lane <bcl@redhat.com> 24.9-1
- livemedia-creator: Add kernel-modules and kernel-modules-extra to examples
  (bcl@redhat.com)
- livemedia-creator: Make sure the rootfs.img can be compressed
  (bcl@redhat.com)

* Tue Jan 12 2016 Brian C. Lane <bcl@redhat.com> 24.8-1
- Make arm .treeinfo match reality (dennis@ausil.us)
- Add --iso-name to use with --iso-only (bcl@redhat.com)

* Fri Jan 08 2016 Brian C. Lane <bcl@redhat.com> 24.7-1
- Add kpartx to Requires (bcl@redhat.com)
- Prefix temporary files and directories with lmc- (bcl@redhat.com)
- Add --iso-only option to --make-iso (bcl@redhat.com)
- livemedia-creator: Fix calculation of disk_size in some cases
  (logans@cottsay.net)
- docs: Update documentation for livemedia-creator (bcl@redhat.com)
- livemedia-creator: Add --image-type and --qemu-args options (bcl@redhat.com)
- pylorax: Add mkqemu_img function, alias mkqcow2 to it. (bcl@redhat.com)
- Update things to make pylint 1.5.1 happy (bcl@redhat.com)
- Write a list of debuginfo packages to /root/debug-pkgs.log (#1068675)
  (bcl@redhat.com)
- Also remove uboot from live arm.tmpl (bcl@redhat.com)
- no longer make u-boot wrapped kernels (dennis@ausil.us)
- Fix chronyd not working in the installation (#1288905) (jkonecny@redhat.com)
- Update Lorax documentation - 24.6 (bcl@redhat.com)
- Update docs for product.img (bcl@redhat.com)

* Wed Dec 02 2015 Brian C. Lane <bcl@redhat.com> 24.6-1
- livemedia-creator: Raise an error if url is used without networking
  (fabiand@fedoraproject.org)
- livemedia-creator: Fix a small typo (fabiand@fedoraproject.org)
- livemedia-creator: Use discard during installation
  (fabiand@fedoraproject.org)
- livemedia-creator: Use cache=unsafe for the installation disk
  (fabiand@fedoraproject.org)
- Remove requires for pocketlint as it is not used in build process
  (bcl@redhat.com)
- Include qemu modules in the initrd (bcl@redhat.com)
- livemedia-creator: Check kickstart for shutdown (#1207959) (bcl@redhat.com)
- livemedia-creator: Correctly handle not mounting image (bcl@redhat.com)
- livemedia-creator: Use hd:LABEL for stage2 iso (bcl@redhat.com)
- Add support for .repo files (#1264058) (bcl@redhat.com)
- livemedia-creator: Actually pass vcpus to virt-install (bcl@redhat.com)
- paste is needed by os-prober (#1275105) (bcl@redhat.com)

* Fri Nov 06 2015 Brian C. Lane <bcl@redhat.com> 24.5-1
- Add --virt-uefi to boot the VM using OVMF (bcl@redhat.com)
- Enable gtk inspector. (dshea@redhat.com)
- lorax: Improve argument parsing and help (bcl@redhat.com)
- lorax: Add --sharedir to override configuration path (bcl@redhat.com)

* Wed Oct 28 2015 Brian C. Lane <bcl@redhat.com> 24.4-1
- livemedia-creator: Allow novirt ostree partitioned images (#1273199)
  (bcl@redhat.com)
- Add documentation and kickstart for --make-vagrant (bcl@redhat.com)
- livemedia-creator: Make --make-vagrant work with --no-virt (bcl@redhat.com)
- livemedia-creator: Add --make-vagrant command (bcl@redhat.com)
- Add selinux switch to mktar (bcl@redhat.com)
- livemedia-creator: Make --make-oci work with --no-virt (bcl@redhat.com)
- Add documentation for --make-oci (bcl@redhat.com)
- livemedia-creator: Add --make-oci for Open Container Initiative images
  (bcl@redhat.com)
- Add submount directory to PartitionMount class (bcl@redhat.com)
- Keep libthread so that gdb will work correctly (#1269055) (bcl@redhat.com)
- Update Lorax documentation - 24.3 (bcl@redhat.com)

* Tue Oct 06 2015 Brian C. Lane <bcl@redhat.com> 24.3-1
- Do not let systemd-tmpfiles set up /etc on boot (dshea@redhat.com)
- Fix the concatenation of error output. (dshea@redhat.com)
- Add findmnt command (jkonecny@redhat.com)
- Reduce the size of macboot.img (#952747) (bcl@redhat.com)
- rsa1 keys are not supported any more by our openssh (dan@danny.cz)
- Look for crashes from the anaconda signal handler. (dshea@redhat.com)
- Include gdb in the boot.iso (dshea@redhat.com)
- Do not install weak deps in boot.iso (bcl@redhat.com)
- Require correct dnf version for API changes (bcl@redhat.com)
- Drop multiprocessing for do_transaction (#1208296) (bcl@redhat.com)
- Add a font that supports Urdu characters (#1004717) (bcl@redhat.com)
- livemedia-creator: Remove random-seed from images (#1258986) (bcl@redhat.com)
- Don't include early microcode in initramfs (#1258498) (bcl@redhat.com)

* Mon Aug 31 2015 Brian C. Lane <bcl@redhat.com> 24.2-1
- drop fedup-dracut and friends (wwoods@redhat.com)
- don't build upgrade.img anymore (wwoods@redhat.com)
- livemedia-creator: no-virt fsimage should only use / size from ks
  (bcl@redhat.com)
- Update lmc docs for new mock (bcl@redhat.com)
- No longer offer a rescue boot menu option on liveinst (#1256061).
  (clumens@redhat.com)
- document --timeout in livemedia-creator man page (atodorov@redhat.com)
- Add enough of shadow-utils to create new user accounts. (dshea@redhat.com)
- Update Lorax documentation - 24.1 (bcl@redhat.com)
- Add lldptool (#1085325) (rvykydal@redhat.com)

* Fri Aug 07 2015 Brian C. Lane <bcl@redhat.com> 24.1-1
- some of the PowerPC utilities (powerpc-utils and fbset) need perl too
  (pbrobinson@gmail.com)
- Add a default vconsole.conf to the boot.iso (#1250260) (bcl@redhat.com)
- Return the output from failed commands in CalledProcessError (bcl@redhat.com)
- Add dracut-live for livemedia kickstart example (bcl@redhat.com)

* Thu Jul 30 2015 Brian C. Lane <bcl@redhat.com> 24.0-1
- Bump version to 24.0 (bcl@redhat.com)
- Use execReadlines in livemedia-creator (bcl@redhat.com)
- Add execReadlines to executils. (bcl@redhat.com)
- Add reset_lang argument to everything in executils. (bcl@redhat.com)

* Tue Jul 21 2015 Brian C. Lane <bcl@redhat.com> 23.14-1
- Add a new makefile target that does everything needed for jenkins.
  (clumens@redhat.com)
- Revert "Revert "Turn off ldconfig"" (dshea@redhat.com)
- Add back libraries needed by spice-vdagent (dshea@redhat.com)
- Remove some junk that didn't work anyway (dshea@redhat.com)
- Add a verification step to Lorax.run. (dshea@redhat.com)
- Create an empty selinux config file (#1243168) (bcl@redhat.com)
- Update Lorax documentation - 23.13 (bcl@redhat.com)

* Fri Jul 10 2015 Brian C. Lane <bcl@redhat.com> 23.13-1
- Add a bit more overhead to the root filesystem size (bcl@redhat.com)
- network: turn slaves autoconnection on (rvykydal@redhat.com)
- Keep hyperv_fb driver in the image (#834791) (bcl@redhat.com)

* Fri Jun 26 2015 Brian C. Lane <bcl@redhat.com> 23.12-1
- Explicitly add kernel-modules and kernel-modules-extra (bcl@redhat.com)

* Fri Jun 19 2015 Brian C. Lane <bcl@redhat.com> 23.11-1
- Disable systemd-tmpfiles-clean (#1202545) (bcl@redhat.com)

* Wed Jun 10 2015 Brian C. Lane <bcl@redhat.com> 23.10-1
- Remove some stale entires from runtime-install (dshea@redhat.com)
- Stop moving sitecustomize into site-packages (bcl@redhat.com)
- Pass setup_logging the log file, not the whole opts structure.
  (clumens@redhat.com)
- Move IsoMountpoint into its own module. (clumens@redhat.com)
- Move setup_logging into pylorax/__init__.py. (clumens@redhat.com)
- Break all the log monitoring stuff from LMC out into its own module.
  (clumens@redhat.com)
- Fix bug with product DataHolder overwriting product string. (bcl@redhat.com)

* Fri May 15 2015 Brian C. Lane <bcl@redhat.com> 23.9-1
- Update execWith* docstrings (bcl@redhat.com)
- livemedia-creator: Update example kickstarts (bcl@redhat.com)
- Update fedora-livemedia.ks example (bcl@redhat.com)
- Include html documentation under docs/html (bcl@redhat.com)
- Switch documentation to python3 (bcl@redhat.com)
- Create html documentation under docs/html/ (bcl@redhat.com)
- livemedia-creator: Catch missing package errors (bcl@redhat.com)
- Update spec for python3 and add subpackages for lmc (bcl@redhat.com)
- Convert to using pocketlint for pylint rules (bcl@redhat.com)
- Convert livemedia-creator to py3 (bcl@redhat.com)
- Convert test-parse-template to py3 (bcl@redhat.com)
- Update image-minimizer for py3 (bcl@redhat.com)
- Change mkefiboot to py3 (bcl@redhat.com)
- Additional python3 changes (bcl@redhat.com)
- Update lorax for python3 and argparse (bcl@redhat.com)
- Use the execWith* methods from Anaconda (bcl@redhat.com)
- Convert pylorax to python3 (bcl@redhat.com)
- Clean up some pylint warnings (bcl@redhat.com)
- Make sure openssh-clients is installed (#1219398) (bcl@redhat.com)
- Add product.img support for s390 templates (dan@danny.cz)
- Add some more details about template rendering errors (bcl@redhat.com)
- Mock more modules for RTD (bcl@redhat.com)
- Mock the selinux package for RTD (bcl@redhat.com)
- Added Sphinx Documentation (bcl@redhat.com)

* Thu Apr 02 2015 Brian C. Lane <bcl@redhat.com> 23.8-1
- Include cryptsetup in the image (#1208214) (bcl@redhat.com)

* Fri Mar 27 2015 Brian C. Lane <bcl@redhat.com> 23.7-1
- Check that the transaction process is still alive (vpodzime@redhat.com)
- livemedia-creator: Clean up resultdir handling (bcl@redhat.com)

* Fri Mar 20 2015 Brian C. Lane <bcl@redhat.com> 23.6-1
- Include ld.so.conf (#1204031) (bcl@redhat.com)
- Revert "Turn off ldconfig" (bcl@redhat.com)
- Add ability for external templates to graft content into boot.iso
  (walters@verbum.org)
- Keep logitech hid drivers (#1199770) (bcl@redhat.com)

* Mon Mar 16 2015 Brian C. Lane <bcl@redhat.com> 23.5-1
- Don't erase /usr/lib/os.release.d (sgallagh@redhat.com)

* Fri Mar 13 2015 Brian C. Lane <bcl@redhat.com> 23.4-1
- Require python-dnf so that we get the python2 version (bcl@redhat.com)
- livemedia-creator: Fix up fake yum object for DNF change (bcl@redhat.com)
- Update logic for stage2 detection on boot.iso (bcl@redhat.com)

* Fri Mar 06 2015 Brian C. Lane <bcl@redhat.com> 23.3-1
- Turn off ldconfig (bcl@redhat.com)
- Add removekmod template command (bcl@redhat.com)
- Move stage2 to images/install.img (#815275) (bcl@redhat.com)

* Fri Feb 27 2015 Brian C. Lane <bcl@redhat.com> 23.2-1
- Update pykickstart requirement (bcl@redhat.com)
- Explicitly install notification-daemon (dshea@redhat.com)

* Tue Feb 17 2015 Brian C. Lane <bcl@redhat.com> 23.1-1
- Skip using srpm repos (bcl@redhat.com)
- Drop the dnf Base object deletion code and use reset (bcl@redhat.com)
- Get the log directory from the configfile (bcl@redhat.com)
- lorax: Add --cachedir, --force and --workdir cmdline options (bcl@redhat.com)
- Cleanup help alignment (bcl@redhat.com)
- dnf: remove files from installed packages (bcl@redhat.com)
- Switch lorax to use dnf instead of yum (bcl@redhat.com)
- Fix Source0 for use with github (bcl@redhat.com)

* Thu Feb 12 2015 Brian C. Lane <bcl@redhat.com> 23.0-1
- Bump version to 23.0 (bcl@redhat.com)
- os-release moved to /usr/lib (#1191713) (bcl@redhat.com)
- Use /usr/bin/python2 in scripts (bcl@redhat.com)
- Add bridge-utils (#1188812) (bcl@redhat.com)

* Fri Feb 06 2015 Brian C. Lane <bcl@redhat.com> 22.4-1
- livemedia-creator: Add --timeout option to cancel install after X minutes
  (bcl@redhat.com)
- network: add support for bridge (#1075195) (rvykydal@redhat.com)
- Move url and source to github in specfile (bcl@redhat.com)
- Use %%license in lorax.spec (bcl@redhat.com)

* Fri Jan 23 2015 Brian C. Lane <bcl@redhat.com> 22.3-1
- livemedia-creator: Add documentation on using mock and livemedia-creator (bcl@redhat.com)
- livemedia-creator: Bump default releasever to 22 (bcl@redhat.com)
- Change console font to eurlatgr (myllynen@redhat.com)

* Fri Jan 16 2015 Brian C. Lane <bcl@redhat.com> 22.2-1
- Add --live-rootfs-keep-size option (rvykydal@redhat.com)
- Add --live-rootfs-size option. (rvykydal@redhat.com)
- livemedia-creator: Update example kickstarts (bcl@redhat.com)
- livemedia-creator: Turn on debug output for dracut (bcl@redhat.com)
- livemedia-creator: Copy all the logs from /tmp/ (bcl@redhat.com)
- livemedia-creator: Create parent dirs for logfile path (bcl@redhat.com)
- Remove fedora-icon-theme (dshea@redhat.com)
- Remove fedora-gnome-theme (dshea@redhat.com)
- Remove the GSettings overrides for metacity (dshea@redhat.com)
- Remove gnome-python2-gconf (dshea@redhat.com)
- --make-pxe-target: change permissions of regenerated initramrfs to 0644
  (rvykydal@redhat.com)
- Override services kickstart setting from interactive-defaults.ks
  (rvykydal@redhat.com)
- Use gcdaa64.efi on aarch64 (#1174475) (bcl@redhat.com)
- livemedia-creator: add a timeout to the log monitor startup (bcl@redhat.com)
- Add --make-pxe-live and --make-ostree-live (for Atomic) targets.
  (rvykydal@redhat.com)
- Revert "Install optional product and updates packages (#1155228)"
  (bcl@redhat.com)
- Add log monitoring to lmc --no-virt installation (bcl@redhat.com)
- runtime-cleanup.tmpl: keep virtio-rng (#1179000) (lersek@redhat.com)
- Install python-nss (vpodzime@redhat.com)

* Fri Dec 12 2014 Brian C. Lane <bcl@redhat.com> 22.1-1
- Actually make boot.iso on aarch64. (pjones@redhat.com)
- Add --includepkg argument (walters@verbum.org)

* Fri Dec 05 2014 Brian C. Lane <bcl@redhat.com> 22.0-1
- aarch64 no longer needs explicit console setting (#1170412) (bcl@redhat.com)
- Bump version to 22.0 (bcl@redhat.com)

* Wed Dec 03 2014 Brian C. Lane <bcl@redhat.com> 21.31-1
- Drop 32 bit for loop from ppc64 grub2 config (#1169878) (bcl@redhat.com)
- gschemas: Fix typo button_laytout -> button_layout (walters@verbum.org)

* Thu Nov 20 2014 Brian C. Lane <bcl@redhat.com> 21.30-1
- Install optional product and updates packages (#1155228) (bcl@redhat.com)

* Wed Nov 19 2014 Brian C. Lane <bcl@redhat.com> 21.29-1
- Remove diagnostic product.img test (#1165425) (bcl@redhat.com)

* Thu Nov 06 2014 Brian C. Lane <bcl@redhat.com> 21.28-1
- Add product.img support for arm templates (bcl@redhat.com)
- Revert "add fedora-repos-anaconda to runtime environment" (bcl@redhat.com)

* Wed Nov 05 2014 Brian C. Lane <bcl@redhat.com> 21.27-1
- Remove the ppc magic file (bcl@redhat.com)
- Update templates to use installimg for product and updates (bcl@redhat.com)
- Add installimg command for use in the templates (bcl@redhat.com)
- Setup mdadm to turn off homehost (#1156614) (bcl@redhat.com)
- Don't include the stock lvm.conf. (#1157864) (dlehman@redhat.com)
- Write list of packages to /root/lorax-packages.log (bcl@redhat.com)

* Mon Oct 20 2014 Brian C. Lane <bcl@redhat.com> 21.26-1
- Use all upper case for shim in live/efi.tmpl (bcl@redhat.com)
- livemedia-creator: Add nfs support for no-virt mode (#1121255)
  (bcl@redhat.com)
- Include /usr/bin/bugzilla in the installation environment.
  (clumens@redhat.com)

* Tue Oct 07 2014 Brian C. Lane <bcl@redhat.com> 21.25-1
- Libgailutil is required yelp, don't remove it (#1072033) (mkolman@redhat.com)
- Revert "Don't remove /usr/share/doc/anaconda." (#1072033)
  (mkolman@redhat.com)
- Look for "BOOT${efiarch}.EFI" in mkefiboot as well. (pjones@redhat.com)
- Make sure shim is actually in the package list on aarch64 as well.
  (pjones@redhat.com)
- Fix 'docs' typo in livemedia-creator manpage (#1149026) (bcl@redhat.com)
- Keep the /etc/lvm/profiles directory in the image (vpodzime@redhat.com)
- Use shim on aarch64. (pjones@redhat.com)

* Tue Sep 30 2014 Brian C. Lane <bcl@redhat.com> 21.24-1
- Rework how including /usr/share/doc/anaconda works. (clumens@redhat.com)
- Don't remove /usr/share/doc/anaconda. (clumens@redhat.com)
- Stop removing libXt from the installation media. (clumens@redhat.com)

* Tue Sep 23 2014 Brian C. Lane <bcl@redhat.com> 21.23-1
- livemedia-creator: Make sure ROOT_PATH exists (#1144140) (bcl@redhat.com)
- livemedia-creator: Add --no-recursion to mktar (#1144140) (bcl@redhat.com)
- Remove at-spi (dshea@redhat.com)

* Mon Sep 15 2014 Brian C. Lane <bcl@redhat.com> 21.22-1
- add fedora-repos-anaconda to runtime environment (awilliam@redhat.com)
- Let the plymouth dracut module back into the ppc64 upgrade.img
  (dshea@redhat.com)
- Add more tools for rescue mode (#1109785) (bcl@redhat.com)
- Add ppc64le arch (#1136490) (bcl@redhat.com)
- allow setting additional dracut parameters for DVD s390x installs
  (dan@danny.cz)

* Thu Aug 28 2014 Brian C. Lane <bcl@redhat.com> 21.21-1
- Revert "Require 32bit glibc on ppc64" (bcl@redhat.com)
- livemedia-creator: Update ppc64 live to use grub2 (bcl@redhat.com)
- livemedia-creator: Add ppc64 live creation support (#1102318)
  (bcl@redhat.com)
- Include /sbin/ldconfig from glibc. (dlehman@redhat.com)

* Fri Aug 15 2014 Brian C. Lane <bcl@redhat.com> 21.20-1
- Require 32bit glibc on ppc64 (bcl@redhat.com)
- Add ipmitool and drivers (#1126009) (bcl@redhat.com)
- livemedia-creator: Padd disk size by 2MiB (bcl@redhat.com)
- livemedia-creator: Run setfiles after no-virt installation (bcl@redhat.com)
- https is a sane package source URL scheme (walters@verbum.org)

* Wed Jul 30 2014 Brian C. Lane <bcl@redhat.com> 21.19-1
- Add kexec anaconda addon (#1115914) (bcl@redhat.com)

* Wed Jul 23 2014 Brian C. Lane <bcl@redhat.com> 21.18-1
- Revert "Add kexec anaconda addon (#1115914)" (bcl@redhat.com)
- Disable dnf-makecache.timer (#1120368) (bcl@redhat.com)

* Wed Jul 16 2014 Brian C. Lane <bcl@redhat.com> 21.17-1
- livemedia-creator: close the socket when done (bcl@redhat.com)
- Keep seq and getconf utilities in the image (vpodzime@redhat.com)
- Allow _ in isolabel (#1118955) (bcl@redhat.com)

* Fri Jul 11 2014 Brian C. Lane <bcl@redhat.com> 21.16-1
- Don't remove usr/lib/rpm/platform/ (#1116450) (bcl@redhat.com)
- Add xfsdump and remove extra files from xfsprogs (#1118654) (bcl@redhat.com)
- Add kexec anaconda addon (#1115914) (bcl@redhat.com)
- Fix typo in lohit-telugu-fonts (bcl@redhat.com)
- Drop writing to resolv.conf in postinstall (bcl@redhat.com)
- livemedia-creator: Allow the boot.iso to be shared (bcl@redhat.com)
- livemedia-creator: log more failure information (bcl@redhat.com)
- livemedia-creator: drop console=ttyS0 (bcl@redhat.com)
- livemedia-creator: Log the line that caused the failure (bcl@redhat.com)
- livemedia-creator: add more errors (bcl@redhat.com)
- Allow doing non-URL installs if using virt. (clumens@redhat.com)

* Wed Jul 02 2014 Brian C. Lane <bcl@redhat.com> 21.15-1
- Convert metacity gconf settings into gsettings schema overrides
  (dshea@redhat.com)
- Add more keybindings to the gschema override (dshea@redhat.com)
- Don't emit media labels with spaces in them. (pjones@redhat.com)
- Remove biosdevname (#989209) (bcl@redhat.com)

* Fri Jun 27 2014 Brian C. Lane <bcl@redhat.com> 21.14-1
- The theme has been absorbed into gtk3 (bcl@redhat.com)

* Thu Jun 26 2014 Brian C. Lane <bcl@redhat.com> 21.13-1
- livemedia-creator: Ignore IGNORED errors in anaconda logs (bcl@redhat.com)

* Tue Jun 24 2014 Brian C. Lane <bcl@redhat.com> 21.12-1
- tito.props section name is buildconfig (bcl@redhat.com)
- Stop removing libcanberra-gtk3 libraries (#1111724) (bcl@redhat.com)
- Update tito config (bcl@redhat.com)

* Thu Jun 19 2014 Brian C. Lane <bcl@redhat.com> 21.11-1
- livemedia-creator: Handle virt-install failure cleanup (bcl@redhat.com)
- livemedia-creator: Fail when there are missing packages (bcl@redhat.com)
- Keep virtio_console harder. (dshea@redhat.com)

* Mon May 12 2014 Brian C. Lane <bcl@redhat.com> 21.10-1
- Add --add-template{,-var} (walters@verbum.org)
- runtime-install: Add rpm-ostree, move dnf here (walters@verbum.org)
- Update copyright statements (bcl@redhat.com)
- livemedia-creator: Cleanup docstrings (bcl@redhat.com)
- livemedia-creator: Cleanup some style issues (bcl@redhat.com)
- Cleanup other misc pylint warnings (bcl@redhat.com)
- Cleanup pylorax pylint warnings (bcl@redhat.com)
- Add pylint testing (bcl@redhat.com)
- Require uboot-tools when running on arm (dennis@ausil.us)
- Obsolete appliance-tools-minimizer (#1084110) (bcl@redhat.com)
- livemedia-creator: Copy fsimage if hardlink fails (bcl@redhat.com)
- Turn on debug output for mkefiboot (bcl@redhat.com)
- Clean up download and install output (bcl@redhat.com)
- Install specific lohit fonts instead of all of them (#1090390)
  (bcl@redhat.com)
- Update grub2-efi.cfg for aarch64 to more closely match x86 (#1089418).
  (dmarlin@redhat.com)
- Install rdma so that dracut will use it along with libmlx4 (#1089564)
  (bcl@redhat.com)

* Tue Apr 15 2014 Brian C. Lane <bcl@redhat.com> 21.9-1
- Update syslinux 6.02 support for noarch change (bcl@redhat.com)
- runtime-cleanup: Do install GPG (walters@verbum.org)

* Thu Apr 10 2014 Brian C. Lane <bcl@redhat.com> 21.8-1
- Update to support syslinux 6.02 (bcl@redhat.com)
- livemedia-creator: Add support for making tarfiles (bcl@redhat.com)
- livemedia-creator: Allow disk sizes to be < 1GiB (bcl@redhat.com)
- livemedia-creator: Check fsimage kickstart for single partition
  (bcl@redhat.com)
- livemedia-creator: Output all the errors at once (bcl@redhat.com)
- livemedia-creator: Update documentation to reflect new options
  (bcl@redhat.com)
- livemedia-creator: Make --make-fsimage work with virt-install
  (bcl@redhat.com)

* Wed Apr 02 2014 Brian C. Lane <bcl@redhat.com> 21.7-1
- Use BOOTAA64.efi for AARCH64 bootloader filename (#1080113) (bcl@redhat.com)
- Stop removing curl after adding it (bcl@redhat.com)
- move image-minimizer to lorax (#1082642) (bcl@redhat.com)
- support ppc64le in lorax (hamzy@us.ibm.com)

* Wed Mar 26 2014 Brian C. Lane <bcl@redhat.com> 21.6-1
- Install bzip2 for liveimg tar.bz2 support (bcl@redhat.com)
- Remove obsolete firstaidkit packages (#1076237) (bcl@redhat.com)
- livemedia-creator: Add option to create qcow2 disk images (bcl@redhat.com)
- Add support for creating qcow2 images (bcl@redhat.com)
- utf-8 encode yum actions before displaying them (#1072362) (bcl@redhat.com)

* Fri Feb 28 2014 Brian C. Lane <bcl@redhat.com> 21.5-1
- Use string for releasever not int (#1067746) (bcl@redhat.com)
- createrepo is needed by driver disks (#1016004) (bcl@redhat.com)
- Improve aarch64 UEFI support (#1067671) (dmarlin@redhat.com)
- livemedia-creator: Set the product and release version env variables
  (#1067746) (bcl@redhat.com)
- Check initrd size on ppc64 and warn (#1060691) (bcl@redhat.com)
- Remove drivers and modules on ppc64 (#1060691) (bcl@redhat.com)

* Mon Feb 10 2014 Brian C. Lane <bcl@redhat.com> 21.4-1
- livemedia-creator: virt-image needs ram in MiB not KiB (#1061773)
  (bcl@redhat.com)
- Don't remove libraries from bind-libs-lite (dshea@redhat.com)
- Include all the example kickstarts (#1019728) (bcl@redhat.com)
- Remove floppy and scsi_debug from initrd (#1060691) (bcl@redhat.com)

* Tue Feb 04 2014 Brian C. Lane <bcl@redhat.com> 21.3-1
- Install aajohan-comfortaa-fonts (#1047430) (bcl@redhat.com)
- Include mesa-dri-drivers (#1053940) (bcl@redhat.com)

* Fri Jan 24 2014 Brian C. Lane <bcl@redhat.com> 21.2-1
- Activate anaconda-shell@.service on switch to empty VT (#980062)
  (wwoods@redhat.com)
- flush data to disk after mkfsimage (#1052175) (bcl@redhat.com)
- livemedia-creator: Use findkernels instead of KernelInfo (bcl@redhat.com)
- Print error when kickstart is missing (#1052872) (bcl@redhat.com)

* Tue Dec 17 2013 Brian C. Lane <bcl@redhat.com> 21.1-1
- Add initial 64-bit ARM (aarch64) support (#1034432) (dmarlin@redhat.com)

* Mon Dec 16 2013 Brian C. Lane <bcl@redhat.com> 21.0-1
- s390 switch to generic condev (#1042766) (bcl@redhat.com)
- sort glob output before using it (bcl@redhat.com)
- Bless grub2 for PPC (#1020112) (catacombae@gmail.com)
- livemedia-creator: Cleanup temp yum files (#1025837) (bcl@redhat.com)
- lorax: pass size from Lorax.run to create_runtime (#903385) (bcl@redhat.com)

* Mon Nov 18 2013 Brian C. Lane <bcl@redhat.com> 20.4-1
- drop 'xdriver=vesa' from basic graphics mode parameters (per ajax)
  (awilliam@redhat.com)
- Include partx (#1022899) (bcl@redhat.com)
- Run compressions in multiple threads (vpodzime@redhat.com)
- Do not remove libdaemon from the runtime environment (#1028938)
  (vpodzime@redhat.com)
- Set UEFI defaults to match BIOS (#1021451,#1021446) (bcl@redhat.com)
- livemedia-creator: Add minimal disk example kickstart (#1019728)
  (bcl@redhat.com)

* Wed Oct 16 2013 Brian C. Lane <bcl@redhat.com> 20.3-1
- ARM: install the dtb files into the install tree. (dennis@ausil.us)
- ARM: Don't install or deal with in templates, no longer existing kernels
  (dennis@ausil.us)
- kernel changed seperator for flavours from . to + update regular expression
  (dennis@ausil.us)
- Keep virtio_console module (#1019564) (bcl@redhat.com)
- Add macboot option (#1012529) (bcl@redhat.com)

* Wed Sep 25 2013 Brian C. Lane <bcl@redhat.com> 20.2-1
- drop dracut args from config files (#1008054) (bcl@redhat.com)
- livemedia-creator: Update example kickstart (bcl@redhat.com)

* Mon Sep 09 2013 Brian C. Lane <bcl@redhat.com> 20.1-1
- Yaboot to grub2 conversion cleanup. (dwa@redhat.com)
- Firstboot is not an anaconda dependency (vpodzime@redhat.com)
- Revert "Switch to cgit url for Source0" (bcl@redhat.com)
- Switch to cgit url for Source0 (bcl@redhat.com)

* Tue Sep 03 2013 Brian C. Lane <bcl@redhat.com> 20.0-1
- remove firewalld from installroot (#1002195) (bcl@redhat.com)
- Make sure grubby is installed for initrd creation (#1001896) (bcl@redhat.com)
- GRUB2 as the ISO boot loader for POWER arch (pfsmorigo@br.ibm.com)
- Require hfsplus-tools on Fedora x86_64 (bcl@redhat.com)

* Fri Aug 23 2013 Brian C. Lane <bcl@redhat.com> 19.8-1
- Make sure we have a theme settings file in place. (clumens@redhat.com)
- Keep liblzo2.* (#997643) (dshea@redhat.com)
- Make sure dracut uses no-hostonly mode (bcl@redhat.com)
- Run spice-vdagentd without systemd-logind integration (#969405)
  (dshea@redhat.com)

* Thu Aug 01 2013 Brian C. Lane <bcl@redhat.com> 19.7-1
- Add a dist target that copies the archive to fedorahosted (bcl@redhat.com)
- dracut-nohostonly and dracut-norescue got renamed for dracut >= 030
  (harald@redhat.com)
- EFI and related packages are only for x86_64 (pjones@redhat.com)
- Don't remove xkeyboard-config message files (#972236) (dshea@redhat.com)

* Fri Jul 26 2013 Brian C. Lane <bcl@redhat.com> 19.6-1
- Add manpage for lorax (bcl@redhat.com)
- Add manpage for livemedia-creator (bcl@redhat.com)
- livemedia-creator: pass inst.cmdline for headless installs (#985487)
  (bcl@redhat.com)
- Stop using /usr/bin/env (#987028) (bcl@redhat.com)
- livemedia-creator: clarify required package errors (#985340) (bcl@redhat.com)
- Include device-mapper-persistent-data in images for thinp support.
  (dlehman@redhat.com)

* Thu Jun 13 2013 Brian C. Lane <bcl@redhat.com> 19.5-1
- Let sshd decide which keys to create (#971856) (bcl@redhat.com)
- Don't remove thbrk.tri (#886250) (bcl@redhat.com)
- Switch from xorg-x11-fonts-ethiopic to sil-abyssinica-fonts (#875664)
  (bcl@redhat.com)
- Make ignoring yum_lock messages in anaconda easier. (clumens@redhat.com)
- Bump image size up to 2G (#967556) (bcl@redhat.com)
- livemedia-creator: Fix logic for anaconda test (#958036) (bcl@redhat.com)

* Tue May 21 2013 Brian C. Lane <bcl@redhat.com> 19.4-1
- Add command for opening anaconda log file to history (mkolman@gmail.com)
- Do not install chrony and rdate explicitly (vpodzime@redhat.com)

* Mon Apr 29 2013 Brian C. Lane <bcl@redhat.com> 19.3-1
- Remove /var/log/journal so journald won't write to overlay
  (wwoods@redhat.com)
- Leave /etc/os-release in the initrd (#956241) (bcl@redhat.com)
- no standalone modutils package (dan@danny.cz)
- remove no longer supported arm kernel variants add the new lpae one
  (dennis@ausil.us)
- livemedia-creator: Update example kickstarts (bcl@redhat.com)
- livemedia-creator: Ignore rescue kernels (bcl@redhat.com)

* Mon Apr 15 2013 Brian C. Lane <bcl@redhat.com> 19.2-1
- Let devices get detected and started automatically. (dlehman@redhat.com)
- Fix import of version (bcl@redhat.com)
- fix version query and add one to the log file (hamzy@us.ibm.com)
- Do not remove files required by tools from the s390utils-base package.
  (jstodola@redhat.com)

* Tue Mar 19 2013 Brian C. Lane <bcl@redhat.com> 19.1-1
- Print & log messages on scriptlet/transaction errors (wwoods@redhat.com)
- sysutils: add -x to cp in linktree (wwoods@redhat.com)
- treebuilder: fix "Can't stat exclude path "/selinux"..." message
  (wwoods@redhat.com)
- runtime: install dracut-{nohostonly,norescue} (wwoods@redhat.com)
- runtime-install: install shim-unsigned (wwoods@redhat.com)
- Add explicit install of net-tools (#921619) (bcl@redhat.com)
- Don't remove hmac files for ssh and sshd (#882153) (bcl@redhat.com)
- Raise an error when there are no initrds (bcl@redhat.com)
- Add yum logging to yum.log (bcl@redhat.com)
- remove sparc support (dennis@ausil.us)
- Change Makefile to produce .tgz (bcl@redhat.com)

* Thu Feb 28 2013 Brian C. Lane <bcl@redhat.com> 19.0-1
- New Version 19.0
- Remove some env variables (#907692) (bcl@redhat.com)
- Make sure tmpfs is enabled (#908253) (bcl@redhat.com)

* Tue Feb 12 2013 Brian C. Lane <bcl@redhat.com> 18.31-1
- add syslinux and ssm (bcl@redhat.com)
- Add filesystem image install support (bcl@redhat.com)

* Thu Jan 31 2013 Brian C. Lane <bcl@redhat.com> 18.30-1
- yum changed the callback info (bcl@redhat.com)
- tigervnc-server-module depends on Xorg, which doesn't exist on s390x
  (dan@danny.cz)
- tools not existing on s390x (dan@danny.cz)
- specspo is dead for a long time (dan@danny.cz)
- no Xorg on s390x (dan@danny.cz)
- Make boot configs consistent. (dmach@redhat.com)
- Dynamically generate the list of installed platforms for .treeinfo
  (dmarlin@redhat.com)
- Add a U-Boot wrapped image of 'upgrade.img'. (dmarlin@redhat.com)
- Add trigger for Anaconda's exception handling to bash_history
  (vpodzime@redhat.com)
- livemedia-creator: update example kickstarts (bcl@redhat.com)
- livemedia-creator: don't pass console=ttyS0 (bcl@redhat.com)
- Fix gcdx64.efi path to work for other distros than Fedora. (dmach@redhat.com)

* Thu Dec 20 2012 Martin Gracik <mgracik@redhat.com> 18.29-1
- Do not remove gtk3 share files (mgracik@redhat.com)

* Wed Dec 19 2012 Martin Gracik <mgracik@redhat.com> 18.28-1
- Fix rexists (mgracik@redhat.com)
- Several 'doupgrade' fixes in the x86 template. (dmach@redhat.com)
- Missing semicolon (mgracik@redhat.com)

* Tue Dec 18 2012 Martin Gracik <mgracik@redhat.com> 18.27-1
- Only run installupgradeinitrd if upgrade on s390x (mgracik@redhat.com)

* Tue Dec 18 2012 Martin Gracik <mgracik@redhat.com> 18.26-1
- Only run installupgradeinitrd if upgrade (mgracik@redhat.com)

* Tue Dec 18 2012 Martin Gracik <mgracik@redhat.com> 18.25-1
- Add --noupgrade option (mgracik@redhat.com)
- Require fedup-dracut* only on Fedora. (dmach@redhat.com)

* Fri Dec 14 2012 Brian C. Lane <bcl@redhat.com> 18.24-1
- imgutils: use -s for kpartx, wait for device creation (bcl@redhat.com)
- livemedia-creator: Use SELinux Permissive mode (bcl@redhat.com)
- livemedia-creator: use cmdline mode (bcl@redhat.com)
- use correct variable for upgrade image on s390 (dan@danny.cz)
- only ix86/x86_64 and ppc/ppc64 need grub2 (dan@danny.cz)
- no mount (sub-)package since RHEL-2 (dan@danny.cz)
- Correct argument to installupgradeinitrd. (dmarlin@redhat.com)
- Added fedup requires to spec (bcl@redhat.com)

* Wed Dec 05 2012 Brian C. Lane <bcl@redhat.com> 18.23-1
- remove multipath rules (#880263) (bcl@redhat.com)
- add installupgradeinitrd function and use it to install the upgrade initrds
  (dennis@ausil.us)
- use installinitrd to install the upgrade.img initramfs so that we get correct
  permissions (dennis@ausil.us)
- ppc and arm need to use kernel.upgrade not kernel.upgrader (dennis@ausil.us)
- remove upgrade from the sparc and sysylinux config templates
  (dennis@ausil.us)
- Add the 'fedup' plymouth theme if available (wwoods@redhat.com)
- make templates install upgrade.img (wwoods@redhat.com)
- build fedup upgrade.img (wwoods@redhat.com)
- treebuilder: improve findkernels() initrd search (wwoods@redhat.com)
- treebuilder: add 'prefix' to rebuild_initrds() (wwoods@redhat.com)
- Add thai-scalable-waree-fonts (#872468) (mgracik@redhat.com)
- Do not remove the fipscheck package (#882153) (mgracik@redhat.com)
- Add MokManager.efi to EFI/BOOT (#882101) (mgracik@redhat.com)

* Tue Nov 06 2012 Brian C. Lane <bcl@redhat.com> 18.22-1
- Install the yum-langpacks plugin (#868869) (jkeating@redhat.com)
- perl is required by some low-level tools on s390x (#868824) (dan@danny.cz)

* Thu Oct 11 2012 Brian C. Lane <bcl@redhat.com> 18.21-1
- Change the install user's shell for tmux (jkeating@redhat.com)
- Set permissions on the initrd (#863018) (mgracik@redhat.com)
- Remove the default word from boot menu (#848676) (mgracik@redhat.com)
- Disable a whole bunch more keyboard shortcuts (#863823). (clumens@redhat.com)
- use /var/tmp instead of /tmp (bcl@redhat.com)
- remove rv from unmount error log (bcl@redhat.com)

* Wed Sep 19 2012 Brian C. Lane <bcl@redhat.com> 18.20-1
- Remove grub 0.97 splash (bcl@redhat.com)
- livemedia-creator: use rd.live.image instead of liveimg (bcl@redhat.com)

* Mon Sep 17 2012 Brian C. Lane <bcl@redhat.com> 18.19-1
- There's no lang-table in anaconda anymore (#857925) (mgracik@redhat.com)
- add convienience functions for running commands (bcl@redhat.com)
- restore CalledProcessError handling (bcl@redhat.com)
- add CalledProcessError to execWith* functions (bcl@redhat.com)
- live uses root not inst.stage2 (bcl@redhat.com)
- Revert "X needs the DRI drivers" (#855289) (bcl@redhat.com)

* Fri Sep 07 2012 Brian C. Lane <bcl@redhat.com> 18.18-1
- Keep the dracut-lib.sh around for runtime (#851362) (jkeating@redhat.com)
- X needs the DRI drivers (#855289) (bcl@redhat.com)

* Fri Aug 31 2012 Brian C. Lane <bcl@redhat.com> 18.17-1
- use inst.stage2=hd:LABEL (#848641) (bcl@redhat.com)
- Disable the maximize/unmaximize key bindings (#853410). (clumens@redhat.com)

* Thu Aug 30 2012 Brian C. Lane <bcl@redhat.com> 18.16-1
- Revert "Mask the tmp.mount service to avoid tmpfs" (jkeating@redhat.com)

* Thu Aug 23 2012 Brian C. Lane <bcl@redhat.com> 18.15-1
- change grub-cd.efi to gcdx64.efi (#851326) (bcl@redhat.com)
- use wildcard for product path to efi binaries (#851196) (bcl@redhat.com)
- Add yum-plugin-fastestmirror (#849797) (bcl@redhat.com)
- livemedia-creator: update templates for grub2-efi support (bcl@redhat.com)
- imgutils: fix umount retry handling (bcl@redhat.com)
- livemedia-creator: use stage2 instead of root (bcl@redhat.com)
- livemedia-creator: add location option (bcl@redhat.com)
- nm-connection-editor was moved to separate package (#849056)
  (rvykydal@redhat.com)

* Thu Aug 16 2012 Brian C. Lane <bcl@redhat.com> 18.14-1
- remove cleanup of some essential libraries (bcl@redhat.com)
- Mask the tmp.mount service to avoid tmpfs (jkeating@redhat.com)

* Wed Aug 15 2012 Brian C. Lane <bcl@redhat.com> 18.13-1
- Add a command line option to override the ARM platform. (dmarlin@redhat.com)
- Don't remove krb5-libs (#848227) (mgracik@redhat.com)
- Add grub2-efi support and Secure Boot shim support. (pjones@redhat.com)
- Fix GPT code to allocate space for /2/ tables. (pjones@redhat.com)
- Add platforms to the treeinfo for Beaker support. (dmarlin@redhat.com)
- add logging to lorax (bcl@redhat.com)
- move live templates into their own subdir of share (bcl@redhat.com)
- clean up command execution (bcl@redhat.com)
- livemedia-creator: cleanup logging a bit (bcl@redhat.com)

* Wed Jul 25 2012 Martin Gracik <mgracik@redhat.com> 18.12-1
- Add 'mvebu' to list of recognized ARM kernels. (dmarlin@redhat.com)
- Cleanup boot menus (#809663) (mgracik@redhat.com)
- Don't remove chvt from the install image (#838554) (mgracik@redhat.com)
- Add llvm-libs (#826351) (mgracik@redhat.com)

* Fri Jul 20 2012 Brian C. Lane <bcl@redhat.com> 18.11-1
- livemedia-creator: add some error checking (bcl@redhat.com)

* Tue Jul 10 2012 Martin Gracik <mgracik@redhat.com> 18.10-1
- Don't set a root= argument (wwoods@redhat.com)
  Resolves: rhbz#837208
- Don't remove the id tool (mgracik@redhat.com)
  Resolves: rhbz#836493
- Xauth is in bin (mgracik@redhat.com)
  Resolves: rhbz#837317
- Actually add plymouth to the initramfs (wwoods@redhat.com)
- don't use --prefix with dracut anymore (wwoods@redhat.com)
- newui requires checkisomd5 to run media check. (clumens@redhat.com)

* Thu Jun 21 2012 Martin Gracik <mgracik@redhat.com> 18.9-1
- Add initial support for ARM based systems (dmarlin) (mgracik@redhat.com)
- Add plymouth to the installer runtime (wwoods@redhat.com)
- add 'systemctl' command and use it in postinstall (wwoods@redhat.com)
- add dracut-shutdown.service (and its dependencies) (wwoods@redhat.com)
- leave pregenerated locale files (save RAM) (wwoods@redhat.com)
- runtime-cleanup: log broken symlinks being removed (wwoods@redhat.com)
- Add some documentation to LoraxTemplateRunner (wwoods@redhat.com)
- fix '-runcmd' and improve logging (wwoods@redhat.com)
- mkefiboot: add --debug (wwoods@redhat.com)
- pylorax.imgutils: add retry loop and "lazy" to umount() (wwoods@redhat.com)
- pylorax.imgutils: add debug logging (wwoods@redhat.com)
- pylorax: set up logging as recommended by logging module (wwoods@redhat.com)
- remove dmidecode (wwoods@redhat.com)
- clean up net-tools properly (wwoods@redhat.com)
- runtime-cleanup: correctly clean up kbd (wwoods@redhat.com)
- runtime-cleanup: correctly clean up iproute (wwoods@redhat.com)
- runtime-cleanup: drop a bunch of do-nothing removals (wwoods@redhat.com)
- Create missing /etc/fstab (wwoods@redhat.com)
- Fix systemd unit cleanup in runtime-postinstall (wwoods@redhat.com)
- Disable Alt+Tab in metacity (mgracik@redhat.com)
- Add pollcdrom module to dracut (bcl@redhat.com)

* Wed Jun 06 2012 Martin Gracik <mgracik@redhat.com> 18.8-1
- Check if selinux is enabled before getting the mode (mgracik@redhat.com)
- Add grub2 so that rescue is more useful (bcl@redhat.com)

* Mon Jun 04 2012 Martin Gracik <mgracik@redhat.com> 18.7-1
- Comment on why selinux needs to be in permissive or disabled
  (mgracik@redhat.com)
- Verify the yum transaction (mgracik@redhat.com)
- Do not remove shared-mime-info (#825960) (mgracik@redhat.com)
- Add a --required switch to installpkg (mgracik@redhat.com)
- livemedia-creator: Hook up arch option (bcl@redhat.com)
- livemedia-creator: Add appliance creation (bcl@redhat.com)
- livemedia-creator: handle failed mount for ami (bcl@redhat.com)

* Fri Jun 01 2012 Martin Gracik <mgracik@redhat.com> 18.6-1
- Fix the rpm call (mgracik@redhat.com)
- Use selinux python module to get enforcing mode (mgracik@redhat.com)

* Thu May 31 2012 Martin Gracik <mgracik@redhat.com> 18.5-1
- Don't remove sha256sum from the install image (mgracik@redhat.com)
- Check if selinux is not in Enforcing mode (#824835) (mgracik@redhat.com)
- Install rpcbind (#824835) (mgracik@redhat.com)
- Remove hfsplus-tools dependency (#818913) (mgracik@redhat.com)
- Copy mapping and magic to BOOTDIR on ppc (#815550) (mgracik@redhat.com)
- Automatic commit of package [lorax] release [18.4-1]. (mgracik@redhat.com)

* Fri May 25 2012 Martin Gracik <mgracik@redhat.com> 18.4-1
- Initialized to use tito.
- Use gz not bz2 for source
- remove 'loadkeys' stub (#804306)
- add name field to .treeinfo its a concatination of family and version
- Fix typo in help (#819476)
- include the new cmsfs-fuse interface
- linuxrc.s390 is dead in anaconda
- Add the ppc magic file
- Install proper branding packages from repo (#813969)
- Use --mac for isohybrid only if doing macboot images
- Add --nomacboot option
- Add packages needed for NTP functionality in the installer
- livemedia-creator: check kickstart for display modes (#819660)
- livemedia-creator: Removed unused ImageMount class
- livemedia-creator: cleanup after a crash
- livemedia-creator: start using /var/tmp instead of /tmp
- livemedia-creator: make libvirt module optional
- stop moving /run (#818918)

* Thu May 03 2012 Brian C. Lane <bcl@redhat.com> 18.3-1
- Added BCM4331 firmware (#817151) (mgracik)
- mkefiboot: Add support for disk label files (mjg)
- Add 'tmux' to runtime image (wwoods)
- Add /etc/sysctl.d/anaconda.conf, set kernel.printk=1 (#816022) (wwoods)
- reduce image size from 2GB to 1GB (wwoods)
- keep all filesystem tools (wwoods)
- Leave some of the grub2 utilities in the install image (#749323) (mgracik)
- add media check menu option (bcl)
- remove unneeded dracut bootargs (bcl)
- mkefiboot: Copy Mac bootloader, rather than linking it (mjg)
- Remove workdir if it was created by lorax (#807964) (mgracik)
- add gdisk to install image (#811083) (bcl)
- Don't use --allbut for xfsprogs cleanup (#804779) (mgracik)
- Log all removed files (mgracik)
- Add spice-vdagent to initrd (#804739) (mgracik)
- Add ntfs-3g to initrd (#804302) (mgracik)
- ntfs-3g now uses /usr/lib (#810039) (bcl)

* Fri Mar 30 2012 Brian C. Lane <bcl@redhat.com> 18.2-1
- Merge noloader commits from f17-branch (bcl)
- mkefiboot: Make Apple boot images appear in the startup preferences (mjg)
- add symlink from /mnt/install -> /run/install (wwoods)
- Don't trash all the initscripts 'fedora*' services (wwoods)
- remove anaconda-copy-ks.sh (wwoods)
- add anaconda dracut module (wwoods)
- runtime-postinstall: remove references to loader (wwoods)
- runtime-postinstall: remove keymap stuff (wwoods)
- Add the icfg package (#771733) (mgracik)
- Log the output of mkfs (#769928) (mgracik)
- Fix product name replacing in templates (#799919) (mgracik)
- Fix requires (mgracik)
- use cache outside the installtree (bcl)
- add iscsi-initiator-utils (#804522) (bcl)
- livemedia-creator: update TreeBuilder use for isolabel (bcl)

* Tue Mar 06 2012 Brian C. Lane <bcl@redhat.com> 18.1-1
- livemedia-creator: update README (bcl)
- example livemedia kickstart for ec2 (bcl)
- livemedia-creator: console=ttyS0 not /dev/ttyS0 (bcl)
- livemedia-creator: Add support for making ami images (bcl)
- Don't remove btrfs utils (#796511) (mgracik)
- Remove root and ip parameters from generic.prm (#796572) (mgracik)
- Check if the volume id is not longer than 32 chars (#786832) (mgracik)
- Add option to specify volume id on command line (#786834) (mgracik)
- Install nhn-nanum-gothic-fonts (#790266) (mgracik)
- Change the locale to C (#786833) (mgracik)
- iputils is small and required by dhclient-script (bcl)
- util-linux-ng is now util-linux (bcl)

* Mon Feb 20 2012 Brian C. Lane <bcl@redhat.com> 18.0-1
- use --prefix=/run/initramfs when building initramfs (wwoods)
- dhclient-script needs cut and arping (bcl)
- Fix missing CalledProcessError import (bcl)
- metacity now depends on gsettings-desktop-schemas (bcl)
- Add findiso to grub config (mjg)
- add memtest to the boot.iso for x86 (#787234) (bcl)
- Don't use mk-s390-cdboot (dhorak) (mgracik)
- Add dracut args to grub.conf (bcl)
- Change the squashfs image section in .treeinfo (mgracik)
- Add path to squashfs image to the treeinfo (mgracik)
- Add runtime basename variable to the template (mgracik)
- use internal implementation of the addrsize utility (dan)
- Make sure var/run is not a symlink on s390x (#787217) (mgracik)
- Create var/run/dbus directory on s390x (#787217) (mgracik)

* Wed Feb 08 2012 Brian C. Lane <bcl@redhat.com> 17.3-1
- keep convertfs.sh script in image (#787893) (bcl)
- Add dracut convertfs module (#787893) (bcl)
- fix templates to work with F17 usrmove (tflink)
- changing hfs to hfsplus so that the correct mkfs binary is called (tflink)
- Add luks, md and dm dracut args to bootloaders (bcl)
- update lorax and livemedia_creator to use isfinal (bcl)
- lorax: copy kickstarts into sysroot (#743135) (bcl)
- livemedia-creator: Mount iso if rootfs is LiveOS (bcl)
- Log output of failed command (mgracik)
- Add packages required for gtk3 and the new anaconda UI. (clumens)

* Thu Jan 12 2012 Martin Gracik <mgracik@redhat.com> 17.2-1
- Allow specifying buildarch on the command line (#771382) (mgracik)
- lorax: Don't touch /etc/mtab in cleanup (bcl)
- Update TODO and POLICY to reflect the current state of things (wwoods)
- consider %ghost files part of the filelists in templates (wwoods)
- lorax: Add option to exclude packages (bcl)
- dracut needs kbd directories (#769932) (bcl)
- better debug, handle relative output paths (bcl)

* Wed Dec 21 2011 Brian C. Lane <bcl@redhat.com> 17.1-1
- lorax: check for output directory early and quit (bcl)
- lorax: Add --proxy command (bcl)
- lorax: add --config option (bcl)
- Modify spec file for livemedia-creator (bcl)
- Add no-virt mode to livemedia-creator (bcl)
- Add livemedia-creator README and example ks (bcl)
- Add config files for live media (bcl)
- Add livemedia-creator (bcl)
- Allow a None to be passed as size to create_runtime (bcl)
- Add execWith utils from anaconda (bcl)
- Changes needed for livecd creation (bcl)
- dracut has moved to /usr/bin (bcl)

* Mon Oct 21 2011 Will Woods <wwoods@redhat.com> 17.0-1
- Merges the 'treebuilder' branch of lorax
- images are split into two parts again (initrd.img, LiveOS/squashfs.img)
- base memory use reduced to ~200M (was ~550M in F15, ~320MB in F16)
- initrd.img is now built by dracut
- booting now requires correct "root=live:..." argument
- boot.iso is EFI hybrid capable (copy iso to USB stick, boot from EFI)
- Better support for Apple EFI (now with custom boot icon!)
- new syslinux config (#734170)
- add fpaste to installer environment (#727842)
- rsyslog.conf: hardcode hostname for virtio forwarding (#744544)
- Use a predictable ISO Volume Label (#732298)
- syslinux-vesa-splash changed filename (#739345)
- don't create /etc/sysconfig/network (#733425)
- xauth and libXmu are needed for ssh -X (#731046)
- add libreport plugins (#729537), clean up libreport
- keep nss certs for libreport (#730438)
- keep ModemManager (#727946)
- keep vmmouse binaries (#723831)
- change isbeta to isfinal, default to isFinal=False (#723901)
- use pungi's installroot rather than making our own (#722481)
- keep ntfsresize around (#722711)
- replace cjkuni-uming-fonts with wqy-microhei-fonts (#709962)
- install all firmware packages (#703291, #705392)
- keep libmodman and libproxy (#701622)
- write the lorax verion in the .buildstamp (#689697)
- disable rsyslogd rate limiting on imuxsock (#696943)
- disable debuginfo package

* Wed Apr 13 2011 Martin Gracik <mgracik@redhat.com> 0.5-1
- Remove pungi patch
- Remove pseudo code
- Add a /bin/login shim for use only in the installation environment.
- Set the hostname from a config file, not programmatically.
- Add systemd and agetty to the installation environment.
- Specify "cpio -H newc" instead of "cpio -c".
- Provide shutdown on s390x (#694518)
- Fix arch specific requires in spec file
- Add s390 modules and do some cleanup of the template
- Generate ssh keys on s390
- Don't remove tr, needed for s390
- Do not check if we have all commands
- Change location of addrsize and mk-s390-cdboot
- Shutdown is in another location
- Do not skip broken packages
- Don't install network-manager-netbook
- Wait for subprocess to finish
- Have to call os.makedirs
- images dir already exists, we just need to set it
- Do not remove libassuan.
- The biarch is a function not an attribute
- Create images directory in outputtree
- Use gzip on ppc initrd
- Create efibootdir if doing efi images
- Get rid of create_gconf().
- gconf/metacity: have only one workspace.
- Add yum-langpacks yum plugin to anaconda environment (notting)
- Replace variables in yaboot.conf
- Add sparc specific packages
- Skip keymap creation on s390
- Copy shutdown and linuxrc.s390 on s390
- Add packages for s390
- Add support for sparc
- Use factory to get the image classes
- treeinfo has to be addressed as self.treeinfo
- Add support for s390
- Add the xen section to treeinfo on x86_64
- Fix magic and mapping paths
- Fix passing of prepboot and macboot arguments
- Small ppc fixes
- Check if the file we want to remove exists
- Install x86 specific packages only on x86
- Change the location of zImage.lds
- Added ppc specific packages
- memtest and efika.forth are in /boot
- Add support for ppc
- Minor sparc pseudo code changes
- Added sparc pseudo code (dgilmore)
- Added s390 and x86 pseudo code
- Added ppc pseudo code

* Mon Mar 14 2011 Martin Gracik <mgracik@redhat.com> 0.4-1
- Add the images-xen section to treeinfo on x86_64
- Print a message when no arguments given (#684463)
- Mako template returns unicode strings (#681003)
- The check option in options causes ValueError
- Disable all ctrl-alt-arrow metacity shortcuts
- Remove the locale-archive explicitly
- Use xz when compressing the initrd
- Keep the source files for locales and get rid of the binary form
- Add /sbin to $PATH (for the tty2 terminal)
- Create /var/run/dbus directory in installtree
- Add mkdir support to template
- gpart is present only on i386 arch (#672611)
- util-linux-ng changed to util-linux

* Mon Jan 24 2011 Martin Gracik <mgracik@redhat.com> 0.3-1
- Don't remove libmount package
- Don't create mtab symlink, already exists
- Exit with error if we have no lang-table
- Fix file logging
- Overwrite the /etc/shadow file
- Use [images-xen] section for PAE and xen kernels

* Fri Jan 14 2011 Martin Gracik <mgracik@redhat.com> 0.2-2
- Fix the gnome themes
- Add biosdevname package
- Edit .bash_history file
- Add the initrd and kernel lines to .treeinfo
- Don't remove the gamin package from installtree

* Wed Dec 01 2010 Martin Gracik <mgracik@redhat.com> 0.1-1
- First packaging of the new lorax tool.
