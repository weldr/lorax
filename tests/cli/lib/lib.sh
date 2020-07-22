#!/usr/bin/env bash

. /usr/share/beakerlib/beakerlib.sh

BACKEND="${BACKEND:-lorax-composer}"
export BACKEND

# Monkey-patch beakerlib to exit on first failure if COMPOSER_TEST_FAIL_FAST is
# set. https://github.com/beakerlib/beakerlib/issues/42
COMPOSER_TEST_FAIL_FAST=${COMPOSER_TEST_FAIL_FAST:-0}
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


setup_beakerlib_env() {
    export BEAKERLIB_DIR=$(mktemp -d /tmp/composer-test.XXXXXX)
    export BEAKERLIB_JOURNAL=0
}

run_beakerlib_tests() {
    if [ -z "$*" ]; then
        echo "run_beakerlib_tests() requires a test to execute"
    else
        # execute tests
        for TEST in "$@"; do
            $TEST
        done
    fi
}

parse_beakerlib_results() {
    if [ ! -f "$BEAKERLIB_DIR/TestResults" ]; then
        exit "$BEAKERLIB_DIR/TestResults not found" 1
    fi
    . $BEAKERLIB_DIR/TestResults

    TESTRESULT_RESULT_ECODE="${TESTRESULT_RESULT_ECODE:-}"
    if [ $TESTRESULT_RESULT_ECODE != 0 ]; then
      echo "Test failed. Leaving log in $BEAKERLIB_DIR"
      exit $TESTRESULT_RESULT_ECODE
    fi

    rm -rf $BEAKERLIB_DIR
}

export QEMU_BIN="/usr/bin/qemu-system-$(uname -m)"
export QEMU="$QEMU_BIN -machine accel=kvm:tcg"
export SSH_PORT=2222

boot_image() {
    QEMU_BOOT=$1
    TIMEOUT=$2
    rlRun -t -c "$QEMU -m 2048 $QEMU_BOOT -nographic -monitor none \
                 -net user,id=nic0,hostfwd=tcp::$SSH_PORT-:22 -net nic \
                 -chardev null,id=log0,mux=on,logfile=/var/log$TEST/qemu.log,logappend=on \
                 -serial chardev:log0 &"
    # wait for ssh to become ready (yes, http is the wrong protocol, but it returns the header)
    tries=0
    until curl --http0.9 -sS -m 15 "http://localhost:$SSH_PORT/" | grep 'OpenSSH'; do
        tries=$((tries + 1))
        if [ $tries -gt $TIMEOUT ]; then
            exit 1
        fi
        sleep 1
        echo "DEBUG: Waiting for ssh become ready before testing ..."
    done;
}

wait_for_composer() {
    tries=0
    until curl -m 15 --unix-socket /run/weldr/api.socket http://localhost:4000/api/status | grep 'db_supported.*true'; do
        tries=$((tries + 1))
        if [ $tries -gt 50 ]; then
            exit 1
        fi
        sleep 5
        echo "DEBUG: Waiting for backend API to become ready before testing ..."
    done;
}

composer_start() {
    local rc
    local params="$@"

    if [ "$BACKEND" == "lorax-composer" ] && [[ -z "$CLI" || "$CLI" == "./src/bin/composer-cli" ]]; then
        ./src/sbin/lorax-composer $params --sharedir $SHARE_DIR $BLUEPRINTS_DIR &
    elif [ "$BACKEND" == "lorax-composer" ] && [ -n "$params" ]; then
        /usr/sbin/lorax-composer $params /var/lib/lorax/composer/blueprints &
    else
        # socket stop/start seems to be necessary for a proper service restart
        # after a previous direct manual run for it to work properly
        systemctl start $BACKEND.socket
        systemctl start $BACKEND
    fi
    rc=$?

    # wait for the backend to become ready
    if [ "$rc" -eq 0 ]; then
        wait_for_composer
    else
        rlLogFail "Unable to start $BACKEND (exit code $rc)"
    fi
    return $rc
}

composer_stop() {
    MANUAL=${MANUAL:-0}
    # socket stop/start seems to be necessary for a proper service restart
    # after a previous direct manual run for it to work properly
    if systemctl list-units | grep -q $BACKEND.socket; then
        systemctl stop $BACKEND.socket
    fi

    if [[ -z "$CLI" || "$CLI" == "./src/bin/composer-cli" || "$MANUAL" == "1" ]]; then
        pkill -9 lorax-composer
        rm -f /run/weldr/api.socket
    else
        systemctl stop $BACKEND
    fi
}

# a generic helper function unifying the specific checks executed on a running
# image instance
verify_image() {
    SSH_USER="$1"
    SSH_MACHINE="$2"
    SSH_OPTS="-o StrictHostKeyChecking=no -o BatchMode=yes $3"
    rlLogInfo "verify_image: SSH_OPTS:'$SSH_OPTS' SSH_USER:'$SSH_USER' SSH_MACHINE: '$SSH_MACHINE'"
    check_root_account "$@"
    if [ "$CHECK_CMDLINE" != 0 ]; then
        check_kernel_cmdline "$@"
    fi
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

    # If you are connected as root you do not need sudo
    if [[ "$SSH_USER" == "root" ]]; then
        SUDO=""
    else
        SUDO="sudo"
    fi

    if [ $ROOT_ACCOUNT_LOCKED == 0 ]; then
        rlRun -t -c "ssh $SSH_OPTS ${SSH_USER}@${SSH_MACHINE} \"$SUDO passwd --status root | grep -E '^root\s+NP?'\"" \
            0 "Password for root account in /etc/shadow is empty"
    else
        # ssh returns 255 in case of any ssh error, so it's better to grep the specific error message
        rlRun -t -c "ssh $SSH_OPTS -o PubkeyAuthentication=no root@${SSH_MACHINE} 2>&1 | grep -i 'permission denied ('" \
            0 "Can't ssh to '$SSH_MACHINE' as root using password-based auth"
        rlRun -t -c "ssh $SSH_OPTS ${SSH_USER}@${SSH_MACHINE} \"$SUDO passwd --status root | grep -E '^root\s+LK?'\"" \
            0 "root account is disabled in /etc/shadow"
        rlRun -t -c "ssh $SSH_OPTS ${SSH_USER}@${SSH_MACHINE} \"$SUDO journalctl -g 'USER_LOGIN.*acct=\\\"root\\\".*terminal=ssh.*res=failed'\"" \
            0 "audit.log contains entry about unsuccessful root login"
        # We modify the default sshd settings on live ISO, so we can only check the default empty password setting
        # outside of live ISO
        rlRun -t -c "ssh $SSH_OPTS ${SSH_USER}@${SSH_MACHINE} '$SUDO grep -E \"^[[:blank:]]*PermitEmptyPasswords[[:blank:]]*yes\" /etc/ssh/sshd_config'" 1 \
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

# Wait until the compose is done (finished or failed)
wait_for_compose() {
    local UUID=$1
    if [ -n "$UUID" ]; then
        until $CLI compose info $UUID | grep 'FINISHED\|FAILED'; do
            sleep 20
            rlLogInfo "Waiting for compose to finish ..."
        done;
        check_compose_status "$UUID"

        rlRun -t -c "mkdir -p /var/log/$TEST"
        rlRun -t -c "$CLI compose logs $UUID"
        rlRun -t -c "mv $UUID-logs.tar /var/log/$TEST"
    else
        rlFail "Compose UUID is empty!"
    fi
}

