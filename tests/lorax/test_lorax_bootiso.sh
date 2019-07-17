#!/bin/bash
# Note: execute this file from the project root directory

#####
#
# Builds a boot.iso with lorax and boots it with QEMU
#
#####

set -e

. /usr/share/beakerlib/beakerlib.sh

CLI="${CLI:-./src/sbin/lorax}"

QEMU_BIN="/usr/bin/qemu-system-$(uname -m)"
QEMU="$QEMU_BIN -machine accel=kvm:tcg"

SSH_USER="root"
SSH_MACHINE="localhost"
SSH_PORT=2223
SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -p $SSH_PORT"


# Monkey-patch beakerlib to exit on first failure if COMPOSER_TEST_FAIL_FAST is
# set. https://github.com/beakerlib/beakerlib/issues/42
if [ "$COMPOSER_TEST_FAIL_FAST" == "1" ]; then
  eval "original$(declare -f __INTERNAL_LogAndJournalFail)"

  __INTERNAL_LogAndJournalFail () {
    original__INTERNAL_LogAndJournalFail

    # end test somewhat cleanly so that beakerlib logs the FAIL correctly
    rlPhaseEnd
    rlJournalEnd

    exit 1
  }
fi

# Make up a name (slightly unsafe), should not exist before running lorax so use -u
OUTPUT_DIR=$(mktemp -d -u '/var/tmp/lorax-output.XXXXX')
rlJournalStart
    rlPhaseStartSetup
        rlAssertExists "$QEMU_BIN"
    rlPhaseEnd

    rlPhaseStartTest "Build lorax boot.iso"
        rlAssertEquals "SELinux operates in enforcing mode" "$(getenforce)" "Enforcing"

        # Start the test with LORAX_IMAGE pointing to a boot.iso to skip the build step
        if [ -z "$LORAX_IMAGE" ]; then
            lorax -p Fedora-Lorax-Test -v "$RELEASE" -r "$RELEASE" \
                  --repo /etc/yum.repos.d/fedora.repo \
                  --sharedir "$SHARE_DIR" "$OUTPUT_DIR"
            rlAssertEquals "exit code should be zero" $? 0
            IMAGE="$OUTPUT_DIR/images/boot.iso"
        else
            IMAGE="$LORAX_IMAGE"
        fi
    rlPhaseEnd

    rlPhaseStartTest "Boot the boot.iso"
        rlRun -t -c "$QEMU -m 2048 -cdrom $IMAGE -nographic -monitor none \
                           -net user,id=nic0,hostfwd=tcp::$SSH_PORT-:22 -net nic &"
        # wait for ssh to become ready (yes, http is the wrong protocol, but it returns the header)
        tries=0
        until curl -m 15 http://localhost:$SSH_PORT/ | grep 'OpenSSH'; do
            tries=$((tries + 1))
            if [ $tries -gt 60 ]; then
                exit 1
            fi
            sleep 1
            echo "DEBUG: Waiting for ssh become ready before testing ..."
        done;
    rlPhaseEnd

    rlPhaseStartTest "Verify VM instance"
        # Check to see if anaconda is installed in the image
        rlRun -t -c "ssh $SSH_OPTS ${SSH_USER}@${SSH_MACHINE} \"grep anaconda /root/lorax-packages.log\"" 0 "Anaconda is installed"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "killall -9 qemu-system-$(uname -m)"
        rlRun -t -c "rm -rf $OUTPUT_DIR"
    rlPhaseEnd
rlJournalEnd
rlJournalPrintText
