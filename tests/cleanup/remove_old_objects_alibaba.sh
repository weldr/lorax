#!/bin/bash
# Script removes ECS Instances, Custom Images and OSS files older than
# HOURS_LIMIT (24 hours by default) from Alibaba cloud
#
. /usr/share/beakerlib/beakerlib.sh


rlJournalStart
    rlPhaseStartSetup
        ALI_DIR=`mktemp -d /tmp/alicloud.XXXXX`

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
        rlLogInfo "ALICLOUD_BUCKET=$ALICLOUD_BUCKET"

        # VMs older than HOURS_LIMIT will be deleted
        HOURS_LIMIT="${HOURS_LIMIT:-24}"
        TIMESTAMP=`date -u -d "$HOURS_LIMIT hours ago" '+%FT%T'`
        rlLogInfo "HOURS_LIMIT=$HOURS_LIMIT"
        rlLogInfo "TIMESTAMP=$TIMESTAMP"

        for package in jq; do
            if ! rlCheckRpm "$package"; then
                rlRun -t -c "dnf -y install $package"
                rlAssertRpm "$package"
            fi
        done

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

# Check all regions
for REGION_ID in `$ALI_DIR/aliyun Ecs DescribeRegions | jq -r '.Regions.Region[] | .RegionId'`; do
    rlPhaseStartTest "Delete old VMs in region $REGION_ID"
        for INSTANCE_ID in `$ALI_DIR/aliyun ecs DescribeInstances --RegionId $REGION_ID --InstanceName "Composer-Test*" | jq -r '.Instances.Instance[] | .InstanceId'`; do
            CREATION_TIME=`$ALI_DIR/aliyun ecs DescribeInstanceAttribute --InstanceId $INSTANCE_ID | jq -r .CreationTime`
            if [[ "$CREATION_TIME" < "$TIMESTAMP" ]]; then
                rlLogInfo "Removing instance $REGION_ID/$INSTANCE_ID created at $CREATION_TIME < $TIMESTAMP"
                rlRun -t -c "$ALI_DIR/aliyun ecs DeleteInstance --Force True --InstanceId $INSTANCE_ID"
            else
                rlLogInfo "Skipping instance $REGION_ID/$INSTANCE_ID created at $CREATION_TIME >= $TIMESTAMP"
            fi
        done
    rlPhaseEnd

    rlPhaseStartTest "Delete old Images in region $REGION_ID"
        for IMAGE_ID in `$ALI_DIR/aliyun ecs DescribeImages --RegionId $REGION_ID --ImageName "Composer-Test*" | jq -r '.Images.Image[] | .ImageId'`; do
            CREATION_TIME=`$ALI_DIR/aliyun ecs DescribeImages --ImageId $IMAGE_ID | jq -r '.Images.Image[] | .CreationTime'`
            if [[ "$CREATION_TIME" < "$TIMESTAMP" ]]; then
                rlLogInfo "Removing image $REGION_ID/$IMAGE_ID created at $CREATION_TIME < $TIMESTAMP"
                rlRun -t -c "$ALI_DIR/aliyun ecs DeleteImage --Force True --ImageId $IMAGE_ID"
            else
                rlLogInfo "Skipping image $REGION_ID/$IMAGE_ID created at $CREATION_TIME >= $TIMESTAMP"
            fi
        done
    rlPhaseEnd

    rlPhaseStartTest "Delete composer key pairs in region $REGION_ID"
        for KEY_NAME in `$ALI_DIR/aliyun ecs DescribeKeyPairs --KeyPairName "Composer-Test*" | jq -r '.KeyPairs.KeyPair[] | .KeyPairName'`; do
            rlRun -t -c "$ALI_DIR/aliyun ecs DeleteKeyPairs --KeyPairNames '[\"$KEY_NAME\"]'"
        done
    rlPhaseEnd
done

    rlPhaseStartTest "Delete old OSS objects"
        all_objects=`$ALI_DIR/aliyun oss ls oss://$ALICLOUD_BUCKET/Composer-Test | awk 'NR > 1' | head -n -2`
        while read date_f time_f tz_offset tz_name size_bytes storage_class etag filename_f; do
            creation_date=`date -u -d "$date_f $time_f$tz_offset" '+%FT%T'`
            if [[ "$creation_date" < "$TIMESTAMP" ]]; then
                rlLogInfo "Removing old file $filename_f created at $creation_date < $TIMESTAMP"
                rlRun -t -c "$ALI_DIR/aliyun oss rm $filename_f"
            else
                rlLogInfo "Skipping file $filename_f created at $creation_date >= $TIMESTAMP"
            fi
        done <<< "$all_objects"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -t -c "rm -rf $ALI_DIR"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
