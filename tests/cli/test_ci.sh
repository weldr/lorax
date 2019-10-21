#!/bin/bash
# Note: execute this file from the project root directory

set -e

. /usr/share/beakerlib/beakerlib.sh

yum-config-manager --enable epel 

dnf -y install $(cat /lorax/test-packages)

pip3 install pocketlint 

cd /lorax

rlJournalStart
    rlPhaseStartTest "check"
        # running with -k because of possible errors that would make "make test" to not run
    	rlRun "make ci -k"
    rlPhaseEnd

rlJournalEnd
rlJournalPrintText
