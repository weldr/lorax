#!/bin/bash
# Script removes virtual machines, AMIs, volumes, snapshots, key pairs and S3 objects older than HOURS_LIMIT (24 hours by default) from Amazon EC2/S3
# Instances, Volumes, Snapshots, AMIs and s3 objects with the "keep_me" tag will not be affected

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
        AWS_BUCKET="${AWS_BUCKET:-composerredhat}"

        rlLogInfo "HOURS_LIMIT=$HOURS_LIMIT"
        rlLogInfo "AWS_REGION=$AWS_REGION"
        rlLogInfo "TIMESTAMP=$TIMESTAMP"

        for package in ansible python3-boto3 awscli; do
            if ! rlCheckRpm "$package"; then
                rlRun -t -c "dnf -y install $package"
                rlAssertRpm "$package"
            fi
        done

        # Get a list of EC2 regions
        regions=`aws ec2 describe-regions --region="$AWS_REGION" --query "Regions[].{Name:RegionName}" --output text | tr '\n' ' '`
        if [ -z "$regions" ]; then
            rlFail "No EC2 regions returned."
        else
            rlLogInfo "EC2 regions to be checked: $regions"
        fi

        # Get the account ID
        account_id=`aws sts get-caller-identity --output text --query 'Account'`
        if [ -z "$account_id" ]; then
            rlFail "No account ID returned."
        else
            rlLogInfo "Account ID: $account_id"
        fi

        PLAYBOOK_DELETE_VMS=`mktemp`
        PLAYBOOK_DELETE_AMIS=`mktemp`
    rlPhaseEnd

# Check all EC2 regions
for region in $regions; do
    rlPhaseStartTest "Delete old VMs in region $region"
        cat > $PLAYBOOK_DELETE_VMS << __EOF__
- name: Delete old VMs
  hosts: localhost
  gather_facts: False
  tasks:
  - name: Get VMs
    ec2_instance_facts:
      region: "$region"
    register: vms_facts

  - name: List all VMs
    debug:
      var: vms_facts

  - name: Delete old VMs
    ec2_instance:
      instance_ids: "{{item.instance_id}}"
      region: "$region"
      state: absent
    loop: "{{vms_facts.instances}}"
    when: (item.launch_time < lookup('env','TIMESTAMP')) and (item.tags['keep_me'] is not defined)
    loop_control:
      label: "{{item.instance_id}}"
__EOF__

        rlLogInfo "Removing VMs in region $region created before $TIMESTAMP"
        rlRun -t -c "ansible-playbook $PLAYBOOK_DELETE_VMS"
    rlPhaseEnd

    rlPhaseStartTest "Delete old AMIs in region $region"
        cat > $PLAYBOOK_DELETE_AMIS << __EOF__
- name: Delete old AMIs
  hosts: localhost
  gather_facts: False
  tasks:
  - name: Get AMIs
    ec2_ami_facts:
      region: "$region"
      owners: "$account_id"
    register: ami_facts

  - name: List all AMIs
    debug:
      var: ami_facts

  - name: Delete old AMIs
    ec2_ami:
      image_id: "{{item.image_id}}"
      region: "$region"
      state: absent
      delete_snapshot: True
    loop: "{{ami_facts.images}}"
    when: (item.creation_date < lookup('env','TIMESTAMP')) and (item.tags['keep_me'] is not defined)
    loop_control:
      label: "{{item.image_id}}"
__EOF__

        rlLogInfo "Removing AMIs in region $region created before $TIMESTAMP"
        rlRun -t -c "ansible-playbook $PLAYBOOK_DELETE_AMIS"
    rlPhaseEnd

    rlPhaseStartTest "Delete unused composer key pairs in region $region"
        # list all key pairs starting with "composer-"
        keys=`aws ec2 describe-key-pairs --region="$region" --query 'KeyPairs[?starts_with(KeyName, \`composer-\`) == \`true\`].KeyName' --output text`
        rlLogInfo "Found existing composer keys: $keys"

        for key in $keys; do
            # list all instances, which use $key
            instances=`aws ec2 describe-instances --region="$region" --filters Name=key-name,Values="$key" --query 'Reservations[*].Instances[*].InstanceId' --output text`
            # remove the key pair if it's not used
            if [ -z "$instances" ]; then
                rlLogInfo "Removing unused key pair $key"
                rlRun -t -c "aws ec2 delete-key-pair --region='$region' --key-name='$key'"
            else
                rlLogInfo "Keeping key pair $key used by instance $instances"
            fi
        done
    rlPhaseEnd

    rlPhaseStartTest "Delete old volumes in region $region"
        # get a list of unused ("available") volumes older than $TIMESTAMP and not having the tag "keep_me"
        volumes_to_delete=$(aws ec2 describe-volumes --region="$region" --query "Volumes[?CreateTime<\`$TIMESTAMP\`] | [?!(Tags[?Key==\`keep_me\`])] | [?State==\`available\`].[VolumeId,CreateTime]" --output text)

        while read volume_id creation_time; do
            if [ -n "$volume_id" ]; then
                rlLogInfo "Removing volume $volume_id created $creation_time"
                rlRun -t -c "aws ec2 delete-volume --region='$region' --volume-id '$volume_id'"
            fi
        done <<< "$volumes_to_delete"
    rlPhaseEnd

    rlPhaseStartTest "Delete old snapshots in region $region"
        # get a list of snapshots older than $TIMESTAMP and owned by our account and not having the tag "keep_me"
        snapshots_to_delete=$(aws ec2 describe-snapshots --region="$region" --owner-ids "$account_id" --query "Snapshots[?StartTime<\`$TIMESTAMP\`] |[?!(Tags[?Key==\`keep_me\`])].[SnapshotId,StartTime]" --output text)

        while read snapshot_id start_time; do
            if [ -n "$snapshot_id" ]; then
                rlLogInfo "Removing snapshot $snapshot_id started $start_time"
                rlRun -t -c "aws ec2 delete-snapshot --region='$region' --snapshot-id '$snapshot_id'"
            fi
        done <<< "$snapshots_to_delete"
    rlPhaseEnd

# Check all EC2 regions
done

    rlPhaseStartTest "Delete old Amazon S3 objects"
        all_objects=`aws s3 ls s3://${AWS_BUCKET} --recursive`
        while read date_f time_f size_f filename_f; do
            creation_date=`date -u -d "$date_f $time_f" '+%FT%T'`
            if [ "$creation_date" \< "$TIMESTAMP" ]; then
                # find and delete s3 objects without the "keep_me" tag
                keep=$(aws s3api get-object-tagging --bucket ${AWS_BUCKET} --key ${filename_f} --output text | cut -f2 | grep "^keep_me$")
                if [ -z "$keep" ]; then
                    rlLogInfo "Removing old file $filename_f created $date_f $time_f"
                    rlRun -t -c "aws s3 rm s3://${AWS_BUCKET}/${filename_f}"
                fi
            fi
        done <<< "$all_objects"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "rm -f $PLAYBOOK_DELETE_VMS"
        rlRun -t -c "rm -f $PLAYBOOK_DELETE_AMIS"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
