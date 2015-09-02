# Minimal Disk Image
#
# Firewall configuration
firewall --enabled
# Use network installation
url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/rawhide/x86_64/os/"

# Root password
rootpw --plaintext replace-this-pw
# Network information
network  --bootproto=dhcp --activate
# System authorization information
auth --useshadow --enablemd5
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
# Clear the Master Boot Record
zerombr
# Partition clearing information
clearpart --all
# Disk partitioning information
part / --fstype="ext4" --size=3000

%post
# Remove random-seed
rm /var/lib/systemd/random-seed
%end

%packages
@core
kernel
memtest86+
grub2-efi
grub2
shim
syslinux
-dracut-config-rescue

# dracut needs these included
dracut-network
tar

# Openstack support
cloud-utils-growpart
cloud-init

%end
