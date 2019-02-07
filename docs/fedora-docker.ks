# Minimal Disk Image

# Use network installation
url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/rawhide/Everything/x86_64/os/"

# Root password
rootpw --plaintext replace-this-pw
# Network information
network  --bootproto=dhcp --activate
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
bootloader --disabled
# Partition clearing information
clearpart --all --initlabel
# Disk partitioning information
part / --fstype="ext4" --size=3000

%post
# Remove random-seed
rm /var/lib/systemd/random-seed
%end

%packages --nocore --instLangs en
httpd
-kernel
%end
