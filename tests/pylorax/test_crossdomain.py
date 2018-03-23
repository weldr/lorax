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
from flask import Flask
from datetime import timedelta

from pylorax.api.crossdomain import crossdomain


server = Flask(__name__)

@server.route('/01')
@crossdomain(origin='*', methods=['GET'])
def hello_world_01():
    return 'Hello, World!'


@server.route('/02')
@crossdomain(origin='*', headers=['TESTING'])
def hello_world_02():
    return 'Hello, World!'

@server.route('/03')
@crossdomain(origin='*', max_age=timedelta(days=7))
def hello_world_03():
    return 'Hello, World!'


@server.route('/04')
@crossdomain(origin='*', attach_to_all=False)
def hello_world_04():
    return 'Hello, World!'


@server.route('/05')
@crossdomain(origin='*', automatic_options=False)
def hello_world_05():
    return 'Hello, World!'


@server.route('/06')
@crossdomain(origin=['https://redhat.com', 'http://weldr.io'])
def hello_world_06():
    return 'Hello, World!'


class CrossdomainTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.server = server.test_client()

    def test_01_with_methods_specified(self):
        # first send a preflight request to check what methods are allowed
        response = self.server.options("/01")
        self.assertEqual(200, response.status_code)
        self.assertIn('GET', response.headers['Access-Control-Allow-Methods'])

        # then try to issue a POST request which isn't allowed
        response = self.server.post("/01")
        self.assertEqual(405, response.status_code)

    def test_02_with_headers_specified(self):
        response = self.server.get("/02")
        self.assertEqual(200, response.status_code)
        self.assertEqual('Hello, World!', response.data)

        self.assertEqual('TESTING', response.headers['Access-Control-Allow-Headers'])

    def test_03_with_max_age_as_timedelta(self):
        response = self.server.get("/03")
        self.assertEqual(200, response.status_code)
        self.assertEqual('Hello, World!', response.data)

        expected_max_age = int(timedelta(days=7).total_seconds())
        actual_max_age = int(response.headers['Access-Control-Max-Age'])
        self.assertEqual(expected_max_age, actual_max_age)

    def test_04_attach_to_all_false(self):
        response = self.server.get("/04")
        self.assertEqual(200, response.status_code)
        self.assertEqual('Hello, World!', response.data)

        # when attach_to_all is False the decorator will not assign
        # the Access-Control-* headers to the response
        for header, _ in response.headers:
            self.assertFalse(header.startswith('Access-Control-'))


    def test_05_options_request(self):
        response = self.server.options("/05")
        self.assertEqual(200, response.status_code)
        self.assertEqual('Hello, World!', response.data)

        self.assertEqual(response.headers['Access-Control-Allow-Methods'], 'HEAD, OPTIONS, GET')


    def test_06_with_origin_as_list(self):
        response = self.server.get("/06")
        self.assertEqual(200, response.status_code)
        self.assertEqual('Hello, World!', response.data)

        for header, value in response.headers:
            if header == 'Access-Control-Allow-Origin':
                self.assertIn(value, ['https://redhat.com', 'http://weldr.io'])
