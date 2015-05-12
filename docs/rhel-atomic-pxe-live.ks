# Settings for unattended installation:
lang en_US.UTF-8
keyboard us
timezone America/New_York
clearpart --all --initlabel
rootpw --plaintext atomic

# We are only able to install atomic with separate /boot partition currently
part / --fstype="ext4" --size=6000
part /boot --size=500 --fstype="ext4"

shutdown

# Using ostree repo included in installation iso. Respective ostreesetup command is included here.
# The included kickstart file with the command is created during installation iso compose.
%include /usr/share/anaconda/interactive-defaults.ks

services --disabled=cloud-init,cloud-init-local,cloud-final,cloud-config,docker-storage-setup

# We copy content of separate /boot partition to root part when building live squashfs image,
# and we don't want systemd to try to mount it when pxe booting
%post
cat /dev/null > /etc/fstab
%end
