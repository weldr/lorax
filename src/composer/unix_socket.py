#
# Copyright (C) 2018  Red Hat, Inc.
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
import http.client
import socket
import urllib3


# These 2 classes were adapted and simplified for use with just urllib3.
# Originally from https://github.com/msabramo/requests-unixsocket/blob/master/requests_unixsocket/adapters.py

# The following was adapted from some code from docker-py
# https://github.com/docker/docker-py/blob/master/docker/transport/unixconn.py
class UnixHTTPConnection(http.client.HTTPConnection, object):

    def __init__(self, socket_path, timeout=60*5):
        """Create an HTTP connection to a unix domain socket

        :param socket_path: The path to the Unix domain socket
        :param timeout: Number of seconds to timeout the connection
        """
        super(UnixHTTPConnection, self).__init__('localhost', timeout=timeout)
        self.socket_path = socket_path
        self.sock = None

    def __del__(self):  # base class does not have d'tor
        if self.sock:
            self.sock.close()

    def connect(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self.socket_path)
        self.sock = sock

class UnixHTTPConnectionPool(urllib3.connectionpool.HTTPConnectionPool):

    def __init__(self, socket_path, timeout=60*5):
        """Create a connection pool using a Unix domain socket

        :param socket_path: The path to the Unix domain socket
        :param timeout: Number of seconds to timeout the connection

        NOTE: retries are disabled for these connections, they are never useful
        """
        super(UnixHTTPConnectionPool, self).__init__('localhost', timeout=timeout, retries=False)
        self.socket_path = socket_path

    def _new_conn(self):
        return UnixHTTPConnection(self.socket_path, self.timeout)
