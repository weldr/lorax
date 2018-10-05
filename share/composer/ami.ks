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
services --enabled=sshd,chronyd,cloud-init

%post
# Remove random-seed
rm /var/lib/systemd/random-seed

# tell cloud-init to create the ec2-user account
sed -i 's/cloud-user/ec2-user/' /etc/cloud/cloud.cfg
%end

%packages
kernel
-dracut-config-rescue

grub2

chrony

cloud-init

# NOTE lorax-composer will add the blueprint packages below here, including the final %end
