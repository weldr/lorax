# Lorax Composer partitioned disk output kickstart template

# Firewall configuration
firewall --disabled

# NOTE: The root account is locked by default
# Network information
network  --bootproto=dhcp --onboot=on --mtu=1460 --noipv6 --activate
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
timezone --ntpservers metadata.google.internal UTC
# System bootloader configuration
bootloader --location=mbr --append="ttyS0,38400n8d"
# Add platform specific partitions
reqpart --add-boot

services --disabled=irqbalance

%post
# Remove random-seed
rm /var/lib/systemd/random-seed

# Clear /etc/machine-id
rm /etc/machine-id
touch /etc/machine-id

# Remove the rescue kernel and image to save space
rm -f /boot/*-rescue*

# Replace the ssh configuration
cat > /etc/ssh/sshd_config << EOF
# Disable PasswordAuthentication as ssh keys are more secure.
PasswordAuthentication no

# Disable root login, using sudo provides better auditing.
PermitRootLogin no

PermitTunnel no
AllowTcpForwarding yes
X11Forwarding no

# Compute times out connections after 10 minutes of inactivity.  Keep alive
# ssh connections by sending a packet every 7 minutes.
ClientAliveInterval 420
EOF

cat > /etc/ssh/ssh_config << EOF
Host *
Protocol 2
ForwardAgent no
ForwardX11 no
HostbasedAuthentication no
StrictHostKeyChecking no
Ciphers aes128-ctr,aes192-ctr,aes256-ctr,arcfour256,arcfour128,aes128-cbc,3des-cbc
Tunnel no

# Google Compute Engine times out connections after 10 minutes of inactivity.
# Keep alive ssh connections by sending a packet every 7 minutes.
ServerAliveInterval 420
EOF

%end

%packages
kernel
selinux-policy-targeted

# NOTE lorax-composer will add the blueprint packages below here, including the final %end
