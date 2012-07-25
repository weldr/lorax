%define debug_package %{nil}

Name:           lorax
Version:        18.12
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

%ifarch %{ix86} x86_64
Requires:       syslinux >= 4.02-5
%endif

%ifarch %{sparc}
Requires:       silo
%endif

%ifarch ppc ppc64
Requires:       kernel-bootwrapper
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
make DESTDIR=$RPM_BUILD_ROOT install

%files
%defattr(-,root,root,-)
%doc COPYING AUTHORS README.livemedia-creator
%{python_sitelib}/pylorax
%{python_sitelib}/*.egg-info
%{_sbindir}/lorax
%{_sbindir}/mkefiboot
%{_sbindir}/livemedia-creator
%dir %{_sysconfdir}/lorax
%config(noreplace) %{_sysconfdir}/lorax/lorax.conf
%dir %{_datadir}/lorax
%{_datadir}/lorax/*


%changelog
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
