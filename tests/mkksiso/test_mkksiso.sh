#!/bin/bash
# Note: execute this file from the project root directory

set -eu

[ "$(id -u)" -eq 0 ] || (echo "$0 must be run as root"; exit 1)

BEAKERLIB_DIR=$(mktemp -d /tmp/composer-test.XXXXXX)
export BEAKERLIB_DIR
CLI="${CLI:-}"

# Override downloading the iso
TEST_ISO="${TEST_ISO:-}"

if [ -z "$CLI" ]; then
    top_srcdir=$(pwd)
    export top_srcdir
    . ./tests/testenv.sh
fi

# Fetch the boot.iso for the current arch and return the path to a temporary directory
ISO_DIR=$(mktemp -d -p /var/tmp/)
function finish {
    [ -n "$ISO_DIR" ] && rm -rf "$ISO_DIR"
}
trap finish EXIT

pushd "$ISO_DIR"
ARCH=$(uname -m)

if [ -z "$TEST_ISO" ]; then
    # Use the Fedora mirrors to select the iso source
    BASEURL=$(curl "https://mirrors.fedoraproject.org/mirrorlist?repo=fedora-31&arch=$ARCH" | \
              grep -v "^#" | head -n 1)
    curl --remote-name-all "$BASEURL/images/boot.iso"
    TEST_ISO="$ISO_DIR/boot.iso"
elif [ ! -e "$TEST_ISO" ]; then
    echo "$TEST_ISO is missing."
    exit 1
fi
popd

export BEAKERLIB_JOURNAL=0
./tests/mkksiso/test_boot_repo.sh "$TEST_ISO" ./tests/mkksiso/ks/extra-repo.ks
./tests/mkksiso/test_liveimg.sh "$TEST_ISO" ./tests/mkksiso/ks/liveimg.ks

. $BEAKERLIB_DIR/TestResults

if [ "$TESTRESULT_RESULT_ECODE" != 0 ]; then
  echo "Test failed. Leaving log in $BEAKERLIB_DIR"
  exit "$TESTRESULT_RESULT_ECODE"
fi

rm -rf "$BEAKERLIB_DIR"
