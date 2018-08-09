%define debug_package %{nil}

Name:           lorax-composer
Version:        19.7.21
Release:        1%{?dist}
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

# Install example blueprints from the test suite.
# This path MUST match the lorax-composer.service blueprint path.
mkdir -p $RPM_BUILD_ROOT/var/lib/lorax/composer/blueprints/
for bp in http-server.toml glusterfs.toml development.toml atlas.toml; do
    cp ./tests/pylorax/blueprints/$bp $RPM_BUILD_ROOT/var/lib/lorax/composer/blueprints/
done

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
%dir %attr(0771, root, weldr) %{_sharedstatedir}/lorax/composer/
%dir %attr(0771, root, weldr) %{_sharedstatedir}/lorax/composer/blueprints/
%attr(0771, weldr, weldr) %{_sharedstatedir}/lorax/composer/blueprints/*

%files -n composer-cli
%{_bindir}/composer-cli
%{python_sitelib}/composer/*
%{_sysconfdir}/bash_completion.d/composer-cli

%changelog
* Thu Aug 09 2018 Brian C. Lane <bcl@redhat.com> 19.7.21-1
- Move disklabel and UEFI support to compose.py (bcl)
- Fix more tests. (clumens)
- Change INVALID_NAME to INVALID_CHARS. (clumens)
- Update composer-cli for the new error return types. (clumens)
- Add default error IDs everywhere else. (clumens)
- Add error IDs to things that can go wrong when running a compose. (clumens)
- Add error IDs for common source-related errors. (clumens)
- Add error IDs for unknown modules and unknown projects. (clumens)
- Add error IDs for when an unknown commit is requested. (clumens)
- Add error IDs for when an unknown blueprint is requested. (clumens)
- Add error IDs for when an unknown build UUID is requested. (clumens)
- Add error IDs for bad state conditions. (clumens)
- Change the error return type for bad limit= and offset=. (clumens)
- Don't sort error messages. (clumens)
- Fix bash completion of compose info (bcl)
- Add + to the allowed API string character set (bcl)
- Add job_* timestamp support to compose status (bcl)
- Add a test for the pylorax.api.timestamp functions (bcl)
- Add etc/bash_completion.d/composer-cli (wwoods)
- composer-cli: clean up "list" commands (wwoods)
- Add input string checks to the branch and format arguments (bcl)
- Add a test for invalid characters in the API route (bcl)
- Return a JSON error instead of a 404 on certain malformed URLs. (clumens)
- Return an error if /modules/info doesn't return anything. (clumens)
- Update documentation (clumens).
  Resolves: rhbz#409
- Use constants instead of strings (clumens).
  Resolves: rhbz#409
- Write timestamps when important events happen during the compose (clumens).
  Resolves: rhbz#409
- Return multiple timestamps in API results (clumens).
  Resolves: rhbz#409
- Add a new timestamp.py file to the API directory (clumens).
  Resolves: rhbz#409
- Run as root/weldr by default. (clumens)
- Use the first enabled system repo for the test (bcl)
- Show more details when the system repo delete test fails (bcl)
- Add composer-cli function tests (bcl)
- Add a test library (bcl)
- composer-cli: Add support for Group to blueprints diff (bcl)
- Adjust the tests so they will pass on CentOS7 and RHEL7 (bcl)
- Update status.py to use new handle_api_result (bcl)
- Update sources.py to use new handle_api_result (bcl)
- Update projects.py to use new handle_api_result (bcl)
- Update modules.py to use new handle_api_result (bcl)
- Update compose.py to use new handle_api_result (bcl)
- Update blueprints.py to use new handle_api_result (bcl)
- Modify handle_api_result so it can be used in more places (bcl)
- composer-cli: Fix non-zero epoch in projets info (bcl)
- Fix help output on the compose subcommand. (clumens)
- Add timestamps to "compose-cli compose status" output. (clumens)
- And then add real output to the status command. (clumens)
- Add the beginnings of a new status subcommand. (clumens)

* Fri Jul 20 2018 Brian C. Lane <bcl@redhat.com> 19.7.20-1
- Document that you shouldn't run lorax-composer twice. (clumens)
- Add PIDFile to the .service file. (clumens)
- Log and exit on metadata update errors at startup (bcl)
- Check /projects responses for null values. (bcl)
- Clarify error message from /source/new (bcl)
- Download metadata when updating or adding new repos (bcl)

* Fri Jul 13 2018 Brian C. Lane <bcl@redhat.com> 19.7.19-1
- Support loading groups from the kickstart template files. (clumens)
- Add group-based tests. (clumens)
- Include groups in depsolving. (clumens)
- Add support for groups to blueprints. (clumens)
- Check the compose templates at startup (bcl)
- List individual package install failures (bcl)
- lorax-composer: Update documentation (bcl)
- Add help output to each subcommand. (clumens)
- Split the help output into its own module. (clumens)
- If the help subcommand is given, print the help output. (clumens)

* Wed Jun 27 2018 Brian C. Lane <bcl@redhat.com> 19.7.18-1
- Only include some of the test blueprints (bcl)
- Include example blueprints in the rpm (bcl)
- Make sure /run/weldr has correct ownership and permissions (bcl)

* Wed Jun 20 2018 Brian C. Lane <bcl@redhat.com> 19.7.17-1
- new lorax-composer package built with tito

* Tue Jun 19 2018 Brian C. Lane <bcl@redhat.com> - 19.7.16-2
- New lorax-composer only package
