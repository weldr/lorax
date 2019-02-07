# Minimal Disk Image -- Example of image-minimizer usage in %post
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

# lorax for image-minimizer
lorax
%end

#
# Use the image-minimizer to remove some packages and dirs
#
%post --interpreter=image-minimizer --nochroot


# Kernel modules minimization
# Drop many filesystems
drop /lib/modules/*/kernel/fs
keep /lib/modules/*/kernel/fs/ext*
keep /lib/modules/*/kernel/fs/mbcache*
keep /lib/modules/*/kernel/fs/squashfs
keep /lib/modules/*/kernel/fs/jbd*
keep /lib/modules/*/kernel/fs/btrfs
keep /lib/modules/*/kernel/fs/cifs*
keep /lib/modules/*/kernel/fs/fat
keep /lib/modules/*/kernel/fs/nfs
keep /lib/modules/*/kernel/fs/nfs_common
keep /lib/modules/*/kernel/fs/fscache
keep /lib/modules/*/kernel/fs/lockd
keep /lib/modules/*/kernel/fs/nls/nls_utf8.ko
keep /lib/modules/*/kernel/fs/configfs/configfs.ko
keep /lib/modules/*/kernel/fs/fuse
keep /lib/modules/*/kernel/fs/isofs
# No sound
drop /lib/modules/*/kernel/sound


# Drop some unused rpms, without dropping dependencies
droprpm checkpolicy
droprpm dmraid-events
droprpm gamin
droprpm gnupg2
droprpm linux-atm-libs
droprpm make
droprpm mtools
droprpm mysql-libs
droprpm perl
droprpm perl-Module-Pluggable
droprpm perl-Net-Telnet
droprpm perl-PathTools
droprpm perl-Pod-Escapes
droprpm perl-Pod-Simple
droprpm perl-Scalar-List-Utils
droprpm perl-hivex
droprpm perl-macros
droprpm sgpio
droprpm syslinux
droprpm system-config-firewall-base
droprpm usermode
# Not needed after image-minimizer is done
droprpm lorax
%end
