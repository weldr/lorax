# Lorax Composer AMI output kickstart template
# Kickstart file to build RHEL-7 Amazon EC2 image

# Firewall configuration
firewall --disabled

# Root password
rootpw --lock --iscrypted locked
# Network information
network  --bootproto=dhcp --onboot=on --activate
# System authorization information
auth --useshadow --enablemd5 --passalgo=sha512
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
timezone --utc UTC
# System bootloader configuration
bootloader --timeout=1 --location=mbr --append="no_timer_check console=ttyS0,115200n8 console=tty1 net.ifnames=0"
# Basic services
services --enabled=sshd,cloud-init,cloud-init-local,cloud-config,cloud-final

%post
passwd -d root
passwd -l root

# Create grub.conf for EC2. This used to be done by appliance creator but
# anaconda doesn't do it. And, in case appliance-creator is used, we're
# overriding it here so that both cases get the exact same file.
# Note that the console line is different -- that's because EC2 provides
# different virtual hardware, and this is a convenient way to act differently

echo -n "Creating grub.conf for pvgrub"
rootuuid=$( awk '$2=="/" { print $1 };'  /etc/fstab )
mkdir /boot/grub

echo -e 'default=0\ntimeout=0\n\n' > /boot/grub/grub.conf
for kv in $( ls -1v /boot/vmlinuz* |grep -v rescue |sed s/.*vmlinuz-//  ); do
  echo "title Compose ($kv)" >> /boot/grub/grub.conf
  echo -e "\troot (hd0,0)" >> /boot/grub/grub.conf
  echo -e "\tkernel /boot/vmlinuz-$kv ro root=$rootuuid no_timer_check console=hvc0 LANG=en_US.UTF-8" >> /boot/grub/grub.conf
  echo -e "\tinitrd /boot/initramfs-$kv.img" >> /boot/grub/grub.conf
  echo
done

#link grub.conf to menu.lst for ec2 to work
echo -n "Linking menu.lst to old-style grub.conf for pv-grub"
ln -sf grub.conf /boot/grub/menu.lst
ln -sf /boot/grub/grub.conf /etc/grub.conf

# setup systemd to boot to the right runlevel
echo -n "Setting default runlevel to multiuser text mode"
rm -f /etc/systemd/system/default.target
ln -s /lib/systemd/system/multi-user.target /etc/systemd/system/default.target
echo .

echo -n "Getty fixes"
# although we want console output going to the serial console, we don't
# actually have the opportunity to login there. FIX.
# we don't really need to auto-spawn _any_ gettys.
sed -i '/^#NAutoVTs=.*/ a\
NAutoVTs=0' /etc/systemd/logind.conf

# Because memory is scarce resource in most cloud/virt environments,
# and because this impedes forensics, we are differing from the Fedora
# default of having /tmp on tmpfs.
echo "Disabling tmpfs for /tmp."
systemctl mask tmp.mount

# Remove random-seed
rm /var/lib/systemd/random-seed

# tell cloud-init to create the ec2-user account
sed -i 's/cloud-user/ec2-user/' /etc/cloud/cloud.cfg

# allow sudo powers to ec2-user
echo -e 'ec2-user\tALL=(ALL)\tNOPASSWD: ALL' >> /etc/sudoers

# remove these for ec2 debugging
sed -i -e 's/ rhgb quiet//' /boot/grub/grub.conf

# enable resizing on copied AMIs
echo 'install_items+=" sgdisk "' > /etc/dracut.conf.d/sgdisk.conf

cat /dev/null > /etc/machine-id

truncate -s 0 /etc/resolv.conf

echo "Zeroing out empty space."

# This forces the filesystem to reclaim space from deleted files
dd bs=1M if=/dev/zero of=/var/tmp/zeros || :
rm -f /var/tmp/zeros
echo "(Don't worry -- that out-of-space error was expected.)"

%end

%packages
kernel
-dracut-config-rescue
grub2

# cloud-init does magical things with EC2 metadata, including provisioning
# a user account with ssh keys.
cloud-init

# enable rootfs resize on boot
cloud-utils-growpart

# NOTE lorax-composer will add the recipe packages below here, including the final %end
