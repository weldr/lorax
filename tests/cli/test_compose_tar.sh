#!/bin/bash
# Note: execute this file from the project root directory

#####
#
# Builds tar images and tests them with Docker and systemd-nspawn
#
#####

. /usr/share/beakerlib/beakerlib.sh

CLI="${CLI:-./src/bin/composer-cli}"


rlJournalStart
    rlPhaseStartSetup
        rlAssertExists /usr/bin/docker
    rlPhaseEnd

    rlPhaseStartTest "compose start"
        rlAssertEquals "SELinux operates in enforcing mode" "$(getenforce)" "Enforcing"
        UUID=`$CLI compose start example-http-server tar`
        rlAssertEquals "exit code should be zero" $? 0

        UUID=`echo $UUID | cut -f 2 -d' '`
    rlPhaseEnd

    rlPhaseStartTest "compose finished"
        if [ -n "$UUID" ]; then
            until $CLI compose details $UUID | grep FINISHED; do
                sleep 10
                rlLogInfo "Waiting for compose to finish ..."
            done;
        else
            rlFail "Compose UUID is empty!"
        fi

        rlRun -t -c "$CLI compose image $UUID"
        IMAGE="$UUID-root.tar.xz"
    rlPhaseEnd

    rlPhaseStartTest "Verify tar image with Docker"
        rlRun -t -c "docker import $IMAGE composer/$UUID:latest"

        # verify we can run a container with this image
        rlRun -t -c "docker run -it --rm --entrypoint /usr/bin/cat composer/$UUID /etc/redhat-release"
    rlPhaseEnd

    rlPhaseStartTest "Verify tar image with systemd-nspawn"
        if [ -f /usr/bin/systemd-nspawn ]; then
            NSPAWN_DIR=`mktemp -d /tmp/nspawn.XXXX`
            rlRun -t -c "tar -xJvf $IMAGE -C $NSPAWN_DIR"

            # verify we can run a container with this image
            rlRun -t -c "systemd-nspawn -D $NSPAWN_DIR cat /etc/redhat-release"
        else
            rlLogInfo "systemd-nspawn not found!"
        fi
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "rm -rf $IMAGE $NSPAWN_DIR"
        rlRun -t -c "$CLI compose delete $UUID"
        rlRun -t -c "docker rmi composer/$UUID"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
