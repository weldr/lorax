#!/bin/bash
# Note: execute this file from the project root directory

#####
#
# Builds a boot.iso with lorax and boots it with QEMU
#
#####

set -e

. /usr/share/beakerlib/beakerlib.sh
. "$(dirname $0)/lib/lib.sh"

CLI="${CLI:-./src/sbin/lorax}"


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
        boot_image "-boot d -cdrom $IMAGE" 60
    rlPhaseEnd

    rlPhaseStartTest "Verify VM instance"
        # Check to see if anaconda is installed in the image
        verify_image root localhost "-p $SSH_PORT"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "killall -9 qemu-system-$(uname -m)"
        rlRun -t -c "rm -rf $OUTPUT_DIR"
    rlPhaseEnd
rlJournalEnd
rlJournalPrintText
