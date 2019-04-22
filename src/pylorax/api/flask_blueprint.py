#
# Copyright (C) 2019 Red Hat, Inc.
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
""" Flask Blueprints that support skipping routes

When using Blueprints for API versioning you will usually want to fall back
to the previous version's rules for routes that have no new behavior. To do
this we add a 'skip_rule' list to the Blueprint's options dictionary. It lists
all of the routes that you do not want to register.

For example:
    from pylorax.api.v0 import v0
    from pylorax.api.v1 import v1

    server.register_blueprint(v0, url_prefix="/api/v0/")
    server.register_blueprint(v0, url_prefix="/api/v1/", skip_rules=["/blueprints/list"]
    server.register_blueprint(v1, url_prefix="/api/v1/")

This will register all of v0's routes under `/api/v0`, and all but `/blueprints/list` under /api/v1,
and then register v1's version of `/blueprints/list` under `/api/v1`

"""
from flask import Blueprint
from flask.blueprints import BlueprintSetupState

class BlueprintSetupStateSkip(BlueprintSetupState):
    def __init__(self, blueprint, app, options, first_registration, skip_rules):
        self._skip_rules = skip_rules
        super(BlueprintSetupStateSkip, self).__init__(blueprint, app, options, first_registration)

    def add_url_rule(self, rule, endpoint=None, view_func=None, **options):
        if rule not in self._skip_rules:
            super(BlueprintSetupStateSkip, self).add_url_rule(rule, endpoint, view_func, **options)

class BlueprintSkip(Blueprint):
    def __init__(self, *args, **kwargs):
        super(BlueprintSkip, self).__init__(*args, **kwargs)

    def make_setup_state(self, app, options, first_registration=False):
        skip_rules = options.pop("skip_rules", [])
        return BlueprintSetupStateSkip(self, app, options, first_registration, skip_rules)
