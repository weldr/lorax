#
# Copyright (C) 2019  Red Hat, Inc.
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
""" Setup v1 of the API server

"""
import logging
log = logging.getLogger("lorax-composer")
import os

from flask import jsonify, request
from flask import current_app as api

from pylorax.api.checkparams import checkparams
from pylorax.api.errors import INVALID_CHARS, PROJECTS_ERROR, SYSTEM_SOURCE, UNKNOWN_SOURCE
from pylorax.api.flask_blueprint import BlueprintSkip
from pylorax.api.projects import delete_repo_source, dnf_repo_to_file_repo, get_repo_sources, repo_to_source
from pylorax.api.projects import source_to_repo
from pylorax.api.projects import ProjectsError
from pylorax.api.regexes import VALID_API_STRING
import pylorax.api.toml as toml
from pylorax.sysutils import joinpaths

# Create the v1 routes Blueprint with skip_routes support
v1_api = BlueprintSkip("v1_routes", __name__)

@v1_api.route("/projects/source/info", defaults={'source_ids': ""})
@v1_api.route("/projects/source/info/<source_ids>")
@checkparams([("source_ids", "", "no source names given")])
def v1_projects_source_info(source_ids):
    """Return detailed info about the list of sources

    **/api/v1/projects/source/info/<source-ids>**

      Return information about the comma-separated list of source ids. Or all of the
      sources if '*' is passed. Note that general globbing is not supported, only '*'.

      Immutable system sources will have the "system" field set to true. User added sources
      will have it set to false. System sources cannot be changed or deleted.

      Example::

          {
            "errors": [],
            "sources": {
              "fedora": {
                "check_gpg": true,
                "check_ssl": true,
                "gpgkey_urls": [
                  "file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-28-x86_64"
                ],
                "id": "fedora",
                "name": "Fedora $releasever - $basearch",
                "proxy": "http://proxy.brianlane.com:8123",
                "system": true,
                "type": "yum-metalink",
                "url": "https://mirrors.fedoraproject.org/metalink?repo=fedora-28&arch=x86_64"
              }
            }
          }

    In v0 the ``name`` field was used for the id (a short name for the repo). In v1 ``name`` changed
    to ``id`` and ``name`` is now used for the longer descriptive name of the repository.
    """
    if VALID_API_STRING.match(source_ids) is None:
        return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

    out_fmt = request.args.get("format", "json")
    if VALID_API_STRING.match(out_fmt) is None:
        return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in format argument"}]), 400

    # Return info on all of the sources
    if source_ids == "*":
        with api.config["DNFLOCK"].lock:
            source_ids = ",".join(r.id for r in api.config["DNFLOCK"].dbo.repos.iter_enabled())

    sources = {}
    errors = []
    system_sources = get_repo_sources("/etc/yum.repos.d/*.repo")
    for source in source_ids.split(","):
        with api.config["DNFLOCK"].lock:
            repo = api.config["DNFLOCK"].dbo.repos.get(source, None)
        if not repo:
            errors.append({"id": UNKNOWN_SOURCE, "msg": "%s is not a valid source" % source})
            continue
        sources[repo.id] = repo_to_source(repo, repo.id in system_sources, api=1)

    if out_fmt == "toml" and not errors:
        # With TOML output we just want to dump the raw sources, skipping the errors
        return toml.dumps(sources)
    elif out_fmt == "toml" and errors:
        # TOML requested, but there was an error
        return jsonify(status=False, errors=errors), 400
    else:
        return jsonify(sources=sources, errors=errors)

@v1_api.route("/projects/source/new", methods=["POST"])
def v1_projects_source_new():
    """Add a new package source. Or change an existing one

    **POST /api/v0/projects/source/new**

      Add (or change) a source for use when depsolving blueprints and composing images.

      The ``proxy`` and ``gpgkey_urls`` entries are optional. All of the others are required. The supported
      types for the urls are:

      * ``yum-baseurl`` is a URL to a yum repository.
      * ``yum-mirrorlist`` is a URL for a mirrorlist.
      * ``yum-metalink`` is a URL for a metalink.

      If ``check_ssl`` is true the https certificates must be valid. If they are self-signed you can either set
      this to false, or add your Certificate Authority to the host system.

      If ``check_gpg`` is true the GPG key must either be installed on the host system, or ``gpgkey_urls``
      should point to it.

      You can edit an existing source (other than system sources), by doing a POST
      of the new version of the source. It will overwrite the previous one.

      Example::

          {
              "id": "custom-source-1",
              "name": "Custom Package Source #1",
              "url": "https://url/path/to/repository/",
              "type": "yum-baseurl",
              "check_ssl": true,
              "check_gpg": true,
              "gpgkey_urls": [
                  "https://url/path/to/gpg-key"
              ]
          }

    In v0 the ``name`` field was used for the id (a short name for the repo). In v1 ``name`` changed
    to ``id`` and ``name`` is now used for the longer descriptive name of the repository.
    """
    if request.headers['Content-Type'] == "text/x-toml":
        source = toml.loads(request.data)
    else:
        source = request.get_json(cache=False)

    # XXX TODO
    # Check for id in source, return error if not
    # Add test for that
    if "id" not in source:
        return jsonify(status=False, errors=[{"id": UNKNOWN_SOURCE, "msg": "'id' field is missing from API v1 request."}]), 400

    system_sources = get_repo_sources("/etc/yum.repos.d/*.repo")
    if source["id"] in system_sources:
        return jsonify(status=False, errors=[{"id": SYSTEM_SOURCE, "msg": "%s is a system source, it cannot be changed." % source["id"]}]), 400

    try:
        # Remove it from the RepoDict (NOTE that this isn't explicitly supported by the DNF API)
        with api.config["DNFLOCK"].lock:
            dbo = api.config["DNFLOCK"].dbo
            # If this repo already exists, delete it and replace it with the new one
            repos = list(r.id for r in dbo.repos.iter_enabled())
            if source["id"] in repos:
                del dbo.repos[source["id"]]

            repo = source_to_repo(source, dbo.conf)
            dbo.repos.add(repo)

            log.info("Updating repository metadata after adding %s", source["id"])
            dbo.fill_sack(load_system_repo=False)
            dbo.read_comps()

        # Write the new repo to disk, replacing any existing ones
        repo_dir = api.config["COMPOSER_CFG"].get("composer", "repo_dir")

        # Remove any previous sources with this id, ignore it if it isn't found
        try:
            delete_repo_source(joinpaths(repo_dir, "*.repo"), source["id"])
        except ProjectsError:
            pass

        # Make sure the source id can't contain a path traversal by taking the basename
        source_path = joinpaths(repo_dir, os.path.basename("%s.repo" % source["id"]))
        with open(source_path, "w") as f:
            f.write(dnf_repo_to_file_repo(repo))
    except Exception as e:
        log.error("(v0_projects_source_add) adding %s failed: %s", source["id"], str(e))

        # Cleanup the mess, if loading it failed we don't want to leave it in memory
        repos = list(r.id for r in dbo.repos.iter_enabled())
        if source["id"] in repos:
            with api.config["DNFLOCK"].lock:
                dbo = api.config["DNFLOCK"].dbo
                del dbo.repos[source["id"]]

                log.info("Updating repository metadata after adding %s failed", source["id"])
                dbo.fill_sack(load_system_repo=False)
                dbo.read_comps()

        return jsonify(status=False, errors=[{"id": PROJECTS_ERROR, "msg": str(e)}]), 400

    return jsonify(status=True)


