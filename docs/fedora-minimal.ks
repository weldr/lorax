# Minimal Disk Image
#
sshpw --username=root --plaintext randOmStrinGhERE
# Firewall configuration
firewall --enabled
# Use network installation
url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/rawhide/Everything/x86_64/os/"
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
# Installation logging level
logging --level=info
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

%packages
@core
kernel
# Make sure that DNF doesn't pull in debug kernel to satisfy kmod() requires
kernel-modules
kernel-modules-extra

memtest86+
grub2-efi
grub2
shim
syslinux
-dracut-config-rescue

# dracut needs these included
dracut-network
tar
%end
