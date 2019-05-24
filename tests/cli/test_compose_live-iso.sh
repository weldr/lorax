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
QEMU_BIN="/usr/bin/qemu-system-$(uname -m)"
QEMU="$QEMU_BIN -machine accel=kvm:tcg"

rlJournalStart
    rlPhaseStartSetup
        rlAssertExists $QEMU_BIN
    rlPhaseEnd

    rlPhaseStartTest "compose start"
        rlAssertEquals "SELinux operates in enforcing mode" "$(getenforce)" "Enforcing"

        # NOTE: live-iso.ks explicitly disables sshd but test_cli.sh enables it
        UUID=`$CLI compose start example-http-server live-iso`
        rlAssertEquals "exit code should be zero" $? 0

        UUID=`echo $UUID | cut -f 2 -d' '`
    rlPhaseEnd

    rlPhaseStartTest "compose finished"
        if [ -n "$UUID" ]; then
            until $CLI compose info $UUID | grep 'FINISHED\|FAILED'; do
                sleep 20
                rlLogInfo "Waiting for compose to finish ..."
            done;
        else
            rlFail "Compose UUID is empty!"
        fi

        rlRun -t -c "$CLI compose image $UUID"
        IMAGE="$UUID-live.iso"
    rlPhaseEnd

    rlPhaseStartTest "Start VM instance"
        rlRun -t -c "$QEMU -m 2048 -boot c -cdrom $IMAGE -nographic \
                           -net user,id=nic0,hostfwd=tcp::2222-:22 -net nic &"
        # 60 seconds timeout at boot menu screen
        # then media check + boot ~ 30 seconds
        sleep 120
    rlPhaseEnd

    rlPhaseStartTest "Verify VM instance"
        # run generic tests to verify the instance
        ROOT_ACCOUNT_LOCKED=0 verify_image root localhost "-p 2222"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "killall -9 qemu-system-$(uname -m)"
        rlRun -t -c "$CLI compose delete $UUID"
        rlRun -t -c "rm -rf $IMAGE"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
