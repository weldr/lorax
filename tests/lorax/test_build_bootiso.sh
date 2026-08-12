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

CLI="${CLI:-./src/bin/lorax}"
REPODIR="/etc/yum.repos.d"
test -f /usr/share/dnf5/repos.d/fedora.repo && REPODIR="/usr/share/dnf5/repos.d"

# Make up a name (slightly unsafe), should not exist before running lorax so use -u
rlJournalStart
    rlPhaseStartTest "Build lorax boot.iso"
        rlAssertEquals "SELinux operates in enforcing mode" "$(getenforce)" "Enforcing"
        lorax -p Fedora-Lorax-Test -v "$RELEASE" -r "$RELEASE" \
              --repo $REPODIR/fedora.repo \
              --repo $REPODIR/fedora-updates.repo \
              --sharedir "$SHARE_DIR" /var/tmp/test-results/
        rlAssertEquals "exit code should be zero" $? 0
        IMAGE="/var/tmp/test-results/images/boot.iso"
        rlAssertExists "$IMAGE"
    rlPhaseEnd
rlJournalEnd
rlJournalPrintText
