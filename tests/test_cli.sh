#!/bin/bash
# Note: execute this file from the project root directory

# setup
rm -rf /var/tmp/beakerlib-*/
export top_srcdir=`pwd`
. ./tests/testenv.sh

# start the lorax-composer daemon
./src/sbin/lorax-composer --sharedir ./share/ ./tests/pylorax/blueprints/ &

# wait for the backend to become ready
until curl --unix-socket /run/weldr/api.socket http://localhost:4000/api/status | grep '"db_supported": true'; do
    sleep 2
    echo "DEBUG: Waiting for backend API to become ready before testing ..."
done;

# invoke cli/ tests
./tests/cli/test_blueprints_sanity.sh
./tests/cli/test_compose_sanity.sh

# look for failures
grep RESULT_STRING /var/tmp/beakerlib-*/TestResults | grep -v PASS && exit 1

# explicit return code for Makefile
exit 0
