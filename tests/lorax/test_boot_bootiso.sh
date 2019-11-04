#!/bin/bash
# Note: execute this file from inside the booted boot.iso
# We cannot use beakerlib because the boot.iso is missing some of the executables it depends on
#

#####
#
# Test a booted boot.iso
#
#####

set -e

if ! grep anaconda /root/lorax-packages.log; then
    echo "ERROR: anaconda not included in boot.iso package list"
    exit 1
fi
