#!/bin/bash
# Note: execute this file from the project root directory

#####
#
# Test the live-iso image
#
#####

set -e

. /usr/share/beakerlib/beakerlib.sh
. $(dirname $0)/lib/lib.sh

rlJournalStart
    rlPhaseStartTest "Verify live iso"
        # Just the fact that this is running means the image can boot and ssh is working
        ROOT_ACCOUNT_LOCKED=0 verify_image liveuser localhost "-p 22"
        rlAssertGrep "liveuser" /etc/passwd
        rlAssertGrep "custom_cmdline_arg" /proc/cmdline
    rlPhaseEnd
rlJournalEnd
rlJournalPrintText
