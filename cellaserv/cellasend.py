#!/usr/bin/env python3
"""
Send a message to cellaserv.

Use ``-v`` if you want to see the response.

Example use::

    $ cellasend -v command=status
    >> {'command': 'status'}
    << {'services': [{'name': 'date'}], 'service_count': 1, 'messages_waiting_ack': 0, 'version': '0.2', 'connections_open': 2}

    $ cellasend -v command=query service=date action=epoch
    >> {'action': 'epoch', 'service': 'date', 'command': 'query', 'id': '363cd1e9-eb88-499b-bbe9-e122b98446b3'}
    << {'command': 'ack', 'ack-data': {'epoch': 1351606050}, 'id': '363cd1e9-eb88-499b-bbe9-e122b98446b3'}
"""

__version__ = "0.1"

import sys
if sys.version_info.minor < 2:
    raise SystemExit("Python version must be >=3.2 for the argparse module")

import argparse
import socket
import uuid

import cellaserv.client

class AssocAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        namespace.json_dict = {}
        try:
            for assoc in values:
                key, value = assoc.split('=')
                namespace.json_dict[key] = value
        except ValueError:
            parser.error("{} is not a valid key=value argument".format(values))

def main():
    parser = argparse.ArgumentParser(description="Send messages to cellaserv")
    parser.add_argument("--version", action="version",
        version="%(prog)s v" + __version__)
    parser.add_argument("-s", "--server", default="evolutek.org",
            help="hostname/ip of the server (default evolutek.org)")
    parser.add_argument("-p", "--port", type=int, default=4200,
            help="port of the server (default 4200)")
    parser.add_argument("-v", "--verbose", action="store_true",
            help="be verbose, output messages sent")
    parser.add_argument("key=value", nargs="+", metavar="json_dict",
            help="data to be put in the message sent to cellaserv",
            action=AssocAction)

    args = parser.parse_args()

    with socket.create_connection((args.server, args.port)) as conn:
        if args.verbose:
            client = cellaserv.client.SynClientDebug(conn)
        else:
            client = cellaserv.client.SynClient(conn)

        message = args.json_dict

        # tweak the message if necessary
        if 'command' in message \
                and message['command'] in ('query', 'register') \
                and 'id' not in message:
            message['id'] = str(uuid.uuid4())

        client.send_message(message)

        if args.verbose:
            client.read_message()

if __name__ == "__main__":
    main()
