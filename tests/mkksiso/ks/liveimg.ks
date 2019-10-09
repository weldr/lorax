install
lang en_US.UTF-8
keyboard us
rootpw  --plaintext asdasd
timezone --utc America/New_York

# partitioning - nuke and start fresh
clearpart --initlabel --all
autopart --type=plain
bootloader --location=mbr
shutdown

liveimg --url=file:///run/install/repo/root.tar.xz
