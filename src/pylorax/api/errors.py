#
# lorax-composer API server
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

# Returned from the API when ?limit= or ?offset= is given something that does
# not convert into an integer.
BAD_LIMIT_OR_OFFSET = "BadLimitOrOffset"

# Returned from the API when it expected a build to be in a state other than
# what it currently is.  This most often happens when asking for results from
# a build that is not yet done.
BUILD_IN_WRONG_STATE = "BuildInWrongState"

# Returned from the API when a UUID that was requested does not exist.
UNKNOWN_UUID = "UnknownUUID"
