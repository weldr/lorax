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
log = logging.getLogger("lorax-composer")

from flask import jsonify
from functools import update_wrapper

# A decorator for checking the parameters provided to the API route implementing
# functions.  The tuples parameter is a list of tuples.  Each tuple is the string
# name of a parameter ("blueprint_name", not blueprint_name), the value it's set
# to by flask if the caller did not provide it, and a message to be returned to
# the user.
#
# If the parameter is set to its default, the error message is returned.  Otherwise,
# the decorated function is called and its return value is returned.
def checkparams(tuples):
    def decorator(f):
        def wrapped_function(*args, **kwargs):
            for tup in tuples:
                if kwargs[tup[0]] == tup[1]:
                    log.error("(%s) %s", f.__name__, tup[2])
                    return jsonify(status=False, errors=[tup[2]]), 400

            return f(*args, **kwargs)

        return update_wrapper(wrapped_function, f)

    return decorator
