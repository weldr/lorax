%define debug_package %{nil}

Name:           lorax
Version:        16.4.4
Release:        1%{?dist}
Summary:        Tool for creating the anaconda install images

Group:          Applications/System
License:        GPLv2+
URL:            http://git.fedorahosted.org/git/?p=lorax.git
Source0:        https://fedorahosted.org/releases/l/o/%{name}/%{name}-%{version}.tar.bz2

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
Requires:       util-linux-ng
Requires:       dosfstools
Requires:       genisoimage
Requires:       parted
Requires:       gzip
Requires:       xz

%ifarch %{ix86} x86_64
Requires:       syslinux
%endif

%ifarch %{sparc}
Requires:       silo
%endif

%description
Lorax is a tool for creating the anaconda install images.

%prep
%setup -q

%build

%install
rm -rf $RPM_BUILD_ROOT
make DESTDIR=$RPM_BUILD_ROOT install

%files
%defattr(-,root,root,-)
%doc COPYING AUTHORS
%{python_sitelib}/pylorax
%{python_sitelib}/*.egg-info
%{_sbindir}/lorax
%dir %{_sysconfdir}/lorax
%config(noreplace) %{_sysconfdir}/lorax/lorax.conf
%dir %{_datadir}/lorax
%{_datadir}/lorax/*


%changelog
* Mon Sep 19 2011 Martin Gracik <mgracik@redhat.com> 16.4.4-1
- syslinux-vesa-splash changed filename (#739345)

* Fri Sep 16 2011 Martin Gracik <mgracik@redhat.com> 16.4.3-1
- Do not create the sysconfig/network file (#733425)
- New syslinux theme (#734170)

* Thu Aug 25 2011 Martin Gracik <mgracik@redhat.com> 16.4.2-1
- Do not remove ModemManager files (#727946)
- Raise an exception if isohybrid cannot be run on x86
- Use --noprefix when calling dracut
- Do not remove the fedora-release packages
- Remove fedora-storage-init so it can't start raid/lvm. (#729640) (dlehman)

* Mon Aug 15 2011 Martin Gracik <mgracik@redhat.com> 16.4.1-1
- Do not remove nss certificates (#730438)
- Remove dogtail from the image, as it's blocking tree composition. (clumens)
- Add libreport required packages (#729537)

* Tue Jul 26 2011 Martin Gracik <mgracik@redhat.com> 16.4-1
- Add nss libraries to the image.

* Tue Jul 26 2011 Martin Gracik <mgracik@redhat.com> 16.3-1
- Remove the sysvinit-tools removals from the template
- Do not remove vmmouse binaries (#723831)

* Tue Jul 26 2011 Martin Gracik <mgracik@redhat.com> 16.2-1
- Change IsBeta to IsFinal

* Thu Jul 21 2011 Martin Gracik <mgracik@redhat.com> 16.1-1
- Default to isBeta (#723901)

* Tue Jul 19 2011 Martin Gracik <mgracik@redhat.com> 16.0-1
- Prepend dracut to the temporary initramfs directory (#722999)
- Don't change the installroot (#722481)
- Do not remove ntfsprogs (#722711)
- Create dracut initramfs for each kernel (#722466)
- Change cjkuni-uming fonts for wgy-microhei (#709962)
- Remove check for required commands
- Remove outputtree.py
- Remove unused code

* Fri Jun 24 2011 Martin Gracik <mgracik@redhat.com> 0.7-1
- Use bcj filter for compressing squashfs ramdisk
- Add 'squashfs' compression type
- refactor: split make_initramfs_runtime out of compress()
- refactor: rename "compression speed" -> "compression args"
- Install all firmware packages (#705392)
- Use initrd.addrsize, not initrd_addrsize (#703862)
- Do not remove libmodman (#701622)
- Add firmware for Intel Wireless WiFi Link 6030 Adapters (#703291)
- Do not remove libproxy (#701622)
- Use process-specific name for dm devices.

* Tue May 03 2011 Martin Gracik <mgracik@redhat.com> 0.6-3
- Disable debuginfo package

* Mon May 02 2011 Martin Gracik <mgracik@redhat.com> 0.6-1
- Disable rsyslogd rate limiting on imuxsock.
- Use crc32 check when compressing with xz
- Allow compression type be specified in lorax.conf
- Use xz and gzip commands instead of libraries
- Add the udf module to the image.
- Preserve anaconda's /usr/bin so anaconda-cleanup is in the image.
- Use arch macros in the lorax.spec
- use reqs not regs for files to backup (dgilmore)
- Reflect changes made in ntfs-3g and ntfsprogs packages (#696706)
- getkeymaps resides in /usr/libexec/anaconda
- workdir is a local variable, not a class attribute
- Add sparcv9 to arch map
- Change the location of *.b files on sparc
- Change BuildRequires to python2-devel

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
