#!/usr/bin/env bash

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

export QEMU_BIN="/usr/bin/qemu-system-$(uname -m)"
export QEMU="$QEMU_BIN -machine accel=kvm:tcg"
export SSH_PORT=2222

boot_image() {
    QEMU_BOOT=$1
    TIMEOUT=$2
    rlRun -t -c "$QEMU -m 2048 $QEMU_BOOT -nographic -monitor none \
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


# a generic helper function unifying the specific checks executed on a running
# image instance
verify_image() {
    SSH_USER="$1"
    SSH_MACHINE="$2"
    SSH_OPTS="-o StrictHostKeyChecking=no $3"
    rlLogInfo "verify_image: SSH_OPTS:'$SSH_OPTS' SSH_USER:'$SSH_USER' SSH_MACHINE: '$SSH_MACHINE'"
    check_root_account "$@"
    check_kernel_cmdline "$@"
}

check_root_account() {
# Try to SSH to a remote machine first using root account using password-based
# auth (this is expected to fail) and then using key-based auth with the
# supplied username to check content of /etc/shadow and audit.log.
#
# use: check_root_account <user> <machine> [ssh options]

    ROOT_ACCOUNT_LOCKED=${ROOT_ACCOUNT_LOCKED:-1}
    if [[ "$SSH_USER" == "" || "$SSH_MACHINE" == "" ]]; then
        rlFail "check_root_account: Missing user or machine parameter."
        return 1
    fi

    if [ $ROOT_ACCOUNT_LOCKED == 0 ]; then
        rlRun -t -c "ssh $SSH_OPTS ${SSH_USER}@${SSH_MACHINE} \"sudo grep '^root::' /etc/shadow\"" \
            0 "Password for root account in /etc/shadow is empty"
    else
        # ssh returns 255 in case of any ssh error, so it's better to grep the specific error message
        rlRun -t -c "ssh $SSH_OPTS -o PubkeyAuthentication=no root@${SSH_MACHINE} 2>&1 | grep -i 'permission denied ('" \
            0 "Can't ssh to '$SSH_MACHINE' as root using password-based auth"
        rlRun -t -c "ssh $SSH_OPTS ${SSH_USER}@${SSH_MACHINE} \"sudo passwd --status root | grep -E '^root\s+LK?'\"" \
            0 "root account is disabled in /etc/shadow"
        rlRun -t -c "ssh $SSH_OPTS ${SSH_USER}@${SSH_MACHINE} \"sudo grep 'USER_LOGIN.*acct=\\\"root\\\".*terminal=ssh.*res=failed' /var/log/audit/audit.log\"" \
            0 "audit.log contains entry about unsuccessful root login"
        # We modify the default sshd settings on live ISO, so we can only check the default empty password setting
        # outside of live ISO
        rlRun -t -c "ssh $SSH_OPTS ${SSH_USER}@${SSH_MACHINE} 'sudo grep -E \"^[[:blank:]]*PermitEmptyPasswords[[:blank:]]*yes\" /etc/ssh/sshd_config'" 1 \
            "Login with empty passwords is disabled in sshd config file"
    fi
    rlRun -t -c "ssh $SSH_OPTS ${SSH_USER}@${SSH_MACHINE} 'cat /etc/redhat-release'"
}

# verify that a kernel command line argument was passed from the blueprint (this is added to the blueprint in ../test_cli.sh)
check_kernel_cmdline() {
    rlRun -t -c "ssh $SSH_OPTS ${SSH_USER}@${SSH_MACHINE} 'grep custom_cmdline_arg /proc/cmdline'" 0 \
        "System booted from the image contains specified parameter on kernel command line"
}

# Fail if the compose failed, only call after checking for FINISHED|FAILED
check_compose_status() {
    UUID="$1"
    if "$CLI" compose info "$UUID" | grep FAILED; then
        rlFail "compose $UUID FAILED"
        return 1
    fi
}
