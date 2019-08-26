#!/bin/bash
# Note: execute this file from the project root directory

set -e

. /usr/share/beakerlib/beakerlib.sh
. $(dirname $0)/lib/lib.sh

CLI="${CLI:-./src/bin/composer-cli}"


rlJournalStart
    rlPhaseStartTest "compose types"
        rlAssertEquals "lists all supported types" \
                "`$CLI compose types | xargs`" "alibaba ami ext4-filesystem google hyper-v live-iso liveimg-tar openstack partitioned-disk qcow2 tar vhd vmdk"
    rlPhaseEnd

    rlPhaseStartTest "compose start"
        UUID=`$CLI --test=2 compose start example-http-server tar`
        rlAssertEquals "exit code should be zero" $? 0

        UUID=`echo $UUID | cut -f 2 -d' '`
    rlPhaseEnd

    rlPhaseStartTest "compose info"
        if [ -n "$UUID" ]; then
            rlRun -t -c "$CLI compose info $UUID | egrep 'RUNNING|WAITING'"
        else
            rlFail "Compose UUID is empty!"
        fi
    rlPhaseEnd

    rlPhaseStartTest "compose image"
        if [ -n "$UUID" ]; then
            until $CLI compose info $UUID | grep 'FINISHED\|FAILED'; do
                sleep 5
                rlLogInfo "Waiting for compose to finish ..."
            done;
            check_compose_status "$UUID"

            rlRun -t -c "$CLI compose image $UUID"
            rlAssertExists "$UUID-root.tar.xz"

            # because this path is listed in the documentation
            rlAssertExists    "/var/lib/lorax/composer/results/$UUID/"
            rlAssertExists    "/var/lib/lorax/composer/results/$UUID/root.tar.xz"
            rlAssertNotDiffer "/var/lib/lorax/composer/results/$UUID/root.tar.xz" "$UUID-root.tar.xz"
        else
            rlFail "Compose UUID is empty!"
        fi
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
