#!/bin/bash
# Script removes virtual machines older than HOURS_LIMIT (24 hours by default) from OpenStack

. /usr/share/beakerlib/beakerlib.sh


rlJournalStart
    rlPhaseStartSetup
        if [ -z "$OS_AUTH_URL" ]; then
            rlFail "OS_AUTH_URL is empty!"
        else
            rlLogInfo "OS_AUTH_URL=$OS_AUTH_URL"
        fi

        if [ -z "$OS_USERNAME" ]; then
            rlFail "OS_USERNAME is empty!"
        else
            rlLogInfo "OS_USERNAME is configured"
        fi

        if [ -z "$OS_PASSWORD" ]; then
            rlFail "OS_PASSWORD is empty!"
        else
            rlLogInfo "OS_PASSWORD is configured"
        fi

        # VMs older than HOURS_LIMIT will be deleted
        HOURS_LIMIT="${HOURS_LIMIT:-24}"
        export TIMESTAMP=`date -u -d "$HOURS_LIMIT hours ago" '+%FT%T'`

        rlLogInfo "HOURS_LIMIT=$HOURS_LIMIT"

        for package in ansible python3-openstacksdk; do
            if ! rlCheckRpm "$package"; then
                rlRun -t -c "dnf -y install $package"
                rlAssertRpm "$package"
            fi
        done
    rlPhaseEnd

    rlPhaseStartTest "Delete old VMs"
        PLAYBOOK="openstack_delete_old_vms.yml"
        cat > $PLAYBOOK << __EOF__
- name: Delete old VMs
  hosts: localhost
  gather_facts: False
  tasks:
  - name: Get VMs
    os_server_facts:

  - name: List all VMs
    debug:
      var: openstack_servers

  - name: Delete old VMs
    os_server:
      name: "{{item.id}}"
      state: absent
    loop: "{{openstack_servers}}"
    when: item.created < lookup('env','TIMESTAMP')
    loop_control:
      label: "{{item.name}} (id: {{item.id}})"
__EOF__

        rlLogInfo "Removing VMs created before $TIMESTAMP"
        rlRun -t -c "ansible-playbook $PLAYBOOK"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "rm -f $PLAYBOOK"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText

