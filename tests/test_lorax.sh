#!/bin/bash
# Note: execute this file from the project root directory
#
# Test building and booting a boot.iso using lorax

set -eu

BEAKERLIB_DIR=$(mktemp -d /tmp/lorax-test.XXXXXX)
export BEAKERLIB_DIR
source /usr/share/beakerlib/beakerlib.sh

RELEASE=$(awk -F: '{ print $5 }' /etc/system-release-cpe)
export RELEASE

function setup_tests {
    local share_dir=$1

    # TODO -- make this work on all arches, which have different boot options
    X86_ISOLINUX_CFG="$share_dir/templates.d/99-generic/config_files/x86/isolinux.cfg"
    sed -i.orig 's/quiet$/inst.sshd=1 console=ttyS0,115200n8/' "$X86_ISOLINUX_CFG"
    # Set the boot timeout to 2 seconds
    sed -i 's/^timeout.*/timeout 20/' "$X86_ISOLINUX_CFG"
}

function teardown_tests {
    local share_dir=$1

    X86_ISOLINUX_CFG="$share_dir/templates.d/99-generic/config_files/x86/isolinux.cfg"
    mv "$X86_ISOLINUX_CFG".orig "$X86_ISOLINUX_CFG"
}

SHARE_DIR=$(mktemp -d '/tmp/lorax-share.XXXXX')
export SHARE_DIR
if [ -z "$CLI" ]; then
    top_srcdir=$(pwd)
    export top_srcdir
    source ./tests/testenv.sh
    cp -R ./share/* "$SHARE_DIR"
else
    cp -R /usr/share/lorax/* "$SHARE_DIR"
fi
chmod a+rx -R "$SHARE_DIR"
setup_tests "$SHARE_DIR"

export BEAKERLIB_JOURNAL=0

if [ -z "$*" ]; then
    # Run all the lorax tests
    for t in ./tests/lorax/test_*sh; do
        $t
    done
else
    # execute other tests which need more adjustments in the calling environment
    # or can't be executed inside Travis CI
    for TEST in "$@"; do
        $TEST
    done
fi


teardown_tests "$SHARE_DIR"

source "$BEAKERLIB_DIR/TestResults"

if [ $TESTRESULT_RESULT_ECODE != 0 ]; then
  echo "Test failed. Leaving log in $BEAKERLIB_DIR"
  exit $TESTRESULT_RESULT_ECODE
fi

rm -rf "$BEAKERLIB_DIR"
