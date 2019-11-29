#!/bin/bash
# Note: execute this file from the project root directory

#####
#
# Make sure a partitioned-disk compose can be built without errors!
# Note: according to existing test plan we're not going to validate
# direct usage-scenarios for this image type!
#
#####

set -e

. /usr/share/beakerlib/beakerlib.sh
. $(dirname $0)/lib/lib.sh

CLI="${CLI:-./src/bin/composer-cli}"


rlJournalStart
    rlPhaseStartTest "compose start"
        rlAssertEquals "SELinux operates in enforcing mode" "$(getenforce)" "Enforcing"
        rlRun -t -c "$CLI blueprints push $(dirname $0)/lib/test-http-server.toml"
        UUID=`$CLI compose start test-http-server partitioned-disk`
        rlAssertEquals "exit code should be zero" $? 0

        UUID=`echo $UUID | cut -f 2 -d' '`
    rlPhaseEnd

    rlPhaseStartTest "compose finished"
        wait_for_compose $UUID
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "$CLI compose delete $UUID"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
