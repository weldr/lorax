#!/bin/bash
# Script removes virtual machines and other artifacts older than HOURS_LIMIT (24 hours by default) from VMware vShere

. /usr/share/beakerlib/beakerlib.sh


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

        # VMs older than HOURS_LIMIT will be deleted
        HOURS_LIMIT="${HOURS_LIMIT:-24}"
        export TIMESTAMP=`date -u -d "$HOURS_LIMIT hours ago" '+%FT%T'`

        rlLogInfo "HOURS_LIMIT=$HOURS_LIMIT"
        rlLogInfo "TIMESTAMP=$TIMESTAMP"

        for package in python3-pip git; do
            if ! rlCheckRpm "$package"; then
                rlRun -t -c "dnf -y install $package"
                rlAssertRpm "$package"
            fi
        done

        rlRun -t -c "pip3 install pyvmomi"

        TMP_DIR=`mktemp -d /tmp/composer-vmware.XXXXX`
        SAMPLES="$TMP_DIR/pyvmomi-community-samples"
        if [ ! -d "$SAMPLES" ]; then
            rlRun -t -c "git clone https://github.com/weldr/pyvmomi-community-samples $SAMPLES"
            pushd $SAMPLES && git checkout composer_testing && popd
        fi
        SAMPLES="$SAMPLES/samples"
        SCRIPT_DIR=$(dirname "$0")
    rlPhaseEnd

    rlPhaseStartTest "Delete old VMs"
        # list all VMs
        rlRun -t -c 'python3 $SCRIPT_DIR/vmware_list_vms.py --host $V_HOST --user $V_USERNAME --password $V_PASSWORD --disable_ssl_verification > $TMP_DIR/vmware_vms' 0 'Getting a list of VMs'

        while read name uuid creation_date; do
            # remove VMs with name starting "Composer-Auto-VM" and older than $TIMESTAMP
            echo $name | grep ^Composer-Auto-VM > /dev/null
            if [ $? -eq 0 -a "$creation_date" \< "$TIMESTAMP" ]; then
                # note: vmdk disk is removed when destroying the VM
                rlRun 'python3 $SAMPLES/destroy_vm.py -S -s $V_HOST -u $V_USERNAME -p $V_PASSWORD --uuid $uuid' 0 "Delete VM: $name UUID: $uuid"
                rlAssert0 "VM destroyed" $?
            fi
        done < $TMP_DIR/vmware_vms

    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "rm -rf $TMP_DIR"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText

