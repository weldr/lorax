#!/bin/bash
# Script removes virtual machines and other artifacts older than HOURS_LIMIT (24 hours by default) from Azure

. /usr/share/beakerlib/beakerlib.sh


# Delete old objects based on the $TAG_NAME tag value defined in a previous execution of the script
delete_old_resources() {
    local resource_type="$1"

    # list resources older than $TIMESTAMP based on the $TAG_NAME tag created in a previous run
    rlRun -c -s 'az resource list --resource-type $resource_type --query "[?tags.$TAG_NAME < \`$TIMESTAMP\`].name" --output tsv' 0 "Get a list of $resource_type older than $TIMESTAMP"
    resources_to_delete=$(cat $rlRun_LOG)

    if [ -n "$resources_to_delete" ]; then
        for object in $resources_to_delete; do
            rlRun -t -c "az resource delete --resource-type=$resource_type --name $object --resource-group $AZURE_RESOURCE_GROUP"
        done
    else
        rlLogInfo "No $resource_type older than $TIMESTAMP was found."
    fi
}

# Find objects without the $TAG_NAME tag and create the tag with the current date/time value
tag_new_resources() {
    local resource_type="$1"

    # list resources without the $TAG_NAME tag
    rlRun -c -s 'az resource list --resource-type $resource_type --query "[?tags.$TAG_NAME == null].name" --output tsv' 0 "Get a list of $resource_type without the $TAG_NAME tag."
    resources_without_tag=$(cat $rlRun_LOG)

    if [ -n "$resources_without_tag" ]; then
        now=$(date -u '+%FT%T')
        for object in $resources_without_tag; do
            rlRun -t -c 'az resource update --resource-type $resource_type --name $object --resource-group $AZURE_RESOURCE_GROUP --set "tags.$TAG_NAME=$now"' 0 "Add tag $TAG_NAME:$now to $resource_type: $object"
        done
    else
        rlLogInfo "No $resource_type without the $TAG_NAME tag was found."
    fi
}

rlJournalStart
    rlPhaseStartSetup
        if [ -z "$AZURE_SUBSCRIPTION_ID" ]; then
            rlFail "AZURE_SUBSCRIPTION_ID is empty!"
        else
            rlLogInfo "AZURE_SUBSCRIPTION_ID is configured"
        fi

        if [ -z "$AZURE_TENANT" ]; then
            rlFail "AZURE_TENANT is empty!"
        else
            rlLogInfo "AZURE_TENANT is configured"
        fi

        if [ -z "$AZURE_CLIENT_ID" ]; then
            rlFail "AZURE_CLIENT_ID is empty!"
        else
            rlLogInfo "AZURE_CLIENT_ID is configured"
        fi

        if [ -z "$AZURE_SECRET" ]; then
            rlFail "AZURE_SECRET is empty!"
        else
            rlLogInfo "AZURE_SECRET is configured"
        fi

        export AZURE_RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-composer}"
        rlLogInfo "AZURE_RESOURCE_GROUP=$AZURE_RESOURCE_GROUP"

        export AZURE_STORAGE_ACCOUNT="${AZURE_STORAGE_ACCOUNT:-composerredhat}"
        rlLogInfo "AZURE_STORAGE_ACCOUNT=$AZURE_STORAGE_ACCOUNT"

        export AZURE_STORAGE_CONTAINER="${AZURE_STORAGE_CONTAINER:-composerredhat}"
        rlLogInfo "AZURE_STORAGE_CONTAINER=$AZURE_STORAGE_CONTAINER"

        # VMs older than HOURS_LIMIT will be deleted
        HOURS_LIMIT="${HOURS_LIMIT:-24}"
        export TIMESTAMP=`date -u -d "$HOURS_LIMIT hours ago" '+%FT%T'`

        rlLogInfo "HOURS_LIMIT=$HOURS_LIMIT"
        rlLogInfo "TIMESTAMP=$TIMESTAMP"

        # It's not easily possible to get creation date/time of Azure objects.
        # Use a tag to record when the object was seen for the first time
        # and remove objects based on the value of the tag. The value is UTC
        # date/time, format: 2019-01-29T15:16:40
        TAG_NAME="first_seen"

        # Use Microsoft repository to install azure-cli
        rlRun -t -c "rpm --import https://packages.microsoft.com/keys/microsoft.asc"
        cat > /etc/yum.repos.d/azure-cli.repo << __EOF__
[azure-cli]
name=Azure CLI
baseurl=https://packages.microsoft.com/yumrepos/azure-cli
enabled=1
gpgcheck=1
gpgkey=https://packages.microsoft.com/keys/microsoft.asc
__EOF__
        rlRun -c -t "dnf install -y azure-cli"

        # sign in
        rlRun -c -t 'az login --service-principal --username "$AZURE_CLIENT_ID" --password "$AZURE_SECRET" --tenant "$AZURE_TENANT"'
    rlPhaseEnd

    # A list of Azure resources we want to clean
    resource_types="
Microsoft.Compute/virtualMachines
Microsoft.Network/networkInterfaces
Microsoft.Network/publicIPAddresses
Microsoft.Network/networkSecurityGroups
Microsoft.Compute/disks
Microsoft.Compute/images
"

    # Remove old resources and tag new resources
    for resource_type in $resource_types; do
        rlPhaseStartTest "Delete old $resource_type"
            delete_old_resources $resource_type
        rlPhaseEnd

        rlPhaseStartTest "Tag new $resource_type"
            tag_new_resources $resource_type
        rlPhaseEnd
    done

    rlPhaseStartTest "Delete old blobs"
        # get a list of blobs older than $TIMESTAMP
        rlRun -c -s 'az storage blob list --container-name $AZURE_STORAGE_CONTAINER --query "[?properties.creationTime < \`$TIMESTAMP\`].[name,properties.creationTime]" --output tsv'
        blobs_to_delete=$(cat $rlRun_LOG)

        if [ -n "$blobs_to_delete" ]; then
            while read name creation_time; do
                rlLogInfo "Removing blob $name created $creation_time"
                rlRun -t -c "az storage blob delete --container-name $AZURE_STORAGE_CONTAINER --name $name"
            done <<< "$blobs_to_delete"
        else
            rlLogInfo "No blob older than $TIMESTAMP was found."
        fi
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun -c -t "rm -f /etc/yum.repos.d/azure-cli.repo"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
