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
import sys
import json
from urllib.parse import urlparse, urlunparse

from composer.unix_socket import UnixHTTPConnectionPool

def api_url(api_version, url):
    """Return the versioned path to the API route

    :param api_version: The version of the API to talk to. eg. "0"
    :type api_version: str
    :param url: The API route to talk to
    :type url: str
    :returns: The full url to use for the route and API version
    :rtype: str
    """
    return os.path.normpath("/api/v%s/%s" % (api_version, url))

def append_query(url, query):
    """Add a query argument to a URL

    The query should be of the form "param1=what&param2=ever", i.e., no
    leading '?'. The new query data will be appended to any existing
    query string.

    :param url: The original URL
    :type url: str
    :param query: The query to append
    :type query: str
    :returns: The new URL with the query argument included
    :rtype: str
    """

    url_parts = urlparse(url)
    if url_parts.query:
        new_query = url_parts.query + "&" + query
    else:
        new_query = query
    return urlunparse([url_parts[0], url_parts[1], url_parts[2],
                       url_parts[3], new_query, url_parts[5]])

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
    if r.status == 400:
        err = json.loads(r.data.decode("utf-8"))
        if "status" in err and err["status"] == False:
            msgs = [e["msg"] for e in err["errors"]]
            raise RuntimeError(", ".join(msgs))

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

def get_url_json_unlimited(socket_path, url, total_fn=None):
    """Return the JSON results of a GET request

    For URLs that use offset/limit arguments, this command will
    fetch all results for the given request.

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param url: URL to request
    :type url: str
    :returns: The json response from the server
    :rtype: dict
    """
    def default_total_fn(data):
        """Return the total number of available results"""
        return data["total"]

    http = UnixHTTPConnectionPool(socket_path)

    # Start with limit=0 to just get the number of objects
    total_url = append_query(url, "limit=0")
    r_total = http.request("GET", total_url)
    json_total = json.loads(r_total.data.decode('utf-8'))

    # Where to get the total from
    if not total_fn:
        total_fn = default_total_fn

    # Add the "total" returned by limit=0 as the new limit
    unlimited_url = append_query(url, "limit=%d" % total_fn(json_total))
    r_unlimited = http.request("GET", unlimited_url)
    return json.loads(r_unlimited.data.decode('utf-8'))

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
    """POST a TOML string to the URL

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

def post_url_json(socket_path, url, body):
    """POST some JSON data to the URL

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
                     headers={"Content-Type": "application/json"})
    return json.loads(r.data.decode("utf-8"))

def get_filename(headers):
    """Get the filename from the response header

    :param response: The urllib3 response object
    :type response: Response
    :raises: RuntimeError if it cannot find a filename in the header
    :returns: Filename from content-disposition header
    :rtype: str
    """
    log.debug("Headers = %s", headers)
    if "content-disposition" not in headers:
        raise RuntimeError("No Content-Disposition header; cannot get filename")

    try:
        k, _, v = headers["content-disposition"].split(";")[1].strip().partition("=")
        if k != "filename":
            raise RuntimeError("No filename= found in content-disposition header")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError("Error parsing filename from content-disposition header: %s" % str(e))

    return os.path.basename(v)

def download_file(socket_path, url, progress=True):
    """Download a file, saving it to the CWD with the included filename

    :param socket_path: Path to the Unix socket to use for API communication
    :type socket_path: str
    :param url: URL to send POST to
    :type url: str
    """
    http = UnixHTTPConnectionPool(socket_path)
    r = http.request("GET", url, preload_content=False)
    if r.status == 400:
        err = json.loads(r.data.decode("utf-8"))
        if not err["status"]:
            msgs = [e["msg"] for e in err["errors"]]
            raise RuntimeError(", ".join(msgs))

    filename = get_filename(r.headers)
    if os.path.exists(filename):
        msg = "%s exists, skipping download" % filename
        log.error(msg)
        raise RuntimeError(msg)

    with open(filename, "wb") as f:
        while True:
            data = r.read(10 * 1024**2)
            if not data:
                break
            f.write(data)

            if progress:
                data_written = f.tell()
                if data_written > 5 * 1024**2:
                    sys.stdout.write("%s: %0.2f MB    \r" % (filename, data_written / 1024**2))
                else:
                    sys.stdout.write("%s: %0.2f kB\r" % (filename, data_written / 1024))
                sys.stdout.flush()

    print("")
    r.release_conn()

    return 0
