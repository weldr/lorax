#!/bin/bash
# Script removes virtual machines and other artifacts older than HOURS_LIMIT (24 hours by default) from OpenStack

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

        export OS_PROJECT_NAME="${OS_PROJECT_NAME:-$OS_USERNAME}"
        rlLogInfo "OS_PROJECT_NAME=$OS_PROJECT_NAME"

        # VMs older than HOURS_LIMIT will be deleted
        HOURS_LIMIT="${HOURS_LIMIT:-24}"
        export TIMESTAMP=`date -u -d "$HOURS_LIMIT hours ago" '+%FT%T'`

        rlLogInfo "HOURS_LIMIT=$HOURS_LIMIT"

        for package in ansible python3-openstacksdk python3-openstackclient; do
            if ! rlCheckRpm "$package"; then
                rlRun -t -c "dnf -y install $package"
                rlAssertRpm "$package"
            fi
        done

        PLAYBOOK_DELETE_VMS=`mktemp`
        PLAYBOOK_DELETE_IMAGES=`mktemp`
    rlPhaseEnd

    rlPhaseStartTest "Delete old VMs"
# The openstack_servers variable used in the playbook bellow is set by the os_server_facts ansible module.
# The variable contains details about all discovered virtual machines.
# See https://docs.ansible.com/ansible/latest/modules/os_server_facts_module.html
        cat > $PLAYBOOK_DELETE_VMS << __EOF__
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
      label: "{{item.name}} (id: {{item.id}} created: {{item.created}})"
__EOF__

        rlLogInfo "Removing VMs created before $TIMESTAMP"
        rlRun -t -c "ansible-playbook $PLAYBOOK_DELETE_VMS"
    rlPhaseEnd

    rlPhaseStartTest "Delete old images"
# The openstack_image variable used in the playbook bellow is set by the os_image_facts ansible module.
# The variable contains details about all discovered images.
# See https://docs.ansible.com/ansible/latest/modules/os_image_facts_module.html
        cat > $PLAYBOOK_DELETE_IMAGES << __EOF__
- name: Delete old images
  hosts: localhost
  gather_facts: False
  tasks:
  - name: Get images
    os_image_facts:

  - name: Delete old images
    os_image:
      name: "{{item.name}}"
      id: "{{item.id}}"
      state: absent
    loop: "{{openstack_image}}"
    when: (item.created_at < lookup('env','TIMESTAMP')) and (item.name | regex_search('Composer-[a-f0-9-]{36}-Automated-Import'))
    loop_control:
      label: "{{item.name}} (id: {{item.id}} created: {{item.created_at}})"
__EOF__

        rlLogInfo "Removing images created before $TIMESTAMP"
        rlRun -t -c "ansible-playbook $PLAYBOOK_DELETE_IMAGES"
    rlPhaseEnd

    rlPhaseStartTest "Delete old volumes"
        volume_list=`openstack-3 volume list --format value --column ID`
        for volume in $volume_list; do
            creation_date=`openstack-3 volume show $volume --column created_at --format value`
            if [ $? -ne 0 ]; then
                rlLogWarning "Failed to get the creation date of volume $volume"
                continue
            fi

            # The format of the date/time returned by openstack-3 looks like this:
            # 2019-01-22T18:50:14.000000
            # The TIMESTAMP variable format is:
            # 2019-01-21T18:45:36
            # "<" does a lexicographic comparison using the character collating sequence
            # specified by the ‘LC_COLLATE’ locale. "<" needs to be escaped, otherwise
            # it's a symbol for redirection.
            if [ "$creation_date" \< "$TIMESTAMP" ]; then
                rlLogInfo "Removing old volume $volume created $creation_date"
                rlRun -t -c "openstack-3 volume delete $volume"
            fi
        done
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "rm -f $PLAYBOOK_DELETE_VMS"
        rlRun -t -c "rm -f $PLAYBOOK_DELETE_IMAGES"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText

