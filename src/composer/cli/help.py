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

# Documentation for the commands
compose_help = """
compose start [--size XXXX] <BLUEPRINT> <TYPE> [<IMAGE-NAME> <PROVIDER> <PROFILE> | <IMAGE-NAME> <PROFILE.TOML>]
    Start a compose using the selected blueprint and output type. Optionally start an upload.
    --size is supported by osbuild-composer, and is in MiB.

compose start-ostree [--size XXXX] [--parent PARENT] [--ref REF] <BLUEPRINT> <TYPE> [<IMAGE-NAME> <PROFILE.TOML>]
    Start an ostree compose using the selected blueprint and output type. Optionally start an upload. This command
    is only supported by osbuild-composer. --size is in MiB.

compose types
    List the supported output types.

compose status
    List the status of all running and finished composes.

compose list [waiting|running|finished|failed]
    List basic information about composes.

compose log <UUID> [<SIZE>]
    Show the last SIZE kB of the compose log.

compose cancel <UUID>
    Cancel a running compose and delete any intermediate results.

compose delete <UUID,...>
    Delete the listed compose results.

compose info <UUID>
    Show detailed information on the compose.

compose metadata <UUID>
    Download the metadata use to create the compose to <uuid>-metadata.tar

compose logs <UUID>
    Download the compose logs to <uuid>-logs.tar

compose results <UUID>
    Download all of the compose results; metadata, logs, and image to <uuid>.tar

compose image <UUID>
    Download the output image from the compose. Filename depends on the type.
"""

blueprints_help = """
blueprints list
    List the names of the available blueprints.

blueprints show <BLUEPRINT,...>
    Display the blueprint in TOML format.

blueprints changes <BLUEPRINT,...>
    Display the changes for each blueprint.

blueprints diff <BLUEPRINT> <FROM-COMMIT> <TO-COMMIT>
    Display the differences between 2 versions of a blueprint.
    FROM-COMMIT can be a commit hash or NEWEST
    TO-COMMIT  can be a commit hash, NEWEST, or WORKSPACE

blueprints save <BLUEPRINT,...>
    Save the blueprint to a file, <BLUEPRINT>.toml

blueprints delete <BLUEPRINT>
    Delete a blueprint from the server

blueprints depsolve <BLUEPRINT,...>
    Display the packages needed to install the blueprint.

blueprints push <BLUEPRINT>
    Push a blueprint TOML file to the server.

blueprints freeze <BLUEPRINT,...>
    Display the frozen blueprint's modules and packages.

blueprints freeze show <BLUEPRINT,...>
    Display the frozen blueprint in TOML format.

blueprints freeze save <BLUEPRINT,...>
    Save the frozen blueprint to a file, <blueprint-name>.frozen.toml.

blueprints tag <BLUEPRINT>
    Tag the most recent blueprint commit as a release.

blueprints undo <BLUEPRINT> <COMMIT>
    Undo changes to a blueprint by reverting to the selected commit.

blueprints workspace <BLUEPRINT>
    Push the blueprint TOML to the temporary workspace storage.
"""

modules_help = """
modules list
    List the available modules.
"""

projects_help = """
projects list
    List the available projects.

projects info <PROJECT,...>
    Show details about the listed projects.
"""

sources_help = """
sources list
    List the available sources

sources info <SOURCE-NAME,...>
    Details about the source.

sources add <SOURCE.TOML>
    Add a package source to the server.

sources change <SOURCE.TOML>
    Change an existing source

sources delete <SOURCE-NAME>
    Delete a package source.
"""

status_help = """
status show                         Show API server status.
"""

upload_help = """
upload info <UPLOAD-UUID>
    Details about an upload

upload start <BUILD-UUID> <IMAGE-NAME> [<PROVIDER> <PROFILE>|<PROFILE.TOML>]
    Upload a build image to the selected provider.

upload log <UPLOAD-UUID>
    Show the upload log

upload cancel <UPLOAD-UUID>
    Cancel an upload with that is queued or in progress

upload delete <UPLOAD-UUID>
    Delete the upload and remove it from the build

upload reset <UPLOAD-UUID>
    Reset the upload so that it can be tried again
"""

providers_help = """
providers list <PROVIDER>
    List the available providers, or list the <provider's> available profiles

providers show <PROVIDER> <PROFILE>
    show the details of a specific provider's profile

providers push <PROFILE.TOML>
    Add a new profile, or overwrite an existing one

providers save <PROVIDER> <PROFILE>
    Save the profile's details to a TOML file named <PROFILE>.toml

providers delete <PROVIDER> <PROFILE>
    Delete a profile from a provider
"""

epilog = compose_help + blueprints_help + modules_help + projects_help \
         + sources_help + status_help + upload_help + providers_help
