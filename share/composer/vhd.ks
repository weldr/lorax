# Lorax Composer VHD (Azure, Hyper-V) output kickstart template

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
bootloader --location=mbr --append="no_timer_check console=ttyS0,115200n8 earlyprintk=ttyS0,115200 rootdelay=300 net.ifnames=0"

# Basic services
services --enabled=sshd,chronyd,waagent

%post
# Remove random-seed
rm /var/lib/systemd/random-seed

# This file is required by waagent in RHEL, but compatible with NetworkManager
cat > /etc/sysconfig/network-scripts/ifcfg-eth0 << EOF
DEVICE=eth0
ONBOOT=yes
BOOTPROTO=dhcp
TYPE=Ethernet
USERCTL=yes
PEERDNS=yes
IPV6INIT=no
EOF

# Add Hyper-V modules into initramfs
cat > /etc/dracut.conf.d/10-hyperv.conf << EOF
add_drivers+=" hv_vmbus hv_netvsc hv_storvsc "
EOF

# Regenerate the intramfs image
dracut -f -v --persistent-policy by-uuid
%end

%addon com_redhat_kdump --disable
%end

%packages
kernel
-dracut-config-rescue

grub2

chrony

WALinuxAgent

# Requirements of WALinuxAgent
net-tools

# NOTE lorax-composer will add the recipe packages below here, including the final %end
