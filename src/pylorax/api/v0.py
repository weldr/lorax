#
# Copyright (C) 2017-2018  Red Hat, Inc.
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
""" Setup v0 of the API server

v0_api() must be called to setup the API routes for Flask

Status Responses
----------------

Some requests only return a status/error response.

  The response will be a status response with `status` set to true, or an
  error response with it set to false and an error message included.

  Example response::

      {
        "status": true
      }

  Error response::

      {
        "errors": ["ggit-error: Failed to remove entry. File isn't in the tree - jboss.toml (-1)"]
        "status": false
      }

API Routes
----------

All of the blueprints routes support the optional `branch` argument. If it is not
used then the API will use the `master` branch for blueprints. If you want to create
a new branch use the `new` or `workspace` routes with ?branch=<branch-name> to
store the new blueprint on the new branch.

`/api/v0/blueprints/list`
^^^^^^^^^^^^^^^^^^^^^^^^^

  List the available blueprints::

      { "limit": 20,
        "offset": 0,
        "blueprints": [
          "atlas",
          "development",
          "glusterfs",
          "http-server",
          "jboss",
          "kubernetes" ],
        "total": 6 }

`/api/v0/blueprints/info/<blueprint_names>[?format=<json|toml>]`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Return the JSON representation of the blueprint. This includes 3 top level
  objects.  `changes` which lists whether or not the workspace is different from
  the most recent commit. `blueprints` which lists the JSON representation of the
  blueprint, and `errors` which will list any errors, like non-existant blueprints.

  By default the response is JSON, but if `?format=toml` is included in the URL's
  arguments it will return the response as the blueprint's raw TOML content.
  *Unless* there is an error which will only return a 400 and a standard error
  `Status Response`_.

  If there is an error when JSON is requested the successful blueprints and the
  errors will both be returned.

  Example of json response::

      {
        "changes": [
          {
            "changed": false,
            "name": "glusterfs"
          }
        ],
        "errors": [],
        "blueprints": [
          {
            "description": "An example GlusterFS server with samba",
            "modules": [
              {
                "name": "glusterfs",
                "version": "3.7.*"
              },
              {
                "name": "glusterfs-cli",
                "version": "3.7.*"
              }
            ],
            "name": "glusterfs",
            "packages": [
              {
                "name": "2ping",
                "version": "3.2.1"
              },
              {
                "name": "samba",
                "version": "4.2.*"
              }
            ],
            "version": "0.0.6"
          }
        ]
      }

  Error example::

      {
        "changes": [],
        "errors": ["ggit-error: the path 'missing.toml' does not exist in the given tree (-3)"]
        "blueprints": []
      }

`/api/v0/blueprints/changes/<blueprint_names>[?offset=0&limit=20]`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Return the commits to a blueprint. By default it returns the first 20 commits, this
  can be changed by passing `offset` and/or `limit`. The response will include the
  commit hash, summary, timestamp, and optionally the revision number. The commit
  hash can be passed to `/api/v0/blueprints/diff/` to retrieve the exact changes.

  Example::

      {
        "errors": [],
        "limit": 20,
        "offset": 0,
        "blueprints": [
          {
            "changes": [
              {
                "commit": "e083921a7ed1cf2eec91ad12b9ad1e70ef3470be",
                "message": "blueprint glusterfs, version 0.0.6 saved.",
                "revision": null,
                "timestamp": "2017-11-23T00:18:13Z"
              },
              {
                "commit": "cee5f4c20fc33ea4d54bfecf56f4ad41ad15f4f3",
                "message": "blueprint glusterfs, version 0.0.5 saved.",
                "revision": null,
                "timestamp": "2017-11-11T01:00:28Z"
              },
              {
                "commit": "29b492f26ed35d80800b536623bafc51e2f0eff2",
                "message": "blueprint glusterfs, version 0.0.4 saved.",
                "revision": null,
                "timestamp": "2017-11-11T00:28:30Z"
              },
              {
                "commit": "03374adbf080fe34f5c6c29f2e49cc2b86958bf2",
                "message": "blueprint glusterfs, version 0.0.3 saved.",
                "revision": null,
                "timestamp": "2017-11-10T23:15:52Z"
              },
              {
                "commit": "0e08ecbb708675bfabc82952599a1712a843779d",
                "message": "blueprint glusterfs, version 0.0.2 saved.",
                "revision": null,
                "timestamp": "2017-11-10T23:14:56Z"
              },
              {
                "commit": "3e11eb87a63d289662cba4b1804a0947a6843379",
                "message": "blueprint glusterfs, version 0.0.1 saved.",
                "revision": null,
                "timestamp": "2017-11-08T00:02:47Z"
              }
            ],
            "name": "glusterfs",
            "total": 6
          }
        ]
      }

POST `/api/v0/blueprints/new`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Create a new blueprint, or update an existing blueprint. This supports both JSON and TOML
  for the blueprint format. The blueprint should be in the body of the request with the
  `Content-Type` header set to either `application/json` or `text/x-toml`.

  The response will be a status response with `status` set to true, or an
  error response with it set to false and an error message included.

DELETE `/api/v0/blueprints/delete/<blueprint_name>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Delete a blueprint. The blueprint is deleted from the branch, and will no longer
  be listed by the `list` route. A blueprint can be undeleted using the `undo` route
  to revert to a previous commit.

  The response will be a status response with `status` set to true, or an
  error response with it set to false and an error message included.

POST `/api/v0/blueprints/workspace`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Write a blueprint to the temporary workspace. This works exactly the same as `new` except
  that it does not create a commit. JSON and TOML bodies are supported.

  The workspace is meant to be used as a temporary blueprint storage for clients.
  It will be read by the `info` and `diff` routes if it is different from the
  most recent commit.

  The response will be a status response with `status` set to true, or an
  error response with it set to false and an error message included.

DELETE `/api/v0/blueprints/workspace/<blueprint_name>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Remove the temporary workspace copy of a blueprint. The `info` route will now
  return the most recent commit of the blueprint. Any changes that were in the
  workspace will be lost.

  The response will be a status response with `status` set to true, or an
  error response with it set to false and an error message included.

POST `/api/v0/blueprints/undo/<blueprint_name>/<commit>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  This will revert the blueprint to a previous commit. The commit hash from the `changes`
  route can be used in this request.

  The response will be a status response with `status` set to true, or an
  error response with it set to false and an error message included.

POST `/api/v0/blueprints/tag/<blueprint_name>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Tag a blueprint as a new release. This uses git tags with a special format.
  `refs/tags/<branch>/<filename>/r<revision>`. Only the most recent blueprint commit
  can be tagged. Revisions start at 1 and increment for each new tag
  (per-blueprint). If the commit has already been tagged it will return false.

  The response will be a status response with `status` set to true, or an
  error response with it set to false and an error message included.

`/api/v0/blueprints/diff/<blueprint_name>/<from_commit>/<to_commit>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Return the differences between two commits, or the workspace. The commit hash
  from the `changes` response can be used here, or several special strings:

  - NEWEST will select the newest git commit. This works for `from_commit` or `to_commit`
  - WORKSPACE will select the workspace copy. This can only be used in `to_commit`

  eg. `/api/v0/blueprints/diff/glusterfs/NEWEST/WORKSPACE` will return the differences
  between the most recent git commit and the contents of the workspace.

  Each entry in the response's diff object contains the old blueprint value and the new one.
  If old is null and new is set, then it was added.
  If new is null and old is set, then it was removed.
  If both are set, then it was changed.

  The old/new entries will have the name of the blueprint field that was changed. This
  can be one of: Name, Description, Version, Module, or Package.
  The contents for these will be the old/new values for them.

  In the example below the version was changed and the ping package was added.

  Example::

      {
        "diff": [
          {
            "new": {
              "Version": "0.0.6"
            },
            "old": {
              "Version": "0.0.5"
            }
          },
          {
            "new": {
              "Package": {
                "name": "ping",
                "version": "3.2.1"
              }
            },
            "old": null
          }
        ]
      }

`/api/v0/blueprints/freeze/<blueprint_names>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Return a JSON representation of the blueprint with the package and module versions set
  to the exact versions chosen by depsolving the blueprint.

  Example::

      {
        "errors": [],
        "blueprints": [
          {
            "blueprint": {
              "description": "An example GlusterFS server with samba",
              "modules": [
                {
                  "name": "glusterfs",
                  "version": "3.8.4-18.4.el7.x86_64"
                },
                {
                  "name": "glusterfs-cli",
                  "version": "3.8.4-18.4.el7.x86_64"
                }
              ],
              "name": "glusterfs",
              "packages": [
                {
                  "name": "ping",
                  "version": "2:3.2.1-2.el7.noarch"
                },
                {
                  "name": "samba",
                  "version": "4.6.2-8.el7.x86_64"
                }
              ],
              "version": "0.0.6"
            }
          }
        ]
      }

`/api/v0/blueprints/depsolve/<blueprint_names>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Depsolve the blueprint using yum, return the blueprint used, and the NEVRAs of the packages
  chosen to satisfy the blueprint's requirements. The response will include a list of results,
  with the full dependency list in `dependencies`, the NEVRAs for the blueprint's direct modules
  and packages in `modules`, and any error will be in `errors`.

  Example::

      {
        "errors": [],
        "blueprints": [
          {
            "dependencies": [
              {
                "arch": "noarch",
                "epoch": "0",
                "name": "2ping",
                "release": "2.el7",
                "version": "3.2.1"
              },
              {
                "arch": "x86_64",
                "epoch": "0",
                "name": "acl",
                "release": "12.el7",
                "version": "2.2.51"
              },
              {
                "arch": "x86_64",
                "epoch": "0",
                "name": "audit-libs",
                "release": "3.el7",
                "version": "2.7.6"
              },
              {
                "arch": "x86_64",
                "epoch": "0",
                "name": "avahi-libs",
                "release": "17.el7",
                "version": "0.6.31"
              },
              ...
            ],
            "modules": [
              {
                "arch": "noarch",
                "epoch": "0",
                "name": "2ping",
                "release": "2.el7",
                "version": "3.2.1"
              },
              {
                "arch": "x86_64",
                "epoch": "0",
                "name": "glusterfs",
                "release": "18.4.el7",
                "version": "3.8.4"
              },
              ...
            ],
            "blueprint": {
              "description": "An example GlusterFS server with samba",
              "modules": [
                {
                  "name": "glusterfs",
                  "version": "3.7.*"
                },
             ...
            }
          }
        ]
      }

`/api/v0/projects/list[?offset=0&limit=20]`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  List all of the available projects. By default this returns the first 20 items,
  but this can be changed by setting the `offset` and `limit` arguments.

  Example::

      {
        "limit": 20,
        "offset": 0,
        "projects": [
          {
            "description": "0 A.D. (pronounced \"zero ey-dee\") is a ...",
            "homepage": "http://play0ad.com",
            "name": "0ad",
            "summary": "Cross-Platform RTS Game of Ancient Warfare",
            "upstream_vcs": "UPSTREAM_VCS"
          },
          ...
        ],
        "total": 21770
      }

`/api/v0/projects/info/<project_names>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Return information about the comma-separated list of projects. It includes the description
  of the package along with the list of available builds.

  Example::

      {
        "projects": [
          {
            "builds": [
              {
                "arch": "x86_64",
                "build_config_ref": "BUILD_CONFIG_REF",
                "build_env_ref": "BUILD_ENV_REF",
                "build_time": "2017-03-01T08:39:23",
                "changelog": "- restore incremental backups correctly, files ...",
                "epoch": "2",
                "metadata": {},
                "release": "32.el7",
                "source": {
                  "license": "GPLv3+",
                  "metadata": {},
                  "source_ref": "SOURCE_REF",
                  "version": "1.26"
                }
              }
            ],
            "description": "The GNU tar program saves many ...",
            "homepage": "http://www.gnu.org/software/tar/",
            "name": "tar",
            "summary": "A GNU file archiving program",
            "upstream_vcs": "UPSTREAM_VCS"
          }
        ]
      }

`/api/v0/projects/depsolve/<project_names>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Depsolve the comma-separated list of projects and return the list of NEVRAs needed
  to satisfy the request.

  Example::

      {
        "projects": [
          {
            "arch": "noarch",
            "epoch": "0",
            "name": "basesystem",
            "release": "7.el7",
            "version": "10.0"
          },
          {
            "arch": "x86_64",
            "epoch": "0",
            "name": "bash",
            "release": "28.el7",
            "version": "4.2.46"
          },
          {
            "arch": "x86_64",
            "epoch": "0",
            "name": "filesystem",
            "release": "21.el7",
            "version": "3.2"
          },
          ...
        ]
      }

`/api/v0/projects/source/list`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Return the list of repositories used for depsolving and installing packages.

  Example::

      {
        "sources": [
          "fedora",
          "fedora-cisco-openh264",
          "fedora-updates-testing",
          "fedora-updates"
        ]
      }

`/api/v0/projects/source/info/<source-names>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Return information about the comma-separated list of source names. Or all of the
  sources if '*' is passed. Note that general globbing is not supported, only '*'.

  immutable system sources will have the "system" field set to true. User added sources
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
            "name": "fedora",
            "proxy": "http://proxy.brianlane.com:8123",
            "system": true,
            "type": "yum-metalink",
            "url": "https://mirrors.fedoraproject.org/metalink?repo=fedora-28&arch=x86_64"
          }
        }
      }

POST `/api/v0/projects/source/new`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
          "name": "custom-source-1",
          "url": "https://url/path/to/repository/",
          "type": "yum-baseurl",
          "check_ssl": true,
          "check_gpg": true,
          "gpgkey_urls": [
              "https://url/path/to/gpg-key"
          ]
      }

DELETE `/api/v0/projects/source/delete/<source-name>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Delete a user added source. This will fail if a system source is passed to
  it.

  The response will be a status response with `status` set to true, or an
  error response with it set to false and an error message included.

`/api/v0/modules/list[?offset=0&limit=20]`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Return a list of all of the available modules. This includes the name and the
  group_type, which is always "rpm" for lorax-composer. By default this returns
  the first 20 items. This can be changed by setting the `offset` and `limit`
  arguments.

  Example::

      {
        "limit": 20,
        "modules": [
          {
            "group_type": "rpm",
            "name": "0ad"
          },
          {
            "group_type": "rpm",
            "name": "0ad-data"
          },
          {
            "group_type": "rpm",
            "name": "0install"
          },
          {
            "group_type": "rpm",
            "name": "2048-cli"
          },
          ...
        ]
        "total": 21770
      }

`/api/v0/modules/list/<module_names>[?offset=0&limit=20]`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Return the list of comma-separated modules. Output is the same as `/modules/list`

  Example::

      {
        "limit": 20,
        "modules": [
          {
            "group_type": "rpm",
            "name": "tar"
          }
        ],
        "offset": 0,
        "total": 1
      }

`/api/v0/modules/info/<module_names>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Return the module's dependencies, and the information about the module.

  Example::

      {
        "modules": [
          {
            "dependencies": [
              {
                "arch": "noarch",
                "epoch": "0",
                "name": "basesystem",
                "release": "7.el7",
                "version": "10.0"
              },
              {
                "arch": "x86_64",
                "epoch": "0",
                "name": "bash",
                "release": "28.el7",
                "version": "4.2.46"
              },
              ...
            ],
            "description": "The GNU tar program saves ...",
            "homepage": "http://www.gnu.org/software/tar/",
            "name": "tar",
            "summary": "A GNU file archiving program",
            "upstream_vcs": "UPSTREAM_VCS"
          }
        ]
      }

POST `/api/v0/compose`
^^^^^^^^^^^^^^^^^^^^^^

  Start a compose. The content type should be 'application/json' and the body of the POST
  should look like this
  
  Example::

      {
        "blueprint_name": "http-server",
        "compose_type": "tar",
        "branch": "master"
      }

  Pass it the name of the blueprint, the type of output (from '/api/v0/compose/types'), and the
  blueprint branch to use. 'branch' is optional and will default to master. It will create a new
  build and add it to the queue. It returns the build uuid and a status if it succeeds

  Example::
  
      {
        "build_id": "e6fa6db4-9c81-4b70-870f-a697ca405cdf",
        "status": true
      }

`/api/v0/compose/types`
^^^^^^^^^^^^^^^^^^^^^^^

  Returns the list of supported output types that are valid for use with 'POST /api/v0/compose'

  Example::

      {
        "types": [
          {
            "enabled": true,
            "name": "tar"
          }
        ]
      }

`/api/v0/compose/queue`
^^^^^^^^^^^^^^^^^^^^^^^

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
            "version": "0.0.6"
          }
        ]
      }

`/api/v0/compose/finished`
^^^^^^^^^^^^^^^^^^^^^^^^^^

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
            "version": "0.0.6"
          }
        ]
      }

`/api/v0/compose/failed`
^^^^^^^^^^^^^^^^^^^^^^^^^^

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
            "version": "0.0.2"
          }
        ]
      }

`/api/v0/compose/status/<uuids>[?blueprint=<blueprint_name>&status=<compose_status>&type=<compose_type>]`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
            "version": "0.0.6"
          }
        ]
      }

DELETE `/api/v0/compose/cancel/<uuid>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Cancel the build, if it is not finished, and delete the results. It will return a
  status of True if it is successful.

  Example::

      {
        "status": true,
        "uuid": "03397f8d-acff-4cdb-bd31-f629b7a948f5"
      }

DELETE `/api/v0/compose/delete/<uuids>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Delete the list of comma-separated uuids from the compose results.

  Example::

      {
        "errors": [],
        "uuids": [
          {
            "status": true,
            "uuid": "ae1bf7e3-7f16-4c9f-b36e-3726a1093fd0"
          }
        ]
      }

`/api/v0/compose/info/<uuid>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
        }
      }

`/api/v0/compose/metadata/<uuid>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Returns a .tar of the metadata used for the build. This includes all the
  information needed to reproduce the build, including the final kickstart
  populated with repository and package NEVRA.

  The mime type is set to 'application/x-tar' and the filename is set to
  UUID-metadata.tar

  The .tar is uncompressed, but is not large.

`/api/v0/compose/results/<uuid>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Returns a .tar of the metadata, logs, and output image of the build. This
  includes all the information needed to reproduce the build, including the
  final kickstart populated with repository and package NEVRA. The output image
  is already in compressed form so the returned tar is not compressed.

  The mime type is set to 'application/x-tar' and the filename is set to
  UUID.tar

`/api/v0/compose/logs/<uuid>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Returns a .tar of the anaconda build logs. The tar is not compressed, but is
  not large.

  The mime type is set to 'application/x-tar' and the filename is set to
  UUID-logs.tar

`/api/v0/compose/image/<uuid>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Returns the output image from the build. The filename is set to the filename
  from the build with the UUID as a prefix. eg. UUID-root.tar.xz or UUID-boot.iso.

`/api/v0/compose/log/<uuid>[?size=kbytes]`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  Returns the end of the anaconda.log. The size parameter is optional and defaults to 1Mbytes
  if it is not included. The returned data is raw text from the end of the logfile, starting on
  a line boundry.

  Example::

      12:59:24,222 INFO anaconda: Running Thread: AnaConfigurationThread (140629395244800)
      12:59:24,223 INFO anaconda: Configuring installed system
      12:59:24,912 INFO anaconda: Configuring installed system
      12:59:24,912 INFO anaconda: Creating users
      12:59:24,913 INFO anaconda: Clearing libuser.conf at /tmp/libuser.Dyy8Gj
      12:59:25,154 INFO anaconda: Creating users
      12:59:25,155 INFO anaconda: Configuring addons
      12:59:25,155 INFO anaconda: Configuring addons
      12:59:25,155 INFO anaconda: Generating initramfs
      12:59:49,467 INFO anaconda: Generating initramfs
      12:59:49,467 INFO anaconda: Running post-installation scripts
      12:59:49,467 INFO anaconda: Running kickstart %%post script(s)
      12:59:50,782 INFO anaconda: All kickstart %%post script(s) have been run
      12:59:50,782 INFO anaconda: Running post-installation scripts
      12:59:50,784 INFO anaconda: Thread Done: AnaConfigurationThread (140629395244800)

"""

import logging
log = logging.getLogger("lorax-composer")

import os
from flask import jsonify, request, Response, send_file
import pytoml as toml

from pylorax.sysutils import joinpaths
from pylorax.api.checkparams import checkparams
from pylorax.api.compose import start_build, compose_types
from pylorax.api.crossdomain import crossdomain
from pylorax.api.errors import *                               # pylint: disable=wildcard-import
from pylorax.api.projects import projects_list, projects_info, projects_depsolve
from pylorax.api.projects import modules_list, modules_info, ProjectsError, repo_to_source
from pylorax.api.projects import get_repo_sources, delete_repo_source, source_to_repo, dnf_repo_to_file_repo
from pylorax.api.queue import queue_status, build_status, uuid_delete, uuid_status, uuid_info
from pylorax.api.queue import uuid_tar, uuid_image, uuid_cancel, uuid_log
from pylorax.api.recipes import RecipeError, list_branch_files, read_recipe_commit, recipe_filename, list_commits
from pylorax.api.recipes import recipe_from_dict, recipe_from_toml, commit_recipe, delete_recipe, revert_recipe
from pylorax.api.recipes import tag_recipe_commit, recipe_diff
from pylorax.api.regexes import VALID_API_STRING
from pylorax.api.workspace import workspace_read, workspace_write, workspace_delete

# The API functions don't actually get called by any code here
# pylint: disable=unused-variable

def take_limits(iterable, offset, limit):
    """ Apply offset and limit to an iterable object

    :param iterable: The object to limit
    :type iterable: iter
    :param offset: The number of items to skip
    :type offset: int
    :param limit: The total number of items to return
    :type limit: int
    :returns: A subset of the iterable
    """
    return iterable[offset:][:limit]

def blueprint_exists(api, branch, blueprint_name):
    try:
        with api.config["GITLOCK"].lock:
            read_recipe_commit(api.config["GITLOCK"].repo, branch, blueprint_name)

        return True
    except RecipeError:
        return False

def v0_api(api):
    # Note that Sphinx will not generate documentations for any of these.
    @api.route("/api/v0/blueprints/list")
    @crossdomain(origin="*")
    def v0_blueprints_list():
        """List the available blueprints on a branch."""
        branch = request.args.get("branch", "master")
        if VALID_API_STRING.match(branch) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in branch argument"}]), 400

        try:
            limit = int(request.args.get("limit", "20"))
            offset = int(request.args.get("offset", "0"))
        except ValueError as e:
            return jsonify(status=False, errors=[{"id": BAD_LIMIT_OR_OFFSET, "msg": str(e)}]), 400

        with api.config["GITLOCK"].lock:
            blueprints = [f[:-5] for f in list_branch_files(api.config["GITLOCK"].repo, branch)]
            limited_blueprints = take_limits(blueprints, offset, limit)
        return jsonify(blueprints=limited_blueprints, limit=limit, offset=offset, total=len(blueprints))

    @api.route("/api/v0/blueprints/info", defaults={'blueprint_names': ""})
    @api.route("/api/v0/blueprints/info/<blueprint_names>")
    @crossdomain(origin="*")
    @checkparams([("blueprint_names", "", "no blueprint names given")])
    def v0_blueprints_info(blueprint_names):
        """Return the contents of the blueprint, or a list of blueprints"""
        if VALID_API_STRING.match(blueprint_names) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        branch = request.args.get("branch", "master")
        if VALID_API_STRING.match(branch) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in branch argument"}]), 400

        out_fmt = request.args.get("format", "json")
        if VALID_API_STRING.match(out_fmt) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in format argument"}]), 400

        blueprints = []
        changes = []
        errors = []
        for blueprint_name in [n.strip() for n in blueprint_names.split(",")]:
            exceptions = []
            # Get the workspace version (if it exists)
            try:
                with api.config["GITLOCK"].lock:
                    ws_blueprint = workspace_read(api.config["GITLOCK"].repo, branch, blueprint_name)
            except Exception as e:
                ws_blueprint = None
                exceptions.append(str(e))
                log.error("(v0_blueprints_info) %s", str(e))

            # Get the git version (if it exists)
            try:
                with api.config["GITLOCK"].lock:
                    git_blueprint = read_recipe_commit(api.config["GITLOCK"].repo, branch, blueprint_name)
            except Exception as e:
                git_blueprint = None
                exceptions.append(str(e))
                log.error("(v0_blueprints_info) %s", str(e))

            if not ws_blueprint and not git_blueprint:
                # Neither blueprint, return an error
                errors.append({"id": UNKNOWN_BLUEPRINT, "msg": "%s: %s" % (blueprint_name, ", ".join(exceptions))})
            elif ws_blueprint and not git_blueprint:
                # No git blueprint, return the workspace blueprint
                changes.append({"name":blueprint_name, "changed":True})
                blueprints.append(ws_blueprint)
            elif not ws_blueprint and git_blueprint:
                # No workspace blueprint, no change, return the git blueprint
                changes.append({"name":blueprint_name, "changed":False})
                blueprints.append(git_blueprint)
            else:
                # Both exist, maybe changed, return the workspace blueprint
                changes.append({"name":blueprint_name, "changed":ws_blueprint != git_blueprint})
                blueprints.append(ws_blueprint)

        # Sort all the results by case-insensitive blueprint name
        changes = sorted(changes, key=lambda c: c["name"].lower())
        blueprints = sorted(blueprints, key=lambda r: r["name"].lower())

        if out_fmt == "toml":
            if errors:
                # If there are errors they need to be reported, use JSON and 400 for this
                return jsonify(status=False, errors=errors), 400
            else:
                # With TOML output we just want to dump the raw blueprint, skipping the rest.
                return "\n\n".join([r.toml() for r in blueprints])
        else:
            return jsonify(changes=changes, blueprints=blueprints, errors=errors)

    @api.route("/api/v0/blueprints/changes", defaults={'blueprint_names': ""})
    @api.route("/api/v0/blueprints/changes/<blueprint_names>")
    @crossdomain(origin="*")
    @checkparams([("blueprint_names", "", "no blueprint names given")])
    def v0_blueprints_changes(blueprint_names):
        """Return the changes to a blueprint or list of blueprints"""
        if VALID_API_STRING.match(blueprint_names) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        branch = request.args.get("branch", "master")
        if VALID_API_STRING.match(branch) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in branch argument"}]), 400

        try:
            limit = int(request.args.get("limit", "20"))
            offset = int(request.args.get("offset", "0"))
        except ValueError as e:
            return jsonify(status=False, errors=[{"id": BAD_LIMIT_OR_OFFSET, "msg": str(e)}]), 400

        blueprints = []
        errors = []
        for blueprint_name in [n.strip() for n in blueprint_names.split(",")]:
            filename = recipe_filename(blueprint_name)

            if not blueprint_exists(api, branch, blueprint_name):
                errors.append({"id": UNKNOWN_BLUEPRINT, "msg": "Unknown blueprint name: %s" % blueprint_name})
                continue

            try:
                with api.config["GITLOCK"].lock:
                    commits = list_commits(api.config["GITLOCK"].repo, branch, filename)
                    limited_commits = take_limits(list_commits(api.config["GITLOCK"].repo, branch, filename), offset, limit)
            except Exception as e:
                errors.append({"id": BLUEPRINTS_ERROR, "msg": "%s: %s" % (blueprint_name, str(e))})
                log.error("(v0_blueprints_changes) %s", str(e))
            else:
                blueprints.append({"name":blueprint_name, "changes":limited_commits, "total":len(commits)})

        blueprints = sorted(blueprints, key=lambda r: r["name"].lower())

        return jsonify(blueprints=blueprints, errors=errors, offset=offset, limit=limit)

    @api.route("/api/v0/blueprints/new", methods=["POST"])
    @crossdomain(origin="*")
    def v0_blueprints_new():
        """Commit a new blueprint"""
        branch = request.args.get("branch", "master")
        if VALID_API_STRING.match(branch) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in branch argument"}]), 400

        try:
            if request.headers['Content-Type'] == "text/x-toml":
                blueprint = recipe_from_toml(request.data)
            else:
                blueprint = recipe_from_dict(request.get_json(cache=False))

            if VALID_API_STRING.match(blueprint["name"]) is None:
                return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

            with api.config["GITLOCK"].lock:
                commit_recipe(api.config["GITLOCK"].repo, branch, blueprint)

                # Read the blueprint with new version and write it to the workspace
                blueprint = read_recipe_commit(api.config["GITLOCK"].repo, branch, blueprint["name"])
                workspace_write(api.config["GITLOCK"].repo, branch, blueprint)
        except Exception as e:
            log.error("(v0_blueprints_new) %s", str(e))
            return jsonify(status=False, errors=[{"id": BLUEPRINTS_ERROR, "msg": str(e)}]), 400
        else:
            return jsonify(status=True)

    @api.route("/api/v0/blueprints/delete", defaults={'blueprint_name': ""}, methods=["DELETE"])
    @api.route("/api/v0/blueprints/delete/<blueprint_name>", methods=["DELETE"])
    @crossdomain(origin="*")
    @checkparams([("blueprint_name", "", "no blueprint name given")])
    def v0_blueprints_delete(blueprint_name):
        """Delete a blueprint from git"""
        if VALID_API_STRING.match(blueprint_name) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        branch = request.args.get("branch", "master")
        if VALID_API_STRING.match(branch) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in branch argument"}]), 400

        try:
            with api.config["GITLOCK"].lock:
                delete_recipe(api.config["GITLOCK"].repo, branch, blueprint_name)
        except Exception as e:
            log.error("(v0_blueprints_delete) %s", str(e))
            return jsonify(status=False, errors=[{"id": BLUEPRINTS_ERROR, "msg": str(e)}]), 400
        else:
            return jsonify(status=True)

    @api.route("/api/v0/blueprints/workspace", methods=["POST"])
    @crossdomain(origin="*")
    def v0_blueprints_workspace():
        """Write a blueprint to the workspace"""
        branch = request.args.get("branch", "master")
        if VALID_API_STRING.match(branch) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in branch argument"}]), 400

        try:
            if request.headers['Content-Type'] == "text/x-toml":
                blueprint = recipe_from_toml(request.data)
            else:
                blueprint = recipe_from_dict(request.get_json(cache=False))

            if VALID_API_STRING.match(blueprint["name"]) is None:
                return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

            with api.config["GITLOCK"].lock:
                workspace_write(api.config["GITLOCK"].repo, branch, blueprint)
        except Exception as e:
            log.error("(v0_blueprints_workspace) %s", str(e))
            return jsonify(status=False, errors=[{"id": BLUEPRINTS_ERROR, "msg": str(e)}]), 400
        else:
            return jsonify(status=True)

    @api.route("/api/v0/blueprints/workspace", defaults={'blueprint_name': ""}, methods=["DELETE"])
    @api.route("/api/v0/blueprints/workspace/<blueprint_name>", methods=["DELETE"])
    @crossdomain(origin="*")
    @checkparams([("blueprint_name", "", "no blueprint name given")])
    def v0_blueprints_delete_workspace(blueprint_name):
        """Delete a blueprint from the workspace"""
        if VALID_API_STRING.match(blueprint_name) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        branch = request.args.get("branch", "master")
        if VALID_API_STRING.match(branch) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in branch argument"}]), 400

        try:
            with api.config["GITLOCK"].lock:
                workspace_delete(api.config["GITLOCK"].repo, branch, blueprint_name)
        except Exception as e:
            log.error("(v0_blueprints_delete_workspace) %s", str(e))
            return jsonify(status=False, errors=[{"id": BLUEPRINTS_ERROR, "msg": str(e)}]), 400
        else:
            return jsonify(status=True)

    @api.route("/api/v0/blueprints/undo", defaults={'blueprint_name': "", 'commit': ""}, methods=["POST"])
    @api.route("/api/v0/blueprints/undo/<blueprint_name>", defaults={'commit': ""}, methods=["POST"])
    @api.route("/api/v0/blueprints/undo/<blueprint_name>/<commit>", methods=["POST"])
    @crossdomain(origin="*")
    @checkparams([("blueprint_name", "", "no blueprint name given"),
                  ("commit", "", "no commit ID given")])
    def v0_blueprints_undo(blueprint_name, commit):
        """Undo changes to a blueprint by reverting to a previous commit."""
        if VALID_API_STRING.match(blueprint_name) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        branch = request.args.get("branch", "master")
        if VALID_API_STRING.match(branch) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in branch argument"}]), 400

        try:
            with api.config["GITLOCK"].lock:
                revert_recipe(api.config["GITLOCK"].repo, branch, blueprint_name, commit)

                # Read the new recipe and write it to the workspace
                blueprint = read_recipe_commit(api.config["GITLOCK"].repo, branch, blueprint_name)
                workspace_write(api.config["GITLOCK"].repo, branch, blueprint)
        except Exception as e:
            log.error("(v0_blueprints_undo) %s", str(e))
            return jsonify(status=False, errors=[{"id": UNKNOWN_COMMIT, "msg": str(e)}]), 400
        else:
            return jsonify(status=True)

    @api.route("/api/v0/blueprints/tag", defaults={'blueprint_name': ""}, methods=["POST"])
    @api.route("/api/v0/blueprints/tag/<blueprint_name>", methods=["POST"])
    @crossdomain(origin="*")
    @checkparams([("blueprint_name", "", "no blueprint name given")])
    def v0_blueprints_tag(blueprint_name):
        """Tag a blueprint's latest blueprint commit as a 'revision'"""
        if VALID_API_STRING.match(blueprint_name) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        branch = request.args.get("branch", "master")
        if VALID_API_STRING.match(branch) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in branch argument"}]), 400

        try:
            with api.config["GITLOCK"].lock:
                tag_recipe_commit(api.config["GITLOCK"].repo, branch, blueprint_name)
        except Exception as e:
            log.error("(v0_blueprints_tag) %s", str(e))
            return jsonify(status=False, errors=[{"id": BLUEPRINTS_ERROR, "msg": str(e)}]), 400
        else:
            return jsonify(status=True)

    @api.route("/api/v0/blueprints/diff", defaults={'blueprint_name': "", 'from_commit': "", 'to_commit': ""})
    @api.route("/api/v0/blueprints/diff/<blueprint_name>", defaults={'from_commit': "", 'to_commit': ""})
    @api.route("/api/v0/blueprints/diff/<blueprint_name>/<from_commit>", defaults={'to_commit': ""})
    @api.route("/api/v0/blueprints/diff/<blueprint_name>/<from_commit>/<to_commit>")
    @crossdomain(origin="*")
    @checkparams([("blueprint_name", "", "no blueprint name given"),
                  ("from_commit", "", "no from commit ID given"),
                  ("to_commit", "", "no to commit ID given")])
    def v0_blueprints_diff(blueprint_name, from_commit, to_commit):
        """Return the differences between two commits of a blueprint"""
        for s in [blueprint_name, from_commit, to_commit]:
            if VALID_API_STRING.match(s) is None:
                return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        branch = request.args.get("branch", "master")
        if VALID_API_STRING.match(branch) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in branch argument"}]), 400

        try:
            if from_commit == "NEWEST":
                with api.config["GITLOCK"].lock:
                    old_blueprint = read_recipe_commit(api.config["GITLOCK"].repo, branch, blueprint_name)
            else:
                with api.config["GITLOCK"].lock:
                    old_blueprint = read_recipe_commit(api.config["GITLOCK"].repo, branch, blueprint_name, from_commit)
        except Exception as e:
            log.error("(v0_blueprints_diff) %s", str(e))
            return jsonify(status=False, errors=[{"id": UNKNOWN_COMMIT, "msg": str(e)}]), 400

        try:
            if to_commit == "WORKSPACE":
                with api.config["GITLOCK"].lock:
                    new_blueprint = workspace_read(api.config["GITLOCK"].repo, branch, blueprint_name)
                # If there is no workspace, use the newest commit instead
                if not new_blueprint:
                    with api.config["GITLOCK"].lock:
                        new_blueprint = read_recipe_commit(api.config["GITLOCK"].repo, branch, blueprint_name)
            elif to_commit == "NEWEST":
                with api.config["GITLOCK"].lock:
                    new_blueprint = read_recipe_commit(api.config["GITLOCK"].repo, branch, blueprint_name)
            else:
                with api.config["GITLOCK"].lock:
                    new_blueprint = read_recipe_commit(api.config["GITLOCK"].repo, branch, blueprint_name, to_commit)
        except Exception as e:
            log.error("(v0_blueprints_diff) %s", str(e))
            return jsonify(status=False, errors=[{"id": UNKNOWN_COMMIT, "msg": str(e)}]), 400

        diff = recipe_diff(old_blueprint, new_blueprint)
        return jsonify(diff=diff)

    @api.route("/api/v0/blueprints/freeze", defaults={'blueprint_names': ""})
    @api.route("/api/v0/blueprints/freeze/<blueprint_names>")
    @crossdomain(origin="*")
    @checkparams([("blueprint_names", "", "no blueprint names given")])
    def v0_blueprints_freeze(blueprint_names):
        """Return the blueprint with the exact modules and packages selected by depsolve"""
        if VALID_API_STRING.match(blueprint_names) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        branch = request.args.get("branch", "master")
        if VALID_API_STRING.match(branch) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in branch argument"}]), 400

        out_fmt = request.args.get("format", "json")
        if VALID_API_STRING.match(out_fmt) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in format argument"}]), 400

        blueprints = []
        errors = []
        for blueprint_name in [n.strip() for n in sorted(blueprint_names.split(","), key=lambda n: n.lower())]:
            # get the blueprint
            # Get the workspace version (if it exists)
            blueprint = None
            try:
                with api.config["GITLOCK"].lock:
                    blueprint = workspace_read(api.config["GITLOCK"].repo, branch, blueprint_name)
            except Exception:
                pass

            if not blueprint:
                # No workspace version, get the git version (if it exists)
                try:
                    with api.config["GITLOCK"].lock:
                        blueprint = read_recipe_commit(api.config["GITLOCK"].repo, branch, blueprint_name)
                except Exception as e:
                    errors.append({"id": BLUEPRINTS_ERROR, "msg": "%s: %s" % (blueprint_name, str(e))})
                    log.error("(v0_blueprints_freeze) %s", str(e))

            # No blueprint found, skip it.
            if not blueprint:
                errors.append({"id": UNKNOWN_BLUEPRINT, "msg": "%s: blueprint_not_found" % blueprint_name})
                continue

            # Combine modules and packages and depsolve the list
            # TODO include the version/glob in the depsolving
            module_nver = blueprint.module_nver
            package_nver = blueprint.package_nver
            projects = sorted(set(module_nver+package_nver), key=lambda p: p[0].lower())
            deps = []
            try:
                with api.config["DNFLOCK"].lock:
                    deps = projects_depsolve(api.config["DNFLOCK"].dbo, projects, blueprint.group_names)
            except ProjectsError as e:
                errors.append({"id": BLUEPRINTS_ERROR, "msg": "%s: %s" % (blueprint_name, str(e))})
                log.error("(v0_blueprints_freeze) %s", str(e))

            blueprints.append({"blueprint": blueprint.freeze(deps)})

        if out_fmt == "toml":
            # With TOML output we just want to dump the raw blueprint, skipping the rest.
            return "\n\n".join([e["blueprint"].toml() for e in blueprints])
        else:
            return jsonify(blueprints=blueprints, errors=errors)

    @api.route("/api/v0/blueprints/depsolve", defaults={'blueprint_names': ""})
    @api.route("/api/v0/blueprints/depsolve/<blueprint_names>")
    @crossdomain(origin="*")
    @checkparams([("blueprint_names", "", "no blueprint names given")])
    def v0_blueprints_depsolve(blueprint_names):
        """Return the dependencies for a blueprint"""
        if VALID_API_STRING.match(blueprint_names) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        branch = request.args.get("branch", "master")
        if VALID_API_STRING.match(branch) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in branch argument"}]), 400

        blueprints = []
        errors = []
        for blueprint_name in [n.strip() for n in sorted(blueprint_names.split(","), key=lambda n: n.lower())]:
            # get the blueprint
            # Get the workspace version (if it exists)
            blueprint = None
            try:
                with api.config["GITLOCK"].lock:
                    blueprint = workspace_read(api.config["GITLOCK"].repo, branch, blueprint_name)
            except Exception:
                pass

            if not blueprint:
                # No workspace version, get the git version (if it exists)
                try:
                    with api.config["GITLOCK"].lock:
                        blueprint = read_recipe_commit(api.config["GITLOCK"].repo, branch, blueprint_name)
                except Exception as e:
                    errors.append({"id": BLUEPRINTS_ERROR, "msg": "%s: %s" % (blueprint_name, str(e))})
                    log.error("(v0_blueprints_depsolve) %s", str(e))

            # No blueprint found, skip it.
            if not blueprint:
                errors.append({"id": UNKNOWN_BLUEPRINT, "msg": "%s: blueprint not found" % blueprint_name})
                continue

            # Combine modules and packages and depsolve the list
            # TODO include the version/glob in the depsolving
            module_nver = blueprint.module_nver
            package_nver = blueprint.package_nver
            projects = sorted(set(module_nver+package_nver), key=lambda p: p[0].lower())
            deps = []
            try:
                with api.config["DNFLOCK"].lock:
                    deps = projects_depsolve(api.config["DNFLOCK"].dbo, projects, blueprint.group_names)
            except ProjectsError as e:
                errors.append({"id": BLUEPRINTS_ERROR, "msg": "%s: %s" % (blueprint_name, str(e))})
                log.error("(v0_blueprints_depsolve) %s", str(e))

            # Get the NEVRA's of the modules and projects, add as "modules"
            modules = []
            for dep in deps:
                if dep["name"] in projects:
                    modules.append(dep)
            modules = sorted(modules, key=lambda m: m["name"].lower())

            blueprints.append({"blueprint":blueprint, "dependencies":deps, "modules":modules})

        return jsonify(blueprints=blueprints, errors=errors)

    @api.route("/api/v0/projects/list")
    @crossdomain(origin="*")
    def v0_projects_list():
        """List all of the available projects/packages"""
        try:
            limit = int(request.args.get("limit", "20"))
            offset = int(request.args.get("offset", "0"))
        except ValueError as e:
            return jsonify(status=False, errors=[{"id": BAD_LIMIT_OR_OFFSET, "msg": str(e)}]), 400

        try:
            with api.config["DNFLOCK"].lock:
                available = projects_list(api.config["DNFLOCK"].dbo)
        except ProjectsError as e:
            log.error("(v0_projects_list) %s", str(e))
            return jsonify(status=False, errors=[{"id": PROJECTS_ERROR, "msg": str(e)}]), 400

        projects = take_limits(available, offset, limit)
        return jsonify(projects=projects, offset=offset, limit=limit, total=len(available))

    @api.route("/api/v0/projects/info", defaults={'project_names': ""})
    @api.route("/api/v0/projects/info/<project_names>")
    @crossdomain(origin="*")
    @checkparams([("project_names", "", "no project names given")])
    def v0_projects_info(project_names):
        """Return detailed information about the listed projects"""
        if VALID_API_STRING.match(project_names) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        try:
            with api.config["DNFLOCK"].lock:
                projects = projects_info(api.config["DNFLOCK"].dbo, project_names.split(","))
        except ProjectsError as e:
            log.error("(v0_projects_info) %s", str(e))
            return jsonify(status=False, errors=[{"id": PROJECTS_ERROR, "msg": str(e)}]), 400

        if not projects:
            msg = "one of the requested projects does not exist: %s" % project_names
            log.error("(v0_projects_info) %s", msg)
            return jsonify(status=False, errors=[{"id": UNKNOWN_PROJECT, "msg": msg}]), 400

        return jsonify(projects=projects)

    @api.route("/api/v0/projects/depsolve", defaults={'project_names': ""})
    @api.route("/api/v0/projects/depsolve/<project_names>")
    @crossdomain(origin="*")
    @checkparams([("project_names", "", "no project names given")])
    def v0_projects_depsolve(project_names):
        """Return detailed information about the listed projects"""
        if VALID_API_STRING.match(project_names) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        try:
            with api.config["DNFLOCK"].lock:
                deps = projects_depsolve(api.config["DNFLOCK"].dbo, [(n, "*") for n in project_names.split(",")], [])
        except ProjectsError as e:
            log.error("(v0_projects_depsolve) %s", str(e))
            return jsonify(status=False, errors=[{"id": PROJECTS_ERROR, "msg": str(e)}]), 400

        if not deps:
            msg = "one of the requested projects does not exist: %s" % project_names
            log.error("(v0_projects_depsolve) %s", msg)
            return jsonify(status=False, errors=[{"id": UNKNOWN_PROJECT, "msg": msg}]), 400

        return jsonify(projects=deps)

    @api.route("/api/v0/projects/source/list")
    @crossdomain(origin="*")
    def v0_projects_source_list():
        """Return the list of source names"""
        with api.config["DNFLOCK"].lock:
            repos = list(api.config["DNFLOCK"].dbo.repos.iter_enabled())
        sources = sorted([r.id for r in repos])
        return jsonify(sources=sources)

    @api.route("/api/v0/projects/source/info", defaults={'source_names': ""})
    @api.route("/api/v0/projects/source/info/<source_names>")
    @crossdomain(origin="*")
    @checkparams([("source_names", "", "no source names given")])
    def v0_projects_source_info(source_names):
        """Return detailed info about the list of sources"""
        if VALID_API_STRING.match(source_names) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        out_fmt = request.args.get("format", "json")
        if VALID_API_STRING.match(out_fmt) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in format argument"}]), 400

        # Return info on all of the sources
        if source_names == "*":
            with api.config["DNFLOCK"].lock:
                source_names = ",".join(r.id for r in api.config["DNFLOCK"].dbo.repos.iter_enabled())

        sources = {}
        errors = []
        system_sources = get_repo_sources("/etc/yum.repos.d/*.repo")
        for source in source_names.split(","):
            with api.config["DNFLOCK"].lock:
                repo = api.config["DNFLOCK"].dbo.repos.get(source, None)
            if not repo:
                errors.append({"id": UNKNOWN_SOURCE, "msg": "%s is not a valid source" % source})
                continue
            sources[repo.id] = repo_to_source(repo, repo.id in system_sources)

        if out_fmt == "toml" and not errors:
            # With TOML output we just want to dump the raw sources, skipping the errors
            return toml.dumps(sources)
        elif out_fmt == "toml" and errors:
            # TOML requested, but there was an error
            return jsonify(status=False, errors=errors), 400
        else:
            return jsonify(sources=sources, errors=errors)

    @api.route("/api/v0/projects/source/new", methods=["POST"])
    @crossdomain(origin="*")
    def v0_projects_source_new():
        """Add a new package source. Or change an existing one"""
        if request.headers['Content-Type'] == "text/x-toml":
            source = toml.loads(request.data)
        else:
            source = request.get_json(cache=False)

        system_sources = get_repo_sources("/etc/yum.repos.d/*.repo")
        if source["name"] in system_sources:
            return jsonify(status=False, errors=[{"id": SYSTEM_SOURCE, "msg": "%s is a system source, it cannot be changed." % source["name"]}]), 400

        try:
            # Remove it from the RepoDict (NOTE that this isn't explicitly supported by the DNF API)
            with api.config["DNFLOCK"].lock:
                dbo = api.config["DNFLOCK"].dbo
                # If this repo already exists, delete it and replace it with the new one
                repos = list(r.id for r in dbo.repos.iter_enabled())
                if source["name"] in repos:
                    del dbo.repos[source["name"]]

                repo = source_to_repo(source, dbo.conf)
                dbo.repos.add(repo)

                log.info("Updating repository metadata after adding %s", source["name"])
                dbo.fill_sack(load_system_repo=False)
                dbo.read_comps()

            # Write the new repo to disk, replacing any existing ones
            repo_dir = api.config["COMPOSER_CFG"].get("composer", "repo_dir")

            # Remove any previous sources with this name, ignore it if it isn't found
            try:
                delete_repo_source(joinpaths(repo_dir, "*.repo"), source["name"])
            except ProjectsError:
                pass

            # Make sure the source name can't contain a path traversal by taking the basename
            source_path = joinpaths(repo_dir, os.path.basename("%s.repo" % source["name"]))
            with open(source_path, "w") as f:
                f.write(dnf_repo_to_file_repo(repo))
        except Exception as e:
            log.error("(v0_projects_source_add) adding %s failed: %s", source["name"], str(e))

            # Cleanup the mess, if loading it failed we don't want to leave it in memory
            repos = list(r.id for r in dbo.repos.iter_enabled())
            if source["name"] in repos:
                with api.config["DNFLOCK"].lock:
                    dbo = api.config["DNFLOCK"].dbo
                    del dbo.repos[source["name"]]

                    log.info("Updating repository metadata after adding %s failed", source["name"])
                    dbo.fill_sack(load_system_repo=False)
                    dbo.read_comps()

            return jsonify(status=False, errors=[{"id": PROJECTS_ERROR, "msg": str(e)}]), 400

        return jsonify(status=True)

    @api.route("/api/v0/projects/source/delete", defaults={'source_name': ""}, methods=["DELETE"])
    @api.route("/api/v0/projects/source/delete/<source_name>", methods=["DELETE"])
    @crossdomain(origin="*")
    @checkparams([("source_name", "", "no source name given")])
    def v0_projects_source_delete(source_name):
        """Delete the named source and return a status response"""
        if VALID_API_STRING.match(source_name) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        system_sources = get_repo_sources("/etc/yum.repos.d/*.repo")
        if source_name in system_sources:
            return jsonify(status=False, errors=[{"id": SYSTEM_SOURCE, "msg": "%s is a system source, it cannot be deleted." % source_name}]), 400
        share_dir = api.config["COMPOSER_CFG"].get("composer", "repo_dir")
        try:
            # Remove the file entry for the source
            delete_repo_source(joinpaths(share_dir, "*.repo"), source_name)

            # Remove it from the RepoDict (NOTE that this isn't explicitly supported by the DNF API)
            with api.config["DNFLOCK"].lock:
                if source_name in api.config["DNFLOCK"].dbo.repos:
                    del api.config["DNFLOCK"].dbo.repos[source_name]
                    log.info("Updating repository metadata after removing %s", source_name)
                    api.config["DNFLOCK"].dbo.fill_sack(load_system_repo=False)
                    api.config["DNFLOCK"].dbo.read_comps()

        except ProjectsError as e:
            log.error("(v0_projects_source_delete) %s", str(e))
            return jsonify(status=False, errors=[{"id": UNKNOWN_SOURCE, "msg": str(e)}]), 400

        return jsonify(status=True)

    @api.route("/api/v0/modules/list")
    @api.route("/api/v0/modules/list/<module_names>")
    @crossdomain(origin="*")
    def v0_modules_list(module_names=None):
        """List available modules, filtering by module_names"""
        if module_names and VALID_API_STRING.match(module_names) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        try:
            limit = int(request.args.get("limit", "20"))
            offset = int(request.args.get("offset", "0"))
        except ValueError as e:
            return jsonify(status=False, errors=[{"id": BAD_LIMIT_OR_OFFSET, "msg": str(e)}]), 400

        if module_names:
            module_names = module_names.split(",")

        try:
            with api.config["DNFLOCK"].lock:
                available = modules_list(api.config["DNFLOCK"].dbo, module_names)
        except ProjectsError as e:
            log.error("(v0_modules_list) %s", str(e))
            return jsonify(status=False, errors=[{"id": MODULES_ERROR, "msg": str(e)}]), 400

        if module_names and not available:
            msg = "one of the requested modules does not exist: %s" % module_names
            log.error("(v0_modules_list) %s", msg)
            return jsonify(status=False, errors=[{"id": UNKNOWN_MODULE, "msg": msg}]), 400

        modules = take_limits(available, offset, limit)
        return jsonify(modules=modules, offset=offset, limit=limit, total=len(available))

    @api.route("/api/v0/modules/info", defaults={'module_names': ""})
    @api.route("/api/v0/modules/info/<module_names>")
    @crossdomain(origin="*")
    @checkparams([("module_names", "", "no module names given")])
    def v0_modules_info(module_names):
        """Return detailed information about the listed modules"""
        if VALID_API_STRING.match(module_names) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400
        try:
            with api.config["DNFLOCK"].lock:
                modules = modules_info(api.config["DNFLOCK"].dbo, module_names.split(","))
        except ProjectsError as e:
            log.error("(v0_modules_info) %s", str(e))
            return jsonify(status=False, errors=[{"id": MODULES_ERROR, "msg": str(e)}]), 400

        if not modules:
            msg = "one of the requested modules does not exist: %s" % module_names
            log.error("(v0_modules_info) %s", msg)
            return jsonify(status=False, errors=[{"id": UNKNOWN_MODULE, "msg": msg}]), 400

        return jsonify(modules=modules)

    @api.route("/api/v0/compose", methods=["POST"])
    @crossdomain(origin="*")
    def v0_compose_start():
        """Start a compose

        The body of the post should have these fields:
          blueprint_name - The blueprint name from /blueprints/list/
          compose_type   - The type of output to create, from /compose/types
          branch         - Optional, defaults to master, selects the git branch to use for the blueprint.
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
            errors.append({"id": UNKNOWN_BLUEPRINT,"msg": "No 'blueprint_name' in the JSON request"})
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

        if VALID_API_STRING.match(blueprint_name) is None:
            errors.append({"id": INVALID_CHARS, "msg": "Invalid characters in API path"})

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

        return jsonify(status=True, build_id=build_id)

    @api.route("/api/v0/compose/types")
    @crossdomain(origin="*")
    def v0_compose_types():
        """Return the list of enabled output types

        (only enabled types are returned)
        """
        share_dir = api.config["COMPOSER_CFG"].get("composer", "share_dir")
        return jsonify(types=[{"name": k, "enabled": True} for k in compose_types(share_dir)])

    @api.route("/api/v0/compose/queue")
    @crossdomain(origin="*")
    def v0_compose_queue():
        """Return the status of the new and running queues"""
        return jsonify(queue_status(api.config["COMPOSER_CFG"]))

    @api.route("/api/v0/compose/finished")
    @crossdomain(origin="*")
    def v0_compose_finished():
        """Return the list of finished composes"""
        return jsonify(finished=build_status(api.config["COMPOSER_CFG"], "FINISHED"))

    @api.route("/api/v0/compose/failed")
    @crossdomain(origin="*")
    def v0_compose_failed():
        """Return the list of failed composes"""
        return jsonify(failed=build_status(api.config["COMPOSER_CFG"], "FAILED"))

    @api.route("/api/v0/compose/status", defaults={'uuids': ""})
    @api.route("/api/v0/compose/status/<uuids>")
    @crossdomain(origin="*")
    @checkparams([("uuids", "", "no UUIDs given")])
    def v0_compose_status(uuids):
        """Return the status of the listed uuids"""
        if VALID_API_STRING.match(uuids) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        blueprint = request.args.get("blueprint", None)
        status = request.args.get("status", None)
        compose_type = request.args.get("type", None)

        results = []
        errors = []

        if uuids.strip() == '*':
            queue_status_dict = queue_status(api.config["COMPOSER_CFG"])
            queue_new = queue_status_dict["new"]
            queue_running = queue_status_dict["run"]
            candidates = queue_new + queue_running + build_status(api.config["COMPOSER_CFG"])
        else:
            candidates = []
            for uuid in [n.strip().lower() for n in uuids.split(",")]:
                details = uuid_status(api.config["COMPOSER_CFG"], uuid)
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

    @api.route("/api/v0/compose/cancel", defaults={'uuid': ""}, methods=["DELETE"])
    @api.route("/api/v0/compose/cancel/<uuid>", methods=["DELETE"])
    @crossdomain(origin="*")
    @checkparams([("uuid", "", "no UUID given")])
    def v0_compose_cancel(uuid):
        """Cancel a running compose and delete its results directory"""
        if VALID_API_STRING.match(uuid) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        status = uuid_status(api.config["COMPOSER_CFG"], uuid)
        if status is None:
            return jsonify(status=False, errors=[{"id": UNKNOWN_UUID, "msg": "%s is not a valid build uuid" % uuid}]), 400

        if status["queue_status"] not in ["WAITING", "RUNNING"]:
            return jsonify(status=False, errors=[{"id": BUILD_IN_WRONG_STATE, "msg": "Build %s is not in WAITING or RUNNING." % uuid}])

        try:
            uuid_cancel(api.config["COMPOSER_CFG"], uuid)
        except Exception as e:
            return jsonify(status=False, errors=[{"id": COMPOSE_ERROR, "msg": "%s: %s" % (uuid, str(e))}]),400
        else:
            return jsonify(status=True, uuid=uuid)

    @api.route("/api/v0/compose/delete", defaults={'uuids': ""}, methods=["DELETE"])
    @api.route("/api/v0/compose/delete/<uuids>", methods=["DELETE"])
    @crossdomain(origin="*")
    @checkparams([("uuids", "", "no UUIDs given")])
    def v0_compose_delete(uuids):
        """Delete the compose results for the listed uuids"""
        if VALID_API_STRING.match(uuids) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        results = []
        errors = []
        for uuid in [n.strip().lower() for n in uuids.split(",")]:
            status = uuid_status(api.config["COMPOSER_CFG"], uuid)
            if status is None:
                errors.append({"id": UNKNOWN_UUID, "msg": "%s is not a valid build uuid" % uuid})
            elif status["queue_status"] not in ["FINISHED", "FAILED"]:
                errors.append({"id": BUILD_IN_WRONG_STATE, "msg": "Build %s is not in FINISHED or FAILED." % uuid})
            else:
                try:
                    uuid_delete(api.config["COMPOSER_CFG"], uuid)
                except Exception as e:
                    errors.append({"id": COMPOSE_ERROR, "msg": "%s: %s" % (uuid, str(e))})
                else:
                    results.append({"uuid":uuid, "status":True})
        return jsonify(uuids=results, errors=errors)

    @api.route("/api/v0/compose/info", defaults={'uuid': ""})
    @api.route("/api/v0/compose/info/<uuid>")
    @crossdomain(origin="*")
    @checkparams([("uuid", "", "no UUID given")])
    def v0_compose_info(uuid):
        """Return detailed info about a compose"""
        if VALID_API_STRING.match(uuid) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        try:
            info = uuid_info(api.config["COMPOSER_CFG"], uuid)
        except Exception as e:
            return jsonify(status=False, errors=[{"id": COMPOSE_ERROR, "msg": str(e)}]), 400

        if info is None:
            return jsonify(status=False, errors=[{"id": UNKNOWN_UUID, "msg": "%s is not a valid build uuid" % uuid}]), 400
        else:
            return jsonify(**info)

    @api.route("/api/v0/compose/metadata", defaults={'uuid': ""})
    @api.route("/api/v0/compose/metadata/<uuid>")
    @crossdomain(origin="*")
    @checkparams([("uuid","", "no UUID given")])
    def v0_compose_metadata(uuid):
        """Return a tar of the metadata for the build"""
        if VALID_API_STRING.match(uuid) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        status = uuid_status(api.config["COMPOSER_CFG"], uuid)
        if status is None:
            return jsonify(status=False, errors=[{"id": UNKNOWN_UUID, "msg": "%s is not a valid build uuid" % uuid}]), 400
        if status["queue_status"] not in ["FINISHED", "FAILED"]:
            return jsonify(status=False, errors=[{"id": BUILD_IN_WRONG_STATE, "msg": "Build %s not in FINISHED or FAILED state." % uuid}]), 400
        else:
            return Response(uuid_tar(api.config["COMPOSER_CFG"], uuid, metadata=True, image=False, logs=False),
                            mimetype="application/x-tar",
                            headers=[("Content-Disposition", "attachment; filename=%s-metadata.tar;" % uuid)],
                            direct_passthrough=True)

    @api.route("/api/v0/compose/results", defaults={'uuid': ""})
    @api.route("/api/v0/compose/results/<uuid>")
    @crossdomain(origin="*")
    @checkparams([("uuid","", "no UUID given")])
    def v0_compose_results(uuid):
        """Return a tar of the metadata and the results for the build"""
        if VALID_API_STRING.match(uuid) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        status = uuid_status(api.config["COMPOSER_CFG"], uuid)
        if status is None:
            return jsonify(status=False, errors=[{"id": UNKNOWN_UUID, "msg": "%s is not a valid build uuid" % uuid}]), 400
        elif status["queue_status"] not in ["FINISHED", "FAILED"]:
            return jsonify(status=False, errors=[{"id": BUILD_IN_WRONG_STATE, "msg": "Build %s not in FINISHED or FAILED state." % uuid}]), 400
        else:
            return Response(uuid_tar(api.config["COMPOSER_CFG"], uuid, metadata=True, image=True, logs=True),
                            mimetype="application/x-tar",
                            headers=[("Content-Disposition", "attachment; filename=%s.tar;" % uuid)],
                            direct_passthrough=True)

    @api.route("/api/v0/compose/logs", defaults={'uuid': ""})
    @api.route("/api/v0/compose/logs/<uuid>")
    @crossdomain(origin="*")
    @checkparams([("uuid","", "no UUID given")])
    def v0_compose_logs(uuid):
        """Return a tar of the metadata for the build"""
        if VALID_API_STRING.match(uuid) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        status = uuid_status(api.config["COMPOSER_CFG"], uuid)
        if status is None:
            return jsonify(status=False, errors=[{"id": UNKNOWN_UUID, "msg": "%s is not a valid build uuid" % uuid}]), 400
        elif status["queue_status"] not in ["FINISHED", "FAILED"]:
            return jsonify(status=False, errors=[{"id": BUILD_IN_WRONG_STATE, "msg": "Build %s not in FINISHED or FAILED state." % uuid}]), 400
        else:
            return Response(uuid_tar(api.config["COMPOSER_CFG"], uuid, metadata=False, image=False, logs=True),
                            mimetype="application/x-tar",
                            headers=[("Content-Disposition", "attachment; filename=%s-logs.tar;" % uuid)],
                            direct_passthrough=True)

    @api.route("/api/v0/compose/image", defaults={'uuid': ""})
    @api.route("/api/v0/compose/image/<uuid>")
    @crossdomain(origin="*")
    @checkparams([("uuid","", "no UUID given")])
    def v0_compose_image(uuid):
        """Return the output image for the build"""
        if VALID_API_STRING.match(uuid) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        status = uuid_status(api.config["COMPOSER_CFG"], uuid)
        if status is None:
            return jsonify(status=False, errors=[{"id": UNKNOWN_UUID, "msg": "%s is not a valid build uuid" % uuid}]), 400
        elif status["queue_status"] not in ["FINISHED", "FAILED"]:
            return jsonify(status=False, errors=[{"id": BUILD_IN_WRONG_STATE, "msg": "Build %s not in FINISHED or FAILED state." % uuid}]), 400
        else:
            image_name, image_path = uuid_image(api.config["COMPOSER_CFG"], uuid)

            # Make sure it really exists
            if not os.path.exists(image_path):
                return jsonify(status=False, errors=[{"id": BUILD_MISSING_FILE, "msg": "Build %s is missing image file %s" % (uuid, image_name)}]), 400

            # Make the image name unique
            image_name = uuid + "-" + image_name
            # XXX - Will mime type guessing work for all our output?
            return send_file(image_path, as_attachment=True, attachment_filename=image_name, add_etags=False)

    @api.route("/api/v0/compose/log", defaults={'uuid': ""})
    @api.route("/api/v0/compose/log/<uuid>")
    @crossdomain(origin="*")
    @checkparams([("uuid","", "no UUID given")])
    def v0_compose_log_tail(uuid):
        """Return the end of the main anaconda.log, defaults to 1Mbytes"""
        if VALID_API_STRING.match(uuid) is None:
            return jsonify(status=False, errors=[{"id": INVALID_CHARS, "msg": "Invalid characters in API path"}]), 400

        try:
            size = int(request.args.get("size", "1024"))
        except ValueError as e:
            return jsonify(status=False, errors=[{"id": COMPOSE_ERROR, "msg": str(e)}]), 400

        status = uuid_status(api.config["COMPOSER_CFG"], uuid)
        if status is None:
            return jsonify(status=False, errors=[{"id": UNKNOWN_UUID, "msg": "%s is not a valid build uuid" % uuid}]), 400
        elif status["queue_status"] == "WAITING":
            return jsonify(status=False, errors=[{"id": BUILD_IN_WRONG_STATE, "msg": "Build %s has not started yet. No logs to view" % uuid}])
        try:
            return Response(uuid_log(api.config["COMPOSER_CFG"], uuid, size), direct_passthrough=True)
        except RuntimeError as e:
            return jsonify(status=False, errors=[{"id": COMPOSE_ERROR, "msg": str(e)}]), 400
