#!/bin/bash
# Note: execute this file from the project root directory

#####
#
# Make sure we can build an image and deploy it inside vSphere!
#
#####

. /usr/share/beakerlib/beakerlib.sh

CLI="${CLI:-./src/bin/composer-cli}"


rlJournalStart
    rlPhaseStartSetup
        if [ -z "$V_HOST" ]; then
            rlFail "V_HOST is empty!"
        else
            rlLogInfo "V_HOST=$V_HOST"
        fi

        if [ -z "$V_USERNAME" ]; then
            rlFail "V_USERNAME is empty!"
        else
            rlLogInfo "V_USERNAME=$V_USERNAME"
        fi

        if [ -z "$V_PASSWORD" ]; then
            rlFail "V_PASSWORD is empty!"
        else
            rlLogInfo "V_PASSWORD is configured"
        fi

        V_DATACENTER="${V_DATACENTER:-RH_Engineering}"
        rlLogInfo "V_DATACENTER=$V_DATACENTER"

        V_CLUSTER="${V_CLUSTER:-SysMgmt_vMotion}"
        rlLogInfo "V_CLUSTER=$V_CLUSTER"

        V_NETWORK="${V_NETWORK:-CEE_VM_Network}"
        rlLogInfo "V_NETWORK=$V_NETWORK"

        V_DATASTORE="${V_DATASTORE:-NFS-Synology-1}"
        rlLogInfo "V_DATASTORE=$V_DATASTORE"

        V_FOLDER="${V_FOLDER:-Composer}"
        rlLogInfo "V_FOLDER=$V_FOLDER"

        if ! rlCheckRpm "python3-pip"; then
            rlRun -t -c "dnf -y install python3-pip"
            rlAssertRpm python3-pip
        fi

        rlRun -t -c "pip3 install pyvmomi"

        TMP_DIR=`mktemp -d /tmp/composer-vmware.XXXXX`
        SAMPLES="$TMP_DIR/pyvmomi-community-samples"
        if [ ! -d "$SAMPLES" ]; then
            rlRun -t -c "git clone https://github.com/weldr/pyvmomi-community-samples $SAMPLES"
            pushd $SAMPLES && git checkout composer_testing && popd
        fi
        SAMPLES="$SAMPLES/samples"
    rlPhaseEnd

    rlPhaseStartTest "compose start"
        rlAssertEquals "SELinux operates in enforcing mode" "$(getenforce)" "Enforcing"
        SSH_KEY_DIR=`mktemp -d /tmp/composer-ssh-keys.XXXXXX`
        rlRun -t -c "ssh-keygen -t rsa -N '' -f $SSH_KEY_DIR/id_rsa"
        PUB_KEY=`cat $SSH_KEY_DIR/id_rsa.pub`

        cat > $TMP_DIR/vmware.toml << __EOF__
name = "vmware"
description = "HTTP image for vmware"
version = "0.0.1"

[[modules]]
name = "httpd"
version = "*"

[[customizations.user]]
name = "root"
key = "$PUB_KEY"
__EOF__

        rlRun -t -c "$CLI blueprints push $TMP_DIR/vmware.toml"

        UUID=`$CLI compose start vmware vmdk`
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

    rlPhaseStartTest "Upload vmdk image in vCenter"
        rlRun -t -c "$CLI compose image $UUID"
        IMAGE="$UUID-disk.vmdk"

        python3 $SAMPLES/upload_file_to_datastore.py -S -s $V_HOST -u $V_USERNAME -p $V_PASSWORD \
                -d $V_DATASTORE -l `readlink -f $IMAGE` -r $IMAGE
        rlAssert0 "Image upload successfull" $?
    rlPhaseEnd

    rlPhaseStartTest "Start VM instance"
        VM_NAME="Composer-Auto-VM-$UUID"
        INSTANCE_UUID=`python3 $SAMPLES/create_vm.py -S -s $V_HOST -u $V_USERNAME -p $V_PASSWORD \
                        --datacenter $V_DATACENTER -c $V_CLUSTER -f $V_FOLDER -d $V_DATASTORE \
                        --portgroup $V_NETWORK -v $IMAGE -m 2048 -g rhel7_64Guest -n $VM_NAME \
                        --power-on`

        if [ -z "$INSTANCE_UUID" ]; then
            rlFail "INSTANCE_UUID is empty!"
        else
            rlLogInfo "INSTANCE_UUID=$INSTANCE_UUID"
        fi

        # wait for instance to become running and had assigned a public IP
        IP_ADDRESS="None"
        while [ "$IP_ADDRESS" == "None" ]; do
            rlLogInfo "IP_ADDRESS is not assigned yet ..."
            sleep 30
            IP_ADDRESS=`python3 $SAMPLES/find_by_uuid.py -S -s $V_HOST -u $V_USERNAME -p $V_PASSWORD \
                            --uuid $INSTANCE_UUID | grep 'ip address' | tr -d ' ' | cut -f2 -d:`
        done

        rlLogInfo "Running instance IP_ADDRESS=$IP_ADDRESS"

        rlLogInfo "Waiting 30sec for instance to initialize ..."
        sleep 30
    rlPhaseEnd

    rlPhaseStartTest "Verify VM instance"
        # verify we can login into that instance and root account is disabled
        . ./tests/cli/lib/root_account.sh
        check_root_account root $IP_ADDRESS "-i $SSH_KEY_DIR/id_rsa"
    rlPhaseEnd

    rlPhaseStartCleanup
        # note: vmdk disk is removed when destroying the VM
        python3 $SAMPLES/destroy_vm.py -S -s $V_HOST -u $V_USERNAME -p $V_PASSWORD --uuid $INSTANCE_UUID
        rlAssert0 "VM destroyed" $?
        rlRun -t -c "$CLI compose delete $UUID"
        rlRun -t -c "rm -rf $IMAGE $TMP_DIR $SSH_KEY_DIR"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
