#!/bin/bash
# Note: execute this file from the project root directory

#####
#
# Test the qcow2 image
#
#####

set -e

. /usr/share/beakerlib/beakerlib.sh
. $(dirname $0)/lib/lib.sh

rlJournalStart
    rlPhaseStartTest "Verify VM instance"
        # Just the fact that this is running means the image can boot and ssh is working
        verify_image root localhost "-p 22"
        rlAssertExists "/root/.ssh/authorized_keys"
    rlPhaseEnd
rlJournalEnd
rlJournalPrintText
