# Lorax Composer vmdk kickstart template

# Firewall configuration
firewall --enabled

# NOTE: The root account is locked by default
# Network information
network  --bootproto=dhcp --onboot=on --activate
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

# Basic services
services --enabled=sshd,chronyd,vmtoolsd

%post
# Remove random-seed
rm /var/lib/systemd/random-seed
%end

%packages
kernel
-dracut-config-rescue

grub2

chrony
open-vm-tools

# NOTE lorax-composer will add the blueprint packages below here, including the final %end
