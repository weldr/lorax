#!/bin/bash
# Note: execute this file from the project root directory

#####
#
# Make sure we can build an image and deploy it inside AWS!
#
#####

. /usr/share/beakerlib/beakerlib.sh

CLI="./src/bin/composer-cli"


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

        if ! rlCheckRpm "python2-pip"; then
            rlRun -t -c "yum -y install python2-pip"
            rlAssertRpm python2-pip
        fi

        rlRun -t -c "pip install --upgrade pip setuptools"
        rlRun -t -c "pip install awscli"

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

        # make sure bucket exists
        rlRun -t -c "aws s3 mb s3://$AWS_BUCKET"

        # make sure vmimport role exists
        rlRun -t -c "aws iam get-role --role-name vmimport"
    rlPhaseEnd

    rlPhaseStartTest "compose start"
        rlAssertEquals "SELinux operates in enforcing mode" "$(getenforce)" "Enforcing"
        UUID=`$CLI compose start example-http-server ami`
        rlAssertEquals "exit code should be zero" $? 0

        UUID=`echo $UUID | cut -f 2 -d' '`
    rlPhaseEnd

    rlPhaseStartTest "compose finished"
        if [ -n "$UUID" ]; then
            until $CLI compose details $UUID | grep FINISHED; do
                rlLogInfo "Waiting for compose to finish ..."
                sleep 30
            done;
        else
            rlFail "Compose UUID is empty!"
        fi
    rlPhaseEnd

    rlPhaseStartTest "Import AMI image in AWS"
        rlRun -t -c "$CLI compose image $UUID"

        AMI="$UUID-disk.ami"

        # upload to S3
        rlRun -t -c "aws s3 cp $AMI s3://$AWS_BUCKET"

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
        # generate new ssh key and import it into EC2
        KEY_NAME=composer-$UUID
        SSH_KEY_DIR=`mktemp -d /tmp/composer-ssh-keys.XXXXXX`
        rlRun -t -c "ssh-keygen -t rsa -N '' -f $SSH_KEY_DIR/id_rsa"
        rlRun -t -c "aws ec2 import-key-pair --key-name $KEY_NAME --public-key-material file://$SSH_KEY_DIR/id_rsa.pub"

        # start a new instance with selected ssh key, enable ssh
        INSTANCE_ID=`aws ec2 run-instances --image-id $AMI_ID --instance-type t2.small --key-name $KEY_NAME \
            --security-groups allow-ssh --instance-initiated-shutdown-behavior terminate --enable-api-termination \
            --count 1| grep InstanceId | cut -f4 -d'"'`

        if [ -z "$INSTANCE_ID" ]; then
            rlFail "INSTANCE_ID is empty!"
        else
            rlLogInfo "INSTANCE_ID=$INSTANCE_ID"
        fi

        # wait for instance to become running and had assigned a public IP
        IP_ADDRESS=""
        while [ -z "$IP_ADDRESS" ]; do
            rlLogInfo "IP_ADDRESS is not assigned yet ..."
            sleep 10
            IP_ADDRESS=`aws ec2 describe-instances --instance-ids $INSTANCE_ID --filters=Name=instance-state-name,Values=running | grep PublicIpAddress | cut -f4 -d'"'`
        done

        rlLogInfo "Running instance IP_ADDRESS=$IP_ADDRESS"

        until aws ec2 describe-instance-status --instance-ids $INSTANCE_ID --filter Name=instance-status.status,Values=ok | grep ok; do
            rlLogInfo "Waiting for instance to initialize ..."
            sleep 60
        done
    rlPhaseEnd

    rlPhaseStartTest "Verify EC2 instance"
        # cloud-init default config differs between RHEL and Fedora
        # and ami.ks will create ec2-user only on RHEL
        CLOUD_USER="ec2-user"
        if [ -f "/etc/fedora-release" ]; then
            CLOUD_USER="fedora"
        fi

        # verify we can login into that instance and maybe some other details
        rlRun -t -c "ssh -oStrictHostKeyChecking=no -i $SSH_KEY_DIR/id_rsa $CLOUD_USER@$IP_ADDRESS 'cat /etc/redhat-release'"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "aws ec2 terminate-instances --instance-ids $INSTANCE_ID"
        rlRun -t -c "aws ec2 delete-key-pair --key-name $KEY_NAME"
        rlRun -t -c "aws ec2 deregister-image --image-id $AMI_ID"
        rlRun -t -c "aws ec2 delete-snapshot --snapshot-id $SNAPSHOT_ID"
        rlRun -t -c "aws s3 rm s3://$AWS_BUCKET/$AMI"
        rlRun -t -c "$CLI compose delete $UUID"
        rlRun -t -c "rm -rf $AMI $SSH_KEY_DIR containers.json"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
