#version=DEVEL
# X Window System configuration information
xconfig  --startxonboot
# Keyboard layouts
keyboard 'us'

# System timezone
timezone US/Eastern
# System language
lang en_US.UTF-8
# Firewall configuration
firewall --enabled --service=mdns
url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/rawhide/Everything/x86_64/os/"
# Network information
network  --bootproto=dhcp --device=link --activate

# SELinux configuration
selinux --enforcing

# System services
services --disabled="sshd" --enabled="NetworkManager,ModemManager,livesys,livesys-late"

# livemedia-creator modifications.
shutdown
# System bootloader configuration
bootloader --location=none
# Clear blank disks or all existing partitions
clearpart --all --initlabel
rootpw rootme
# Disk partitioning information
reqpart
part / --size=6656

%post
# enable tmpfs for /tmp
systemctl enable tmp.mount

# make it so that we don't do writing to the overlay for things which
# are just tmpdirs/caches
# note https://bugzilla.redhat.com/show_bug.cgi?id=1135475
cat >> /etc/fstab << EOF
vartmp   /var/tmp    tmpfs   defaults   0  0
EOF

# work around for poor key import UI in PackageKit
rm -f /var/lib/rpm/__db*
releasever=$(rpm -q --qf '%{version}\n' --whatprovides system-release)
basearch=$(uname -i)
rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-$releasever-$basearch
echo "Packages within this LiveCD"
rpm -qa --qf '%{size}\t%{name}-%{version}-%{release}.%{arch}\n' |sort -rn
# Note that running rpm recreates the rpm db files which aren't needed or wanted
rm -f /var/lib/rpm/__db*

# go ahead and pre-make the man -k cache (#455968)
/usr/bin/mandb

# make sure there aren't core files lying around
rm -f /core*

# remove random seed, the newly installed instance should make it's own
rm -f /var/lib/systemd/random-seed

# convince readahead not to collect
# FIXME: for systemd

echo 'File created by kickstart. See systemd-update-done.service(8).' \
    | tee /etc/.updated >/var/.updated

# Remove the rescue kernel and image to save space
# Installation will recreate these on the target
rm -f /boot/*-rescue*

# Remove machine-id on pre generated images
rm -f /etc/machine-id
touch /etc/machine-id

%end

# Architecture specific packages
# The bootloader package requirements are different, and workstation-product-environment
# is only available on x86_64
%pre
PKGS=/tmp/arch-packages.ks
echo > $PKGS
ARCH=$(uname -m)
case $ARCH in
    x86_64)
        echo "%packages" >> $PKGS
        echo "@^workstation-product-environment" >> $PKGS
        echo "shim" >> $PKGS
        echo "shim-ia32" >> $PKGS
        echo "grub2" >> $PKGS
        echo "grub2-efi" >> $PKGS
        echo "grub2-efi-ia32" >> $PKGS
        echo "grub2-efi-*-cdboot" >> $PKGS
        echo "efibootmgr" >> $PKGS
        echo "%end" >> $PKGS
    ;;
    aarch64)
        echo "%packages" >> $PKGS
        echo "efibootmgr" >> $PKGS
        echo "grub2-efi-aa64-cdboot" >> $PKGS
        echo "shim-aa64" >> $PKGS
        echo "%end" >> $PKGS
    ;;
    ppc64le)
        echo "%packages" >> $PKGS
        echo "powerpc-utils" >> $PKGS
        echo "grub2-tools" >> $PKGS
        echo "grub2-tools-minimal" >> $PKGS
        echo "grub2-tools-extra" >> $PKGS
        echo "grub2-ppc64le" >> $PKGS
        echo "%end" >> $PKGS
    ;;
    s390x)
        echo "%packages" >> $PKGS
        echo "s390utils-base" >> $PKGS
        echo "%end" >> $PKGS
    ;;
esac
%end

%include /tmp/arch-packages.ks

%packages
# Use https://pagure.io/livesys-scripts to configure the system
livesys-scripts

@anaconda-tools
aajohan-comfortaa-fonts
anaconda
anaconda-install-env-deps
anaconda-live
dracut-config-generic
dracut-live
glibc-all-langpacks
kernel
# Make sure that DNF doesn't pull in debug kernel to satisfy kmod() requires
kernel-modules
kernel-modules-extra
-@dial-up
-@input-methods
-@standard
-gfs2-utils
-gnome-boxes
%end
