#!/usr/bin/env bash

check_root_account() {
# Try to SSH to a remote machine first using root account using password-based
# auth (this is expected to fail) and then using key-based auth with the
# supplied username to check content of /etc/shadow and audit.log.
#
# use: check_root_account <user> <machine> [ssh options]

    local ssh_opts="-o StrictHostKeyChecking=no $3"
    local user="$1"
    local machine="$2"
    if [[ "$user" == "" || "$machine" == "" ]]; then
        rlFail "check_root_account: Missing user or machine parameter."
        return 1
    fi

    if [ $ROOT_ACCOUNT_LOCKED == 0 ]; then
        rlRun -t -c "ssh $ssh_opts ${user}@${machine} \"sudo grep '^root::' /etc/shadow\"" \
            0 "Password for root account in /etc/shadow is empty"
    else
        # ssh returns 255 in case of any ssh error, so it's better to grep the specific error message
        rlRun -t -c "ssh $ssh_opts -o PubkeyAuthentication=no root@${machine} 2>&1 | grep -i 'permission denied ('" \
            0 "Can't ssh to '$machine' as root using password-based auth"
        rlRun -t -c "ssh $ssh_opts ${user}@${machine} \"sudo grep -E '^root:(\*LOCK\*|!):' /etc/shadow\"" \
            0 "root account is disabled in /etc/shadow"
        rlRun -t -c "ssh $ssh_opts ${user}@${machine} \"sudo grep 'USER_LOGIN.*acct=\\\"root\\\".*terminal=ssh.*res=failed' /var/log/audit/audit.log\"" \
            0 "audit.log contains entry about unsuccessful root login"
        # We modify the default sshd settings on live ISO, so we can only check the default empty password setting
        # outside of live ISO
        rlRun -t -c "ssh $ssh_opts ${user}@${machine} 'grep -E \"^[[:blank:]]*PermitEmptyPasswords[[:blank:]]*yes\" /etc/ssh/sshd_config'" 1 \
            "Login with empty passwords is disabled in sshd config file"
    fi
    rlRun -t -c "ssh $ssh_opts ${user}@${machine} 'cat /etc/redhat-release'"

}

