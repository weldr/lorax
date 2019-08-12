#
# Copyright (C) 2018-2019 Red Hat, Inc.
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

from datetime import datetime
from enum import Enum
from functools import partial
import logging
from multiprocessing import current_process
import os
import signal
from uuid import uuid4

from ansible_runner.interface import run as ansible_run

log = logging.getLogger("lifted")


class Upload:
    """Represents an upload of an image to a cloud provider. Instances of this
    class are serialized and stored upload queue directory, which is
    /var/lib/lorax/upload/queue/ by default"""

    def __init__(
        self,
        uuid=None,
        provider_name=None,
        playbook_path=None,
        image_name=None,
        settings=None,
        creation_time=None,
        upload_log=None,
        upload_pid=None,
        image_path=None,
        status_callback=None,
        status=None,
    ):
        self.uuid = uuid or str(uuid4())
        self.provider_name = provider_name
        self.playbook_path = playbook_path
        self.image_name = image_name
        self.settings = settings
        self.creation_time = creation_time or datetime.now().timestamp()
        self.upload_log = upload_log or ""
        self.upload_pid = upload_pid
        self.image_path = image_path
        if status:
            self.status = status
        else:
            self.set_status("WAITING", status_callback)

    def _log(self, message, callback=None):
        """Logs something to the upload log

        :param message: the object to log
        :type message: object
        """
        log.info(str(message))
        self.upload_log += f"{message}\n"
        if callback:
            callback(self)

    def serializable(self):
        """Returns a representation of the object as a dict for serialization

        :returns: the object's __dict__
        :rtype: dict
        """
        return self.__dict__

    def summary(self):
        """Return a dict with useful information about the upload

        :returns: upload information
        :rtype: dict
        """

        return {
            "uuid": self.uuid,
            "status": self.status,
            "provider_name": self.provider_name,
            "image_name": self.image_name,
            "image_path": self.image_path,
            "creation_time": self.creation_time,
            "settings": self.settings,
        }

    def set_status(self, status, status_callback=None):
        """Sets the status of the upload with an optional callback

        :param status: the new status
        :type status: str
        :param status_callback: a function of the form callback(self)
        :type status_callback: function
        """
        self.status = status
        if status_callback:
            status_callback(self)

    def ready(self, image_path, status_callback):
        """Provide an image_path and mark the upload as ready to execute

        :param image_path: path of the image to upload
        :type image_path: str
        :param status_callback: a function of the form callback(self)
        :type status_callback: function
        """
        self.image_path = image_path
        if self.status == "WAITING":
            self.set_status("READY", status_callback)

    def reset(self, status_callback):
        """Reset the upload so it can be attempted again

        :param status_callback: a function of the form callback(self)
        :type status_callback: function
        """
        if self.is_cancellable():
            raise RuntimeError(f"Can't reset, status is {self.status}!")
        if not self.image_path:
            raise RuntimeError(f"Can't reset, no image supplied yet!")
        # self.error = None
        self._log("Resetting...")
        self.set_status("READY", status_callback)

    def is_cancellable(self):
        """Is the upload in a cancellable state?

        :returns: whether the upload is cancellable
        :rtype: bool
        """
        return self.status in ("WAITING", "READY", "RUNNING")

    def cancel(self, status_callback=None):
        """Cancel the upload. Sends a SIGINT to self.upload_pid.

        :param status_callback: a function of the form callback(self)
        :type status_callback: function
        """
        if not self.is_cancellable():
            raise RuntimeError(f"Can't cancel, status is already {self.status}!")
        if self.upload_pid:
            os.kill(self.upload_pid, signal.SIGINT)
        self.set_status("CANCELLED", status_callback)

    def verify_settings(self, status_callback=None):
        """"""

    def execute(self, status_callback=None):
        """Execute the upload. Meant to be called from a dedicated process so
        that the upload can be cancelled by sending a SIGINT to
        self.upload_pid.

        :param status_callback: a function of the form callback(self)
        :type status_callback: function
        """
        if self.status != "READY":
            raise RuntimeError("This upload is not ready!")
        self.upload_pid = current_process().pid
        self.set_status("RUNNING", status_callback)

        logger = partial(self._log, callback=status_callback)

        runner = ansible_run(
            playbook=self.playbook_path,
            extravars={
                **self.settings,
                "image_name": self.image_name,
                "image_path": self.image_path,
            },
            event_handler=logger,
        )
        if runner.status == "successful":
            self.set_status("FINISHED", status_callback)
        else:
            self.set_status("FAILED", status_callback)
