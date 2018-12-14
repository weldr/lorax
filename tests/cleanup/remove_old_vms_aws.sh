#!/bin/bash
# Script removes virtual machines older than HOURS_LIMIT (24 hours by default) from Amazon EC2

. /usr/share/beakerlib/beakerlib.sh


rlJournalStart
    rlPhaseStartSetup
        if [ -z "$AWS_ACCESS_KEY_ID" ]; then
            rlFail "AWS_ACCESS_KEY_ID is empty!"
        else
            rlLogInfo "AWS_ACCESS_KEY_ID is configured"
        fi

        if [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
            rlFail "AWS_SECRET_ACCESS_KEY is empty!"
        else
            rlLogInfo "AWS_SECRET_ACCESS_KEY is configured"
        fi

        # VMs older than HOURS_LIMIT will be deleted
        HOURS_LIMIT="${HOURS_LIMIT:-24}"
        export TIMESTAMP=`date -u -d "$HOURS_LIMIT hours ago" '+%FT%T'`
        export AWS_REGION="${AWS_REGION:-us-east-1}"

        rlLogInfo "HOURS_LIMIT=$HOURS_LIMIT"
        rlLogInfo "AWS_REGION=$AWS_REGION"

        for package in ansible python3-boto3; do
            if ! rlCheckRpm "$package"; then
                rlRun -t -c "dnf -y install $package"
                rlAssertRpm "$package"
            fi
        done
    rlPhaseEnd

    rlPhaseStartTest "Delete old VMs"
        PLAYBOOK="aws_delete_old_vms.yml"
        cat > $PLAYBOOK << __EOF__
- name: Delete old VMs
  hosts: localhost
  gather_facts: False
  tasks:
  - name: Get VMs
    ec2_instance_facts:
    register: vms_facts

  - name: List all VMs
    debug:
      var: vms_facts

  - name: Delete old VMs
    ec2_instance:
      instance_ids: "{{item.instance_id}}"
      state: absent
    loop: "{{vms_facts.instances}}"
    when: item.launch_time < lookup('env','TIMESTAMP')
    loop_control:
      label: "{{item.instance_id}}"
__EOF__

        rlLogInfo "Removing VMs created before $TIMESTAMP"
        rlRun -t -c "ansible-playbook $PLAYBOOK"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "rm -f $PLAYBOOK"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
