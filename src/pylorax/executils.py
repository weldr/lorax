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
from subprocess import TimeoutExpired
import signal

import logging
log = logging.getLogger("pylorax")
program_log = logging.getLogger("program")

# pylint: disable=not-context-manager
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
        :keyword preexec_fn: A function to run before execution starts.
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

    # pylint: disable=subprocess-popen-preexec-fn
    return subprocess.Popen(argv,
                            stdin=stdin,
                            stdout=stdout,
                            stderr=stderr,
                            close_fds=True,
                            preexec_fn=preexec, cwd=root, env=env, **kwargs)

def _run_program(argv, root='/', stdin=None, stdout=None, env_prune=None, log_output=True,
        binary_output=False, filter_stderr=False, raise_err=False, callback=None,
        env_add=None, reset_handlers=True, reset_lang=True):
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
        :param env_add: environment variables to add before execution
        :param reset_handlers: whether to reset to SIG_DFL any signal handlers set to SIG_IGN
        :param reset_lang: whether to set the locale of the child process to C
        :return: The return code of the command and the output
        :raises: OSError or CalledProcessError
    """
    try:
        if filter_stderr:
            stderr = subprocess.PIPE
        else:
            stderr = subprocess.STDOUT

        proc = startProgram(argv, root=root, stdin=stdin, stdout=subprocess.PIPE, stderr=stderr,
                            env_prune=env_prune, universal_newlines=not binary_output,
                            env_add=env_add, reset_handlers=reset_handlers, reset_lang=reset_lang)

        output_string = None
        err_string = None
        if callback:
            while callback(proc) and proc.poll() is None:
                try:
                    (output_string, err_string) = proc.communicate(timeout=1)
                    break
                except TimeoutExpired:
                    pass
        else:
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
        program_log.debug("Return code: %s", proc.returncode)

    if proc.returncode and raise_err:
        output = (output_string or "") + (err_string or "")
        raise subprocess.CalledProcessError(proc.returncode, argv, output)

    return (proc.returncode, output_string)

def execWithRedirect(command, argv, stdin=None, stdout=None, root='/', env_prune=None,
                     log_output=True, binary_output=False, raise_err=False, callback=None,
                     env_add=None, reset_handlers=True, reset_lang=True):
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
        :param env_add: environment variables to add before execution
        :param reset_handlers: whether to reset to SIG_DFL any signal handlers set to SIG_IGN
        :param reset_lang: whether to set the locale of the child process to C
        :return: The return code of the command
    """
    argv = [command] + list(argv)
    return _run_program(argv, stdin=stdin, stdout=stdout, root=root, env_prune=env_prune,
            log_output=log_output, binary_output=binary_output, raise_err=raise_err, callback=callback,
            env_add=env_add, reset_handlers=reset_handlers, reset_lang=reset_lang)[0]

def execWithCapture(command, argv, stdin=None, root='/', log_output=True, filter_stderr=False,
                    raise_err=False, callback=None, env_add=None, reset_handlers=True, reset_lang=True):
    """ Run an external program and capture standard out and err.

        :param command: The command to run
        :param argv: The argument list
        :param stdin: The file object to read stdin from.
        :param root: The directory to chroot to before running command.
        :param log_output: Whether to log the output of command
        :param filter_stderr: Whether stderr should be excluded from the returned output
        :param callback: method to call while waiting for process to finish, passed Popen object
        :param env_add: environment variables to add before execution
        :param reset_handlers: whether to reset to SIG_DFL any signal handlers set to SIG_IGN
        :param reset_lang: whether to set the locale of the child process to C
        :return: The output of the command
    """
    argv = [command] + list(argv)
    return _run_program(argv, stdin=stdin, root=root, log_output=log_output, filter_stderr=filter_stderr,
                        raise_err=raise_err, callback=callback, env_add=env_add,
                        reset_handlers=reset_handlers, reset_lang=reset_lang)[1]

def execReadlines(command, argv, stdin=None, root='/', env_prune=None, filter_stderr=False,
                  callback=lambda x: True, env_add=None, reset_handlers=True, reset_lang=True):
    """ Execute an external command and return the line output of the command
        in real-time.

        This method assumes that there is a reasonably low delay between the
        end of output and the process exiting. If the child process closes
        stdout and then keeps on truckin' there will be problems.

        NOTE/WARNING: UnicodeDecodeError will be raised if the output of the
                      external command can't be decoded as UTF-8.

        :param command: The command to run
        :param argv: The argument list
        :param stdin: The file object to read stdin from.
        :param stdout: Optional file object to redirect stdout and stderr to.
        :param root: The directory to chroot to before running command.
        :param env_prune: environment variable to remove before execution
        :param filter_stderr: Whether stderr should be excluded from the returned output
        :param callback: method to call while waiting for process to finish, passed Popen object
        :param env_add: environment variables to add before execution
        :param reset_handlers: whether to reset to SIG_DFL any signal handlers set to SIG_IGN
        :param reset_lang: whether to set the locale of the child process to C
        :return: Iterator of the lines from the command

        Output from the file is not logged to program.log
        This returns an iterator with the lines from the command until it has finished
    """

    class ExecLineReader(object):
        """Iterator class for returning lines from a process and cleaning
           up the process when the output is no longer needed.
        """

        def __init__(self, proc, argv, callback):
            self._proc = proc
            self._argv = argv
            self._callback = callback

        def __iter__(self):
            return self

        def __del__(self):
            # See if the process is still running
            if self._proc.poll() is None:
                # Stop the process and ignore any problems that might arise
                try:
                    self._proc.terminate()
                except OSError:
                    pass

        def __next__(self):
            # Read the next line, blocking if a line is not yet available
            line = self._proc.stdout.readline().decode("utf-8")
            if line == '' or not self._callback(self._proc):
                # Output finished, wait for the process to end
                self._proc.communicate()

                # Check for successful exit
                if self._proc.returncode < 0:
                    raise OSError("process '%s' was killed by signal %s" %
                            (self._argv, -self._proc.returncode))
                elif self._proc.returncode > 0:
                    raise OSError("process '%s' exited with status %s" %
                            (self._argv, self._proc.returncode))
                raise StopIteration

            return line.strip()

    argv = [command] + argv

    if filter_stderr:
        stderr = subprocess.DEVNULL
    else:
        stderr = subprocess.STDOUT

    try:
        proc = startProgram(argv, root=root, stdin=stdin, stdout=subprocess.PIPE, stderr=stderr,
                            env_prune=env_prune, env_add=env_add, reset_handlers=reset_handlers, reset_lang=reset_lang)
    except OSError as e:
        with program_log_lock:
            program_log.error("Error running %s: %s", argv[0], e.strerror)
        raise

    return ExecLineReader(proc, argv, callback)

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
