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

boot_image() {
    QEMU_BOOT=$1
    TIMEOUT=$2
    # This runs inside a VM, use as little resources as possible
    rlRun -t -c "$QEMU -m 1024 -cpu host $QEMU_BOOT -nographic -monitor none \
                       -net user,id=nic0,hostfwd=tcp::$SSH_PORT-:22 -net nic &"
    # wait for ssh to become ready (yes, http is the wrong protocol, but it returns the header)
    tries=0
    until curl -sS -m 15 "http://localhost:$SSH_PORT/" | grep 'OpenSSH'; do
        tries=$((tries + 1))
        if [ $tries -gt $TIMEOUT ]; then
            exit 1
        fi
        sleep 1
        echo "DEBUG: Waiting for ssh become ready before testing ..."
    done;
}
