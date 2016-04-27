# Fedora Atomic PXE Live creation kickstart
# Suitable for use with livemedia-creator --no-virt

# Settings for unattended installation:
lang en_US.UTF-8
keyboard us
timezone America/New_York
clearpart --all --initlabel
rootpw --plaintext atomic

part / --fstype="ext4" --size=6000

shutdown

ostreesetup --nogpg --osname=fedora-atomic --remote=fedora-atomic --url=https://dl.fedoraproject.org/pub/fedora/linux/atomic/24/ --ref=fedora-atomic/rawhide/x86_64/docker-host

services --disabled=cloud-init,cloud-init-local,cloud-final,cloud-config,docker-storage-setup

# We copy content of separate /boot partition to root part when building live squashfs image,
# and we don't want systemd to try to mount it when pxe booting
%post
cat /dev/null > /etc/fstab
%end

%post --erroronfail
rm -f /etc/ostree/remotes.d/fedora-atomic.conf
ostree remote add --set=gpg-verify=false fedora-atomic 'https://dl.fedoraproject.org/pub/fedora/linux/atomic/24/'
%end
