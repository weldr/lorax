#!/bin/bash
# Note: execute this file from the project root directory

#####
#
# Build tar image and install it using liveimg kickstart command
#
#####

set -e

. /usr/share/beakerlib/beakerlib.sh
. $(dirname $0)/lib/lib.sh

CLI="${CLI:-./src/bin/composer-cli}"

rlJournalStart
    rlPhaseStartSetup
        rlAssertExists $QEMU_BIN
        if ! rlCheckRpm httpd; then
            dnf -y install httpd
        fi
        systemctl start httpd

        ks_path="/var/www/html/ks-tar.cfg"
        tmp_dir=$(mktemp -d /tmp/composer.XXXXX)
        ssh_key_dir=$(mktemp -d /tmp/composer-ssh-keys.XXXXXX)

        rlRun -t -c "ssh-keygen -t rsa -N '' -f $ssh_key_dir/id_rsa"
        pub_key=$(cat $ssh_key_dir/id_rsa.pub)

        bp_name="test-tar"
        blueprint="$bp_name.toml"
        cat > $blueprint << __EOF__
name = "$bp_name"
description = "tar image test"
version = "0.0.1"
modules = []

[[packages]]
name = "openssh-server"
version = "*"

[[customizations.user]]
name = "root"
key = "$pub_key"

__EOF__
        rlRun -t -c "$CLI blueprints push $blueprint"
        image_path="/var/www/html/root.tar.xz"

        version=$(awk -F = '$1 == "VERSION_ID" { print $2 }' /etc/os-release | tr -d \")
        arch=$(uname -m)
        baseurl=$(curl "https://mirrors.fedoraproject.org/mirrorlist?repo=fedora-${version}&arch=${arch}" | \
            grep -v "^#" | head -n 1)
        rlRun -t -c "curl --remote-name-all $baseurl/images/pxeboot/{vmlinuz,initrd.img}"

        rlRun -t -c "fallocate -l 5G disk.img"
    rlPhaseEnd

    rlPhaseStartTest "compose start"
        rlAssertEquals "SELinux operates in enforcing mode" "$(getenforce)" "Enforcing"
        uuid=$($CLI compose start $bp_name liveimg-tar)
        rlAssertEquals "exit code should be zero" $? 0

        uuid=$(echo $uuid | cut -f 2 -d' ')
    rlPhaseEnd

    rlPhaseStartTest "compose finished"
        if [ -n "$uuid" ]; then
            until $CLI compose info $uuid | grep 'FINISHED\|FAILED'; do
                sleep 60
                rlLogInfo "Waiting for compose to finish ..."
            done;
            check_compose_status "$UUID"
        else
            rlFail "Compose uuid is empty!"
        fi

        rlRun -t -c "$CLI compose image $uuid"
        image="$uuid-root.tar.xz"
    rlPhaseEnd

    rlPhaseStartTest "Install tar image using kickstart liveimg command"
        cat > $ks_path << __EOF__
cmdline
lang en_US.UTF-8
timezone America/New_York
keyboard us
rootpw --lock
sshkey --username root "$pub_key"
bootloader --location=mbr
zerombr
clearpart --initlabel --all
autopart
# reboot is used together with --no-reboot qemu-kvm parameter, which makes the qemu-kvm
# process exit after the installation is complete and anaconda reboots the system
# (using 'poweroff' ks command just halted the machine without powering it off)
reboot

liveimg --url http://10.0.2.2/root.tar.xz

__EOF__
        mv $image $image_path
        restorecon $image_path
        rlLogInfo "Starting installation from tar image in a VM"
        $QEMU -m 2048 -drive file=disk.img,format=raw -nographic -kernel vmlinuz -initrd initrd.img \
            -append "inst.ks=http://10.0.2.2/ks-tar.cfg inst.stage2=$baseurl console=ttyS0" --no-reboot

        rlLogInfo "Installation of the image finished."
    rlPhaseEnd

    rlPhaseStartTest "Boot and check the installed system"
        boot_image "-drive file=disk.img,format=raw" 600
        # run generic tests to verify the instance
        CHECK_CMDLINE=0 verify_image root localhost "-i $ssh_key_dir/id_rsa -p 2222"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "killall -9 $QEMU_BIN"
        rlRun -t -c "rm -rf $image $blueprint $image_path vmlinuz initrd.img disk.img $ks_path"
        rlRun -t -c "$CLI blueprints delete $bp_name"
        rlRun -t -c "$CLI compose delete $uuid"
        rlRun -t -c "systemctl stop httpd"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
