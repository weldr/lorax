%define debug_package %{nil}

Name:           lorax
Version:        19.6.33
Release:        1%{?dist}
Summary:        Tool for creating the anaconda install images

Group:          Applications/System
License:        GPLv2+
URL:            http://git.fedorahosted.org/git/?p=lorax.git
Source0:        https://fedorahosted.org/releases/l/o/%{name}/%{name}-%{version}.tar.gz

BuildRequires:  python2-devel

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
Requires:       libselinux-python
Requires:       module-init-tools
Requires:       parted
Requires:       python-mako
Requires:       squashfs-tools >= 4.2
Requires:       util-linux
Requires:       xz
Requires:       yum
Requires:       pykickstart
Requires:       dracut >= 030

%if 0%{?fedora}
# Fedora specific deps
Requires:       fedup-dracut
Requires:       fedup-dracut-plymouth
%endif

%if 0%{?el7}
# RHEL 7 specific deps
Requires:       redhat-upgrade-dracut
Requires:       redhat-upgrade-dracut-plymouth
%endif

%ifarch %{ix86} x86_64
Requires:       syslinux >= 4.02-5
%endif

%ifarch ppc ppc64
Requires:       kernel-bootwrapper
Requires:       grub2
Requires:       grub2-tools
%endif

%ifarch s390 s390x
Requires:       openssh
%endif

%description
Lorax is a tool for creating the anaconda install images.

It also includes livemedia-creator which is used to create bootable livemedia,
including live isos and disk images. It can use libvirtd for the install, or
Anaconda's image install feature.

%prep
%setup -q

%build

%install
rm -rf $RPM_BUILD_ROOT
make DESTDIR=$RPM_BUILD_ROOT mandir=%{_mandir} install

%files
%defattr(-,root,root,-)
%doc COPYING AUTHORS README.livemedia-creator
%doc docs/*ks
%{python_sitelib}/pylorax
%{python_sitelib}/*.egg-info
%{_sbindir}/lorax
%{_sbindir}/mkefiboot
%{_sbindir}/livemedia-creator
%dir %{_sysconfdir}/lorax
%config(noreplace) %{_sysconfdir}/lorax/lorax.conf
%dir %{_datadir}/lorax
%{_datadir}/lorax/*
%{_mandir}/man1/*.1*

%changelog
* Thu Aug 28 2014 Brian C. Lane <bcl@redhat.com> 19.6.33-1
- livemedia-creator: Update ppc64 live to use grub2 (bcl@redhat.com)

* Tue Aug 19 2014 Brian C. Lane <bcl@redhat.com> 19.6.32-1
- Yaboot to grub2 conversion cleanup. (dwa@redhat.com)
  Related: rhbz#1131199
- GRUB2 as the ISO boot loader for POWER arch (#1131199) (pfsmorigo@br.ibm.com)
  Resolves: rhbz#1131199
- Revert "Require 32bit glibc on ppc64" (bcl@redhat.com)
  Related: rhbz#1131199

* Fri Aug 15 2014 Brian C. Lane <bcl@redhat.com> 19.6.31-1
- Add efibootmgr to installpkg list for aarch64. (dmarlin@redhat.com)
  Resolves: rhbz#1130366
* Tue Aug 12 2014 Brian C. Lane <bcl@redhat.com> 19.6.30-1
- livemedia-creator: Cleanup temp yum files (bcl@redhat.com)
  Resolves: rhbz#1073502
- Require 32bit glibc on ppc64 (bcl@redhat.com)
  Resolves: rhbz#1105054
- Add xfsdump and remove extra files from xfsprogs (bcl@redhat.com)
  Resolves: rhbz#1118654
- Add ipmitool and drivers (bcl@redhat.com)
  Resolves: rhbz#1126009
- Update grub2-efi.cfg for aarch64 to more closely match x86 (dmarlin@redhat.com)
  Resolves: rhbz#1089418
* Fri Aug 08 2014 Brian C. Lane <bcl@redhat.com> 19.6.29-1
- utf-8 encode yum actions before displaying them (#1072362) (bcl@redhat.com)
- Use BOOTAA64.efi for AARCH64 bootloader filename (#1080113) (bcl@redhat.com)
- Drop devicetree from aarch64 grub2-efi.cfg (#1089418) (bcl@redhat.com)
- livemedia-creator: Add ppc64 live creation support (#1102318)
  (bcl@redhat.com)
- runtime-install: Add rpm-ostree (walters@verbum.org)

* Wed Apr 23 2014 Brian C. Lane <bcl@redhat.com> 19.6.28-1
- Install rdma so that dracut will use it along with libmlx4 (bcl)
  Resolves: rhbz#1089564

* Thu Apr 03 2014 Brian C. Lane <bcl@redhat.com> 19.6.27-1
- Stop removing curl after adding it (#1083205) (bcl@redhat.com)

* Fri Feb 28 2014 Brian C. Lane <bcl@redhat.com> 19.6.26-1
- Use string for releasever not int (bcl@redhat.com)
  Related: rhbz#1067746
- Make lorax's installation of lockdown.efi conditional on its existence. (pjones@redhat.com)
  Resolves: rhbz#1071380
* Wed Feb 26 2014 Brian C. Lane <bcl@redhat.com> 19.6.25-1
- createrepo is needed by driver disks (bcl@redhat.com)
  Related: rhbz#1016004
* Tue Feb 25 2014 Brian C. Lane <bcl@redhat.com> 19.6.24-1
- Improve aarch64 UEFI support (dmarlin@redhat.com)
  Resolves: rhbz#1067671
* Fri Feb 21 2014 Brian C. Lane <bcl@redhat.com> 19.6.23-1
- livemedia-creator: Set the product and release version env variables (bcl@redhat.com)
  Resolves: rhbz#1067746
- Remove unneeded images from the product -logos (bcl@redhat.com)
  Resolves: rhbz#1068721

* Tue Feb 18 2014 Brian C. Lane <bcl@redhat.com> 19.6.22-1
- fedora- services are named rhel- (#1066118) (bcl@redhat.com)
- Remove unneeded packages from runtime-install (#1065557) (bcl@redhat.com)

* Thu Feb 13 2014 Brian C. Lane <bcl@redhat.com> 19.6.21-1
- Check initrd size on ppc64 and warn (#1060691) (bcl@redhat.com)
- Remove drivers and modules on ppc64 (#1060691) (bcl@redhat.com)

* Wed Feb 12 2014 Brian C. Lane <bcl@redhat.com> 19.6.20-1
- Include mesa-dri-drivers (#1053940) (bcl@redhat.com)

* Tue Feb 11 2014 Brian C. Lane <bcl@redhat.com> 19.6.19-1
- livemedia-creator: virt-image needs ram in MiB not KiB (#1061773)
  (bcl@redhat.com)
- Include all the example kickstarts (#1019728) (bcl@redhat.com)

* Wed Feb 05 2014 Brian C. Lane <bcl@redhat.com> 19.6.18-1
- Remove floppy and scsi_debug from initrd (#1060691) (bcl@redhat.com)

* Fri Jan 31 2014 Brian C. Lane <bcl@redhat.com> 19.6.17-1
- Don't activate default auto connections after switchroot (#1012511)
  (rvykydal@redhat.com)
  Related: rhbz#1012511
* Fri Jan 24 2014 Brian C. Lane <bcl@redhat.com> 19.6.16-1
- Activate anaconda-shell@.service on switch to empty VT (#980062)
  (wwoods@redhat.com)
- flush data to disk after mkfsimage (#1052175) (bcl@redhat.com)

* Tue Dec 17 2013 Brian C. Lane <bcl@redhat.com> 19.6.15-1
- Add initial 64-bit ARM (aarch64) support (#1034432) (dmarlin@redhat.com)

* Mon Dec 16 2013 Brian C. Lane <bcl@redhat.com> 19.6.14-1
- s390 switch to generic condev (#1042765) (bcl@redhat.com)

* Fri Nov 15 2013 Brian C. Lane <bcl@redhat.com> 19.6.13-1
- Add SB lockdown to EFI grub menu (#1030495) (bcl@redhat.com)
  Resolves: rhbz#1030495

* Thu Nov 14 2013 Brian C. Lane <bcl@redhat.com> 19.6.12-1
- Include partx (#1022899) (bcl@redhat.com)
  Resolves: rhbz#1022899

* Thu Nov 14 2013 Brian C. Lane <bcl@redhat.com> 19.6.11-1
- Create upgrade.img using redhat-upgrade-dracut (dshea@redhat.com)

* Mon Nov 11 2013 Vratislav Podzimek <vpodzime@redhat.com> 19.6.10-1
- Do not remove libdaemon from the runtime environment (vpodzime)
  Resolves: rhbz#1028938

* Thu Nov 07 2013 Brian C. Lane <bcl@redhat.com> 19.6.9-1
- Install subscription-manager (#1026304) (bcl@redhat.com)
  Resolves: rhbz#1026304
* Fri Nov 01 2013 Brian C. Lane <bcl@redhat.com> 19.6.8-1
- Set UEFI defaults to match BIOS (#1021451,#1021446) (bcl@redhat.com)
  Resolves: rhbz#1021451
  Resolves: rhbz#1021446
- livemedia-creator: Set default name to Red Hat Enterprise Linux 7 (#1002027)
  (bcl@redhat.com)
  Resolves: rhbz#1002027
- livemedia-creator: Add minimal disk example kickstart (#1019728)
  (bcl@redhat.com)
  Resolves: rhbz#1019728

* Thu Oct 17 2013 Brian C. Lane <bcl@redhat.com> 19.6.7-1
- Keep virtio_console module (#750231) (bcl@redhat.com)

* Mon Oct 07 2013 Brian C. Lane <bcl@redhat.com> 19.6.6-1
- livemedia-creator: Update minimal packages in README (#1003078) (bcl@redhat.com)
- macboot defaults to no on rhel7 (#1012529) (bcl@redhat.com)
- Add macboot option (#1012529) (bcl@redhat.com)

* Wed Sep 25 2013 Brian C. Lane <bcl@redhat.com> 19.6.5-1
- drop dracut args from config files (#1008054) (bcl@redhat.com)

* Fri Sep 20 2013 Brian C. Lane <bcl@redhat.com> 19.6.4-1
- livemedia-creator: Fix gcdx64.efi path to work for other distros than Fedora
  (#1003078) (bcl@redhat.com)
- livemedia-creator: Update example kickstart for rhel7 (#922064)
  (bcl@redhat.com)

* Fri Aug 23 2013 Brian C. Lane <bcl@redhat.com> 19.6.3-1
- Keep liblzo2.* (#997976) (dshea@redhat.com)

* Thu Aug 01 2013 Brian C. Lane <bcl@redhat.com> 19.6.2-1
- dracut-nohostonly and dracut-norescue got renamed for dracut >= 030 (#990305)
  (harald@redhat.com)
- Don't remove xkeyboard-config message files (#989757) (dshea@redhat.com)

* Fri Jul 26 2013 Brian C. Lane <bcl@redhat.com> 19.6.1-1
- remove yum-plugin-fastestmirror (#876135) (bcl@redhat.com)

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
