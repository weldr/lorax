# Minimal Vagrant Disk Image
#

# Firewall configuration
firewall --enabled
# Use network installation
url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/rawhide/Everything/x86_64/os/"
# Network information
network  --bootproto=dhcp --activate

# Root account is locked, access via sudo from vagrant user
rootpw --lock

# Vagrant user with the INSECURE default public key
user --name=vagrant
sshkey --username=vagrant "ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEA6NF8iallvQVp22WDkTkyrtvp9eWW6A8YVr+kz4TjGYe7gHzIw+niNltGEFHzD8+v1I2YJ6oXevct1YeS0o9HZyN1Q9qgCgzUFtdOKLv6IedplqoPkcmF0aYet2PkEDo3MlTBckFXPITAMzF8dJSIFo9D8HfdOV0IAdx4O7PtixWKn5y2hMNG0zQPyUecp4pzC6kivAIhyfHilFR61RGL+GPXQ2MWZWFYbAGjyiYJnAmCP3NOTd0jMZEnDkbUvxhMmBYSdETk1rRgm+R4LOzFUGaHqHDLKLX+FIPKcF96hrucXzcWyLbIbEgE98OHlnVYCzRdK8jlqm8tehUc9c9WhQ== vagrant insecure public key"

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
# Remove random-seed
rm /var/lib/systemd/random-seed

# Setup sudoers for Vagrant
echo 'vagrant ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers
sed -i 's/Defaults\s*requiretty/Defaults !requiretty/' /etc/sudoers

# SSH setup
sed -i 's/.*UseDNS.*/UseDNS no/' /etc/ssh/sshd_config
%end

%packages --excludedocs
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

# Useful tools for Vagrant
openssh-server
openssh-clients
sudo
rsync
%end
