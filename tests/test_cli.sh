#!/bin/bash
# Note: execute this file from the project root directory

# setup

export TESTRESULT_BEAKERLIB_DIR=`mktemp -d /var/tmp/beakerlib-composer-XXXXXX`
export top_srcdir=`pwd`
. ./tests/testenv.sh

# start the lorax-composer daemon
./src/sbin/lorax-composer ./tests/pylorax/blueprints/ &

# wait for the backend to become ready
until curl --unix-socket /run/weldr/api.socket http://localhost:4000/api/status | grep '"db_supported":true'; do
    sleep 2
    echo "DEBUG: Waiting for backend API to become ready before testing ..."
done;

# invoke cli/ tests
./tests/cli/test_blueprints_sanity.sh


# look for failures
grep RESULT_STRING $TESTRESULT_BEAKERLIB_DIR/TestResults | grep -v PASS && exit 1

# explicit return code for Makefile
exit 0
