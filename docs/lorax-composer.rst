lorax-composer
==============

:Authors:
    Brian C. Lane <bcl@redhat.com>

lorax-composer is an API server that is compatible with the Weldr project's
bdcs-api REST protocol. More information on Weldr can be found [on the Weldr
blog](https://www.weldr.io).

The server runs as root, and communication with it is via a unix domain socket
(``/run/weldr/api.socket`` by default). The directory and socket are owned by
root:weldr so that any user in the weldr group can use the API to control
lorax-composer.

When starting the server it will check for the correct permissions and
ownership of pre-existing directory, or it will create a new one if none exist.
The socket path and group owner's name can be changed from the cmdline by
passing it the ``--socket`` and ``--group`` arguments.

Logs
----

Logs are stored under ``/var/log/lorax-composer/`` and includes all console
messages as well as extra debugging info and API requests.

Quickstart
----------

1. Create a ``weldr`` group by running ``groupadd weldr``
2. Remove any pre-existing socket directory with ``rm -rf /run/weldr/``
   A new directory with correct permissions will be created the first time the server runs.
3. Either start it via systemd with ``systemctl start lorax-composer`` or
   run it directly with ``lorax-composer /path/to/recipes/``

The ``/path/to/recipes/`` is where the recipe's git repo will be created, and all
the recipes created with the ``/api/v0/recipes/new`` route will be stored.
