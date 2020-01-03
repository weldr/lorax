#!/bin/bash
# Note: execute this file from the project root directory

set -e

. /usr/share/beakerlib/beakerlib.sh
. $(dirname $0)/lib/lib.sh

CLI="${CLI:-./src/bin/composer-cli}"


rlJournalStart
    rlPhaseStartTest "compose types"
        rlAssertEquals "lists all supported types" \
                "`$CLI compose types | xargs`" "ami ext4-filesystem live-iso openstack partitioned-disk qcow2 tar vhd vmdk"
    rlPhaseEnd

    rlPhaseStartTest "compose start"
        UUID=`$CLI compose start example-http-server ami`
        rlAssertEquals "exit code should be zero" $? 0
        UUID=`echo $UUID | cut -f 2 -d' '`

        if [ -n "$UUID" ]; then
            until $CLI compose details $UUID | grep 'RUNNING'; do
                sleep 20
                rlLogInfo "Waiting for compose to start running..."
                if $CLI compose info $UUID | grep 'FAILED'; then
                    rlFail "Compose FAILED!"
                    break
                fi
            done;
        else
            rlFail "Compose UUID is empty!"
        fi
    rlPhaseEnd

    rlPhaseStartTest "cancel compose"
        rlRun -t -c "$CLI compose cancel $UUID"
        rlRun -t -c "$CLI compose details $UUID" 1 "compose is canceled"
    rlPhaseEnd

    rlPhaseStartTest "compose start again"
        UUID=`$CLI --test=2 compose start example-http-server tar`
        rlAssertEquals "exit code should be zero" $? 0

        UUID=`echo $UUID | cut -f 2 -d' '`
    rlPhaseEnd

    rlPhaseStartTest "compose details"
        if [ -n "$UUID" ]; then
            rlRun -t -c "$CLI compose details $UUID | egrep 'RUNNING|WAITING'"
        else
            rlFail "Compose UUID is empty!"
        fi
    rlPhaseEnd

    rlPhaseStartTest "compose image"
        wait_for_compose $UUID
        if [ -n "$UUID" ]; then
            check_compose_status "$UUID"

            rlRun -t -c "$CLI compose image $UUID"
            rlAssertExists "$UUID-root.tar.xz"

            # because this path is listed in the documentation
            rlAssertExists    "/var/lib/lorax/composer/results/$UUID/"
            rlAssertExists    "/var/lib/lorax/composer/results/$UUID/root.tar.xz"
            rlAssertNotDiffer "/var/lib/lorax/composer/results/$UUID/root.tar.xz" "$UUID-root.tar.xz"
        fi
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
