#!/bin/bash
# Note: execute this file from the project root directory

#####
#
# Make sure an ext4-filesystem compose can be built without errors!
# Note: according to existing test plan we're not going to validate
# direct usage-scenarios for this image type!
#
#####

set -e

. /usr/share/beakerlib/beakerlib.sh
. $(dirname $0)/lib/lib.sh

CLI="${CLI:-./src/bin/composer-cli}"

rlJournalStart
    rlPhaseStartSetup
        if [[ -n "$SUBSCRIPTION_HOSTNAME" && -n "$SUBSCRIPTION_USERNAME" && -n "$SUBSCRIPTION_PASSWORD" ]]; then
            rlRun -t -c "cp -r /etc/yum.repos.d /etc/yum.repos.backup"
            rlRun -t -c "rm -f /etc/yum.repos.d/*.repo"
            rlRun -t -c "subscription-manager config --server.hostname=$SUBSCRIPTION_HOSTNAME"
            subscription-manager register --username=$SUBSCRIPTION_USERNAME --password=$SUBSCRIPTION_PASSWORD
            rlAssert0 "'subscription-manager register' succeeded" $?
            rlRun -t -c "subscription-manager attach --auto"
            rlRun -t -c "systemctl restart lorax-composer"
            rlLogInfo "System is subscribed"
        else
            rlLogInfo "System is not subscribed"
        fi
    rlPhaseEnd

    rlPhaseStartTest "compose start"
        rlAssertEquals "SELinux operates in enforcing mode" "$(getenforce)" "Enforcing"
        rlRun -t -c "$CLI blueprints push $(dirname $0)/lib/test-http-server.toml"
        UUID=`$CLI compose start test-http-server ext4-filesystem`
        rlAssertEquals "exit code should be zero" $? 0

        UUID=`echo $UUID | cut -f 2 -d' '`
    rlPhaseEnd

    rlPhaseStartTest "compose finished"
        wait_for_compose $UUID
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "$CLI compose delete $UUID"
        if [[ -n "$SUBSCRIPTION_HOSTNAME" && -n "$SUBSCRIPTION_USERNAME" && -n "$SUBSCRIPTION_PASSWORD" ]]; then
            rlRun -t -c "subscription-manager unregister"
            rlRun -t -c "rm -rf /etc/yum.repos.d"
            rlRun -t -c "mv /etc/yum.repos.backup /etc/yum.repos.d"
        fi
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
