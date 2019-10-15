#!/bin/bash
# Note: execute this file from the project root directory

#####
#
# Builds live-iso image and test it with QEMU-KVM
#
#####

set -e

. /usr/share/beakerlib/beakerlib.sh
. $(dirname $0)/lib/lib.sh

CLI="${CLI:-./src/bin/composer-cli}"

rlJournalStart
    rlPhaseStartTest "compose start"
        rlAssertEquals "SELinux operates in enforcing mode" "$(getenforce)" "Enforcing"

        TMP_DIR=$(mktemp -d /tmp/composer.XXXXX)
        SSH_KEY_DIR=$(mktemp -d /tmp/composer-ssh-keys.XXXXXX)

        rlRun -t -c "ssh-keygen -t rsa -N '' -f $SSH_KEY_DIR/id_rsa"
        PUB_KEY=$(cat "$SSH_KEY_DIR/id_rsa.pub")

        cat > "$TMP_DIR/with-ssh.toml" << __EOF__
name = "with-ssh"
description = "HTTP image with SSH"
version = "0.0.1"

[[packages]]
name = "httpd"
version = "*"

[[packages]]
name = "openssh-server"
version = "*"

[[packages]]
name = "beakerlib"
version = "*"

[customizations.services]
enabled = ["sshd"]

[[customizations.user]]
name = "root"
key = "$PUB_KEY"

[customizations.kernel]
append = "custom_cmdline_arg"
__EOF__

        rlRun -t -c "$CLI blueprints push $TMP_DIR/with-ssh.toml"

        # NOTE: live-iso.ks explicitly disables sshd but test_cli.sh enables it
        UUID=$($CLI compose start with-ssh live-iso)
        rlAssertEquals "exit code should be zero" $? 0

        UUID=$(echo "$UUID" | cut -f 2 -d' ')
    rlPhaseEnd

    rlPhaseStartTest "compose finished"
        wait_for_compose "$UUID"

        # Save the results for boot test
        rlAssertExists "/var/lib/lorax/composer/results/$UUID/live.iso"
        rlRun -t -c "mkdir -p /var/tmp/test-results/"
        rlRun -t -c "cp /var/lib/lorax/composer/results/$UUID/live.iso /var/tmp/test-results/"
        # Include the ssh key needed to log into the image
        rlRun -t -c "cp $SSH_KEY_DIR/* /var/tmp/test-results"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "$CLI compose delete $UUID"
        rlRun -t -c "rm -rf $TMP_DIR $SSH_KEY_DIR"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
