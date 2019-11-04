#!/bin/bash
# Note: execute this file from the project root directory

#####
#
# Builds a boot.iso with lorax
#
#####

set -e

. /usr/share/beakerlib/beakerlib.sh
. "$(dirname $0)/lib/lib.sh"

CLI="${CLI:-./src/sbin/lorax}"

# Make up a name (slightly unsafe), should not exist before running lorax so use -u
rlJournalStart
    rlPhaseStartTest "Build lorax boot.iso"
        rlAssertEquals "SELinux operates in enforcing mode" "$(getenforce)" "Enforcing"
        lorax -p Fedora-Lorax-Test -v "$RELEASE" -r "$RELEASE" \
              --repo /etc/yum.repos.d/fedora.repo \
              --sharedir "$SHARE_DIR" /var/tmp/test-results/
        rlAssertEquals "exit code should be zero" $? 0
        IMAGE="/var/tmp/test-results/images/boot.iso"
        rlAssertExists "$IMAGE"
    rlPhaseEnd
rlJournalEnd
rlJournalPrintText
