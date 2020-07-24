#!/bin/bash
# Note: execute this file from the project root directory

set -e

. /usr/share/beakerlib/beakerlib.sh
. $(dirname $0)/lib/lib.sh

CLI="${CLI:-./src/bin/composer-cli}"


rlJournalStart
    rlPhaseStartTest "compose types"
        TYPE_LIVE_ISO="live-iso"
        TYPE_ALIBABA="alibaba"
        TYPE_GOOGLE="google"
        TYPE_HYPER_V="hyper-v"
        TYPE_LIVEIMG="liveimg-tar"
        TYPE_EXT4="ext4-filesystem"
        TYPE_PARTITIONED_DISK="partitioned-disk"
        TYPE_TAR="tar"
        TYPE_IOT=""

        # backend specific compose type overrides
        if [ "$BACKEND" == "osbuild-composer" ]; then
            TYPE_LIVE_ISO=""
            TYPE_ALIBABA=""
            TYPE_GOOGLE=""
            TYPE_HYPER_V=""
            TYPE_LIVEIMG=""
            TYPE_EXT4=""
            TYPE_PARTITIONED_DISK=""
            TYPE_TAR=""
            TYPE_IOT="fedora-iot-commit"
        fi

        # arch specific compose type selections
        if [ "$(uname -m)" == "x86_64" ]; then
            SUPPORTED_TYPES="$TYPE_ALIBABA ami $TYPE_IOT $TYPE_EXT4 $TYPE_GOOGLE $TYPE_HYPER_V $TYPE_LIVE_ISO $TYPE_LIVEIMG openstack $TYPE_PARTITIONED_DISK qcow2 $TYPE_TAR vhd vmdk"
        elif [ "$(uname -m)" == "aarch64" ]; then
            # ami is supported on aarch64
            SUPPORTED_TYPES="ami $TYPE_EXT4 $TYPE_LIVE_ISO $TYPE_LIVEIMG openstack $TYPE_PARTITIONED_DISK qcow2 $TYPE_TAR"
        else
            SUPPORTED_TYPES="$TYPE_EXT4 $TYPE_LIVE_ISO $TYPE_LIVEIMG openstack $TYPE_PARTITIONED_DISK qcow2 $TYPE_TAR"
        fi

        # truncate white space in case some types are not available
        SUPPORTED_TYPES=$(echo "$SUPPORTED_TYPES" | tr -s ' ' | sed 's/^[[:space:]]*//')
        rlAssertEquals "lists all supported types" "`$CLI compose types | xargs`" "$SUPPORTED_TYPES"
    rlPhaseEnd

    rlPhaseStartTest "compose start"
        rlRun -t -c "$CLI blueprints push $(dirname $0)/lib/test-http-server.toml"
        UUID=`$CLI compose start test-http-server qcow2`
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
        if [ "$BACKEND" == "lorax-composer" ]; then
            rlRun -t -c "$CLI compose info $UUID" 1 "compose is canceled"
        fi
    rlPhaseEnd

if [ -z "$SKIP_IMAGE_BUILD" ]; then
    rlPhaseStartTest "compose start again"
        UUID=`$CLI compose start test-http-server qcow2`
        rlAssertEquals "exit code should be zero" $? 0

        UUID=`echo $UUID | cut -f 2 -d' '`
    rlPhaseEnd

    rlPhaseStartTest "compose image"
        wait_for_compose $UUID
        if [ -n "$UUID" ]; then
            check_compose_status "$UUID"

            rlRun -t -c "$CLI compose image $UUID"
            rlAssertExists "$UUID-disk.qcow2"
        fi

        if [ "$BACKEND" != "osbuild-composer" ]; then
            # because this path is listed in the documentation
            rlAssertExists    "/var/lib/lorax/composer/results/$UUID/"
            rlAssertExists    "/var/lib/lorax/composer/results/$UUID/disk.qcow2"
            rlAssertNotDiffer "/var/lib/lorax/composer/results/$UUID/disk.qcow2" "$UUID-disk.qcow2"
        fi
    rlPhaseEnd
else
    rlLogInfo "Skipping image build phases"
fi

    rlPhaseStartCleanup
        if [ "$($CLI compose list | grep -c $UUID)" == "1" ]; then
            rlRun -t -c "$CLI compose delete $UUID"
        fi
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
