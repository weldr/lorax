Name:           lorax
Version:        0.2
Release:        2%{?dist}
Summary:        Tool for creating the anaconda install images

Group:          Applications/System
License:        GPLv2+
URL:            http://git.fedorahosted.org/git/?p=lorax.git
Source0:        https://fedorahosted.org/releases/l/o/%{name}/%{name}-%{version}.tar.bz2
BuildArch:      noarch

BuildRequires:  python-setuptools
Requires:       python2-devel
Requires:       python-mako
Requires:       gawk
Requires:       glibc-common
Requires:       cpio
Requires:       module-init-tools
Requires:       device-mapper
Requires:       findutils
Requires:       GConf2
Requires:       isomd5sum
Requires:       syslinux
Requires:       glibc
Requires:       util-linux-ng
Requires:       dosfstools
Requires:       genisoimage
Requires:       parted

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
* Fri Jan 14 2011 Martin Gracik <mgracik@redhat.com> 0.2-2
- Fix the gnome themes
- Add biosdevname package
- Edit .bash_history file
- Add the initrd and kernel lines to .treeinfo
- Don't remove the gamin package from installtree

* Wed Dec 01 2010 Martin Gracik <mgracik@redhat.com> 0.1-1
- First packaging of the new lorax tool.
