url --url="https://dl.fedoraproject.org/pub/fedora/linux/development/rawhide/Everything/$basearch/os/"
repo --name=extra-repo --baseurl=file:///run/install/repo/extra-repo/

lang en_US.UTF-8
keyboard us
rootpw  --plaintext asdasd
timezone --utc America/New_York

# partitioning - nuke and start fresh
clearpart --initlabel --all
autopart --type=plain
bootloader --location=mbr
shutdown

%packages
extra-package
%end
