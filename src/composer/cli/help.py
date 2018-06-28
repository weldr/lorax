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

compose_help = """
compose start <blueprint> <type>    Start a compose using the selected blueprint and output type.
        types                       List the supported output types.
        status                      List the status of all running and finished composes.
        log <uuid> [<size>kB]       Show the last 1kB of the compose log.
        cancel <uuid>               Cancel a running compose and delete any intermediate results.
        delete <uuid,...>           Delete the listed compose results.
        details <uuid>              Show detailed information on the compose.
        metadata <uuid>             Download the metadata use to create the compose to <uuid>-metadata.tar
        logs <uuid>                 Download the compose logs to <uuid>-logs.tar
        results <uuid>              Download all of the compose results; metadata, logs, and image to <uuid>.tar
        image <uuid>                Download the output image from the compose. Filename depends on the type.
"""

blueprints_help = """
blueprints list                     List the names of the available blueprints.
        show <blueprint,...>        Display the blueprint in TOML format.
        changes <blueprint,...>     Display the changes for each blueprint.
        diff <blueprint-name>       Display the differences between 2 versions of a blueprint.
             <from-commit>          Commit hash or NEWEST
             <to-commit>            Commit hash, NEWEST, or WORKSPACE
        save <blueprint,...>        Save the blueprint to a file, <blueprint-name>.toml
        delete <blueprint>          Delete a blueprint from the server
        depsolve <blueprint,...>    Display the packages needed to install the blueprint.
        push <blueprint>            Push a blueprint TOML file to the server.
        freeze <blueprint,...>      Display the frozen blueprint's modules and packages.
        freeze show <blueprint,...> Display the frozen blueprint in TOML format.
        freeze save <blueprint,...> Save the frozen blueprint to a file, <blueprint-name>.frozen.toml.
        tag <blueprint>             Tag the most recent blueprint commit as a release.
        undo <blueprint> <commit>   Undo changes to a blueprint by reverting to the selected commit.
        workspace <blueprint>       Push the blueprint TOML to the temporary workspace storage.
"""

modules_help = """
modules list                        List the available modules.
"""

projects_help = """
projects list                       List the available projects.
         info <project,...>         Show details about the listed projects.
"""

sources_help = """
sources list                        List the available sources
sources info <source,...>           Details about the source.
sources add <source.toml>           Add a package source to the server.
sources change <source.toml>        Change an existing source
sources delete <source>             Delete a package source.
"""

epilog = compose_help + blueprints_help + modules_help + projects_help + sources_help
