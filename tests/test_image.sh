#!/bin/bash
# Note: execute this file from the project root directory

set -eu

. $(dirname $0)/cli/lib/lib.sh

export BEAKERLIB_DIR=$(mktemp -d /tmp/composer-test.XXXXXX)
export BEAKERLIB_JOURNAL=0
if [ -z "$*" ]; then
    echo "test_image.sh requires a test to execute"
else
    # execute tests
    for TEST in "$@"; do
        $TEST
    done
fi

. $BEAKERLIB_DIR/TestResults

if [ $TESTRESULT_RESULT_ECODE != 0 ]; then
  echo "Test failed. Leaving log in $BEAKERLIB_DIR"
  exit $TESTRESULT_RESULT_ECODE
fi

rm -rf $BEAKERLIB_DIR
