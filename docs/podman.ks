# Minimal tar Image

# Use network installation
url --url="http://URL-TO-BASEOS"
repo --name=appstream --baseurl="http://URL-TO-APPSTREAM/"

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

%packages --nocore --inst-langs en
httpd
-kernel

# Needed for selinux --enforcing and setfiles
selinux-policy-targeted
%end
