# monitor.py
#
# Copyright (C) 2011-2015  Red Hat, Inc.
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
# Author(s): Brian C. Lane <bcl@redhat.com>
#
import logging
log = logging.getLogger("livemedia-creator")

import re
import socket
import socketserver
import threading
import time

class LogRequestHandler(socketserver.BaseRequestHandler):
    """
    Handle monitoring and saving the logfiles from the virtual install

    Incoming data is written to self.server.log_path and each line is checked
    for patterns that would indicate that the installation failed.
    self.server.log_error is set True when this happens.
    """

    simple_tests = [
        "Traceback (",
        "traceback script(s) have been run",
        "Out of memory:",
        "Call Trace:",
        "insufficient disk space:",
        "Not enough disk space to download the packages",
        "error populating transaction after",
        "crashed on signal",
        "packaging: Missed: NoSuchPackage",
        "packaging: Installation failed",
        "The following error occurred while installing.  This is a fatal error"
    ]

    re_tests = [
        r"packaging: base repo .* not valid",
        r"packaging: .* requires .*"
    ]

    def setup(self):
        """Start writing to self.server.log_path"""

        if self.server.log_path:
            self.fp = open(self.server.log_path, "w") # pylint: disable=attribute-defined-outside-init
        else:
            self.fp = None
        self.request.settimeout(10)

    def handle(self):
        """
        Write incoming data to a logfile and check for errors

        Split incoming data into lines and check for any Tracebacks or other
        errors that indicate that the install failed.

        Loops until self.server.kill is True
        """
        log.info("Processing logs from %s", self.client_address)
        line = ""
        while True:
            if self.server.kill:
                break

            try:
                data = str(self.request.recv(4096), "utf8")
                if self.fp:
                    self.fp.write(data)
                    self.fp.flush()

                # check the data for errors and set error flag
                # need to assemble it into lines so we can test for the error
                # string.
                while data:
                    more = data.split("\n", 1)
                    line += more[0]
                    if len(more) > 1:
                        self.iserror(line)
                        line = ""
                        data = more[1]
                    else:
                        data = None

            except socket.timeout:
                pass
            except Exception as e:       # pylint: disable=broad-except
                log.info("log processing killed by exception: %s", e)
                break

    def finish(self):
        log.info("Shutting down log processing")
        self.request.close()
        if self.fp:
            self.fp.close()

    def iserror(self, line):
        """
        Check a line to see if it contains an error indicating installation failure

        :param str line: log line to check for failure

        If the line contains IGNORED it will be skipped.
        """
        if "IGNORED" in line:
            return

        for t in self.simple_tests:
            if t in line:
                self.server.log_error = True
                self.server.error_line = line
                return
        for t in self.re_tests:
            if re.search(t, line):
                self.server.log_error = True
                self.server.error_line = line
                return


class LogServer(socketserver.TCPServer):
    """A TCP Server that listens for log data"""

    # Number of seconds to wait for a connection after startup
    timeout = 60

    def __init__(self, log_path, *args, **kwargs):
        """
        Setup the log server

        :param str log_path: Path to the log file to write
        """
        self.kill = False
        self.log_error = False
        self.error_line = ""
        self.log_path = log_path
        self._timeout = kwargs.pop("timeout", None)
        if self._timeout:
            self._start_time = time.time()
        socketserver.TCPServer.__init__(self, *args, **kwargs)

    def log_check(self):
        """
        Check to see if an error has been found in the log

        :returns: True if there has been an error
        :rtype: bool
        """
        if self._timeout:
            taking_too_long = time.time() > self._start_time + (self._timeout * 60)
            if taking_too_long:
                log.error("Canceling installation due to timeout")
        else:
            taking_too_long = False
        return self.log_error or taking_too_long


class LogMonitor(object):
    """
    Setup a server to monitor the logs output by the installation

    This needs to be running before the virt-install runs, it expects
    there to be a listener on the port used for the virtio log port.
    """
    def __init__(self, log_path=None, host="localhost", port=0, timeout=None, log_request_handler_class=LogRequestHandler):
        """
        Start a thread to monitor the logs.

        :param str log_path: Path to the logfile to write
        :param str host: Host to bind to. Default is localhost.
        :param int port: Port to listen to or 0 to pick a port

        If 0 is passed for the port the dynamically assigned port will be
        available as self.port

        If log_path isn't set then it only monitors the logs, instead of
        also writing them to disk.
        """
        self.server = LogServer(log_path, (host, port), log_request_handler_class, timeout=timeout)
        self.host, self.port = self.server.server_address
        self.log_path = log_path
        self.server_thread = threading.Thread(target=self.server.handle_request)
        self.server_thread.daemon = True
        self.server_thread.start()

    def shutdown(self):
        """Force shutdown of the monitoring thread"""
        self.server.kill = True
        self.server_thread.join()
