#
# executil.py - subprocess execution utility functions
#
# Copyright (C) 1999-2011
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
# Author(s): Erik Troan <ewt@redhat.com>
#

import os, sys
import subprocess
import threading

import logging
log = logging.getLogger("pylorax")
program_log = logging.getLogger("program")

class ExecProduct(object):
    def __init__(self, rc, stdout, stderr):
        self.rc = rc
        self.stdout = stdout
        self.stderr = stderr

#Python reimplementation of the shell tee process, so we can
#feed the pipe output into two places at the same time
class tee(threading.Thread):
    def __init__(self, inputdesc, outputdesc, logmethod, command):
        threading.Thread.__init__(self)
        self.inputdesc = os.fdopen(inputdesc, "r")
        self.outputdesc = outputdesc
        self.logmethod = logmethod
        self.running = True
        self.command = command

    def run(self):
        while self.running:
            try:
                data = self.inputdesc.readline()
            except IOError:
                self.logmethod("Can't read from pipe during a call to %s. "
                               "(program terminated suddenly?)" % self.command)
                break
            if data == "":
                self.running = False
            else:
                self.logmethod(data.rstrip('\n'))
                os.write(self.outputdesc, data)

    def stop(self):
        self.running = False
        return self

## Run an external program and redirect the output to a file.
# @param command The command to run.
# @param argv A list of arguments.
# @param stdin The file descriptor to read stdin from.
# @param stdout The file descriptor to redirect stdout to.
# @param stderr The file descriptor to redirect stderr to.
# @param root The directory to chroot to before running command.
# @param preexec_fn function to pass to Popen
# @param cwd working directory to pass to Popen
# @return The return code of command.
def execWithRedirect(command, argv, stdin = None, stdout = None,
                     stderr = None, root = None, preexec_fn=None, cwd=None):
    def chroot ():
        os.chroot(root)

    stdinclose = stdoutclose = stderrclose = lambda : None

    argv = list(argv)
    if isinstance(stdin, str):
        if os.access(stdin, os.R_OK):
            stdin = os.open(stdin, os.O_RDONLY)
            stdinclose = lambda : os.close(stdin)
        else:
            stdin = sys.stdin.fileno()
    elif isinstance(stdin, int):
        pass
    elif stdin is None or not isinstance(stdin, file):
        stdin = sys.stdin.fileno()

    if isinstance(stdout, str):
        stdout = os.open(stdout, os.O_RDWR|os.O_CREAT)
        stdoutclose = lambda : os.close(stdout)
    elif isinstance(stdout, int):
        pass
    elif stdout is None or not isinstance(stdout, file):
        stdout = sys.stdout.fileno()

    if isinstance(stderr, str):
        stderr = os.open(stderr, os.O_RDWR|os.O_CREAT)
        stderrclose = lambda : os.close(stderr)
    elif isinstance(stderr, int):
        pass
    elif stderr is None or not isinstance(stderr, file):
        stderr = sys.stderr.fileno()

    program_log.info("Running... %s" % (" ".join([command] + argv),))

    #prepare os pipes for feeding tee proceses
    pstdout, pstdin = os.pipe()
    perrout, perrin = os.pipe()

    env = os.environ.copy()
    env.update({"LC_ALL": "C"})

    if root:
        preexec_fn = chroot
        cwd = root
        program_log.info("chrooting into %s" % (cwd,))
    elif cwd:
        program_log.info("chdiring into %s" % (cwd,))

    try:
        #prepare tee proceses
        proc_std = tee(pstdout, stdout, program_log.info, command)
        proc_err = tee(perrout, stderr, program_log.error, command)

        #start monitoring the outputs
        proc_std.start()
        proc_err.start()

        proc = subprocess.Popen([command] + argv, stdin=stdin,
                                stdout=pstdin,
                                stderr=perrin,
                                preexec_fn=preexec_fn, cwd=cwd,
                                env=env)

        proc.wait()
        ret = proc.returncode

        #close the input ends of pipes so we get EOF in the tee processes
        os.close(pstdin)
        os.close(perrin)

        #wait for the output to be written and destroy them
        proc_std.join()
        del proc_std

        proc_err.join()
        del proc_err

        stdinclose()
        stdoutclose()
        stderrclose()
    except OSError as e:
        errstr = "Error running %s: %s" % (command, e.strerror)
        log.error(errstr)
        program_log.error(errstr)
        #close the input ends of pipes so we get EOF in the tee processes
        os.close(pstdin)
        os.close(perrin)
        proc_std.join()
        proc_err.join()

        stdinclose()
        stdoutclose()
        stderrclose()
        raise RuntimeError, errstr

    return ret

## Run an external program and capture standard out.
# @param command The command to run.
# @param argv A list of arguments.
# @param stdin The file descriptor to read stdin from.
# @param stderr The file descriptor to redirect stderr to.
# @param root The directory to chroot to before running command.
# @param preexec_fn function to pass to Popen
# @param cwd working directory to pass to Popen
# @return The output of command from stdout.
def execWithCapture(command, argv, stdin = None, stderr = None, root=None, preexec_fn=None, cwd=None):
    def chroot():
        os.chroot(root)

    def closefds ():
        stdinclose()
        stderrclose()

    stdinclose = stderrclose = lambda : None
    rc = ""
    argv = list(argv)

    if isinstance(stdin, str):
        if os.access(stdin, os.R_OK):
            stdin = os.open(stdin, os.O_RDONLY)
            stdinclose = lambda : os.close(stdin)
        else:
            stdin = sys.stdin.fileno()
    elif isinstance(stdin, int):
        pass
    elif stdin is None or not isinstance(stdin, file):
        stdin = sys.stdin.fileno()

    if isinstance(stderr, str):
        stderr = os.open(stderr, os.O_RDWR|os.O_CREAT)
        stderrclose = lambda : os.close(stderr)
    elif isinstance(stderr, int):
        pass
    elif stderr is None or not isinstance(stderr, file):
        stderr = sys.stderr.fileno()

    program_log.info("Running... %s" % (" ".join([command] + argv),))

    env = os.environ.copy()
    env.update({"LC_ALL": "C"})

    if root:
        preexec_fn = chroot
        cwd = root
        program_log.info("chrooting into %s" % (cwd,))
    elif cwd:
        program_log.info("chdiring into %s" % (cwd,))

    try:
        proc = subprocess.Popen([command] + argv, stdin=stdin,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                preexec_fn=preexec_fn, cwd=cwd,
                                env=env)

        while True:
            (outStr, errStr) = proc.communicate()
            if outStr:
                map(program_log.info, outStr.splitlines())
                rc += outStr
            if errStr:
                map(program_log.error, errStr.splitlines())
                os.write(stderr, errStr)

            if proc.returncode is not None:
                break
    except OSError as e:
        log.error ("Error running " + command + ": " + e.strerror)
        closefds()
        raise RuntimeError, "Error running " + command + ": " + e.strerror

    closefds()
    return rc

def execWithCallback(command, argv, stdin = None, stdout = None,
                     stderr = None, echo = True, callback = None,
                     callback_data = None, root = '/'):
    def chroot():
        os.chroot(root)

    def closefds ():
        stdinclose()
        stdoutclose()
        stderrclose()

    stdinclose = stdoutclose = stderrclose = lambda : None

    argv = list(argv)
    if isinstance(stdin, str):
        if os.access(stdin, os.R_OK):
            stdin = os.open(stdin, os.O_RDONLY)
            stdinclose = lambda : os.close(stdin)
        else:
            stdin = sys.stdin.fileno()
    elif isinstance(stdin, int):
        pass
    elif stdin is None or not isinstance(stdin, file):
        stdin = sys.stdin.fileno()

    if isinstance(stdout, str):
        stdout = os.open(stdout, os.O_RDWR|os.O_CREAT)
        stdoutclose = lambda : os.close(stdout)
    elif isinstance(stdout, int):
        pass
    elif stdout is None or not isinstance(stdout, file):
        stdout = sys.stdout.fileno()

    if isinstance(stderr, str):
        stderr = os.open(stderr, os.O_RDWR|os.O_CREAT)
        stderrclose = lambda : os.close(stderr)
    elif isinstance(stderr, int):
        pass
    elif stderr is None or not isinstance(stderr, file):
        stderr = sys.stderr.fileno()

    program_log.info("Running... %s" % (" ".join([command] + argv),))

    p = os.pipe()
    p_stderr = os.pipe()
    childpid = os.fork()
    if not childpid:
        os.close(p[0])
        os.close(p_stderr[0])
        os.dup2(p[1], 1)
        os.dup2(p_stderr[1], 2)
        os.dup2(stdin, 0)
        os.close(stdin)
        os.close(p[1])
        os.close(p_stderr[1])

        os.execvp(command, [command] + argv)
        os._exit(1)

    os.close(p[1])
    os.close(p_stderr[1])

    log_output = ''
    while 1:
        try:
            s = os.read(p[0], 1)
        except OSError as e:
            if e.errno != 4:
                map(program_log.info, log_output.splitlines())
                raise IOError, e.args

        if echo:
            os.write(stdout, s)
        log_output += s

        if callback:
            callback(s, callback_data=callback_data)

        # break out early if the sub-process changes status.
        # no need to flush the stream if the process has exited
        try:
            (pid, status) = os.waitpid(childpid,os.WNOHANG)
            if pid != 0:
                break
        except OSError as e:
            log.critical("exception from waitpid: %s %s" %(e.errno, e.strerror))

        if len(s) < 1:
            break

    map(program_log.info, log_output.splitlines())

    log_errors = ''
    while 1:
        try:
            err = os.read(p_stderr[0], 128)
        except OSError as e:
            if e.errno != 4:
                map(program_log.error, log_errors.splitlines())
                raise IOError, e.args
            break
        log_errors += err
        if len(err) < 1:
            break

    os.write(stderr, log_errors)
    map(program_log.error, log_errors.splitlines())
    os.close(p[0])
    os.close(p_stderr[0])

    try:
        #if we didn't already get our child's exit status above, do so now.
        if not pid:
            (pid, status) = os.waitpid(childpid, 0)
    except OSError as e:
        log.critical("exception from waitpid: %s %s" %(e.errno, e.strerror))

    closefds()

    rc = 1
    if os.WIFEXITED(status):
        rc = os.WEXITSTATUS(status)
    return ExecProduct(rc, log_output , log_errors)

def _pulseProgressCallback(data, callback_data=None):
    if callback_data:
        callback_data.pulse()

def execWithPulseProgress(command, argv, stdin = None, stdout = None,
                          stderr = None, echo = True, progress = None,
                          root = '/'):
    return execWithCallback(command, argv, stdin=stdin, stdout=stdout,
                     stderr=stderr, echo=echo, callback=_pulseProgressCallback,
                     callback_data=progress, root=root)

## Run a shell.
def execConsole():
    try:
        proc = subprocess.Popen(["/bin/sh"])
        proc.wait()
    except OSError as e:
        raise RuntimeError, "Error running /bin/sh: " + e.strerror


