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
            raise RuntimeError(err["error"]["msg"])

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
            raise RuntimeError(err["error"]["msg"])

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
