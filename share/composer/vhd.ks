# Lorax Composer VHD (Azure, Hyper-V) output kickstart template

# Firewall configuration
firewall --enabled

# NOTE: The root account is locked by default
# Network information
network  --bootproto=dhcp --onboot=on --activate
# NOTE: keyboard and lang can be replaced by blueprint customizations.locale settings
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
# System bootloader configuration
bootloader --location=mbr --append="no_timer_check console=ttyS0,115200n8 earlyprintk=ttyS0,115200 rootdelay=300 net.ifnames=0"
# Add platform specific partitions
reqpart --add-boot

# Basic services
services --enabled=sshd,chronyd,waagent,cloud-init,cloud-init-local,cloud-config,cloud-final

%post
# Remove random-seed
rm /var/lib/systemd/random-seed

# Clear /etc/machine-id
rm /etc/machine-id
touch /etc/machine-id

# Remove the rescue kernel and image to save space
rm -f /boot/*-rescue*

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

# Restrict cloud-init to Azure datasource
cat > /etc/cloud/cloud.cfg.d/91-azure_datasource.cfg << EOF
# Azure Data Source config
datasource_list: [ Azure ]
datasource:
    Azure:
        apply_network_config: False
EOF

# Setup waagent to work with cloud-init
sed -i 's/Provisioning.Enabled=y/Provisioning.Enabled=n/g' /etc/waagent.conf
sed -i 's/Provisioning.UseCloudInit=n/Provisioning.UseCloudInit=y/g' /etc/waagent.conf

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
selinux-policy-targeted

chrony

WALinuxAgent
python3
net-tools

cloud-init
cloud-utils-growpart
gdisk

# NOTE lorax-composer will add the recipe packages below here, including the final %end
