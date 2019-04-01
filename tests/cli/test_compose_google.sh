# Note: execute this file from the project root directory

#####
#
# Make sure a google compose can be built without errors
#
#####

. /usr/share/beakerlib/beakerlib.sh

CLI="${CLI:-./src/bin/composer-cli}"

rlJournalStart
    rlPhasStartTest "compose start"
        rlAssertEquals "SELinux operates in enforcing mode" "$(getenforce)" "Enforcing"
        UUID=`$CLI compose start example-http-server google`
        rlAssertEquals "exit code should be zero" $? 0

        UUID=`echo $UUID | cut -f 2 -d ' '`
    rlPhaseEnd

    rlPhaseStart "compose finished"
        if [ -n "$UUID" ]; then
            until $CLI compose info $UUID | grep FINISHED; do
                sleep 10
                rlLogInfo "Waiting for compose to finish..."
            done
        else
            flFail "Compose UUID is empty!"
        fi
    rlPhaseEnd

    rlPhaseStart "compose check"
        $CLI compose image $UUID
        rlAssertEquals "exit code should be zero" $? 0

        fileList=$(gzip -cd "$UUID-disk.tar.gz" | tar tf -)
        rlAssertEquals "archive should contain disk.raw" "$fileList" "disk.raw"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "rm -rf $UUID-disk.tar.gz"
        rlRun -t -c "$CLI compose delete $UUID"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
