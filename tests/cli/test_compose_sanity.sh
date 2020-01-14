#!/bin/bash
# Note: execute this file from the project root directory

set -e

. /usr/share/beakerlib/beakerlib.sh
. $(dirname $0)/lib/lib.sh

CLI="${CLI:-./src/bin/composer-cli}"


rlJournalStart
    rlPhaseStartTest "compose types"
        if [ "$(uname -m)" == "x86_64" ]; then
            rlAssertEquals "lists all supported types" \
                    "`$CLI compose types | xargs`" "alibaba ami ext4-filesystem google hyper-v live-iso liveimg-tar openstack partitioned-disk qcow2 tar vhd vmdk"
        elif [ "$(uname -m)" == "aarch64" ]; then
            # ami is supported on aarch64
            rlAssertEquals "lists all supported types" \
                    "`$CLI compose types | xargs`" "ami ext4-filesystem live-iso liveimg-tar openstack partitioned-disk qcow2 tar"
        else
            # non-x86 architectures disable alibaba
            rlAssertEquals "lists all supported types" \
                    "`$CLI compose types | xargs`" "ext4-filesystem live-iso liveimg-tar openstack partitioned-disk qcow2 tar"
        fi
    rlPhaseEnd

    rlPhaseStartTest "compose start"
        UUID=`$CLI compose start example-http-server ami`
        rlAssertEquals "exit code should be zero" $? 0
        UUID=`echo $UUID | cut -f 2 -d' '`

        if [ -n "$UUID" ]; then
            until $CLI compose info $UUID | grep 'RUNNING'; do
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
        rlRun -t -c "$CLI compose info $UUID" 1 "compose is canceled"
    rlPhaseEnd

    rlPhaseStartTest "compose start again"
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
