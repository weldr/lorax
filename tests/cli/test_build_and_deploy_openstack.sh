#!/bin/bash
# Note: execute this file from the project root directory

#####
#
# Make sure we can build an image and deploy it inside vSphere!
#
#####

. /usr/share/beakerlib/beakerlib.sh

CLI="./src/bin/composer-cli"


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
            rlLogInfo "OS_USERNAME=$OS_USERNAME"
        fi

        export OS_TENANT_NAME="${OS_TENANT_NAME:-$OS_USERNAME}"
        rlLogInfo "OS_TENANT_NAME=$OS_TENANT_NAME"

        if [ -z "$OS_PASSWORD" ]; then
            rlFail "OS_PASSWORD is empty!"
        else
            rlLogInfo "OS_PASSWORD is configured"
        fi

        if ! rlCheckRpm "python3-pip"; then
            rlRun -t -c "dnf -y install python3-pip"
            rlAssertRpm python3-pip
        fi

        rlRun -t -c "pip3 install ansible openstacksdk"
    rlPhaseEnd

    rlPhaseStartTest "compose start"
        UUID=`$CLI compose start example-http-server openstack`
        rlAssertEquals "exit code should be zero" $? 0

        UUID=`echo $UUID | cut -f 2 -d' '`
    rlPhaseEnd

    rlPhaseStartTest "compose finished"
        if [ -n "$UUID" ]; then
            until $CLI compose info $UUID | grep FINISHED; do
                rlLogInfo "Waiting for compose to finish ..."
                sleep 30
            done;
        else
            rlFail "Compose UUID is empty!"
        fi
    rlPhaseEnd

    rlPhaseStartTest "Upload QCOW2 image to OpenStack"
        rlRun -t -c "$CLI compose image $UUID"
        IMAGE="$UUID-disk.qcow2"
        OS_IMAGE_NAME="Composer-$UUID-Automated-Import"

        response=`ansible localhost -m os_image -a "name=$OS_IMAGE_NAME filename=$IMAGE is_public=no"`
        rlAssert0 "Image upload successfull" $?
        rlLogInfo "$response"

        OS_IMAGE_UUID=`echo "$response" | grep '"changed": true' -A1  | grep '"id":' | cut -d'"' -f4`
        rlLogInfo "OS_IMAGE_UUID=$OS_IMAGE_UUID"
    rlPhaseEnd

    rlPhaseStartTest "Start VM instance"
        VM_NAME="Composer-Auto-VM-$UUID"

        if [ ! -f ~/.ssh/id_rsa.pub ]; then
            rlRun -t -c "ssh-keygen -t rsa -N '' -f ~/.ssh/id_rsa"
        fi
        rlRun -t -c "ansible localhost -m os_keypair -a 'name=$VM_NAME-key public_key_file=$(readlink -f ~/.ssh/id_rsa.pub)'"

        response=`ansible localhost -m os_server -a "name=$VM_NAME image=$OS_IMAGE_UUID flavor=t2.medium key_name=$VM_NAME-key auto_ip=yes"`
        rlAssert0 "VM started successfully" $?
        rlLogInfo "$response"

        IP_ADDRESS=`echo "$response" | grep '"OS-EXT-IPS:type": "floating"' -A1 | grep '"addr":' | cut -f4 -d'"'`
        rlLogInfo "Running instance IP_ADDRESS=$IP_ADDRESS"

        rlLogInfo "Waiting 60sec for instance to initialize ..."
        sleep 60
    rlPhaseEnd

    rlPhaseStartTest "Verify VM instance"
        # verify we can login into that instance
        rlRun -t -c "ssh -oStrictHostKeyChecking=no cloud-user@$IP_ADDRESS 'cat /etc/redhat-release'"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "ansible localhost -m os_keypair -a 'name=$VM_NAME-key state=absent'"
        rlRun -t -c "ansible localhost -m os_server -a 'name=$VM_NAME state=absent'"
        rlRun -t -c "ansible localhost -m os_image -a 'name=$OS_IMAGE_NAME state=absent'"
        rlRun -t -c "$CLI compose delete $UUID"
        rlRun -t -c "rm -rf $IMAGE"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
