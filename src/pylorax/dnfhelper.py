#
# dnfhelper.py
#
# Copyright (C) 2010-2015 Red Hat, Inc.
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
# Red Hat Author(s):  Martin Gracik <mgracik@redhat.com>
#                     Brian C. Lane <bcl@redhat.com>
#

import logging
logger = logging.getLogger("pylorax.dnfhelper")
import time
import pylorax.output as output

import libdnf5 as dnf5
SUCCESSFUL = dnf5.repo.DownloadCallbacks.TransferStatus_SUCCESSFUL

__all__ = ['LoraxDownloadCallback', 'LoraxRpmCallback']

def _paced(fn):
    """Execute `fn` no more often then every 2 seconds."""
    def paced_fn(self, *args):
        now = time.time()
        if now - self.last_time < 2:
            return
        self.last_time = now
        return fn(self, *args)
    return paced_fn


class LoraxDownloadCallback(dnf5.repo.DownloadCallbacks):
    def __init__(self, total_files):
        super(LoraxDownloadCallback, self).__init__()
        self.last_time = time.time()
        self.total_files = total_files
        self.pkgno = 0

        self.output = output.LoraxOutput()
        self.nevra = "unknown"

    def add_new_download(self, user_data, description, total_to_download):
        self.nevra = description or "unknown"

        # Returning anything here makes it crash
        return None

    @_paced
    def _update(self):
        msg = "Downloading %(pkgno)s / %(total_files)s RPMs\n"
        vals = {
            'pkgno'       : self.pkgno,
            'total_files' : self.total_files,
        }
        self.output.write(msg % vals)

    def end(self, user_cb_data, status, msg):
        if status == SUCCESSFUL:
            self.pkgno += 1
            self._update()
        else:
            logger.critical("Failed to download '%s': %d - %s", self.nevra, status, msg)
        return 0

    def progress(self, user_cb_data, total_to_download, downloaded):
        self._update()
        return 0

    def mirror_failure(self, user_cb_data, msg, url, metadata):
        message = f"{url} - {msg}"
        logger.critical("Mirror failure on '%s': %s (%s)", self.nevra, message, metadata)
        return 0


class LoraxRpmCallback(dnf5.rpm.TransactionCallbacks):
    def install_start(self, item, total):
        action = dnf5.base.transaction.transaction_item_action_to_string(item.get_action())
        package = item.get_package().get_nevra()
        logger.info("%s %s", action, package)

    # pylint: disable=redefined-builtin
    def script_start(self, item, nevra, type):
        if not item or not type:
            return

        package = item.get_package().get_nevra()
        script_type = self.script_type_to_string(type)
        logger.info("Running %s for %s", script_type, package)

    ## NOTE: These likely will not work right, SWIG seems to crash when raising errors
    ##       from callbacks.
    def unpack_error(self, item):
        package = item.get_package().get_nevra()
        raise RuntimeError(f"unpack_error on {package}")

    def cpio_error(self, item):
        package = item.get_package().get_nevra()
        raise RuntimeError(f"cpio_error on {package}")

    # pylint: disable=redefined-builtin
    def script_error(self, item, nevra, type, return_code):
        package = item.get_package().get_nevra()
        script_type = self.script_type_to_string(type)
        raise RuntimeError(f"script_error on {package}: {script_type} rc={return_code}")
