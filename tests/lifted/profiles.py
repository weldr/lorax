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

# test profile settings for each provider
test_profiles = {
    "aws": ["aws-profile", {
        "aws_access_key": "theaccesskey",
        "aws_secret_key": "thesecretkey",
        "aws_region":     "us-east-1",
        "aws_bucket":     "composer-mops"
        }],
    "azure": ["azure-profile", {
        "resource_group":       "production",
        "storage_account_name": "HomerSimpson",
        "storage_container":    "plastic",
        "subscription_id":      "SpringfieldNuclear",
        "client_id":            "DonutGuy",
        "secret":               "I Like sprinkles",
        "tenant":               "Bart",
        "location":             "Springfield"
        }],
    "dummy": ["dummy-profile", {}],
    "openstack": ["openstack-profile", {
        "auth_url":         "https://localhost/auth/url",
        "username":         "ChuckBurns",
        "password":         "Excellent!",
        "project_name":     "Springfield Nuclear",
        "user_domain_name": "chuck.burns.localhost",
        "project_domain_name":  "springfield.burns.localhost",
        "is_public":        True
        }],
    "vsphere": ["vsphere-profile", {
        "datacenter":       "Lisa's Closet",
        "datastore":        "storage-crate-alpha",
        "host":             "marge",
        "folder":           "the.green.one",
        "username":         "LisaSimpson",
        "password":         "EmbraceNothingnes"
        }]
}
