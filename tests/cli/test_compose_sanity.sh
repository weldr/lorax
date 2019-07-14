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
rlJournalEnd
rlJournalPrintText
