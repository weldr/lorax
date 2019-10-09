#!/usr/bin/bash
# Note: execute this file from the project root directory
set -e

[ -z "$1" ] && (echo "$0: Missing path to iso"; exit 1)
[ -z "$2" ] && (echo "$0: Missing kickstart"; exit 1)
[ "$(id -u)" -eq 0 ] || (echo "$0 must be run as root"; exit 1)

. /usr/share/beakerlib/beakerlib.sh
CLI="${CLI:-./src/sbin/mkksiso}"

rlJournalStart
    rlPhaseStartSetup "Setup a fake root image"
        TMP_DIR=$(mktemp -d -p /var/tmp)
        rlRun -t -c "mkdir -p $TMP_DIR/fake-root/etc"
        rlRun -t -c "touch $TMP_DIR/fake-root/etc/passwd"
        rlRun -t -c "tar -cvaf $TMP_DIR/root.tar.xz -C $TMP_DIR/fake-root/ ."
    rlPhaseEnd

    rlPhaseStartTest "Make a new iso with kickstart and root.tar.xz"
        rlRun -t -c "$CLI --add $TMP_DIR/root.tar.xz $2 $1 $TMP_DIR/liveimg-boot.iso"
        rlAssertExists "$TMP_DIR/liveimg-boot.iso"
    rlPhaseEnd

    rlPhaseStartTest "Check the new ISO"
        ISO_DIR="$TMP_DIR/mnt-iso/"
        rlRun -t -c "mkdir $ISO_DIR"
        rlRun "mount $TMP_DIR/liveimg-boot.iso $ISO_DIR"
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
        rlLogInfo "Checking for root.tar.xz on iso"
        if [ ! -e "$TMP_DIR/root.tar.xz" ]; then
            rlLogError "The root.tar.xz file is missing from the iso"
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
