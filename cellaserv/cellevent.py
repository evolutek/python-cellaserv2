#!/usr/bin/env python3
# Author: Rémi Audebert <mail@halfr.net>
# Evolutek 2013
"""
Wait for an event from cellaserv.

Default server: ``evolutek.org`` port ``4200``

Example usage::

    $ cellevent event_name [event_name]...
"""

__version__ = "0.1"

try:
    import argparse
except ImportError:
    raise SystemExit("Python version must be >=3.2 for the argparse module")

import asyncore
import socket
import subprocess
import sys

import cellaserv.client

def main():
    parser = argparse.ArgumentParser(description="Send query to cellaserv")
    parser.add_argument("-v", "--version", action="version",
            version="%(prog)s v" + __version__ + ", protocol: v" +
            cellaserv.client.__protocol_version__)
    parser.add_argument("-s", "--server", default="evolutek.org",
            help="hostname/ip of the server (default evolutek.org)")
    parser.add_argument("-p", "--port", type=int, default=4200,
            help="port of the server (default 4200)")
    parser.add_argument("-n", "--non-verbose", action="store_true",
            help="be less verbose, don't print messages, only data")
    parser.add_argument("-S", "--spawn", metavar="COMMAND", default=None,
            nargs="*",
            help="spawn command COMMAND with the content of the events")
    parser.add_argument("event_names", metavar="event_names", nargs="+",
            help="Events cellevent will wait for.")

    args = parser.parse_args()

    def callback(message):
        if args.non_verbose:
            try:
                print(message['data'])
            except:
                pass
        if args.spawn:
            for command in args.spawn:
                subprocess.call(command.format(**message.get('data', {})), shell=True)

    with socket.create_connection((args.server, args.port)) as conn:
        if args.non_verbose:
            client = cellaserv.client.AsynClient(conn)
        else:
            client = cellaserv.client.AsynClientDebug(conn)

        for event_name in args.event_names:
            client.subscribe_event(event_name)
            client.connect_event(event_name, callback)

        asyncore.loop()

if __name__ == "__main__":
    main()


