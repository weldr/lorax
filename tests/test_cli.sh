#!/bin/bash
# Note: execute this file from the project root directory

set -eu

. $(dirname $0)/cli/lib/lib.sh

export BEAKERLIB_DIR=$(mktemp -d /tmp/composer-test.XXXXXX)
CLI="${CLI:-}"

function setup_tests {
    local share_dir=$1
    local blueprints_dir=$2

    # explicitly enable sshd for live-iso b/c it is disabled by default
    # due to security concerns (no root password required)
    sed -i.orig 's/^services.*/services --disabled="network" --enabled="NetworkManager,sshd"/' $share_dir/composer/live-iso.ks
    # explicitly enable logging in with empty passwords via ssh, because
    # the default sshd setting for PermitEmptyPasswords is 'no'
    awk -i inplace "
        /%post/ && FLAG != 2 {FLAG=1}
        /%end/ && FLAG == 1 {print \"sed -i 's/.*PermitEmptyPasswords.*/PermitEmptyPasswords yes/' /etc/ssh/sshd_config\"; FLAG=2}
        {print}" \
        $share_dir/composer/live-iso.ks

    # do a backup of the original blueprints directory and get rid of the git
    # directory (otherwise all of the initial changes in blueprints would have
    # to be done using blueprints push)
    cp -r $blueprints_dir ${blueprints_dir}.orig
    rm -rf $blueprints_dir/git

    # append a section with additional option on kernel command line to example-http-server blueprint
    # which is used for building of most of the images
    cat >> $blueprints_dir/example-http-server.toml << __EOF__

[customizations.kernel]
append = "custom_cmdline_arg console=ttyS0,115200n8"
__EOF__
}

function teardown_tests {
    local share_dir=$1
    local blueprints_dir=$2

    mv $share_dir/composer/live-iso.ks.orig $share_dir/composer/live-iso.ks
    rm -rf $blueprints_dir
    mv ${blueprints_dir}.orig $blueprints_dir
}

# cloud credentials
if [ -f "~/.config/lorax-test-env" ]; then
    . ~/.config/lorax-test-env
fi

if [ -f "/var/tmp/lorax-test-env" ]; then
    . /var/tmp/lorax-test-env
fi

if [ -z "$CLI" ]; then
    export top_srcdir=`pwd`
    . ./tests/testenv.sh

    export BLUEPRINTS_DIR=`mktemp -d '/tmp/composer-blueprints.XXXXX'`
    cp ./tests/pylorax/blueprints/*.toml $BLUEPRINTS_DIR

    export SHARE_DIR=`mktemp -d '/tmp/composer-share.XXXXX'`
    cp -R ./share/* $SHARE_DIR
    chmod a+rx -R $SHARE_DIR

    setup_tests $SHARE_DIR $BLUEPRINTS_DIR
    # start the lorax-composer daemon
    composer_start
else
    export PACKAGE="composer-cli"
    export BLUEPRINTS_DIR="/var/lib/lorax/composer/blueprints"
    composer_stop
    setup_tests /usr/share/lorax /var/lib/lorax/composer/blueprints
    composer_start
fi


export BEAKERLIB_JOURNAL=0
if [ -z "$*" ]; then
    # invoke cli/ tests which can be executed without special preparation
    ./tests/cli/test_blueprints_sanity.sh
    ./tests/cli/test_compose_sanity.sh
else
    # execute other cli tests which need more adjustments in the calling environment
    # or can't be executed inside Travis CI
    for TEST in "$@"; do
        $TEST
    done
fi


if [ -z "$CLI" ]; then
    # stop lorax-composer and remove /run/weldr/api.socket
    # only if running against source
    composer_stop
    teardown_tests $SHARE_DIR $BLUEPRINTS_DIR
else
    composer_stop
    teardown_tests /usr/share/lorax /var/lib/lorax/composer/blueprints
    # start lorax-composer again so we can continue with manual or other kinds
    # of testing on the same system
    composer_start
fi

. $BEAKERLIB_DIR/TestResults

if [ $TESTRESULT_RESULT_ECODE != 0 ]; then
  echo "Test failed. Leaving log in $BEAKERLIB_DIR"
  exit $TESTRESULT_RESULT_ECODE
fi

rm -rf $BEAKERLIB_DIR
