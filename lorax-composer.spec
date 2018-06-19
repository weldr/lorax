%define debug_package %{nil}

Name:           lorax-composer
Version:        19.7.16
Release:        2%{?dist}
Summary:        Lorax Image Composer API Server

Group:          Applications/System
License:        GPLv2+
URL:            https://github.com/weldr/lorax
# To generate Source0 do:
# git clone https://github.com/weldr/lorax
# git checkout -b archive-branch lorax-%%{version}-%%{release}
# tito build --tgz
Source0:        %{name}-%{version}.tar.gz

BuildRequires: python2-devel
# For Sphinx documentation build
BuildRequires: python-sphinx yum python-mako pykickstart
BuildRequires: python-flask python-gobject libgit2-glib python2-pytoml python-semantic_version

Requires: lorax >= 19.7.16
Requires(pre): /usr/bin/getent
Requires(pre): /usr/sbin/groupadd
Requires(pre): /usr/sbin/useradd

Requires: python2-pytoml
Requires: python-semantic_version
Requires: libgit2
Requires: libgit2-glib
Requires: python-flask
Requires: python-gevent
Requires: anaconda-tui
Requires: qemu-img
Requires: tar

%{?systemd_requires}
BuildRequires: systemd

%description
lorax-composer provides a REST API for building images using lorax.

%package -n composer-cli
Summary: A command line tool for use with the lorax-composer API server

Requires: python-urllib3

%description -n composer-cli
A command line tool for use with the lorax-composer API server. Examine recipes,
build images, etc. from the command line.

%prep
%setup -q

%build
make docs

%install
rm -rf $RPM_BUILD_ROOT
make DESTDIR=$RPM_BUILD_ROOT mandir=%{_mandir} install

# Do Not Package the lorax files
rm -f $RPM_BUILD_ROOT/%{python_sitelib}/lorax-*.egg-info
rm -rf $RPM_BUILD_ROOT/%{python_sitelib}/pylorax/*py
rm -rf $RPM_BUILD_ROOT/%{python_sitelib}/pylorax/*py?
rm -rf $RPM_BUILD_ROOT/%{_datadir}/lorax/appliance
rm -rf $RPM_BUILD_ROOT/%{_datadir}/lorax/config_files
rm -rf $RPM_BUILD_ROOT/%{_datadir}/lorax/live
rm -rf $RPM_BUILD_ROOT/%{_datadir}/lorax/pxe-live
rm -rf $RPM_BUILD_ROOT/%{_mandir}/man1/*
rm -f $RPM_BUILD_ROOT/%{_datadir}/lorax/*tmpl
rm -f $RPM_BUILD_ROOT/%{_sbindir}/lorax
rm -f $RPM_BUILD_ROOT/%{_sbindir}/livemedia-creator
rm -f $RPM_BUILD_ROOT/%{_sbindir}/mkefiboot
rm -f $RPM_BUILD_ROOT/%{_bindir}/image-minimizer
rm -f $RPM_BUILD_ROOT/%{_bindir}/mk-s390-cdboot
rm -f $RPM_BUILD_ROOT/%{_sysconfdir}/lorax/lorax.conf

%pre
getent group weldr >/dev/null 2>&1 || groupadd -r weldr >/dev/null 2>&1 || :
getent passwd weldr >/dev/null 2>&1 || useradd -r -g weldr -d / -s /sbin/nologin -c "User for lorax-composer" weldr >/dev/null 2>&1 || :

%post
%systemd_post lorax-composer.service
%systemd_post lorax-composer.socket

%preun
%systemd_preun lorax-composer.service
%systemd_preun lorax-composer.socket

%postun
%systemd_postun_with_restart lorax-composer.service
%systemd_postun_with_restart lorax-composer.socket

%files
%defattr(-,root,root,-)
%doc COPYING AUTHORS
%doc docs/html
%dir %{_sysconfdir}/lorax/
%config(noreplace) %{_sysconfdir}/lorax/composer.conf
%{python_sitelib}/pylorax/api/*
%dir %{_datadir}/lorax/composer
%{_datadir}/lorax/composer/*
%{_sbindir}/lorax-composer
%{_unitdir}/lorax-composer.service
%{_unitdir}/lorax-composer.socket
%{_tmpfilesdir}/lorax-composer.conf

%files -n composer-cli
%{_bindir}/composer-cli
%{python_sitelib}/composer/*

%changelog
* Tue Jun 19 2018 Brian C. Lane <bcl@redhat.com> - 19.7.16-2
- New lorax-composer only package
