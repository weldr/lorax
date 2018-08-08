# Lorax Composer partitioned disk output kickstart template

# Firewall configuration
firewall --enabled

# Root password
rootpw --plaintext removethispw
# Network information
network  --bootproto=dhcp --onboot=on --activate
# System authorization information
auth --useshadow --enablemd5
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

%post
# Remove random-seed
rm /var/lib/systemd/random-seed
%end

%packages
kernel
-dracut-config-rescue

grub2

# NOTE lorax-composer will add the recipe packages below here, including the final %end
