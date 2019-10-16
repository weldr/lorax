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

from flask import jsonify, request
from flask import current_app as api

from lifted.queue import get_upload, reset_upload, cancel_upload, delete_upload
from lifted.providers import list_providers, resolve_provider, load_profiles, validate_settings, save_settings
from lifted.providers import load_settings, delete_profile
from pylorax.api.checkparams import checkparams
from pylorax.api.compose import start_build
from pylorax.api.errors import BAD_COMPOSE_TYPE, BUILD_FAILED, INVALID_CHARS, MISSING_POST, PROJECTS_ERROR
from pylorax.api.errors import SYSTEM_SOURCE, UNKNOWN_BLUEPRINT, UNKNOWN_SOURCE, UNKNOWN_UUID, UPLOAD_ERROR
from pylorax.api.errors import COMPOSE_ERROR
from pylorax.api.flask_blueprint import BlueprintSkip
from pylorax.api.queue import queue_status, build_status, uuid_status, uuid_schedule_upload, uuid_remove_upload
from pylorax.api.queue import uuid_info
from pylorax.api.projects import get_repo_sources, repo_to_source
from pylorax.api.projects import new_repo_source
from pylorax.api.regexes import VALID_API_STRING, VALID_BLUEPRINT_NAME
import pylorax.api.toml as toml
from pylorax.api.utils import blueprint_exists


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

    **POST /api/v1/projects/source/new**

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

    # Check for id in source, return error if not
    if "id" not in source:
        return jsonify(status=False, errors=[{"id": UNKNOWN_SOURCE, "msg": "'id' field is missing from API v1 request."}]), 400

    system_sources = get_repo_sources("/etc/yum.repos.d/*.repo")
    if source["id"] in system_sources:
        return jsonify(status=False, errors=[{"id": SYSTEM_SOURCE, "msg": "%s is a system source, it cannot be changed." % source["id"]}]), 400

    try:
        # Remove it from the RepoDict (NOTE that this isn't explicitly supported by the DNF API)
        with api.config["DNFLOCK"].lock:
            repo_dir = api.config["COMPOSER_CFG"].get("composer", "repo_dir")
            new_repo_source(api.config["DNFLOCK"].dbo, source["id"], source, repo_dir)
    except Exception as e:
        return jsonify(status=False, errors=[{"id": PROJECTS_ERROR, "msg": str(e)}]), 400

    return jsonify(status=True)

@v1_api.route("/compose", methods=["POST"])
def v1_compose_start():
    """Start a compose

    The body of the post should have these fields:
      blueprint_name - The blueprint name from /blueprints/list/
      compose_type   - The type of output to create, from /compose/types
      branch         - Optional, defaults to master, selects the git branch to use for the blueprint.

    **POST /api/v1/compose**

      Start a compose. The content type should be 'application/json' and the body of the POST
      should look like this. The "upload" object is optional.

      The upload object can specify either a pre-existing profile to use (as returned by
      `/uploads/providers`) or one-time use settings for the provider.

      Example with upload profile::

          {
            "blueprint_name": "http-server",
            "compose_type": "tar",
            "branch": "master",
            "upload": {
              "image_name": "My Image",
              "provider": "azure",
              "profile": "production-azure-settings"
            }
          }

      Example with upload settings::

          {
            "blueprint_name": "http-server",
            "compose_type": "tar",
            "branch": "master",
            "upload": {
              "image_name": "My Image",
              "provider": "azure",
              "settings": {
                "resource_group": "SOMEBODY",
                "storage_account_name": "ONCE",
                "storage_container": "TOLD",
                "location": "ME",
                "subscription_id": "THE",
                "client_id": "WORLD",
                "secret": "IS",
                "tenant": "GONNA"
              }
            }
          }

      Pass it the name of the blueprint, the type of output (from
      '/api/v1/compose/types'), and the blueprint branch to use. 'branch' is
      optional and will default to master. It will create a new build and add
      it to the queue. It returns the build uuid and a status if it succeeds.
      If an "upload" is given, it will schedule an upload to run when the build
      finishes.

      Example response::

          {
            "build_id": "e6fa6db4-9c81-4b70-870f-a697ca405cdf",
            "upload_id": "572eb0d0-5348-4600-9666-14526ba628bb",
            "status": true
          }
    """
    # Passing ?test=1 will generate a fake FAILED compose.
    # Passing ?test=2 will generate a fake FINISHED compose.
    try:
        test_mode = int(request.args.get("test", "0"))
    except ValueError:
        test_mode = 0

    compose = request.get_json(cache=False)

    errors = []
    if not compose:
        return jsonify(status=False, errors=[{"id": MISSING_POST, "msg": "Missing POST body"}]), 400

    if "blueprint_name" not in compose:
        errors.append({"id": UNKNOWN_BLUEPRINT, "msg": "No 'blueprint_name' in the JSON request"})
    else:
        blueprint_name = compose["blueprint_name"]

    if "branch" not in compose or not compose["branch"]:
        branch = "master"
    else:
        branch = compose["branch"]

    if "compose_type" not in compose:
        errors.append({"id": BAD_COMPOSE_TYPE, "msg": "No 'compose_type' in the JSON request"})
    else:
        compose_type = compose["compose_type"]

    if VALID_BLUEPRINT_NAME.match(blueprint_name) is None:
        errors.append({"id": INVALID_CHARS, "msg": "Invalid characters in API path"})

    if not blueprint_exists(api, branch, blueprint_name):
        errors.append({"id": UNKNOWN_BLUEPRINT, "msg": "Unknown blueprint name: %s" % blueprint_name})

    if "upload" in compose:
        try:
            image_name = compose["upload"]["image_name"]

            if "profile" in compose["upload"]:
                # Load a specific profile for this provider
                profile = compose["upload"]["profile"]
                provider_name = compose["upload"]["provider"]
                settings = load_settings(api.config["COMPOSER_CFG"]["upload"], provider_name, profile)
            else:
                provider_name = compose["upload"]["provider"]
                settings = compose["upload"]["settings"]
        except KeyError as e:
            errors.append({"id": UPLOAD_ERROR, "msg": f'Missing parameter {str(e)}!'})
        try:
            provider = resolve_provider(api.config["COMPOSER_CFG"]["upload"], provider_name)
            if "supported_types" in provider and compose_type not in provider["supported_types"]:
                raise RuntimeError(f'Type "{compose_type}" is not supported by provider "{provider_name}"!')
            validate_settings(api.config["COMPOSER_CFG"]["upload"], provider_name, settings, image_name)
        except Exception as e:
            errors.append({"id": UPLOAD_ERROR, "msg": str(e)})

    if errors:
        return jsonify(status=False, errors=errors), 400

    try:
        build_id = start_build(api.config["COMPOSER_CFG"], api.config["DNFLOCK"], api.config["GITLOCK"],
                               branch, blueprint_name, compose_type, test_mode)
    except Exception as e:
        if "Invalid compose type" in str(e):
            return jsonify(status=False, errors=[{"id": BAD_COMPOSE_TYPE, "msg": str(e)}]), 400
        else:
            return jsonify(status=False, errors=[{"id": BUILD_FAILED, "msg": str(e)}]), 400

    if "upload" in compose:
        upload_id = uuid_schedule_upload(
            api.config["COMPOSER_CFG"],
            build_id,
            provider_name,
            image_name,
            settings
        )
    else:
        upload_id = ""

    return jsonify(status=True, build_id=build_id, upload_id=upload_id)

@v1_api.route("/compose/queue")
def v1_compose_queue():
    """Return the status of the new and running queues

    **/api/v1/compose/queue**

      Return the status of the build queue. It includes information about the builds waiting,
      and the build that is running.

      Example::

          {
            "new": [
              {
                "id": "45502a6d-06e8-48a5-a215-2b4174b3614b",
                "blueprint": "glusterfs",
                "queue_status": "WAITING",
                "job_created": 1517362647.4570868,
                "version": "0.0.6"
              },
              {
                "id": "6d292bd0-bec7-4825-8d7d-41ef9c3e4b73",
                "blueprint": "kubernetes",
                "queue_status": "WAITING",
                "job_created": 1517362659.0034983,
                "version": "0.0.1"
              }
            ],
            "run": [
              {
                "id": "745712b2-96db-44c0-8014-fe925c35e795",
                "blueprint": "glusterfs",
                "queue_status": "RUNNING",
                "job_created": 1517362633.7965999,
                "job_started": 1517362633.8001345,
                "version": "0.0.6",
                "uploads": [
                    {
                        "creation_time": 1568150660.524401,
                        "image_name": "glusterfs server",
                        "image_path": null,
                        "provider_name": "azure",
                        "settings": {
                            "client_id": "need",
                            "location": "need",
                            "resource_group": "group",
                            "secret": "need",
                            "storage_account_name": "need",
                            "storage_container": "need",
                            "subscription_id": "need",
                            "tenant": "need"
                        },
                        "status": "WAITING",
                        "uuid": "21898dfd-9ac9-4e22-bb1d-7f12d0129e65"
                    }
                ]
              }
            ]
          }
    """
    return jsonify(queue_status(api.config["COMPOSER_CFG"], api=1))

@v1_api.route("/compose/finished")
def v1_compose_finished():
    """Return the list of finished composes

    **/api/v1/compose/finished**

      Return the details on all of the finished composes on the system.

      Example::

          {
            "finished": [
              {
                "id": "70b84195-9817-4b8a-af92-45e380f39894",
                "blueprint": "glusterfs",
                "queue_status": "FINISHED",
                "job_created": 1517351003.8210032,
                "job_started": 1517351003.8230415,
                "job_finished": 1517359234.1003145,
                "version": "0.0.6"
              },
              {
                "id": "e695affd-397f-4af9-9022-add2636e7459",
                "blueprint": "glusterfs",
                "queue_status": "FINISHED",
                "job_created": 1517362289.7193348,
                "job_started": 1517362289.9751132,
                "job_finished": 1517363500.1234567,
                "version": "0.0.6",
                "uploads": [
                    {
                        "creation_time": 1568150660.524401,
                        "image_name": "glusterfs server",
                        "image_path": "/var/lib/lorax/composer/results/e695affd-397f-4af9-9022-add2636e7459/disk.vhd",
                        "provider_name": "azure",
                        "settings": {
                            "client_id": "need",
                            "location": "need",
                            "resource_group": "group",
                            "secret": "need",
                            "storage_account_name": "need",
                            "storage_container": "need",
                            "subscription_id": "need",
                            "tenant": "need"
                        },
                        "status": "WAITING",
                        "uuid": "21898dfd-9ac9-4e22-bb1d-7f12d0129e65"
                    }
                ]
              }
            ]
          }
    """
    return jsonify(finished=build_status(api.config["COMPOSER_CFG"], "FINISHED", api=1))

@v1_api.route("/compose/failed")
def v1_compose_failed():
    """Return the list of failed composes

    **/api/v1/compose/failed**

      Return the details on all of the failed composes on the system.

      Example::

          {
            "failed": [
               {
                "id": "8c8435ef-d6bd-4c68-9bf1-a2ef832e6b1a",
                "blueprint": "http-server",
                "queue_status": "FAILED",
                "job_created": 1517523249.9301329,
                "job_started": 1517523249.9314211,
                "job_finished": 1517523255.5623411,
                "version": "0.0.2",
                "uploads": [
                    {
                        "creation_time": 1568150660.524401,
                        "image_name": "http-server",
                        "image_path": null,
                        "provider_name": "azure",
                        "settings": {
                            "client_id": "need",
                            "location": "need",
                            "resource_group": "group",
                            "secret": "need",
                            "storage_account_name": "need",
                            "storage_container": "need",
                            "subscription_id": "need",
                            "tenant": "need"
                        },
                        "status": "WAITING",
                        "uuid": "21898dfd-9ac9-4e22-bb1d-7f12d0129e65"
                    }
                ]
              }
            ]
          }
    """
    return jsonify(failed=build_status(api.config["COMPOSER_CFG"], "FAILED", api=1))

@v1_api.route("/compose/status", defaults={'uuids': ""})
@v1_api.route("/compose/status/<uuids>")
@checkparams([("uuids", "", "no UUIDs given")])
def v1_compose_status(uuids):
    """Return the status of the listed uuids

    **/api/v1/compose/status/<uuids>[?blueprint=<blueprint_name>&status=<compose_status>&type=<compose_type>]**

      Return the details for each of the comma-separated list of uuids. A uuid of '*' will return
      details for all composes.

      Example::

          {
            "uuids": [
              {
                "id": "8c8435ef-d6bd-4c68-9bf1-a2ef832e6b1a",
                "blueprint": "http-server",
                "queue_status": "FINISHED",
                "job_created": 1517523644.2384307,
                "job_started": 1517523644.2551234,
                "job_finished": 1517523689.9864314,
                "version": "0.0.2"
              },
              {
                "id": "45502a6d-06e8-48a5-a215-2b4174b3614b",
                "blueprint": "glusterfs",
                "queue_status": "FINISHED",
                "job_created": 1517363442.188399,
                "job_started": 1517363442.325324,
                "job_finished": 1517363451.653621,
                "version": "0.0.6",
                "uploads": [
                    {
                        "creation_time": 1568150660.524401,
                        "image_name": "glusterfs server",
                        "image_path": null,
                        "provider_name": "azure",
                        "settings": {
                            "client_id": "need",
                            "location": "need",
                            "resource_group": "group",
                            "secret": "need",
                            "storage_account_name": "need",
                            "storage_container": "need",
                            "subscription_id": "need",
                            "tenant": "need"
                        },
                        "status": "WAITING",
                        "uuid": "21898dfd-9ac9-4e22-bb1d-7f12d0129e65"
                    }
                ]
              }
            ]
          }
    """
    if VALID_API_STRING.match(uuids) is None:
        return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

    blueprint = request.args.get("blueprint", None)
    status = request.args.get("status", None)
    compose_type = request.args.get("type", None)

    results = []
    errors = []

    if uuids.strip() == '*':
        queue_status_dict = queue_status(api.config["COMPOSER_CFG"], api=1)
        queue_new = queue_status_dict["new"]
        queue_running = queue_status_dict["run"]
        candidates = queue_new + queue_running + build_status(api.config["COMPOSER_CFG"], api=1)
    else:
        candidates = []
        for uuid in [n.strip().lower() for n in uuids.split(",")]:
            details = uuid_status(api.config["COMPOSER_CFG"], uuid, api=1)
            if details is None:
                errors.append({"id": UNKNOWN_UUID, "msg": "%s is not a valid build uuid" % uuid})
            else:
                candidates.append(details)

    for details in candidates:
        if blueprint is not None and details['blueprint'] != blueprint:
            continue

        if status is not None and details['queue_status'] != status:
            continue

        if compose_type is not None and details['compose_type'] != compose_type:
            continue

        results.append(details)

    return jsonify(uuids=results, errors=errors)

@v1_api.route("/compose/info", defaults={'uuid': ""})
@v1_api.route("/compose/info/<uuid>")
@checkparams([("uuid", "", "no UUID given")])
def v1_compose_info(uuid):
    """Return detailed info about a compose

    **/api/v1/compose/info/<uuid>**

      Get detailed information about the compose. The returned JSON string will
      contain the following information:

        * id - The uuid of the comoposition
        * config - containing the configuration settings used to run Anaconda
        * blueprint - The depsolved blueprint used to generate the kickstart
        * commit - The (local) git commit hash for the blueprint used
        * deps - The NEVRA of all of the dependencies used in the composition
        * compose_type - The type of output generated (tar, iso, etc.)
        * queue_status - The final status of the composition (FINISHED or FAILED)

      Example::

          {
            "commit": "7078e521a54b12eae31c3fd028680da7a0815a4d",
            "compose_type": "tar",
            "config": {
              "anaconda_args": "",
              "armplatform": "",
              "compress_args": [],
              "compression": "xz",
              "image_name": "root.tar.xz",
              ...
            },
            "deps": {
              "packages": [
                {
                  "arch": "x86_64",
                  "epoch": "0",
                  "name": "acl",
                  "release": "14.el7",
                  "version": "2.2.51"
                }
              ]
            },
            "id": "c30b7d80-523b-4a23-ad52-61b799739ce8",
            "queue_status": "FINISHED",
            "blueprint": {
              "description": "An example kubernetes master",
              ...
            },
            "uploads": [
                {
                    "creation_time": 1568150660.524401,
                    "image_name": "glusterfs server",
                    "image_path": "/var/lib/lorax/composer/results/c30b7d80-523b-4a23-ad52-61b799739ce8/disk.vhd",
                    "provider_name": "azure",
                    "settings": {
                        "client_id": "need",
                        "location": "need",
                        "resource_group": "group",
                        "secret": "need",
                        "storage_account_name": "need",
                        "storage_container": "need",
                        "subscription_id": "need",
                        "tenant": "need"
                    },
                    "status": "FAILED",
                    "uuid": "21898dfd-9ac9-4e22-bb1d-7f12d0129e65"
                }
            ]
          }
    """
    if VALID_API_STRING.match(uuid) is None:
        return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

    try:
        info = uuid_info(api.config["COMPOSER_CFG"], uuid, api=1)
    except Exception as e:
        return jsonify(status=False, errors=[{"id": COMPOSE_ERROR, "msg": str(e)}]), 400

    if info is None:
        return jsonify(status=False, errors=[{"id": UNKNOWN_UUID, "msg": "%s is not a valid build uuid" % uuid}]), 400
    else:
        return jsonify(**info)

@v1_api.route("/compose/uploads/schedule", defaults={'compose_uuid': ""}, methods=["POST"])
@v1_api.route("/compose/uploads/schedule/<compose_uuid>", methods=["POST"])
@checkparams([("compose_uuid", "", "no compose UUID given")])
def v1_compose_uploads_schedule(compose_uuid):
    """Schedule an upload of a compose to a given cloud provider

    **POST /api/v1/uploads/schedule/<compose_uuid>**

      The body can specify either a pre-existing profile to use (as returned by
      `/uploads/providers`) or one-time use settings for the provider.

      Example with upload profile::

          {
            "image_name": "My Image",
            "provider": "azure",
            "profile": "production-azure-settings"
          }

      Example with upload settings::

          {
            "image_name": "My Image",
            "provider": "azure",
            "settings": {
              "resource_group": "SOMEBODY",
              "storage_account_name": "ONCE",
              "storage_container": "TOLD",
              "location": "ME",
              "subscription_id": "THE",
              "client_id": "WORLD",
              "secret": "IS",
              "tenant": "GONNA"
            }
          }

      Example response::

          {
            "status": true,
            "upload_id": "572eb0d0-5348-4600-9666-14526ba628bb"
          }
    """
    if VALID_API_STRING.match(compose_uuid) is None:
        error = {"id": INVALID_CHARS, "msg": "Invalid characters in API path"}
        return jsonify(status=False, errors=[error]), 400

    parsed = request.get_json(cache=False)
    if not parsed:
        return jsonify(status=False, errors=[{"id": MISSING_POST, "msg": "Missing POST body"}]), 400

    try:
        image_name = parsed["image_name"]
        provider_name = parsed["provider"]
        if "profile" in parsed:
            # Load a specific profile for this provider
            profile = parsed["profile"]
            settings = load_settings(api.config["COMPOSER_CFG"]["upload"], provider_name, profile)
        else:
            settings = parsed["settings"]
    except KeyError as e:
        error = {"id": UPLOAD_ERROR, "msg": f'Missing parameter {str(e)}!'}
        return jsonify(status=False, errors=[error]), 400
    try:
        compose_type = uuid_status(api.config["COMPOSER_CFG"], compose_uuid)["compose_type"]
        provider = resolve_provider(api.config["COMPOSER_CFG"]["upload"], provider_name)
        if "supported_types" in provider and compose_type not in provider["supported_types"]:
            raise RuntimeError(
                f'Type "{compose_type}" is not supported by provider "{provider_name}"!'
            )
    except Exception as e:
        return jsonify(status=False, errors=[{"id": UPLOAD_ERROR, "msg": str(e)}]), 400

    try:
        upload_id = uuid_schedule_upload(
            api.config["COMPOSER_CFG"],
            compose_uuid,
            provider_name,
            image_name,
            settings
        )
    except RuntimeError as e:
        return jsonify(status=False, errors=[{"id": UPLOAD_ERROR, "msg": str(e)}]), 400
    return jsonify(status=True, upload_id=upload_id)

@v1_api.route("/upload/delete", defaults={"upload_uuid": ""}, methods=["DELETE"])
@v1_api.route("/upload/delete/<upload_uuid>", methods=["DELETE"])
@checkparams([("upload_uuid", "", "no upload UUID given")])
def v1_compose_uploads_delete(upload_uuid):
    """Delete an upload and disassociate it from its compose

    **DELETE /api/v1/upload/delete/<upload_uuid>**

      Example response::

          {
            "status": true,
            "upload_id": "572eb0d0-5348-4600-9666-14526ba628bb"
          }
    """
    if VALID_API_STRING.match(upload_uuid) is None:
        error = {"id": INVALID_CHARS, "msg": "Invalid characters in API path"}
        return jsonify(status=False, errors=[error]), 400

    try:
        uuid_remove_upload(api.config["COMPOSER_CFG"], upload_uuid)
        delete_upload(api.config["COMPOSER_CFG"]["upload"], upload_uuid)
    except RuntimeError as error:
        return jsonify(status=False, errors=[{"id": UPLOAD_ERROR, "msg": str(error)}])
    return jsonify(status=True, upload_id=upload_uuid)

@v1_api.route("/upload/info", defaults={"upload_uuid": ""})
@v1_api.route("/upload/info/<upload_uuid>")
@checkparams([("upload_uuid", "", "no UUID given")])
def v1_upload_info(upload_uuid):
    """Returns information about a given upload

    **GET /api/v1/upload/info/<upload_uuid>**

      Example response::

          {
            "status": true,
            "upload": {
              "creation_time": 1565620940.069004,
              "image_name": "My Image",
              "image_path": "/var/lib/lorax/composer/results/b6218e8f-0fa2-48ec-9394-f5c2918544c4/disk.vhd",
              "provider_name": "azure",
              "settings": {
                "resource_group": "SOMEBODY",
                "storage_account_name": "ONCE",
                "storage_container": "TOLD",
                "location": "ME",
                "subscription_id": "THE",
                "client_id": "WORLD",
                "secret": "IS",
                "tenant": "GONNA"
              },
              "status": "FAILED",
              "uuid": "b637c411-9d9d-4279-b067-6c8d38e3b211"
            }
          }
    """
    if VALID_API_STRING.match(upload_uuid) is None:
        return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

    try:
        upload = get_upload(api.config["COMPOSER_CFG"]["upload"], upload_uuid).summary()
    except RuntimeError as error:
        return jsonify(status=False, errors=[{"id": UPLOAD_ERROR, "msg": str(error)}])
    return jsonify(status=True, upload=upload)

@v1_api.route("/upload/log", defaults={"upload_uuid": ""})
@v1_api.route("/upload/log/<upload_uuid>")
@checkparams([("upload_uuid", "", "no UUID given")])
def v1_upload_log(upload_uuid):
    """Returns an upload's log

    **GET /api/v1/upload/log/<upload_uuid>**

      Example response::

          {
            "status": true,
            "upload_id": "b637c411-9d9d-4279-b067-6c8d38e3b211",
            "log": "< PLAY [localhost] >..."
          }
    """
    if VALID_API_STRING.match(upload_uuid) is None:
        error = {"id": INVALID_CHARS, "msg": "Invalid characters in API path"}
        return jsonify(status=False, errors=[error]), 400

    try:
        upload = get_upload(api.config["COMPOSER_CFG"]["upload"], upload_uuid)
    except RuntimeError as error:
        return jsonify(status=False, errors=[{"id": UPLOAD_ERROR, "msg": str(error)}])
    return jsonify(status=True, upload_id=upload_uuid, log=upload.upload_log)

@v1_api.route("/upload/reset", defaults={"upload_uuid": ""}, methods=["POST"])
@v1_api.route("/upload/reset/<upload_uuid>", methods=["POST"])
@checkparams([("upload_uuid", "", "no UUID given")])
def v1_upload_reset(upload_uuid):
    """Reset an upload so it can be attempted again

    **POST /api/v1/upload/reset/<upload_uuid>**

      Optionally pass in a new image name and/or new settings.

      Example request::

          {
            "image_name": "My renamed image",
            "settings": {
              "resource_group": "ROLL",
              "storage_account_name": "ME",
              "storage_container": "I",
              "location": "AIN'T",
              "subscription_id": "THE",
              "client_id": "SHARPEST",
              "secret": "TOOL",
              "tenant": "IN"
            }
          }

      Example response::

          {
            "status": true,
            "upload_id": "c75d5d62-9d26-42fc-a8ef-18bb14679fc7"
          }
    """
    if VALID_API_STRING.match(upload_uuid) is None:
        error = {"id": INVALID_CHARS, "msg": "Invalid characters in API path"}
        return jsonify(status=False, errors=[error]), 400

    parsed = request.get_json(cache=False)
    image_name = parsed.get("image_name") if parsed else None
    settings = parsed.get("settings") if parsed else None

    try:
        reset_upload(api.config["COMPOSER_CFG"]["upload"], upload_uuid, image_name, settings)
    except RuntimeError as error:
        return jsonify(status=False, errors=[{"id": UPLOAD_ERROR, "msg": str(error)}])
    return jsonify(status=True, upload_id=upload_uuid)

@v1_api.route("/upload/cancel", defaults={"upload_uuid": ""}, methods=["DELETE"])
@v1_api.route("/upload/cancel/<upload_uuid>", methods=["DELETE"])
@checkparams([("upload_uuid", "", "no UUID given")])
def v1_upload_cancel(upload_uuid):
    """Cancel an upload that is either queued or in progress

    **DELETE /api/v1/uploads/cancel/<upload_uuid>**

      Example response::

          {
            "status": true,
            "upload_id": "037a3d56-b421-43e9-9935-c98350c89996"
          }
    """
    if VALID_API_STRING.match(upload_uuid) is None:
        error = {"id": INVALID_CHARS, "msg": "Invalid characters in API path"}
        return jsonify(status=False, errors=[error]), 400

    try:
        cancel_upload(api.config["COMPOSER_CFG"]["upload"], upload_uuid)
    except RuntimeError as error:
        return jsonify(status=False, errors=[{"id": UPLOAD_ERROR, "msg": str(error)}])
    return jsonify(status=True, upload_id=upload_uuid)

@v1_api.route("/upload/providers")
def v1_upload_providers():
    """Return the information about all upload providers, including their
    display names, expected settings, and saved profiles. Refer to the
    `resolve_provider` function.

    **GET /api/v1/upload/providers**

      Example response::

          {
            "providers": {
              "azure": {
                "display": "Azure",
                "profiles": {
                  "default": {
                    "client_id": "example",
                    ...
                  }
                },
                "settings-info": {
                  "client_id": {
                    "display": "Client ID",
                    "placeholder": "",
                    "regex": "",
                    "type": "string"
                  },
                  ...
                },
                "supported_types": ["vhd"]
              },
              ...
            }
          }
    """

    ucfg = api.config["COMPOSER_CFG"]["upload"]

    provider_names = list_providers(ucfg)

    def get_provider_info(provider_name):
        provider = resolve_provider(ucfg, provider_name)
        provider["profiles"] = load_profiles(ucfg, provider_name)
        return provider

    providers = {provider_name: get_provider_info(provider_name)
                 for provider_name in provider_names}
    return jsonify(status=True, providers=providers)

@v1_api.route("/upload/providers/save", methods=["POST"])
def v1_providers_save():
    """Save provider settings as a profile for later use

    **POST /api/v1/upload/providers/save**

      Example request::

          {
            "provider": "azure",
            "profile": "my-profile",
            "settings": {
              "resource_group": "SOMEBODY",
              "storage_account_name": "ONCE",
              "storage_container": "TOLD",
              "location": "ME",
              "subscription_id": "THE",
              "client_id": "WORLD",
              "secret": "IS",
              "tenant": "GONNA"
            }
          }

      Saving to an existing profile will overwrite it.

      Example response::

          {
            "status": true
          }
    """
    parsed = request.get_json(cache=False)

    if parsed is None:
        return jsonify(status=False, errors=[{"id": MISSING_POST, "msg": "Missing POST body"}]), 400

    try:
        provider_name = parsed["provider"]
        profile = parsed["profile"]
        settings = parsed["settings"]
    except KeyError as e:
        error = {"id": UPLOAD_ERROR, "msg": f'Missing parameter {str(e)}!'}
        return jsonify(status=False, errors=[error]), 400
    try:
        save_settings(api.config["COMPOSER_CFG"]["upload"], provider_name, profile, settings)
    except Exception as e:
        error = {"id": UPLOAD_ERROR, "msg": str(e)}
        return jsonify(status=False, errors=[error])
    return jsonify(status=True)

@v1_api.route("/upload/providers/delete", defaults={"provider_name": "", "profile": ""}, methods=["DELETE"])
@v1_api.route("/upload/providers/delete/<provider_name>/<profile>", methods=["DELETE"])
@checkparams([("provider_name", "", "no provider name given"), ("profile", "", "no profile given")])
def v1_providers_delete(provider_name, profile):
    """Delete a provider's profile settings

    **DELETE /api/v1/upload/providers/delete/<provider_name>/<profile>**

      Example response::

          {
            "status": true
          }
    """
    if None in (VALID_API_STRING.match(provider_name), VALID_API_STRING.match(profile)):
        error = {"id": INVALID_CHARS, "msg": "Invalid characters in API path"}
        return jsonify(status=False, errors=[error]), 400

    try:
        delete_profile(api.config["COMPOSER_CFG"]["upload"], provider_name, profile)
    except Exception as e:
        error = {"id": UPLOAD_ERROR, "msg": str(e)}
        return jsonify(status=False, errors=[error])
    return jsonify(status=True)
