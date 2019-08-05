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

from functools import partial
from glob import glob
import logging
import multiprocessing

# We use a multiprocessing Pool for uploads so that we can cancel them with a
# simple SIGINT, which should bubble down to subprocesses.
from multiprocessing import Pool

# multiprocessing.dummy is to threads as multiprocessing is to processes.
# Since daemonic processes can't have children, we use a thread to monitor the
# upload pool.
from multiprocessing.dummy import Process

from operator import attrgetter
import os
import stat
import time

import toml

from lifted.upload import Upload
from lifted.providers import resolve_playbook_path, validate_settings

# the maximum number of simultaneous uploads
SIMULTANEOUS_UPLOADS = 1

log = logging.getLogger("lifted")
multiprocessing.log_to_stderr().setLevel(logging.INFO)


def _get_queue_path(ucfg):
    path = ucfg["queue_dir"]

    # create the upload_queue directory if it doesn't exist
    os.makedirs(path, exist_ok=True)

    return path


def _get_upload_path(ucfg, uuid, write=False):
    path = os.path.join(_get_queue_path(ucfg), f"{uuid}.toml")
    if write and not os.path.exists(path):
        open(path, "a").close()
    if os.path.exists(path):
        # make sure uploads aren't readable by others, as they will contain
        # sensitive credentials
        current = stat.S_IMODE(os.lstat(path).st_mode)
        os.chmod(path, current & ~stat.S_IROTH)
    return path


def _list_upload_uuids(ucfg):
    paths = glob(os.path.join(_get_queue_path(ucfg), "*"))
    return [os.path.splitext(os.path.basename(path))[0] for path in paths]


def _write_upload(ucfg, upload):
    with open(_get_upload_path(ucfg, upload.uuid, write=True), "w") as upload_file:
        toml.dump(upload.serialize(), upload_file)


def _write_callback(ucfg):
    return partial(_write_upload, ucfg)


def get_upload(ucfg, uuid, ignore_missing=False, ignore_corrupt=False):
    """Get an Upload object by UUID

    :param ucfg: upload config
    :type ucfg: object
    :param uuid: UUID of the upload to get
    :type uuid: str
    :param ignore_missing: if True, don't raise a RuntimeError when the
    specified upload is missing, instead just return None
    :type ignore_missing: bool
    :param ignore_corrupt: if True, don't raise a RuntimeError when the
    specified upload could not be deserialized, instead just return None
    :type ignore_corrupt: bool
    :returns: the upload object or None
    :rtype: Upload or None
    :raises: RuntimeError
    """
    try:
        with open(_get_upload_path(ucfg, uuid), "r") as upload_file:
            return Upload(**toml.load(upload_file))
    except FileNotFoundError as error:
        if not ignore_missing:
            raise RuntimeError(f"Could not find upload {uuid}!") from error
    except toml.TomlDecodeError as error:
        if not ignore_corrupt:
            raise RuntimeError(f"Could not parse upload {uuid}!") from error


def get_uploads(ucfg, uuids):
    """Gets a list of Upload objects from a list of upload UUIDs, ignoring
    missing or corrupt uploads

    :param ucfg: upload config
    :type ucfg: object
    :param uuids: list of upload UUIDs to get
    :type uuids: list of str
    :returns: a list of the uploads that were successfully deserialized
    :rtype: list of Upload
    """
    uploads = (
        get_upload(ucfg, uuid, ignore_missing=True, ignore_corrupt=True)
        for uuid in uuids
    )
    return list(filter(None, uploads))


def get_all_uploads(ucfg):
    """Get a list of all stored Upload objects

    :param ucfg: upload config
    :type ucfg: object
    :returns: a list of all stored upload objects
    :rtype: list of Upload
    """
    return get_uploads(ucfg, _list_upload_uuids(ucfg))


def create_upload(ucfg, provider_name, image_name, settings):
    """Creates a new upload

    :param ucfg: upload config
    :type ucfg: object
    :param provider_name: the name of the cloud provider to upload to, e.g.
    "azure"
    :type provider_name: str
    :param image_name: what to name the image in the cloud
    :type image_name: str
    :param settings: settings to pass to the upload, specific to the cloud
    provider
    :type settings: dict
    :returns: the created upload object
    :rtype: Upload
    """
    validate_settings(ucfg, provider_name, settings, image_name)
    return Upload(
        image_name,
        provider_name,
        resolve_playbook_path(ucfg, provider_name),
        settings,
        _write_callback(ucfg),
    )


def ready_upload(ucfg, uuid, image_path):
    """Pass an image_path to an upload and mark it ready to execute

    :param ucfg: upload config
    :type ucfg: object
    :param uuid: the UUID of the upload to mark ready
    :type uuid: str
    :param image_path: the path of the image to pass to the upload
    :type image_path: str
    """
    get_upload(ucfg, uuid).ready(image_path, _write_callback(ucfg))


def reset_upload(ucfg, uuid, new_image_name=None, new_settings=None):
    """Reset an upload so it can be attempted again

    :param ucfg: upload config
    :type ucfg: object
    :param uuid: the UUID of the upload to reset
    :type uuid: str
    :param new_image_name: optionally update the upload's image_name
    :type new_image_name: str
    :param new_settings: optionally update the upload's settings
    :type new_settings: dict
    """
    upload = get_upload(ucfg, uuid)
    validate_settings(
        ucfg,
        upload.provider_name,
        new_settings or upload.settings,
        new_image_name or upload.image_name,
    )
    if new_image_name:
        upload.image_name = new_image_name
    if new_settings:
        upload.settings = new_settings
    upload.reset(_write_callback(ucfg))


def cancel_upload(ucfg, uuid):
    """Cancel an upload

    :param ucfg: the compose config
    :type ucfg: ComposerConfig
    :param uuid: the UUID of the upload to cancel
    :type uuid: str
    """
    get_upload(ucfg, uuid).cancel(_write_callback(ucfg))


def delete_upload(ucfg, uuid):
    """Delete an upload

    :param ucfg: the compose config
    :type ucfg: ComposerConfig
    :param uuid: the UUID of the upload to delete
    :type uuid: str
    """
    upload = get_upload(ucfg, uuid)
    if upload and upload.is_cancellable():
        upload.cancel()
    os.remove(_get_upload_path(ucfg, uuid))


def start_upload_monitor(ucfg):
    """Start a thread that manages the upload queue

    :param ucfg: the compose config
    :type ucfg: ComposerConfig
    """
    process = Process(target=_monitor, args=(ucfg,))
    process.daemon = True
    process.start()


def _monitor(ucfg):
    log.info("Started upload monitor.")
    for upload in get_all_uploads(ucfg):
        # Set abandoned uploads to FAILED
        if upload.status == "RUNNING":
            upload.set_status("FAILED", _write_callback(ucfg))
    pool = Pool(processes=SIMULTANEOUS_UPLOADS)
    pool_uuids = set()

    def remover(uuid):
        return lambda _: pool_uuids.remove(uuid)

    while True:
        # Every second, scoop up READY uploads from the filesystem and throw
        # them in the pool
        all_uploads = get_all_uploads(ucfg)
        for upload in sorted(all_uploads, key=attrgetter("creation_time")):
            ready = upload.status == "READY"
            if ready and upload.uuid not in pool_uuids:
                log.info("Starting upload %s...", upload.uuid)
                pool_uuids.add(upload.uuid)
                callback = remover(upload.uuid)
                pool.apply_async(
                    upload.execute,
                    (_write_callback(ucfg),),
                    callback=callback,
                    error_callback=callback,
                )
        time.sleep(1)
