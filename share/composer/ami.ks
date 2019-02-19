# Lorax Composer AMI output kickstart template

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
# Add platform specific partitions
reqpart --add-boot

# Basic services
services --enabled=sshd,chronyd,cloud-init

%post
# Remove random-seed
rm /var/lib/systemd/random-seed

# Clear /etc/machine-id
rm /etc/machine-id
touch /etc/machine-id

# tell cloud-init to create the ec2-user account
sed -i 's/cloud-user/ec2-user/' /etc/cloud/cloud.cfg

# Remove the rescue kernel and image to save space
rm -f /boot/*-rescue*
%end

%packages
kernel
selinux-policy-targeted

chrony

cloud-init

# NOTE lorax-composer will add the recipe packages below here, including the final %end
