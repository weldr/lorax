#!/usr/bin/bash
# Note: execute this file from the project root directory
set -e

[ -z "$1" ] && (echo "$0: Missing path to iso"; exit 1)
[ -z "$2" ] && (echo "$0: Missing kickstart"; exit 1)
[ "$(id -u)" -eq 0 ] || (echo "$0 must be run as root"; exit 1)

. /usr/share/beakerlib/beakerlib.sh
CLI="${CLI:-./src/sbin/mkksiso}"

rlJournalStart
    rlPhaseStartSetup "Setup repo with fake rpm"
        TMP_DIR=$(mktemp -d -p /var/tmp)
        rlRun -t -c "mkdir $TMP_DIR/extra-repo/"
        rlRun -t -c "$(dirname "$0")/mk-fake-rpm $TMP_DIR/extra-repo/ extra-package"
        rlRun -t -c "createrepo_c $TMP_DIR/extra-repo/"
    rlPhaseEnd

    rlPhaseStartTest "Make new iso with kickstart and extra-repo"
        rlRun -t -c "$CLI --add $TMP_DIR/extra-repo $2 $1 $TMP_DIR/ks-boot.iso"
        rlAssertExists "$TMP_DIR/ks-boot.iso"
    rlPhaseEnd

    rlPhaseStartTest "Check the new ISO"
        ISO_DIR="$TMP_DIR/mnt-iso/"
        rlRun -t -c "mkdir $ISO_DIR"
        rlRun "mount $TMP_DIR/ks-boot.iso $ISO_DIR"
        fail=0
        rlLogInfo "Checking for kickstart $(basename "$2")"
        if [ ! -e "$ISO_DIR$(basename "$2")" ]; then
            rlLogError "The kickstart is missing from the iso"
            fail=1
        fi
        for cfg in isolinux/isolinux.cfg EFI/BOOT/grub.cfg EFI/BOOT/BOOT.conf \
                   boot/grub/grub.cfg images/generic.prm; do
            if [ -e "$ISO_DIR$cfg" ]; then
                rlLogInfo "Checking $cfg"
                if ! grep -q "$(basename "$2")" "$ISO_DIR$cfg"; then
                    rlLogError "$cfg is missing the kickstart"
                    fail=1
                fi
            fi
        done
        rlLogInfo "Checking for /extra-repo/ on iso"
        if [ ! -e "$TMP_DIR/extra-repo/" ]; then
            rlLogError"The extra-repo directory is missing from the iso"
            fail=1
        fi
        rlAssertEquals "All checks have passed" $fail 0
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "umount $ISO_DIR"
        rlRun -t -c "rm -rf $TMP_DIR"
    rlPhaseEnd
rlJournalEnd
rlJournalPrintText
