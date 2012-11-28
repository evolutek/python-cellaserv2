#!/usr/bin/env python3
# Author: Rémi Audebert <mail@halfr.net>
# Evolutek 2013
"""
Send a query to cellaserv.

Default server: ``evolutek.org`` port ``4200``

Example usage::

    $ cellaquery service_name(identification).action parameters

    $ cellaquery timer.start duration=1
"""

__version__ = "1"

try:
    import argparse
except ImportError:
    raise SystemExit("Python version must be >=3.2 for the argparse module")

import socket
import uuid

import cellaserv.client

class QueryAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        query = {}
        query['command'] = 'query'

        try:
            query['service'], rest = values[0].split('(', 1)
            query['identification'], query['action'] = rest.split(').', 1)
        except ValueError: # no identification
            rest = values[0]
            query['service'], query['action'] = rest.split('.', 1)

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
    parser = argparse.ArgumentParser(description="Send a query to cellaserv")
    parser.add_argument("-v", "--version", action="version",
            version="%(prog)s v" + __version__ + ", protocol: v" +
            cellaserv.client.__protocol_version__)
    parser.add_argument("-s", "--server", default="evolutek.org",
            help="hostname/ip of the server (default evolutek.org)")
    parser.add_argument("-p", "--port", type=int, default=4200,
            help="port of the server (default 4200)")
    parser.add_argument("-n", "--non-verbose", action="store_true",
            help="be less verbose, do no print messages")
    parser.add_argument("[identification:]service.action([key=value], ...)",
            metavar="query", nargs="+", help="The query sent to cellaserv",
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
                print(ret_value['data'])
            except:
                pass

if __name__ == "__main__":
    main()

