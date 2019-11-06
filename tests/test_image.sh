#!/bin/bash
# Note: execute this file from the project root directory
# Used for running a beakerlib test script inside a running VM
# without setting up composer first!

set -eu

. $(dirname $0)/cli/lib/lib.sh

setup_beakerlib_env

run_beakerlib_tests "$@"

parse_beakerlib_results
