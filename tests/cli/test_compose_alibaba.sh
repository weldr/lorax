#!/bin/bash
# Note: execute this file from the project root directory

#####
#
# Make sure we can build an image and deploy it inside Alibaba cloud!
#
#####

set -e

. /usr/share/beakerlib/beakerlib.sh
. $(dirname $0)/lib/lib.sh

CLI="${CLI:-./src/bin/composer-cli}"


rlJournalStart
    rlPhaseStartSetup
        if [ -z "$ALICLOUD_ACCESS_KEY" ]; then
            rlFail "ALICLOUD_ACCESS_KEY is empty!"
        else
            rlLogInfo "ALICLOUD_ACCESS_KEY is configured"
        fi

        if [ -z "$ALICLOUD_SECRET_KEY" ]; then
            rlFail "ALICLOUD_SECRET_KEY is empty!"
        else
            rlLogInfo "ALICLOUD_SECRET_KEY is configured"
        fi

        ALICLOUD_BUCKET="${ALICLOUD_BUCKET:-composer-test}"
        ALICLOUD_REGION="${ALICLOUD_REGION:-us-east-1}"

        rlLogInfo "ALICLOUD_BUCKET=$ALICLOUD_BUCKET"
        rlLogInfo "ALICLOUD_REGION=$ALICLOUD_REGION"

        for package in jq; do
            if ! rlCheckRpm "$package"; then
                rlRun -t -c "dnf -y install $package"
                rlAssertRpm "$package"
            fi
        done

        ALI_DIR=`mktemp -d /tmp/alicloud.XXXXX`
        # use the CLI b/c Ansible modules are not yet upstream and are unreliable
        TAR_FILE="aliyun-cli-linux-3.0.32-amd64.tgz"
        curl -L https://github.com/aliyun/aliyun-cli/releases/download/v3.0.32/$TAR_FILE > $ALI_DIR/$TAR_FILE
        tar -C $ALI_DIR/ -xzvf $ALI_DIR/$TAR_FILE
        chmod a+x $ALI_DIR/aliyun

        # configure
        [ -d ~/.aliyun/ ] || mkdir ~/.aliyun/

        if [ -f ~/.aliyun/config.json ]; then
            rlLogInfo "Reusing existing ~/.aliyun/config.json"
        else
            rlLogInfo "Creating ~/.aliyun/config.json"
            cat > ~/.aliyun/config.json << __EOF__
{
    "current": "",
    "profiles": [
        {
            "mode": "AK",
            "access_key_id": "$ALICLOUD_ACCESS_KEY",
            "access_key_secret": "$ALICLOUD_SECRET_KEY",
            "region_id": "$ALICLOUD_REGION",
            "output_format": "json",
            "language": "en"
        }
    ],
    "meta_path": ""
}
__EOF__
        fi

    rlPhaseEnd

    rlPhaseStartTest "compose start"
        rlAssertEquals "SELinux operates in enforcing mode" "$(getenforce)" "Enforcing"
        UUID=`$CLI compose start example-http-server alibaba`
        rlAssertEquals "exit code should be zero" $? 0

        UUID=`echo $UUID | cut -f 2 -d' '`
    rlPhaseEnd

    rlPhaseStartTest "compose finished"
        wait_for_compose $UUID
    rlPhaseEnd

    rlPhaseStartTest "Import image in Alibaba cloud"
        rlRun -t -c "$CLI compose image $UUID"

        rlRun -t -c "mv $UUID-disk.qcow2 Composer-Test-$UUID-disk.qcow2"
        IMAGE="Composer-Test-$UUID-disk.qcow2"

        # upload to OSS
        rlRun -t -c "$ALI_DIR/aliyun oss cp --retry-count 20 $IMAGE oss://$ALICLOUD_BUCKET/$IMAGE"

        # now import as machine image
        # WARNING: DiskImageSize *MUST BE* 40 GiB. We don't need all of that but
        # VMs fail to boot otherwise !!! Not sure why.
        rlRun -t -c "$ALI_DIR/aliyun ecs ImportImage \
                        --OSType linux --Platform RedHat \
                        --Architecture x86_64 \
                        --DiskDeviceMapping.1.DiskImageSize 40 \
                        --DiskDeviceMapping.1.Format qcow2 \
                        --DiskDeviceMapping.1.OSSBucket $ALICLOUD_BUCKET \
                        --DiskDeviceMapping.1.OSSObject $IMAGE \
                        --ImageName $IMAGE"

        # wait for status to become available
        while [ `$ALI_DIR/aliyun ecs DescribeImages --ImageName $IMAGE --Status Available | jq .Images.Image | jq -r '.[0].ImageName'` == "null" ]; do
            rlLogInfo "Waiting for import to complete ..."
            sleep 60
        done

        rlRun -t -c "$ALI_DIR/aliyun ecs DescribeImages --ImageName $IMAGE"
        IMAGE_ID=`$ALI_DIR/aliyun ecs DescribeImages --ImageName $IMAGE | jq .Images.Image | jq -r '.[0].ImageId'`

        if [ "$IMAGE_ID" == "null" ]; then
            rlFail "IMAGE_ID is empty!"
        else
            rlLogInfo "IMAGE_ID=$IMAGE_ID"
        fi
    rlPhaseEnd

    rlPhaseStartTest "Start ECS instance"
        INSTANCE_TYPE="ecs.n1.medium"

        # generate & import new ssh key
        KEY_NAME=Composer-Test-$UUID
        SSH_KEY_DIR=`mktemp -d /tmp/composer-ssh-keys.XXXXXX`
        rlRun -t -c "ssh-keygen -t rsa -N '' -f $SSH_KEY_DIR/id_rsa"
        SSH_PUB_KEY=$(cat $SSH_KEY_DIR/id_rsa.pub)
        rlRun -t -c "$ALI_DIR/aliyun ecs ImportKeyPair --KeyPairName $KEY_NAME --PublicKeyBody '$SSH_PUB_KEY'"

        RELEASE_TIME=$(date -u -d "24 hours" '+%FT%TZ')

        # SecurityGroup is composer-allow-ssh
        # VPC is composer-vpc
        response=$($ALI_DIR/aliyun ecs RunInstances --Amount 1 --ImageId $IMAGE_ID \
                    --InstanceType=$INSTANCE_TYPE --InstanceName Composer-Test-VM-$UUID \
                    --SecurityGroupId sg-0xi4w9isg0p1ytj1qbhf \
                    --VSwitchId vsw-0xi36w0a9l894vf2momfb \
                    --KeyPairName $KEY_NAME \
                    --InternetMaxBandwidthIn 5 --InternetMaxBandwidthOut 5 \
                    --AutoReleaseTime $RELEASE_TIME)
        rlAssert0 "VM started successfully" $?
        rlLogInfo "$response"

        INSTANCE_ID=`echo "$response" | jq .InstanceIdSets.InstanceIdSet | jq -r '.[0]' `

        until [ $($ALI_DIR/aliyun ecs DescribeInstanceAttribute --InstanceId $INSTANCE_ID | jq -r .Status | grep "Running\|Stopped") ]; do
            sleep 30
            rlLogInfo "Waiting for instance to start ..."
        done

        rlAssertEquals "Instance $INSTANCE_ID is Running" \
            "$($ALI_DIR/aliyun ecs DescribeInstanceAttribute --InstanceId $INSTANCE_ID | jq -r .Status)" "Running"
        rlRun -t -c "$ALI_DIR/aliyun ecs DescribeInstanceAttribute --InstanceId $INSTANCE_ID"

        IP_ADDRESS="null"
        while [ "$IP_ADDRESS" == "null" ]; do
            rlLogInfo "IP_ADDRESS is not assigned yet ..."
            sleep 30
            IP_ADDRESS=`$ALI_DIR/aliyun ecs DescribeInstanceAttribute --InstanceId $INSTANCE_ID | jq -r .PublicIpAddress.IpAddress | jq -r '.[0]'`
        done

        rlLogInfo "Running INSTANCE_ID=$INSTANCE_ID with IP_ADDRESS=$IP_ADDRESS"
    rlPhaseEnd

    rlPhaseStartTest "Verify ECS instance"
        # cloud-init default config differs between RHEL and Fedora
        CLOUD_USER="cloud-user"
        if [ -f "/etc/fedora-release" ]; then
            CLOUD_USER="fedora"
        fi

        # run generic tests to verify the instance
        verify_image "$CLOUD_USER" "$IP_ADDRESS" "-i $SSH_KEY_DIR/id_rsa"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "$ALI_DIR/aliyun ecs DeleteInstance --Force True --InstanceId $INSTANCE_ID"
        rlRun -t -c "$ALI_DIR/aliyun ecs DeleteImage --Force True --ImageId $IMAGE_ID"
        rlRun -t -c "$ALI_DIR/aliyun oss rm oss://$ALICLOUD_BUCKET/$IMAGE --force"
        rlRun -t -c "$CLI compose delete $UUID"
        # do this here to give time for the VM instance to be removed properly
        # also don't fail if the key is still attached to an instance which is waiting
        # to be desroyed. We're going to remove these keys in cleanup afterwards
        $ALI_DIR/aliyun ecs DeleteKeyPairs --KeyPairNames "['$KEY_NAME']" || echo
        rlRun -t -c "rm -rf $IMAGE $SSH_KEY_DIR $ALI_DIR"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
