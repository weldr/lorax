#!/usr/bin/env bash
# lorax specific functions

. "$(dirname $0)/../lib/lib.sh"

# a generic helper function unifying the specific checks executed on a running
# image instance
verify_image() {
    SSH_USER="$1"
    SSH_MACHINE="$2"
    SSH_OPTS+=" $3"
    rlLogInfo "verify_image: SSH_OPTS:'$SSH_OPTS' SSH_USER:'$SSH_USER' SSH_MACHINE: '$SSH_MACHINE'"
    is_anaconda_installed "$@"
}

is_anaconda_installed() {
        rlRun -t -c "ssh $SSH_OPTS ${SSH_USER}@${SSH_MACHINE} \"grep anaconda /root/lorax-packages.log\"" 0 "Anaconda is installed"
}
