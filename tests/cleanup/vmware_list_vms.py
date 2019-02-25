#!/usr/bin/env python
# list all VMs in vSphere and print their name, UUID and date/time of creation

import atexit
import argparse
import getpass
import ssl

from pyVim import connect
from pyVmomi import vim             # pylint: disable=no-name-in-module


def setup_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('--host', required=True, help='vSphere service to connect to')
    parser.add_argument('--port', type=int, default=443, help="Port number (default is 443)")
    parser.add_argument('--username', required=True, help='User name')
    parser.add_argument('--password', help='User password')
    parser.add_argument('--disable_ssl_verification', action='store_true', help='Disable ssl host certificate verification')

    args = parser.parse_args()
    if not args.password:
        args.password = getpass.getpass()
    return args

def print_vm_datetime(vm):
    create_date = vm.config.createDate
    # spaces are used as field separators, remove them from VM names
    name = vm.config.name.replace(' ', '')
    uuid = vm.config.instanceUuid
    if create_date:
        print(name, uuid, create_date.isoformat())

def main():
    args = setup_args()

    sslContext = None
    if args.disable_ssl_verification:
        sslContext = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        sslContext.verify_mode = ssl.CERT_NONE

    try:
        service_instance = connect.SmartConnect(host=args.host,
                                                port=args.port,
                                                user=args.username,
                                                pwd=args.password,
                                                sslContext=sslContext)
    except Exception:
        print("Unable to connect to %s" % args.host)
        return 1

    atexit.register(connect.Disconnect, service_instance)

    content = service_instance.RetrieveContent()
    viewType = [vim.VirtualMachine]
    container = content.viewManager.CreateContainerView(content.rootFolder, viewType, recursive=True)

    for child in container.view:
        print_vm_datetime(child)

    return 0

if __name__ == "__main__":
    exit(main())
