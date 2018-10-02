# Lorax Composer AMI output kickstart template

# Add a separate /boot partition
part /boot --size=1024

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
bootloader --location=mbr --append="no_timer_check console=ttyS0,115200n8 console=tty1 net.ifnames=0"

# Basic services
services --enabled=sshd,chronyd

%post
# Remove random-seed
rm /var/lib/systemd/random-seed
%end

%packages
kernel
-dracut-config-rescue

grub2

chrony

# NOTE lorax-composer will add the recipe packages below here, including the final %end
