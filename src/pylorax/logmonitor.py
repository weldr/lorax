#
# Copyright (C) 2011-2017  Red Hat, Inc.
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
import re
import socket
import SocketServer
import threading

class LogRequestHandler(SocketServer.BaseRequestHandler):
    """
    Handle monitoring and saving the logfiles from the virtual install
    """
    def setup(self):
        if self.server.log_path:
            self.fp = open(self.server.log_path, "w")
        else:
            print "no log_path specified"
        self.request.settimeout(10)

    def handle(self):
        """
        Handle writing incoming data to a logfile and
        checking the logs for any Tracebacks or other errors that indicate
        that the install failed.
        """
        line = ""
        while True:
            if self.server.kill:
                break

            try:
                data = self.request.recv(4096)
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
            except:
                break

    def finish(self):
        self.fp.close()

    def iserror(self, line):
        """
        Check a line to see if it contains an error indicating install failure
        """
        simple_tests = ["Traceback (",
                        "Out of memory:",
                        "Call Trace:",
                        "insufficient disk space:"]
        re_tests =     [r"packaging: base repo .* not valid"]
        for t in simple_tests:
            if line.find(t) > -1:
                self.server.log_error = True
                return
        for t in re_tests:
            if re.search(t, line):
                self.server.log_error = True
                return


class LogServer(SocketServer.TCPServer):
    """
    Add path to logfile
    Add log error flag
    Add a kill switch
    """
    def __init__(self, log_path, *args, **kwargs):
        self.kill = False
        self.log_error = False
        self.log_path = log_path
        SocketServer.TCPServer.__init__(self, *args, **kwargs)

    def log_check(self):
        return self.log_error


class LogMonitor(object):
    """
    Contains all the stuff needed to setup a thread to listen to the logs
    from the virtual install
    """
    def __init__(self, log_path, host="localhost", port=0):
        """
        Fire up the thread listening for logs
        """
        self.server = LogServer(log_path, (host, port), LogRequestHandler)
        self.host, self.port = self.server.server_address
        self.log_path = log_path
        self.server_thread = threading.Thread(target=self.server.handle_request)
        self.server_thread.daemon = True
        self.server_thread.start()

    def shutdown(self):
        self.server.kill = True
        self.server_thread.join()
