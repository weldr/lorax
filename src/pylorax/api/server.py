#
# Copyright (C) 2017  Red Hat, Inc.
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
from collections import namedtuple
from flask import Flask

from pylorax.api.crossdomain import crossdomain
from pylorax.api.v0 import v0_api

GitLock = namedtuple("GitLock", ["repo", "lock", "dir"])

server = Flask(__name__)

__all__ = ["server", "GitLock"]

@server.route('/')
@crossdomain(origin="*")
def hello_world():
    return 'Hello, World!'

v0_api(server)
