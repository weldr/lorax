# Hacking on Lorax

Here's where to get the code:

    $ git clone https://github.com/weldr/lorax
    $ cd lorax/

How to build it:

    $ make

## How to run the tests

To run the tests you need the following dependencies installed:

    $ yum install python3-nose python3-pytest-mock python3-pocketlint \
		python3-mock python3-magic

Run the basic linting tests like this:

    $ make check


To run the broader unit and integration tests we use:

    $ make test

Some of the tests will be skipped unless a lorax-composer process is running
and listening on an accessible socket. Either run lorax-composer from the
checkout, or the installed version.

