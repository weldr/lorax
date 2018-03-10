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
import logging
log = logging.getLogger("composer-cli")

import os
import json

from composer.unix_socket import UnixHTTPConnectionPool

def api_url(api_version, url):
    """Return the versioned path to the API route

    """
    return os.path.normpath("/api/v%s/%s" % (api_version, url))

def get_url_raw(socket_path, url):
    """Return the raw results of a GET request

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param url: URL to request
    :type url: str
    :returns: The raw response from the server
    :rtype: str
    """
    http = UnixHTTPConnectionPool(socket_path)
    r = http.request("GET", url)
    return r.data.decode('utf-8')

def get_url_json(socket_path, url):
    """Return the JSON results of a GET request

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param url: URL to request
    :type url: str
    :returns: The json response from the server
    :rtype: dict
    """
    http = UnixHTTPConnectionPool(socket_path)
    r = http.request("GET", url)
    return json.loads(r.data.decode('utf-8'))

def delete_url_json(socket_path, url):
    """Send a DELETE request to the url and return JSON response

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param url: URL to send DELETE to
    :type url: str
    :returns: The json response from the server
    :rtype: dict
    """
    http = UnixHTTPConnectionPool(socket_path)
    r = http.request("DELETE", url)
    return json.loads(r.data.decode("utf-8"))

def post_url(socket_path, url, body):
    """POST raw data to the URL

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param url: URL to send POST to
    :type url: str
    :param body: The data for the body of the POST
    :type body: str
    :returns: The json response from the server
    :rtype: dict
    """
    http = UnixHTTPConnectionPool(socket_path)
    r = http.request("POST", url,
                     body=body.encode("utf-8"))
    return json.loads(r.data.decode("utf-8"))

def post_url_toml(socket_path, url, body):
    """POST a TOML recipe to the URL

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param url: URL to send POST to
    :type url: str
    :param body: The data for the body of the POST
    :type body: str
    :returns: The json response from the server
    :rtype: dict
    """
    http = UnixHTTPConnectionPool(socket_path)
    r = http.request("POST", url,
                     body=body.encode("utf-8"),
                     headers={"Content-Type": "text/x-toml"})
    return json.loads(r.data.decode("utf-8"))
