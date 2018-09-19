#!/bin/bash
# Note: execute this file from the project root directory

. /usr/share/beakerlib/beakerlib.sh

CLI="./src/bin/composer"


rlJournalStart
    rlPhaseStartTest "blueprints list"
        for bp in example-http-server example-development example-atlas; do
            rlAssertEquals "blueprint list finds $bp" \
                "`$CLI blueprints list | grep $bp`" "$bp"
        done
    rlPhaseEnd

    rlPhaseStartTest "blueprints save"
        rlRun -t -c "$CLI blueprints save example-http-server"
        rlAssertExists "example-http-server.toml"
        rlAssertGrep "example-http-server" "example-http-server.toml"
        rlAssertGrep "httpd" "example-http-server.toml"

        # non-existing blueprint
        rlRun -t -c "$CLI blueprints save non-existing-bp" 1
        rlAssertNotExists "non-existing-bp.toml"
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
        rlAssertEquals "pushed bp is found via list" "`$CLI blueprints list | grep beakerlib`" "beakerlib"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
