#
# executil.py - subprocess execution utility functions
#
# Copyright (C) 1999-2015
# Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os
import subprocess
import signal
from time import sleep

import logging
log = logging.getLogger("pylorax")
program_log = logging.getLogger("program")

from threading import Lock
program_log_lock = Lock()

_child_env = {}

def setenv(name, value):
    """ Set an environment variable to be used by child processes.

        This method does not modify os.environ for the running process, which
        is not thread-safe. If setenv has already been called for a particular
        variable name, the old value is overwritten.

        :param str name: The name of the environment variable
        :param str value: The value of the environment variable
    """

    _child_env[name] = value

def augmentEnv():
    env = os.environ.copy()
    env.update(_child_env)
    return env

class ExecProduct(object):
    def __init__(self, rc, stdout, stderr):
        self.rc = rc
        self.stdout = stdout
        self.stderr = stderr

def startProgram(argv, root='/', stdin=None, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env_prune=None, env_add=None, reset_handlers=True, reset_lang=True, **kwargs):
    """ Start an external program and return the Popen object.

        The root and reset_handlers arguments are handled by passing a
        preexec_fn argument to subprocess.Popen, but an additional preexec_fn
        can still be specified and will be run. The user preexec_fn will be run
        last.

        :param argv: The command to run and argument
        :param root: The directory to chroot to before running command.
        :param stdin: The file object to read stdin from.
        :param stdout: The file object to write stdout to.
        :param stderr: The file object to write stderr to.
        :param env_prune: environment variables to remove before execution
        :param env_add: environment variables to add before execution
        :param reset_handlers: whether to reset to SIG_DFL any signal handlers set to SIG_IGN
        :param reset_lang: whether to set the locale of the child process to C
        :param kwargs: Additional parameters to pass to subprocess.Popen
        :return: A Popen object for the running command.
    """
    if env_prune is None:
        env_prune = []

    # Check for and save a preexec_fn argument
    preexec_fn = kwargs.pop("preexec_fn", None)

    def preexec():
        # If a target root was specificed, chroot into it
        if root and root != '/':
            os.chroot(root)
            os.chdir("/")

        # Signal handlers set to SIG_IGN persist across exec. Reset
        # these to SIG_DFL if requested. In particular this will include the
        # SIGPIPE handler set by python.
        if reset_handlers:
            for signum in range(1, signal.NSIG):
                if signal.getsignal(signum) == signal.SIG_IGN:
                    signal.signal(signum, signal.SIG_DFL)

        # If the user specified an additional preexec_fn argument, run it
        if preexec_fn is not None:
            preexec_fn()

    with program_log_lock:
        program_log.info("Running... %s", " ".join(argv))

    env = augmentEnv()
    for var in env_prune:
        env.pop(var, None)

    if reset_lang:
        env.update({"LC_ALL": "C"})

    if env_add:
        env.update(env_add)

    return subprocess.Popen(argv,
                            stdin=stdin,
                            stdout=stdout,
                            stderr=stderr,
                            close_fds=True,
                            preexec_fn=preexec, cwd=root, env=env, **kwargs)

def _run_program(argv, root='/', stdin=None, stdout=None, env_prune=None, log_output=True,
        binary_output=False, filter_stderr=False, raise_err=False, callback=None):
    """ Run an external program, log the output and return it to the caller

        :param argv: The command to run and argument
        :param root: The directory to chroot to before running command.
        :param stdin: The file object to read stdin from.
        :param stdout: Optional file object to write the output to.
        :param env_prune: environment variable to remove before execution
        :param log_output: whether to log the output of command
        :param binary_output: whether to treat the output of command as binary data
        :param filter_stderr: whether to exclude the contents of stderr from the returned output
        :param raise_err: whether to raise a CalledProcessError if the returncode is non-zero
        :param callback: method to call while waiting for process to finish, passed Popen object
        :return: The return code of the command and the output
        :raises: OSError or CalledProcessError
    """
    try:
        if filter_stderr:
            stderr = subprocess.PIPE
        else:
            stderr = subprocess.STDOUT

        proc = startProgram(argv, root=root, stdin=stdin, stdout=subprocess.PIPE, stderr=stderr,
                            env_prune=env_prune, universal_newlines=not binary_output)

        if callback:
            while callback(proc) and proc.poll() is None:
                sleep(1)

        (output_string, err_string) = proc.communicate()
        if output_string:
            if binary_output:
                output_lines = [output_string]
            else:
                if output_string[-1] != "\n":
                    output_string = output_string + "\n"
                output_lines = output_string.splitlines(True)

            if log_output:
                with program_log_lock:
                    for line in output_lines:
                        program_log.info(line.strip())

            if stdout:
                stdout.write(output_string)

        # If stderr was filtered, log it separately
        if filter_stderr and err_string and log_output:
            err_lines = err_string.splitlines(True)

            with program_log_lock:
                for line in err_lines:
                    program_log.info(line.strip())

    except OSError as e:
        with program_log_lock:
            program_log.error("Error running %s: %s", argv[0], e.strerror)
        raise

    with program_log_lock:
        program_log.debug("Return code: %d", proc.returncode)

    if proc.returncode and raise_err:
        raise subprocess.CalledProcessError(proc.returncode, argv)

    return (proc.returncode, output_string)

def execWithRedirect(command, argv, stdin=None, stdout=None, root='/', env_prune=None,
                     log_output=True, binary_output=False, raise_err=False, callback=None):
    """ Run an external program and redirect the output to a file.

        :param command: The command to run
        :param argv: The argument list
        :param stdin: The file object to read stdin from.
        :param stdout: Optional file object to redirect stdout and stderr to.
        :param root: The directory to chroot to before running command.
        :param env_prune: environment variable to remove before execution
        :param log_output: whether to log the output of command
        :param binary_output: whether to treat the output of command as binary data
        :param raise_err: whether to raise a CalledProcessError if the returncode is non-zero
        :param callback: method to call while waiting for process to finish, passed Popen object
        :return: The return code of the command
    """
    argv = [command] + list(argv)
    return _run_program(argv, stdin=stdin, stdout=stdout, root=root, env_prune=env_prune,
            log_output=log_output, binary_output=binary_output, raise_err=raise_err, callback=callback)[0]

def execWithCapture(command, argv, stdin=None, root='/', log_output=True, filter_stderr=False,
                    raise_err=False, callback=None):
    """ Run an external program and capture standard out and err.

        :param command: The command to run
        :param argv: The argument list
        :param stdin: The file object to read stdin from.
        :param root: The directory to chroot to before running command.
        :param log_output: Whether to log the output of command
        :param filter_stderr: Whether stderr should be excluded from the returned output
        :param raise_err: whether to raise a CalledProcessError if the returncode is non-zero
        :return: The output of the command
    """
    argv = [command] + list(argv)
    return _run_program(argv, stdin=stdin, root=root, log_output=log_output, filter_stderr=filter_stderr,
                        raise_err=raise_err, callback=callback)[1]

def runcmd(cmd, **kwargs):
    """ run execWithRedirect with raise_err=True
    """
    kwargs["raise_err"] = True
    return execWithRedirect(cmd[0], cmd[1:], **kwargs)

def runcmd_output(cmd, **kwargs):
    """ run execWithCapture with raise_err=True
    """
    kwargs["raise_err"] = True
    return execWithCapture(cmd[0], cmd[1:], **kwargs)
