# Lorax Composer tar output kickstart template

#
sshpw --username=root --plaintext randOmStrinGhERE
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
# System bootloader configuration (tar doesn't need a bootloader)
bootloader --location=none

%post
# Remove root password
passwd -d root > /dev/null

# Remove random-seed
rm /var/lib/systemd/random-seed
%end

# NOTE Do NOT add any other sections after %packages
%packages
# Packages requires to support this output format go here


# NOTE lorax-composer will add the recipe packages below here, including the final %end
