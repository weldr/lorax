#!/bin/bash
# Note: execute this file from the project root directory

. /usr/share/beakerlib/beakerlib.sh

CLI="./src/bin/composer-cli"


rlJournalStart
    rlPhaseStartTest "blueprints list"
        for bp in http-server development atlas; do
            rlRun -t -c "$CLI blueprints list | grep $bp"
        done
    rlPhaseEnd

    rlPhaseStartTest "blueprints save"
        rlRun -t -c "$CLI blueprints save http-server"
        rlAssertExists "http-server.toml"
        rlAssertGrep "http-server" "http-server.toml"
        rlAssertGrep "httpd" "http-server.toml"

        # non-existing blueprint
# enable test for https://github.com/weldr/lorax/issues/460
#        rlRun -t -c "$CLI blueprints save non-existing-bp" 1
#        rlAssertNotExists "non-existing-bp.toml"
    rlPhaseEnd

    rlPhaseStartTest "blueprints push"

        cat > beakerlib.toml << __EOF__
name = "beakerlib"
description = "Start building tests with beakerlib."
version = "0.0.1"

[[modules]]
name = "beakerlib"
version = "*"
__EOF__

        rlRun -t -c "$CLI blueprints push beakerlib.toml"
        rlRun -t -c "$CLI blueprints list | grep beakerlib"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
