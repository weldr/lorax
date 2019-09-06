#!/bin/bash
# Note: execute this file from the project root directory

#####
#
# Make sure we can build an image and deploy it inside AWS!
#
#####

set -e

. /usr/share/beakerlib/beakerlib.sh
. $(dirname $0)/lib/lib.sh

CLI="${CLI:-./src/bin/composer-cli}"


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

        AWS_BUCKET="${AWS_BUCKET:-composerredhat}"
        AWS_REGION="${AWS_REGION:-us-east-1}"

        rlLogInfo "AWS_BUCKET=$AWS_BUCKET"
        rlLogInfo "AWS_REGION=$AWS_REGION"

        for package in python3-pip python3-boto3; do
            if ! rlCheckRpm "$package"; then
                rlRun -t -c "dnf -y install $package"
                rlAssertRpm "$package"
            fi
        done

        rlRun -t -c "pip3 install awscli ansible[aws]"

        # aws configure
        [ -d ~/.aws/ ] || mkdir ~/.aws/

        if [ -f ~/.aws/config ]; then
            rlLogInfo "Reusing existing ~/.aws/config"
        else
            rlLogInfo "Creating ~/.aws/config"
            cat > ~/.aws/config << __EOF__
[default]
region = $AWS_REGION
__EOF__
        fi

        if [ -f ~/.aws/credentials ]; then
            rlLogInfo "Reusing existing ~/.aws/credentials"
        else
            rlLogInfo "Creating ~/.aws/credentials"
            cat > ~/.aws/credentials << __EOF__
[default]
aws_access_key_id = $AWS_ACCESS_KEY_ID
aws_secret_access_key = $AWS_SECRET_ACCESS_KEY
__EOF__
        fi

        TMP_DIR=$(mktemp -d)
        PLAYBOOKS_DIR=$(dirname "$0")/playbooks/aws

        # make sure bucket and vmimport role exist
        rlRun -t -c "ansible-playbook --extra-vars 'aws_bucket=$AWS_BUCKET' $PLAYBOOKS_DIR/setup.yml"
    rlPhaseEnd

    rlPhaseStartTest "compose start"
        rlAssertEquals "SELinux operates in enforcing mode" "$(getenforce)" "Enforcing"
        UUID=`$CLI compose start example-http-server ami`
        rlAssertEquals "exit code should be zero" $? 0

        UUID=`echo $UUID | cut -f 2 -d' '`
    rlPhaseEnd

    rlPhaseStartTest "compose finished"
        wait_for_compose $UUID
    rlPhaseEnd

    rlPhaseStartTest "Import AMI image in AWS"
        rlRun -t -c "$CLI compose image $UUID"

        AMI="$UUID-disk.ami"

        # upload to S3
        rlRun -t -c "ansible localhost -m aws_s3 -a \
                       'bucket=$AWS_BUCKET \
                        src=$AMI \
                        object=$AMI \
                        mode=put'"

        # import image as snapshot into EC2
        cat > containers.json << __EOF__
{
    "Description": "Composer image",
    "Format": "raw",
    "UserBucket": {
        "S3Bucket": "$AWS_BUCKET",
        "S3Key": "$AMI"
    }
}
__EOF__

        IMPORT_TASK_ID=`aws ec2 import-snapshot --disk-container file://containers.json | grep ImportTaskId | cut -f4 -d'"'`

        if [ -z "$IMPORT_TASK_ID" ]; then
            rlFail "IMPORT_TASK_ID is empty!"
        fi

        # wait for the import to complete
        while aws ec2 describe-import-snapshot-tasks --filters Name=task-state,Values=active | grep $IMPORT_TASK_ID; do
            rlLogInfo "Waiting for $IMPORT_TASK_ID to complete ..."
            sleep 60
        done

        DESCRIPTION="Created by AWS-VMImport service for $IMPORT_TASK_ID"
        rlRun -t -c "aws ec2 describe-snapshots --filters Name=description,Values='$DESCRIPTION'"
        SNAPSHOT_ID=`aws ec2 describe-snapshots --filters Name=description,Values="$DESCRIPTION" | grep SnapshotId | cut -f4 -d'"'`

        if [ -z "$SNAPSHOT_ID" ]; then
            rlFail "SNAPSHOT_ID is empty!"
        else
            rlLogInfo "SNAPSHOT_ID=$SNAPSHOT_ID"
        fi

        # create an image from the imported selected snapshot
        AMI_ID=`aws ec2 register-image --name "Composer-Test-$UUID" --virtualization-type hvm --root-device-name /dev/sda1 \
                    --block-device-mappings "[{\"DeviceName\": \"/dev/sda1\", \"Ebs\": {\"SnapshotId\": \"$SNAPSHOT_ID\"}}]" | \
                    grep ImageId | cut -f4 -d'"'`

        if [ -z "$AMI_ID" ]; then
            rlFail "AMI_ID is empty!"
        else
            rlLogInfo "AMI_ID=$AMI_ID"
        fi
    rlPhaseEnd

    rlPhaseStartTest "Start EC2 instance"
        # generate new ssh key
        KEY_NAME=composer-$UUID
        SSH_KEY_DIR=`mktemp -d /tmp/composer-ssh-keys.XXXXXX`
        rlRun -t -c "ssh-keygen -t rsa -N '' -f $SSH_KEY_DIR/id_rsa"

        rlRun -t -c "ansible-playbook  --extra-vars \
                       'key_name=$KEY_NAME \
                        ssh_key_dir=$SSH_KEY_DIR \
                        ami_id=$AMI_ID \
                        tmp_dir=$TMP_DIR' \
                     $PLAYBOOKS_DIR/instance.yml"

        INSTANCE_ID=$(cat $TMP_DIR/instance_id)
        IP_ADDRESS=$(cat $TMP_DIR/public_ip)

        rlLogInfo "Running INSTANCE_ID=$INSTANCE_ID with IP_ADDRESS=$IP_ADDRESS"
    rlPhaseEnd

    rlPhaseStartTest "Verify EC2 instance"
        # cloud-init default config differs between RHEL and Fedora
        # and ami.ks will create ec2-user only on RHEL
        CLOUD_USER="ec2-user"
        if [ -f "/etc/fedora-release" ]; then
            CLOUD_USER="fedora"
        fi

        # run generic tests to verify the instance
        verify_image "$CLOUD_USER" "$IP_ADDRESS" "-i $SSH_KEY_DIR/id_rsa"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "ansible localhost -m ec2_instance -a 'state=terminated instance_ids=$INSTANCE_ID'"
        rlRun -t -c "ansible localhost -m ec2_key -a 'state=absent name=$KEY_NAME'"
        rlRun -t -c "ansible localhost -m ec2_ami -a 'state=absent image_id=$AMI_ID delete_snapshot=True'"
        rlRun -t -c "ansible localhost -m aws_s3 -a 'mode=delobj bucket=$AWS_BUCKET object=$AMI'"
        rlRun -t -c "$CLI compose delete $UUID"
        rlRun -t -c "rm -rf $AMI $SSH_KEY_DIR containers.json $TMP_DIR"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
