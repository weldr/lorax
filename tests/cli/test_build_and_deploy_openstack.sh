#!/bin/bash
# Note: execute this file from the project root directory

#####
#
# Make sure we can build an image and deploy it inside OpenStack!
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
        # workaround for https://bugzilla.redhat.com/show_bug.cgi?id=1639326
        cat > $TMP_DIR/http-with-rng.toml << __EOF__
name = "http-with-rng"
description = "HTTP image for OpenStack with rng-tools"
version = "0.0.1"

[[modules]]
name = "httpd"
version = "*"

[[modules]]
name = "rng-tools"
version = "*"
__EOF__

        rlRun -t -c "$CLI blueprints push $TMP_DIR/http-with-rng.toml"

        UUID=`$CLI compose start http-with-rng openstack`
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

        SSH_KEY_DIR=`mktemp -d /tmp/composer-ssh-keys.XXXXXX`
        rlRun -t -c "ssh-keygen -t rsa -N '' -f $SSH_KEY_DIR/id_rsa"
        rlRun -t -c "ansible localhost -m os_keypair -a 'name=$VM_NAME-key public_key_file=$SSH_KEY_DIR/id_rsa.pub'"

        response=`ansible localhost -m os_server -a "name=$VM_NAME image=$OS_IMAGE_UUID flavor=t2.medium key_name=$VM_NAME-key auto_ip=yes"`
        rlAssert0 "VM started successfully" $?
        rlLogInfo "$response"

        IP_ADDRESS=`echo "$response" | grep '"OS-EXT-IPS:type": "floating"' -A1 | grep '"addr":' | cut -f4 -d'"'`
        rlLogInfo "Running instance IP_ADDRESS=$IP_ADDRESS"

        rlLogInfo "Waiting 60sec for instance to initialize ..."
        sleep 60
    rlPhaseEnd

    rlPhaseStartTest "Verify VM instance"
        # cloud-init default config differs between RHEL and Fedora
        CLOUD_USER="cloud-user"
        if [ -f "/etc/fedora-release" ]; then
            CLOUD_USER="fedora"
        fi

        # verify we can login into that instance
        rlRun -t -c "ssh -oStrictHostKeyChecking=no -i $SSH_KEY_DIR/id_rsa $CLOUD_USER@$IP_ADDRESS 'cat /etc/redhat-release'"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "ansible localhost -m os_keypair -a 'name=$VM_NAME-key state=absent'"
        rlRun -t -c "ansible localhost -m os_server -a 'name=$VM_NAME state=absent'"
        rlRun -t -c "ansible localhost -m os_image -a 'name=$OS_IMAGE_NAME state=absent'"
        rlRun -t -c "$CLI compose delete $UUID"
        rlRun -t -c "rm -rf $IMAGE $SSH_KEY_DIR $TMP_DIR"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
