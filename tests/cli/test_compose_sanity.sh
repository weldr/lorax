#!/bin/bash
# Note: execute this file from the project root directory

. /usr/share/beakerlib/beakerlib.sh

CLI="${CLI:-./src/bin/composer-cli}"


rlJournalStart
    rlPhaseStartTest "compose types"
        rlAssertEquals "lists all supported types" \
                "`$CLI compose types | sort | xargs`" "alibaba ami ext4-filesystem google live-iso openstack partitioned-disk qcow2 tar vhd vmdk"
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
            until $CLI compose info $UUID | grep FINISHED; do
                sleep 5
                rlLogInfo "Waiting for compose to finish ..."
            done;

            rlRun -t -c "$CLI compose image $UUID"
            rlAssertExists "$UUID-root.tar.xz"
        else
            rlFail "Compose UUID is empty!"
        fi
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
