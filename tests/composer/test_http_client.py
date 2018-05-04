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
import unittest

from composer.http_client import api_url, get_filename

headers = {'content-disposition': 'attachment; filename=e7b9b9b0-5867-493d-89c3-115cfe9227d7-metadata.tar;',
           'access-control-max-age': '21600',
           'transfer-encoding': 'chunked',
           'date': 'Tue, 13 Mar 2018 17:37:18 GMT',
           'access-control-allow-origin': '*',
           'access-control-allow-methods': 'HEAD, OPTIONS, GET',
           'content-type': 'application/x-tar'}

class HttpClientTest(unittest.TestCase):
    def test_api_url(self):
        """Return the API url including the API version"""
        self.assertEqual(api_url("0", "/path/to/enlightenment"), "/api/v0/path/to/enlightenment")

    def test_get_filename(self):
        """Return the filename from a content-disposition header"""
        self.assertEqual(get_filename(headers), "e7b9b9b0-5867-493d-89c3-115cfe9227d7-metadata.tar")
