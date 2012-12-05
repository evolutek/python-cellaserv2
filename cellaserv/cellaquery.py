#!/usr/bin/env python3
# Author: Rémi Audebert <mail@halfr.net>
# Evolutek 2013
"""
Send a query to cellaserv.

Default server: ``evolutek.org`` port ``4200``, or HOST, PORT values imported
from ``local_settings.py``

Example usage::

    $ cellaquery service_name[identification].action parameters

    $ cellaquery timer.start duration=1
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

class QueryAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        query = {}
        query['command'] = 'query'

        try:
            query['service'], rest = values[0].split('[', 1)
            query['identification'], query['action'] = rest.split('].', 1)
        except ValueError: # no identification
            rest = values[0]
            query['service'], query['action'] = rest.split('.', 1)

        query['action'] = query['action'].replace('_', '-')

        if len(values) >= 2:
            data = {}
            for arg in values[1:]:
                key, value = arg.split('=', 1)
                try:
                    data[key]  = eval(value)
                except:
                    data[key] = value

            query['data'] = data

        namespace.query = query


def main():
    try:
        import local_settings
        HOST, PORT = local_settings.HOST, local_settings.PORT
    except:
        HOST, PORT = 'evolutek.org', 4200

    parser = argparse.ArgumentParser(description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-v", "--version", action="version",
            version="%(prog)s v" + __version__ + ", protocol: v" +
            cellaserv.client.__protocol_version__)
    parser.add_argument("-s", "--server", default=HOST,
            help="hostname/ip of the server")
    parser.add_argument("-p", "--port", type=int, default=PORT,
            help="port of the server")
    parser.add_argument("-n", "--non-verbose", action="store_true",
            help="be less verbose, do no print messages, only return value")
    parser.add_argument("-P", "--pretty", action="store_true",
            help="pretty print output")
    parser.add_argument("query", nargs="+", help="the query sent to cellaserv",
            action=QueryAction)

    args = parser.parse_args()

    with socket.create_connection((args.server, args.port)) as conn:
        if args.non_verbose:
            client = cellaserv.client.SynClient(conn)
        else:
            client = cellaserv.client.SynClientDebug(conn)

        message = args.query
        message['id'] = str(uuid.uuid4())

        client.send_message(message)

        ret_value = client.read_message(message['id'])

        if args.non_verbose:
            try:
                if args.pretty:
                    pprint.pprint(ret_value['data'])
                else:
                    print(ret_value['data'])
            except:
                pass

if __name__ == "__main__":
    main()

