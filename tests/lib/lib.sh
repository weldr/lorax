#!/usr/bin/env bash
# Common settings and functions for ./cli/ and ./lorax/ test scripts

export SSH_OPTS="-o StrictHostKeyChecking=no"
export SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes"
export SSH_PORT=2223

QEMU_BIN="/usr/bin/qemu-system-$(uname -m)"
export QEMU_BIN
export QEMU="$QEMU_BIN -machine accel=kvm:tcg"


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

