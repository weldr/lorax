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
        rlAssertEquals "SELinux operates in enforcing mode" "$(getenforce)" "Enforcing"

        rlRun -t -c "lsmod"
        rlRun -t -c "ls -l /dev/kvm"

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
            check_compose_status "$UUID"
        else
            rlFail "Compose UUID is empty!"
        fi

        rlRun -t -c "$CLI compose image $UUID"
        IMAGE="$UUID-live.iso"
    rlPhaseEnd

    rlPhaseStartTest "Start VM instance"
        boot_image "-boot d -cdrom $IMAGE" 120
    rlPhaseEnd

    rlPhaseStartTest "Verify VM instance"
        # run generic tests to verify the instance
        ROOT_ACCOUNT_LOCKED=0 verify_image liveuser localhost "-p $SSH_PORT"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "killall -9 qemu-kvm"
        rlRun -t -c "$CLI compose delete $UUID"
        rlRun -t -c "rm -rf $IMAGE"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
