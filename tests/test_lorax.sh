#!/bin/bash
# Note: execute this file from the project root directory
#
# Test building a boot.iso using lorax

set -eu

BEAKERLIB_DIR=$(mktemp -d /tmp/lorax-test.XXXXXX)
CLI="${CLI:-}"
export BEAKERLIB_DIR
source /usr/share/beakerlib/beakerlib.sh

RELEASE=$(awk -F: '{ print $5 }' /etc/system-release-cpe)
export RELEASE

function setup_tests {
    local share_dir=$1

    # Make the boot.iso boot more quickly (isolinux.cfg)
    for cfg in "$share_dir"/templates.d/99-generic/config_files/*/isolinux.cfg; do
        sed -i.orig 's/^timeout.*/timeout 20/' "$cfg"
        sed -i 's/quiet$/inst.sshd=1 console=ttyS0,115200n8/' "$cfg"
    done

    # Make the boot.iso boot more quickly (grub.conf)
    for cfg in "$share_dir"/templates.d/99-generic/config_files/*/grub.conf; do
        sed -i.orig 's/^timeout.*/timeout 2/' "$cfg"
        sed -i 's/quiet$/inst.sshd=1 console=ttyS0,115200n8/' "$cfg"
    done

    # Make the boot.iso boot more quickly (grub2-efi.cfg)
    for cfg in "$share_dir"/templates.d/99-generic/config_files/*/grub2-efi.cfg; do
        sed -i.orig 's/^set timeout.*/set timeout=2/' "$cfg"
        sed -i 's/\(.*linux .* ro$\)/\1 inst.sshd=1 console=ttyS0,115200n8/' "$cfg"
    done

}

function teardown_tests {
    local share_dir=$1

    # Restore all the configuration files
    for cfg in "$share_dir"/templates.d/99-generic/config_files/*/*.orig; do
        mv "$cfg" "${cfg%%.orig}"
    done
}

SHARE_DIR=$(mktemp -d '/tmp/lorax-share.XXXXX')
export SHARE_DIR
if [ -z "$CLI" ]; then
    cp -R /usr/share/lorax/* "$SHARE_DIR"
else
    top_srcdir=$(pwd)
    export top_srcdir
    source ./tests/testenv.sh
    cp -R ./share/* "$SHARE_DIR"
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
