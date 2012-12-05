#!/usr/bin/env python3
# Author: Rémi Audebert <mail@halfr.net>
# Evolutek 2013
# TODO: use local_settings.py, if any
"""
Send a crafted message to cellaserv.

Default server: ``evolutek.org`` port ``4200``.

Example usage::

    $ cellasend command=query service=date action=epoch
    >> {"action": "protocol-version", "id": "1dacff38-5511-436f-9bea-8acc6158dafc", "command": "server"}
    << {"data": {"protocol-version": "0.5"}, "id": "1dacff38-5511-436f-9bea-8acc6158dafc", "command": "ack"}
    >> {"action": "epoch", "service": "date", "id": "0934ddd9-6ab6-426f-8105-0e92d477ef8c", "command": "query"}
    << {"ack-data": {"epoch": 1352746477}, "id": "0934ddd9-6ab6-426f-8105-0e92d477ef8c", "command": "ack"}

    $ cellasend command=server action=list-services
    >> {"id": "8d6cc9cd-39d4-4fd0-af19-1ff2056bcf14", "action": "protocol-version", "command": "server"}
    << {"id": "8d6cc9cd-39d4-4fd0-af19-1ff2056bcf14", "data": {"protocol-version": "0.5"}, "command": "ack"}
    >> {"id": "8e6991c3-6157-489a-8472-1094e9f9e852", "action": "list-services", "command": "server"}
    << {"id": "8e6991c3-6157-489a-8472-1094e9f9e852", "data": {"services": []}, "command": "ack"}

    # With pretty print:
    $ cellasend command=server action=list-services -nP
    {'command': 'ack',
     'data': {'services': [{'identification': '3', 'name': 'ax'},
                           {'identification': '5', 'name': 'ax'},
                           {'name': 'webcam'},
                           {'name': 'date'},
                           {'name': 'timer'},
                           {'name': 'twitter'}]},
     'id': 'b65ad395-c277-42d0-bdb3-7d8a1614a046'}

    # Short syntax for data={"duration": 1}
    $ cellasend command=query service=timer action=start .duration=1
"""

__version__ = "1"

try:
    import argparse
except ImportError:
    raise SystemExit("Python version must be >=3.2 for the argparse module")

import pprint
import socket
import uuid

import cellaserv.client

class AssocAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        namespace.json_dict = {}
        try:
            for assoc in values:
                key, value = assoc.split('=', maxsplit=1)

                # quick and dirty: .key=stuff <=> msg['data'][key] = stuff
                if key.startswith('.'):
                    data_key = key.split('.', maxsplit=1)[1]
                    try:
                        namespace.json_dict['data'][data_key] = value
                    except KeyError:
                        namespace.json_dict['data'] = {}
                        namespace.json_dict['data'][data_key] = value
                else:
                    namespace.json_dict[key] = value
        except ValueError:
            parser.error("{} is not a valid key=value argument".format(values))

def main():
    parser = argparse.ArgumentParser(description="Send messages to cellaserv")
    parser.add_argument("-v", "--version", action="version",
            version="%(prog)s v" + __version__ + ", protocol: v" +
            cellaserv.client.__protocol_version__)
    parser.add_argument("-s", "--server", default="evolutek.org",
            help="hostname/ip of the server (default evolutek.org)")
    parser.add_argument("-p", "--port", type=int, default=4200,
            help="port of the server (default 4200)")
    parser.add_argument("-n", "--non-verbose", action="store_true",
            help="be less verbose, do no print messages")
    parser.add_argument("-P", "--pretty", action="store_true",
            help="pretty print output")
    parser.add_argument("key=value", nargs="+", metavar="json_dict",
            help="content of the message sent to cellaserv",
            action=AssocAction)

    args = parser.parse_args()

    with socket.create_connection((args.server, args.port)) as conn:
        if args.non_verbose:
            client = cellaserv.client.SynClient(conn)
        else:
            client = cellaserv.client.SynClientDebug(conn)

        message = args.json_dict

        # tweak the message if necessary
        if 'command' in message \
                and message['command'] in ('query', 'register', 'server') \
                and 'id' not in message:
            message['id'] = str(uuid.uuid4())

        client.send_message(message)

        if message['command'] == 'notify':
            return

        if not args.non_verbose:
            client.read_message()
        else:
            if args.pretty:
                pprint.pprint(client.read_message())
            else:
                print(client.read_message())

if __name__ == "__main__":
    main()
