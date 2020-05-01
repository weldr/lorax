#!/bin/bash
# Note: execute this file from the project root directory

set -e

. /usr/share/beakerlib/beakerlib.sh
. $(dirname $0)/lib/lib.sh

CLI="${CLI:-./src/bin/composer-cli}"


rlJournalStart
    rlPhaseStartTest "blueprints list"
        if [ "$BACKEND" != "osbuild-composer" ]; then
            for bp in example-http-server example-development example-atlas; do
                rlAssertEquals "blueprint list finds $bp" \
                    "`$CLI blueprints list | grep $bp`" "$bp"
            done
        fi

        rlRun -t -c "$CLI blueprints push $(dirname $0)/lib/test-http-server.toml"
    rlPhaseEnd

    rlPhaseStartTest "blueprints save"
        rlRun -t -c "$CLI blueprints save test-http-server"
        rlAssertExists "test-http-server.toml"
        rlAssertGrep "test-http-server" "test-http-server.toml"
        rlAssertGrep "httpd" "test-http-server.toml"

        # non-existing blueprint
        rlRun -t -c "$CLI blueprints save non-existing-bp" 1
        rlAssertNotExists "non-existing-bp.toml"
    rlPhaseEnd

    rlPhaseStartTest "blueprints push"

        BLUEPRINT_NAME="openssh-server"
        cat > $BLUEPRINT_NAME.toml << __EOF__
name = "$BLUEPRINT_NAME"
description = "Simple blueprint including only openssh"
version = "0.0.1"
modules = []
groups = []
[[packages]]
name = "openssh-server"
version = "*"
__EOF__

        rlRun -t -c "$CLI blueprints push $BLUEPRINT_NAME.toml"
        rlAssertEquals "pushed bp is found via list" "`$CLI blueprints list | grep $BLUEPRINT_NAME`" "$BLUEPRINT_NAME"
    rlPhaseEnd

    rlPhaseStartTest "blueprints show"
        $CLI blueprints show $BLUEPRINT_NAME > shown-$BLUEPRINT_NAME.toml
        rlRun -t -c "$(dirname $0)/lib/toml-compare $BLUEPRINT_NAME.toml shown-$BLUEPRINT_NAME.toml"
    rlPhaseEnd

    rlPhaseStartTest "SemVer .patch version is incremented automatically"
        # version is still 0.0.1
        rlAssertEquals "version is 0.0.1" "`$CLI blueprints show $BLUEPRINT_NAME | grep 0.0.1`" 'version = "0.0.1"'
        # add a new package to the existing blueprint
        cat >> $BLUEPRINT_NAME.toml << __EOF__

[[packages]]
name = "php"
version = "*"
__EOF__
        # push again
        rlRun -t -c "$CLI blueprints push $BLUEPRINT_NAME.toml"
        # official documentation says:
        # If a new blueprint is uploaded with the same version the server will
        # automatically bump the PATCH level of the version. If the version
        # doesn't match it will be used as is.
        rlAssertEquals "version is 0.0.2" "`$CLI blueprints show $BLUEPRINT_NAME | grep 0.0.2`" 'version = "0.0.2"'
    rlPhaseEnd

    rlPhaseStartTest "blueprints delete"
        rlRun -t -c "$CLI blueprints delete $BLUEPRINT_NAME"
        rlAssertEquals "bp not found after delete" "`$CLI blueprints list | grep $BLUEPRINT_NAME`" ""
    rlPhaseEnd

    rlPhaseStartTest "start a compose with deleted blueprint"
        cat > to-be-deleted.toml << __EOF__
name = "to-be-deleted"
description = "Dummy blueprint for testing compose start with a deleted blueprint"
version = "0.0.1"
__EOF__

        rlRun -t -c "$CLI blueprints push to-be-deleted.toml"
        rlRun -t -c "$CLI blueprints delete to-be-deleted"
        rlRun -t -c "$CLI compose list | grep to-be-deleted" 1
        rlRun -t -c "$CLI blueprints list | grep to-be-deleted" 1
        compose_id=$($CLI compose start to-be-deleted tar)
        rlAssertEquals "composer-cli exited with 1 when starting a compose using a deleted blueprint" "$?" "1"
        compose_id=$(echo $compose_id | cut -f 2 -d' ')

        if [ -z "$compose_id" ]; then
            rlPass "It wasn't possible to start a compose using a deleted blueprint."
        else
            rlFail "It was possible to start a compose using a deleted blueprint!"
            # don't wait for the compose to finish if it started unexpectedly, and do cleanup
            rlRun -t -c "$CLI compose cancel $compose_id"
            rlRun -t -c "$CLI compose delete $compose_id"
        fi

        rlRun -t -c "rm -f to-be-deleted.toml"
        unset compose_id
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "rm *.toml"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
