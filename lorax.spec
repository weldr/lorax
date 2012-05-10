%define debug_package %{nil}

Name:           lorax
Version:        17.22
Release:        1%{?dist}
Summary:        Tool for creating the anaconda install images

Group:          Applications/System
License:        GPLv2+
URL:            http://git.fedorahosted.org/git/?p=lorax.git
Source0:        https://fedorahosted.org/releases/l/o/%{name}/%{name}-%{version}.tar.gz

BuildRequires:  python2-devel
Requires:       python-mako
Requires:       gawk
Requires:       glibc-common
Requires:       cpio
Requires:       module-init-tools
Requires:       device-mapper
Requires:       findutils
Requires:       GConf2
Requires:       isomd5sum
Requires:       glibc
Requires:       util-linux
Requires:       dosfstools
Requires:       hfsplus-tools
Requires:       genisoimage
Requires:       parted
Requires:       gzip
Requires:       xz
Requires:       squashfs-tools >= 4.2
Requires:       e2fsprogs
Requires:       yum

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
* Thu May 10 2012 Martin Gracik <mgracik@redhat.com> 17.22-1
- Rebuild. (mgracik@redhat.com)

* Thu May 10 2012 Martin Gracik <mgracik@redhat.com> 17.21-1
- new package built with tito

* Wed May 09 2012 Martin Gracik <mgracik@redhat.com> 17.19-1
- Add nhn-nanum-fonts
  Resolves: rhbz#818127
- add name field to .treeinfo its a concatination of family and version (dgilmore)
- include the new cmsfs-fuse interface (dhorak)
- Fix typo in help
  Resolves: rhbz#819476

* Wed May 09 2012 Daniel Mach <dmach@redhat.com> 17.18-2
- Disable macboot.img on RHEL

* Tue May 08 2012 Brian C. Lane <bcl@redhat.com> 17.18-1
- stop moving /run (#818918) (bcl)

* Thu May 03 2012 Brian C. Lane <bcl@redhat.com> 17.17-1
- Added BCM4331 firmware (#817151) (mgracik)
- mkefiboot: Add support for disk label files (mjg)
- Include /usr/bin/ntfsinfo. (#816664) (dlehman)
- Add /etc/sysctl.d/anaconda.conf, set kernel.printk=1 (#816022) (wwoods)

* Mon Apr 23 2012 Brian C. Lane <bcl@redhat.com> 17.16-1
- add media check menu option (bcl)
- remove unneeded dracut bootargs (bcl)
- remove 'loadkeys' stub (#804306) (wwoods)

* Fri Apr 20 2012 Martin Gracik <mgracik@redhat.com> 17.15-1
- Don't remove dosfstools (#806648)
- Leave some of the grub2 utilities in the install image (#749323)
- mkefiboot: Copy Mac bootloader, rather than linking it (mjg)
- Remove workdir if it was created by lorax (#807964)
- add gdisk to install image (#811083) (bcl)

* Wed Apr 11 2012 Martin Gracik <mgracik@redhat.com> 17.14-1
- Don't use --allbut for xfsprogs cleanup (#804779)
- Log all removed files
- Add spice-vdagent to initrd (#804739)
- Add ntfs-3g to initrd (#804302)
- ntfs-3g now uses /usr/lib (#810039) (bcl)

* Wed Mar 28 2012 Brian C. Lane <bcl@redhat.com> 17.13-1
- add iscsi-initiator-utils (#804522) (bcl)
- use cache outside the installtree (bcl)

* Wed Mar 21 2012 Brian C. Lane <bcl@redhat.com> 17.12-1
- mkefiboot: Make Apple boot images appear in the startup preferences (mjg)
- add symlink from /mnt/install -> /run/install (wwoods)

* Fri Mar 16 2012 Brian C. Lane <bcl@redhat.com> 17.10-1
- merge noloader patches
- Don't trash all the initscripts 'fedora*' services (wwoods)
- remove anaconda-copy-ks.sh (wwoods)
- add anaconda dracut module (wwoods)
- runtime-postinstall: remove references to loader (wwoods)
- runtime-postinstall: remove keymap stuff (wwoods)
- Add the icfg package (#771733) (mgracik)
- Log the output of mkfs (#769928) (mgracik)
- livemedia-creator: update TreeBuilder use for isolabel (bcl)

* Wed Mar 07 2012 Martin Gracik <mgracik@redhat.com> 17.9-1
- Fix product name replacing in templates
  Resolves: rhbz#799919

* Tue Mar 06 2012 Brian C. Lane <bcl@redhat.com> 17.8-1
- livemedia-creator: update README (bcl)
- example livemedia kickstart for ec2 (bcl)
- livemedia-creator: console=ttyS0 not /dev/ttyS0 (bcl)
- livemedia-creator: Add support for making ami images (bcl)

* Tue Feb 28 2012 Martin Gracik <mgracik@redhat.com> 17.7-1
- Don't remove btrfs utils (#796511)
- Remove root and ip parameters from generic.prm (#796572)
- Check if the volume id is not longer than 32 chars (#786832)
- Add option to specify volume id on command line (#786834)
- Install nhn-nanum-gothic-fonts (#790266)
- Change the locale to C (#786833)
- Don't use mk-s390-cdboot (dhorak)
- use internal implementation of the addrsize utility
- Make sure var/run is not a symlink on s390x (#787217)
- Create var/run/dbus directory on s390x (#787217)
- iputils is small and required by dhclient-script
- missing version bump in specfile

* Mon Feb 20 2012 Brian C. Lane <bcl@redhat.com> 17.6-1
- use --prefix=/run/initramfs when building initramfs (wwoods)
- dhclient-script needs cut and arping (bcl)
- Fix missing CalledProcessError import (bcl)

* Wed Feb 15 2012 Brian C. Lane <bcl@redhat.com> 17.5-1
- metacity now depends on gsettings-desktop-schemas (bcl)
- Add findiso to grub config (mjg)

* Mon Feb 13 2012 Brian C. Lane <bcl@redhat.com> 17.4-1
- Change the squashfs image section in .treeinfo (mgracik)
- Add path to squashfs image to the treeinfo (mgracik)
- Add runtime basename variable to the template (mgracik)
- add memtest to the boot.iso for x86 (#787234) (bcl)
- Add dracut args to grub.conf (bcl)

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
