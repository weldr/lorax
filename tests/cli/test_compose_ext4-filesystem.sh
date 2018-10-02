#!/bin/bash
# Note: execute this file from the project root directory

#####
#
# Make sure an ext4-filesystem compose can be built without errors!
# Note: according to existing test plan we're not going to validate
# direct usage-scenarios for this image type!
#
#####

. /usr/share/beakerlib/beakerlib.sh

CLI="./src/bin/composer-cli"


rlJournalStart
    rlPhaseStartTest "compose start"
        UUID=`$CLI compose start example-http-server ext4-filesystem`
        rlAssertEquals "exit code should be zero" $? 0

        UUID=`echo $UUID | cut -f 2 -d' '`
    rlPhaseEnd

    rlPhaseStartTest "compose finished"
        if [ -n "$UUID" ]; then
            until $CLI compose info $UUID | grep FINISHED; do
                sleep 10
                rlLogInfo "Waiting for compose to finish ..."
            done;
        else
            rlFail "Compose UUID is empty!"
        fi
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
