#!/bin/bash
# Note: execute this file from the project root directory

#####
#
# Builds qcow2 images and tests them with QEMU-KVM
#
#####

. /usr/share/beakerlib/beakerlib.sh

CLI="${CLI:-./src/bin/composer-cli}"
QEMU="/usr/libexec/qemu-kvm"

rlJournalStart
    rlPhaseStartSetup
        rlAssertExists $QEMU
    rlPhaseEnd

    rlPhaseStartTest "compose start"
        rlAssertEquals "SELinux operates in enforcing mode" "$(getenforce)" "Enforcing"

        TMP_DIR=`mktemp -d /tmp/composer.XXXXX`
        SSH_KEY_DIR=`mktemp -d /tmp/composer-ssh-keys.XXXXXX`

        rlRun -t -c "ssh-keygen -t rsa -N '' -f $SSH_KEY_DIR/id_rsa"
        PUB_KEY=`cat $SSH_KEY_DIR/id_rsa.pub`

        cat > $TMP_DIR/with-ssh.toml << __EOF__
name = "with-ssh"
description = "HTTP image with SSH"
version = "0.0.1"

[[modules]]
name = "httpd"
version = "*"

[[packages]]
name = "openssh-server"
version = "*"

[[customizations.user]]
name = "root"
key = "$PUB_KEY"
__EOF__

        rlRun -t -c "$CLI blueprints push $TMP_DIR/with-ssh.toml"

        UUID=`$CLI compose start with-ssh qcow2`
        rlAssertEquals "exit code should be zero" $? 0

        UUID=`echo $UUID | cut -f 2 -d' '`
    rlPhaseEnd

    rlPhaseStartTest "compose finished"
        if [ -n "$UUID" ]; then
            until $CLI compose details $UUID | grep FINISHED; do
                sleep 20
                rlLogInfo "Waiting for compose to finish ..."
            done;
        else
            rlFail "Compose UUID is empty!"
        fi

        rlRun -t -c "$CLI compose image $UUID"
        IMAGE="$UUID-disk.qcow2"
    rlPhaseEnd

    rlPhaseStartTest "Start VM instance"
        rlRun -t -c "$QEMU -m 2048 -boot c -hda $IMAGE -nographic \
                           -net user,id=nic0,hostfwd=tcp::2222-:22 -net nic &"
        sleep 60
    rlPhaseEnd

    rlPhaseStartTest "Verify VM instance"
        # verify we can login into that instance and root account is disabled
        . ./tests/cli/lib/root_account.sh
        check_root_account $CLOUD_USER $IP_ADDRESS "-i $SSH_KEY_DIR/id_rsa -p 2222"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "killall -9 qemu-system"
        rlRun -t -c "$CLI compose delete $UUID"
        rlRun -t -c "rm -rf $IMAGE $TMP_DIR $SSH_KEY_DIR"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
