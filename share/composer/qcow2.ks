# Lorax Composer qcow2 output kickstart template

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
# Add platform specific partitions
reqpart

%post
# Remove random-seed
rm /var/lib/systemd/random-seed

# Clear /etc/machine-id
rm /etc/machine-id
touch /etc/machine-id
%end

%packages
kernel
-dracut-config-rescue
selinux-policy-targeted

# Make sure virt guest agents are installed
qemu-guest-agent
spice-vdagent

# NOTE lorax-composer will add the blueprint packages below here, including the final %end
