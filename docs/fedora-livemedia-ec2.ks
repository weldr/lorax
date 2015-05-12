# Build a basic Fedora AMI using livemedia-creator
lang en_US.UTF-8
keyboard us
timezone --utc America/New_York
auth --useshadow --enablemd5
selinux --enforcing
firewall --service=ssh
bootloader --location=none
services --enabled=network,sshd,rsyslog
shutdown

# By default the root password is emptied
rootpw --plaintext removethispw

#
# Define how large you want your rootfs to be
# NOTE: S3-backed AMIs have a limit of 10G
#
clearpart --all --initlabel
part / --size 10000 --fstype ext4
part swap --size=512

#
# Repositories
url --url="http://dl.fedoraproject.org/pub/fedora/linux/development/rawhide/x86_64/os/"

#
#
# Add all the packages after the base packages
#
%packages --nobase
@core
system-config-securitylevel-tui
audit
pciutils
bash
coreutils
kernel

e2fsprogs
passwd
policycoreutils
chkconfig
rootfiles
yum
vim-minimal
acpid
openssh-clients
openssh-server
curl
sudo

#Allow for dhcp access
dhclient
iputils

-firstboot
-biosdevname

# package to setup cloudy bits for us
cloud-init

grub
-dracut-config-rescue
%end

# more ec2-ify
%post --erroronfail

# create ec2-user
/usr/sbin/useradd ec2-user
/bin/echo -e 'ec2-user\tALL=(ALL)\tNOPASSWD: ALL' >> /etc/sudoers

# fstab mounting is different for x86_64 and i386
cat <<EOL > /etc/fstab
/dev/xvda1 /    ext4    defaults        1 1
/dev/xvda2 /mnt ext3    defaults        0 0
/dev/xvda3 swap swap    defaults        0 0
EOL

if [ ! -d /lib64 ] ; then
# workaround xen performance issue (bz 651861)
echo "hwcap 1 nosegneg" > /etc/ld.so.conf.d/libc6-xen.conf
fi

# Install grub.conf
# idle=nomwait is to allow xen images to boot and not try use cpu features that are not supported
INITRD=`ls /boot/initramfs-* | head -n1`
KERNEL=`ls /boot/vmlinuz-* | head -n1`
mkdir /boot/grub
pushd /boot/grub
cat <<EOL > grub.conf
default 0
timeout 0

title Fedora Linux
    root (hd0)
    kernel $KERNEL root=/dev/xvda1 idle=halt
    initrd $INITRD
EOL
# symlink grub.conf to menu.lst for use by EC2 pv-grub
ln -s grub.conf menu.lst
popd

# the firewall rules get saved as .old  without this we end up not being able 
# ssh in as iptables blocks access
rename -v  .old "" /etc/sysconfig/*old

# setup systemd to boot to the right runlevel
rm /etc/systemd/system/default.target
ln -s /lib/systemd/system/multi-user.target /etc/systemd/system/default.target

# remove the root password
passwd -d root > /dev/null

%end

