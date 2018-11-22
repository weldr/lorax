#!/bin/bash
# Note: execute this file from the project root directory

# setup
rm -rf /var/tmp/beakerlib-*/
export top_srcdir=`pwd`
. ./tests/testenv.sh

BLUEPRINTS_DIR=`mktemp -d '/tmp/blueprints.XXXXX'`
cp ./tests/pylorax/blueprints/*.toml $BLUEPRINTS_DIR

# start the lorax-composer daemon
./src/sbin/lorax-composer --sharedir ./share/ $BLUEPRINTS_DIR &

# wait for the backend to become ready
tries=0
until curl -m 15 --unix-socket /run/weldr/api.socket http://localhost:4000/api/status | grep 'db_supported.*true'; do
    tries=$((tries + 1))
    if [ $tries -gt 20 ]; then
        exit 1
    fi
    sleep 2
    echo "DEBUG: Waiting for backend API to become ready before testing ..."
done;


if [ -z "$*" ]; then
    # invoke cli/ tests which can be executed without special preparation
    ./tests/cli/test_blueprints_sanity.sh
    ./tests/cli/test_compose_sanity.sh
else
    # execute other cli tests which need more adjustments in the calling environment
    # or can't be executed inside Travis CI
    for TEST in "$*"; do
        ./$TEST
    done
fi


# Stop lorax-composer and remove /run/weldr/api.socket
pkill -9 lorax-composer
rm -f /run/weldr/api.socket

# look for failures
grep RESULT_STRING /var/tmp/beakerlib-*/TestResults | grep -v PASS && exit 1

# explicit return code for Makefile
exit 0
