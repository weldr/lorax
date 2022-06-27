# Minimal Disk Image
#
sshpw --username=root --plaintext randOmStrinGhERE
# Firewall configuration
firewall --enabled
# Use network installation
url --url="http://URL-TO-BASEOS"
repo --name=appstream --baseurl="http://URL-TO-APPSTREAM/"
# Network information
network  --bootproto=dhcp --device=link --activate

# Root password
rootpw --plaintext removethispw
# System keyboard
keyboard --xlayouts=us --vckeymap=us
# System language
lang en_US.UTF-8
# SELinux configuration
selinux --enforcing
# Shutdown after installation
shutdown
# System timezone
timezone  US/Eastern
# System bootloader configuration
bootloader --location=mbr
# Partition clearing information
clearpart --all --initlabel
# Disk partitioning information
reqpart
part / --fstype="ext4" --size=4000
part swap --size=1000

%post
# Remove root password
passwd -d root > /dev/null

# Remove random-seed
rm /var/lib/systemd/random-seed
%end

# Architecture specific packages
# The bootloader package requirements are different
%pre
PKGS=/tmp/arch-packages.ks
echo > $PKGS
ARCH=$(uname -m)
case $ARCH in
    x86_64)
        echo "%packages" >> $PKGS
        echo "shim" >> $PKGS
        echo "grub2" >> $PKGS
        echo "grub2-efi" >> $PKGS
        echo "efibootmgr" >> $PKGS
        echo "%end" >> $PKGS
    ;;
    aarch64)
        echo "%packages" >> $PKGS
        echo "efibootmgr" >> $PKGS
        echo "grub2-efi" >> $PKGS
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
@core
kernel
# Make sure that DNF doesn't pull in debug kernel to satisfy kmod() requires
kernel-modules
kernel-modules-extra

# dracut needs these included
dracut-network
tar
%end
