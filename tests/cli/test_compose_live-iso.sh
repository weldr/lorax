#!/bin/bash
# Note: execute this file from the project root directory

#####
#
# Builds live-iso image and test it with QEMU-KVM
#
#####

set -e

. /usr/share/beakerlib/beakerlib.sh
. $(dirname $0)/lib/lib.sh

CLI="${CLI:-./src/bin/composer-cli}"

rlJournalStart
    rlPhaseStartSetup
        rlAssertExists $QEMU
    rlPhaseEnd

    rlPhaseStartTest "compose start"
        rlRun -t -c "curl -O http://mirror2.hs-esslingen.de/fedora/linux/releases/30/Server/x86_64/iso/Fedora-Server-netinst-x86_64-30-1.2.iso"
        IMAGE=$(realpath "Fedora-Server-netinst-x86_64-30-1.2.iso")
    rlPhaseEnd

    rlPhaseStartTest "Start VM instance"
        boot_image "-boot d -cdrom $IMAGE" 120
    rlPhaseEnd

    rlPhaseStartTest "Verify VM instance"
        # run generic tests to verify the instance
        # ROOT_ACCOUNT_LOCKED=0 verify_image liveuser localhost "-p $SSH_PORT"
        sleep 30
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "killall -9 qemu-kvm"
        # rlRun -t -c "$CLI compose delete $UUID"
        rlRun -t -c "rm -rf $IMAGE"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
