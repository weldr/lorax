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
        TMP_DIR=$(mktemp -d /tmp/composer.XXXXX)
        SSH_KEY_DIR=$(mktemp -d /tmp/composer-ssh-keys.XXXXXX)

        rlRun -t -c "ssh-keygen -t rsa -N '' -f $SSH_KEY_DIR/id_rsa"
        PUB_KEY=$(cat "$SSH_KEY_DIR/id_rsa.pub")

        cat > "$TMP_DIR/test-tar.toml" << __EOF__
name = "test-tar"
description = "tar image test"
version = "0.0.1"
modules = []

[[groups]]
name = "anaconda-tools"

[[packages]]
name = "kernel"
version = "*"

[[packages]]
name = "beakerlib"
version = "*"

[[packages]]
name = "openssh-server"
version = "*"

[[packages]]
name = "openssh-clients"
version = "*"

[[packages]]
name = "passwd"
version = "*"

[[customizations.user]]
name = "root"
key = "$PUB_KEY"

__EOF__
        rlRun -t -c "$CLI blueprints push $TMP_DIR/test-tar.toml"
    rlPhaseEnd

    rlPhaseStartTest "compose start"
        rlAssertEquals "SELinux operates in enforcing mode" "$(getenforce)" "Enforcing"
        UUID=$($CLI compose start test-tar tar)
        rlAssertEquals "exit code should be zero" $? 0

        UUID=$(echo "$UUID" | cut -f 2 -d' ')
    rlPhaseEnd

    rlPhaseStartTest "compose finished"
        wait_for_compose "$UUID"
    rlPhaseEnd

    rlPhaseStartTest "Install tar image using kickstart liveimg command"
        cat > "$TMP_DIR/test-liveimg.ks" << __EOF__
cmdline
lang en_US.UTF-8
timezone America/New_York
keyboard us
rootpw --lock
sshkey --username root "$PUB_KEY"
bootloader --location=mbr
zerombr
clearpart --initlabel --all
autopart
# reboot is used together with --no-reboot qemu-kvm parameter, which makes the qemu-kvm
# process exit after the installation is complete and anaconda reboots the system
# (using 'poweroff' ks command just halted the machine without powering it off)
reboot

liveimg --url file:///var/lib/lorax/composer/results/$UUID/root.tar.xz

__EOF__
        # Build the disk image directly in the results directory
        rlRun -t -c "mkdir -p /var/tmp/test-results/"
        rlRun -t -c "fallocate -l 5G /var/tmp/test-results/disk.img"

        rlLogInfo "Starting installation from tar image using anaconda"
        rlRun -t -c "anaconda --image=/var/tmp/test-results/disk.img --kickstart=$TMP_DIR/test-liveimg.ks"
        rlLogInfo "Installation of the image finished."

        # Include the ssh key needed to log into the image
        rlRun -t -c "cp $SSH_KEY_DIR/* /var/tmp/test-results"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "$CLI compose delete $UUID"
        rlRun -t -c "rm -rf $TMP_DIR $SSH_KEY_DIR"
    rlPhaseEnd
rlJournalEnd
rlJournalPrintText
